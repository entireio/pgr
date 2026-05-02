#!/usr/bin/env python3
"""Ranking benchmark on the public entireio/cli prompt suite."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_V2_DIR = REPO_ROOT / "eval" / "v2"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = Path(os.environ.get("PGR_EVAL_REPO_ROOT", "/tmp/pgr-eval/repos/entireio-cli"))
DEFAULT_TASKS_FILE = DEFAULT_OUTPUT_DIR / "tasks_full60.json"
DEFAULT_DESIGN_FILE = DEFAULT_OUTPUT_DIR / "design_full60.json"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def build_imports():
    sys.path.insert(0, str(EVAL_V2_DIR))
    from agent import run_task  # type: ignore

    return run_task


def load_existing_result(results_dir: Path, condition: str, task_id: str, repeat: int) -> dict[str, Any] | None:
    path = results_dir / condition / f"{task_id}_r{repeat}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def run_single(
    run_task_fn: Any,
    task: dict[str, Any],
    condition: str,
    model: str,
    max_turns: int,
    repo_root: str,
) -> dict[str, Any]:
    result = run_task_fn(
        task_id=task["id"],
        repo=task["repo"],
        task_type=task["type"],
        prompt=task["prompt"],
        repo_root=repo_root,
        condition=condition,
        model=model,
        max_turns=max_turns,
    )
    return result.to_dict()


def tool_metrics(result: dict[str, Any]) -> dict[str, Any]:
    tool_calls = result.get("tool_calls", [])
    search_calls = [tc for tc in tool_calls if tc.get("tool_name") == "search_code"]
    read_calls = [tc for tc in tool_calls if tc.get("tool_name") == "read_code"]
    total_tool_duration_ms = sum(float(tc.get("duration_ms", 0.0)) for tc in tool_calls)
    return {
        "total_tool_duration_ms": total_tool_duration_ms,
        "tool_execution_share": (total_tool_duration_ms / result["wall_clock_ms"]) if result["wall_clock_ms"] else 0.0,
        "search_call_count": len(search_calls),
        "read_call_count": len(read_calls),
        "avg_search_code_duration_ms": statistics.mean(float(tc.get("duration_ms", 0.0)) for tc in search_calls)
        if search_calls
        else 0.0,
        "median_search_code_duration_ms": statistics.median(float(tc.get("duration_ms", 0.0)) for tc in search_calls)
        if search_calls
        else 0.0,
    }


def summarize(rows: list[dict[str, Any]], conditions: list[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {"overall": {}, "by_type": {}, "paired_by_task": {}}
    metrics = [
        "wall_clock_ms",
        "total_tool_calls",
        "total_cost_usd",
        "tool_output_tokens",
        "total_tool_duration_ms",
        "tool_execution_share",
        "search_call_count",
        "read_call_count",
        "avg_search_code_duration_ms",
        "median_search_code_duration_ms",
    ]

    for condition in conditions:
        subset = [row for row in rows if row["condition"] == condition]
        summary["overall"][condition] = {
            metric: statistics.mean(float(row[metric]) for row in subset) for metric in metrics
        }

    for task_type in sorted({row["task_type"] for row in rows}):
        summary["by_type"][task_type] = {}
        for condition in conditions:
            subset = [row for row in rows if row["condition"] == condition and row["task_type"] == task_type]
            summary["by_type"][task_type][condition] = {
                metric: statistics.mean(float(row[metric]) for row in subset) for metric in metrics
            }

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in rows:
        grouped.setdefault(row["task_id"], {}).setdefault(row["condition"], []).append(row)

    baseline_condition = conditions[0]
    for other_condition in conditions[1:]:
        summary["paired_by_task"][other_condition] = {}
        for metric in metrics:
            diffs = []
            for condition_map in grouped.values():
                if baseline_condition not in condition_map or other_condition not in condition_map:
                    continue
                base = statistics.mean(float(r[metric]) for r in condition_map[baseline_condition])
                other = statistics.mean(float(r[metric]) for r in condition_map[other_condition])
                diffs.append(other - base)
            if diffs:
                summary["paired_by_task"][other_condition][metric] = {
                    "n_tasks": len(diffs),
                    "mean_diff": statistics.mean(diffs),
                    "median_diff": statistics.median(diffs),
                }

    return summary


def write_markdown(design: dict[str, Any], summary: dict[str, Any], out_path: Path, conditions: list[str]) -> None:
    tasks = design["tasks"]
    task_types = sorted({task["type"] for task in tasks})
    examples = tasks[:8]

    headers = ["Metric", *conditions]
    lines = [
        f"# {design['name']}",
        "",
        "This benchmark compares raw `ripgrep` against ranked-search variants on a public, trace-derived `entireio/cli` prompt suite.",
        "",
        "## Setup",
        "",
        f"- Tasks: {len(tasks)}",
        f"- Repeats per condition: {design['repeats']}",
        f"- Conditions: {', '.join(f'`{c}`' for c in conditions)}",
        f"- Model: `{design['model']}`",
        f"- Max turns: {design['max_turns']}",
        f"- Repo: `{design['selection']['repo']}`",
        f"- Repo root: `{design['repo_root']}`",
        "",
        "## Prompt categories",
        "",
    ]
    lines.extend(f"- `{task_type}`" for task_type in task_types)
    lines.extend(["", "## Example tasks", ""])
    lines.extend(f"- `{task['id']}` ({task['type']}): {task['prompt'][:180]}" for task in examples)
    lines.extend(["", "## Overall", ""])

    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---", *["---:" for _ in conditions]]) + "|")

    metric_rows = [
        ("Avg wall clock per run", "wall_clock_ms", lambda v: f"{v / 1000:.2f}s"),
        ("Avg tool calls", "total_tool_calls", lambda v: f"{v:.2f}"),
        ("Avg cost per run", "total_cost_usd", lambda v: f"${v:.4f}"),
        ("Avg search calls", "search_call_count", lambda v: f"{v:.2f}"),
        ("Avg read calls", "read_call_count", lambda v: f"{v:.2f}"),
        ("Avg output chars", "tool_output_tokens", lambda v: f"{v:.0f}"),
        ("Avg search_code duration", "avg_search_code_duration_ms", lambda v: f"{v:.1f}ms"),
        ("Median search_code duration", "median_search_code_duration_ms", lambda v: f"{v:.1f}ms"),
    ]
    for label, metric, fmt in metric_rows:
        values = [fmt(summary["overall"][condition][metric]) for condition in conditions]
        lines.append("| " + " | ".join([label, *values]) + " |")

    lines.extend(["", "## Paired Differences Vs Baseline", ""])
    for other_condition in conditions[1:]:
        lines.append(f"### `{other_condition}` vs `{conditions[0]}`")
        paired = summary["paired_by_task"][other_condition]
        for metric in ("total_tool_calls", "total_cost_usd", "search_call_count", "wall_clock_ms"):
            if metric not in paired:
                continue
            diff = paired[metric]["mean_diff"]
            if metric == "total_cost_usd":
                rendered = f"${diff:.4f}"
            elif metric == "wall_clock_ms":
                rendered = f"{diff / 1000:.2f}s"
            else:
                rendered = f"{diff:.2f}"
            lines.append(f"- `{metric}`: {rendered}")
        lines.append("")

    out_path.write_text("\n".join(lines).rstrip() + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ranking benchmark on public entireio/cli prompt suite")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--tasks-file", type=Path, default=DEFAULT_TASKS_FILE)
    parser.add_argument("--design-file", type=Path, default=DEFAULT_DESIGN_FILE)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=["baseline", "fff", "rg_ranked", "pgr_v4"],
        choices=["baseline", "fff", "rg_ranked", "pgr_v4"],
    )
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env_file(args.env_file)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set. Use --env-file or export it before running.")
    if not args.repo_root.exists():
        raise SystemExit(f"repo root does not exist: {args.repo_root}")

    tasks = json.loads(args.tasks_file.read_text())
    design = json.loads(args.design_file.read_text())
    design = {
        **design,
        "tasks": tasks,
        "repeats": args.repeats,
        "model": args.model,
        "max_turns": args.max_turns,
        "repo_root": str(args.repo_root),
    }

    if args.dry_run:
        print(
            json.dumps(
                {
                    "task_count": len(tasks),
                    "conditions": args.conditions,
                    "repo_root": str(args.repo_root),
                    "first_tasks": tasks[:5],
                },
                indent=2,
            )
        )
        return

    output_dir = args.output_dir
    results_dir = output_dir / "results"
    for condition in args.conditions:
        (results_dir / condition).mkdir(parents=True, exist_ok=True)

    run_task_fn = build_imports()

    rows = []
    jobs = []
    for repeat in range(args.repeats):
        for task in tasks:
            for condition in args.conditions:
                if args.reuse_existing:
                    existing = load_existing_result(results_dir, condition, task["id"], repeat)
                    if existing is not None:
                        rows.append(existing)
                        print(f"[reuse:{condition}] {task['id']} r{repeat}", flush=True)
                        continue
                jobs.append((repeat, task, condition))

    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        future_map = {
            ex.submit(run_single, run_task_fn, task, condition, args.model, args.max_turns, str(args.repo_root)): (repeat, task, condition)
            for repeat, task, condition in jobs
        }
        for future in as_completed(future_map):
            repeat, task, condition = future_map[future]
            result = future.result()
            row = {
                "repeat": repeat,
                "task_id": task["id"],
                "repo": task["repo"],
                "task_type": task["type"],
                "condition": condition,
                **result,
            }
            row.update(tool_metrics(result))
            rows.append(row)
            out_file = results_dir / condition / f"{task['id']}_r{repeat}.json"
            out_file.write_text(json.dumps(row, indent=2) + "\n")
            print(
                f"[{condition}] {task['id']} complete: wall={row['wall_clock_ms'] / 1000:.2f}s tool_calls={row['total_tool_calls']}",
                flush=True,
            )

    summary = summarize(rows, args.conditions)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_markdown(design, summary, output_dir / "SUMMARY.md", args.conditions)
    print(json.dumps(summary["overall"], indent=2))


if __name__ == "__main__":
    main()
