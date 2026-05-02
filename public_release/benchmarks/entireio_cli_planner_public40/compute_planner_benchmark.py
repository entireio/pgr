#!/usr/bin/env python3
"""Build a public planner benchmark from the saved entireio/cli 4-condition runs."""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path


BENCHMARK_DIR = Path(__file__).resolve().parent
FULL60_RESULTS_DIR = BENCHMARK_DIR.parent / "entireio_cli_ranking_public60" / "full60" / "results"
OFFLINE_FIRST_SEARCH = BENCHMARK_DIR.parent / "entireio_cli_offline_ir_public60" / "first_search" / "results.json"

RESULT_DIR_BY_CONDITION = {
    "baseline": "baseline",
    "fff": "fff",
    "rg_ranked": "rg_ranked",
    "pgr_v4": "pgr_v4",
}

CONDITIONS = ["baseline", "fff", "rg_ranked", "pgr_v4"]
COMPARISONS = ["fff", "rg_ranked", "pgr_v4"]
TARGET_TOTAL = 40

NUMERIC_METRICS = [
    "total_searches",
    "total_reads",
    "total_tool_calls",
    "tool_output_tokens",
    "total_cost_usd",
    "wall_clock_ms",
    "consecutive_searches_before_first_read",
]


def load_condition_results(condition: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    result_dir = RESULT_DIR_BY_CONDITION[condition]
    for path in sorted((FULL60_RESULTS_DIR / result_dir).glob("*.json")):
        row = json.loads(path.read_text())
        rows[row["task_id"]] = row
    return rows


def planner_metrics(result: dict) -> dict[str, float]:
    tool_calls = result["tool_calls"]
    first_read_idx = next((i for i, tc in enumerate(tool_calls) if tc["tool_name"] == "read_code"), None)
    before_first_read = tool_calls if first_read_idx is None else tool_calls[:first_read_idx]
    return {
        "total_searches": sum(1 for tc in tool_calls if tc["tool_name"] == "search_code"),
        "total_reads": sum(1 for tc in tool_calls if tc["tool_name"] == "read_code"),
        "total_tool_calls": result["total_tool_calls"],
        "tool_output_tokens": result["tool_output_tokens"],
        "total_cost_usd": result["total_cost_usd"],
        "wall_clock_ms": result["wall_clock_ms"],
        "consecutive_searches_before_first_read": sum(
            1 for tc in before_first_read if tc["tool_name"] == "search_code"
        ),
    }


def paired_stats(rows: list[dict], metric: str, comparison: str) -> dict[str, float | int | list[float]]:
    diffs = []
    for task_id in sorted({row["task_id"] for row in rows}):
        baseline_value = next(
            row[metric]
            for row in rows
            if row["task_id"] == task_id and row["condition"] == "baseline"
        )
        comparison_value = next(
            row[metric]
            for row in rows
            if row["task_id"] == task_id and row["condition"] == comparison
        )
        diffs.append(float(comparison_value) - float(baseline_value))

    if len(diffs) < 2:
        return {}

    mean_diff = statistics.mean(diffs)
    sd = statistics.stdev(diffs)
    se = sd / math.sqrt(len(diffs)) if sd else 0.0
    ci_crit = 2.023
    return {
        "n_tasks": len(diffs),
        "mean_diff": mean_diff,
        "ci95": [mean_diff - ci_crit * se, mean_diff + ci_crit * se],
    }


def fmt_delta(metric: str, value: float) -> str:
    if metric == "total_cost_usd":
        return f"{value:+.4f}"
    if metric == "wall_clock_ms":
        return f"{value / 1000:+.2f}s"
    return f"{value:+.2f}"


def fmt_mean(metric: str, value: float) -> str:
    if metric == "total_cost_usd":
        return f"${value:.4f}"
    if metric == "wall_clock_ms":
        return f"{value / 1000:.2f}s"
    if metric == "tool_output_tokens":
        return f"{value / 1000:.1f}k"
    return f"{value:.2f}"


def build_summary_markdown(design: dict, summary: dict) -> str:
    overall_metrics = [
        ("total_searches", "Total searches"),
        ("total_tool_calls", "Total tool calls"),
        ("total_cost_usd", "Total cost"),
        ("tool_output_tokens", "Tool output tokens"),
        ("consecutive_searches_before_first_read", "Consecutive searches before first read"),
        ("wall_clock_ms", "Wall clock"),
    ]

    lines = [
        "# entireio/cli Public Planner Benchmark",
        "",
        "This benchmark is derived from the saved public `entireio/cli` 60-task runs across four conditions.",
        "",
        "## Design",
        "",
        f"- Selected tasks: `{len(design['selected_tasks'])}`",
        f"- Cohorts: `recovery={design['cohort_counts']['recovery']}`, `decision={design['cohort_counts']['decision']}`, `neutral={design['cohort_counts']['neutral']}`",
        "- Conditions: `baseline`, `fff`, `rg_ranked`, `pgr_v4`",
        "- Selection rule:",
        "  - `recovery`: baseline first search was a no-match and the agent searched again before first read",
        "  - `decision`: baseline first search already had a weak relevant hit (`MRR > 0`) and the agent still searched again before first read",
        "  - `neutral`: remaining tasks filled by search pressure score",
        "",
        "## Overall",
        "",
        "| Metric | Baseline | `fff` | `rg_ranked` | `pgr_v4` |",
        "|---|---:|---:|---:|---:|",
    ]

    for metric, label in overall_metrics:
        lines.append(
            "| {label} | {baseline} | {fff} | {rg_ranked} | {pgr_v4} |".format(
                label=label,
                baseline=fmt_mean(metric, summary["overall"]["baseline"][metric]),
                fff=fmt_mean(metric, summary["overall"]["fff"][metric]),
                rg_ranked=fmt_mean(metric, summary["overall"]["rg_ranked"][metric]),
                pgr_v4=fmt_mean(metric, summary["overall"]["pgr_v4"][metric]),
            )
        )

    lines.extend(
        [
            "",
            "## Paired vs baseline",
            "",
        ]
    )

    for comparison in COMPARISONS:
        lines.append(f"### `{comparison}`")
        lines.append("")
        for metric, label in [
            ("consecutive_searches_before_first_read", "consecutive_searches_before_first_read"),
            ("total_searches", "total_searches"),
            ("total_tool_calls", "total_tool_calls"),
            ("total_cost_usd", "total_cost_usd"),
            ("wall_clock_ms", "wall_clock_ms"),
        ]:
            stat = summary["paired_vs_baseline"][comparison][metric]
            ci_low, ci_high = stat["ci95"]
            if metric == "wall_clock_ms":
                ci_str = f"[{ci_low / 1000:+.2f}s, {ci_high / 1000:+.2f}s]"
            elif metric == "total_cost_usd":
                ci_str = f"[{ci_low:+.4f}, {ci_high:+.4f}]"
            else:
                ci_str = f"[{ci_low:+.2f}, {ci_high:+.2f}]"
            lines.append(f"- **{label}:** `{fmt_delta(metric, stat['mean_diff'])}`, 95% CI `{ci_str}`")
        lines.append("")

    lines.append("## By cohort")
    lines.append("")
    for cohort in ["decision", "recovery", "neutral"]:
        lines.append(f"### `{cohort}`")
        lines.append("")
        lines.append("| Metric | Baseline | `fff` | `rg_ranked` | `pgr_v4` |")
        lines.append("|---|---:|---:|---:|---:|")
        for metric, label in [
            ("total_searches", "Total searches"),
            ("total_tool_calls", "Total tool calls"),
            ("total_cost_usd", "Total cost"),
            ("consecutive_searches_before_first_read", "Consecutive searches before first read"),
        ]:
            lines.append(
                "| {label} | {baseline} | {fff} | {rg_ranked} | {pgr_v4} |".format(
                    label=label,
                    baseline=fmt_mean(metric, summary["by_cohort"][cohort]["baseline"][metric]),
                    fff=fmt_mean(metric, summary["by_cohort"][cohort]["fff"][metric]),
                    rg_ranked=fmt_mean(metric, summary["by_cohort"][cohort]["rg_ranked"][metric]),
                    pgr_v4=fmt_mean(metric, summary["by_cohort"][cohort]["pgr_v4"][metric]),
                )
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    results = {condition: load_condition_results(condition) for condition in CONDITIONS}
    offline = json.loads(OFFLINE_FIRST_SEARCH.read_text())
    first_search_baseline = {
        row["task_id"]: row
        for row in offline["results"]
        if row["backend"] == "baseline" and row["query_index"] == 1
    }

    candidates = []
    for task_id, row in results["baseline"].items():
        first_search = next((tc for tc in row["tool_calls"] if tc["tool_name"] == "search_code"), None)
        if not first_search:
            continue

        baseline_metrics = planner_metrics(row)
        offline_row = first_search_baseline.get(task_id)
        informative_first_search = bool(offline_row and offline_row.get("mrr", 0) > 0)
        first_search_no_match = "No matches found." in first_search["output"]

        cohort = "neutral"
        if first_search_no_match and baseline_metrics["consecutive_searches_before_first_read"] >= 2:
            cohort = "recovery"
        elif informative_first_search and baseline_metrics["consecutive_searches_before_first_read"] >= 2:
            cohort = "decision"

        search_pressure_score = (
            baseline_metrics["consecutive_searches_before_first_read"]
            + baseline_metrics["total_searches"]
            + (5 if first_search_no_match else 0)
            + (1 if informative_first_search else 0)
        )

        candidates.append(
            {
                "task_id": task_id,
                "task_type": row["task_type"],
                "prompt": row["prompt"],
                "cohort": cohort,
                "score": search_pressure_score,
                "baseline_total_searches": baseline_metrics["total_searches"],
                "baseline_consecutive_searches_before_first_read": baseline_metrics[
                    "consecutive_searches_before_first_read"
                ],
                "baseline_first_search_mrr": offline_row.get("mrr", 0.0) if offline_row else 0.0,
                "baseline_first_search_no_match": first_search_no_match,
            }
        )

    recovery = sorted(
        [item for item in candidates if item["cohort"] == "recovery"],
        key=lambda item: (
            item["baseline_consecutive_searches_before_first_read"],
            item["score"],
            item["task_id"],
        ),
        reverse=True,
    )
    decision = sorted(
        [item for item in candidates if item["cohort"] == "decision"],
        key=lambda item: (
            item["baseline_consecutive_searches_before_first_read"],
            item["baseline_first_search_mrr"],
            item["task_id"],
        ),
        reverse=True,
    )
    neutral = sorted(
        [item for item in candidates if item["cohort"] == "neutral"],
        key=lambda item: (item["score"], item["task_id"]),
        reverse=True,
    )

    selected: list[dict] = []
    selected_ids: set[str] = set()
    for group in [recovery, decision, neutral]:
        for item in group:
            if len(selected) >= TARGET_TOTAL:
                break
            if item["task_id"] in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item["task_id"])

    rows = []
    for item in selected:
        for condition in CONDITIONS:
            metrics = planner_metrics(results[condition][item["task_id"]])
            rows.append(
                {
                    "task_id": item["task_id"],
                    "task_type": item["task_type"],
                    "cohort": item["cohort"],
                    "condition": condition,
                    **metrics,
                }
            )

    summary = {"overall": {}, "by_cohort": {}, "paired_vs_baseline": {}}
    for condition in CONDITIONS:
        subset = [row for row in rows if row["condition"] == condition]
        summary["overall"][condition] = {
            metric: statistics.mean(float(row[metric]) for row in subset)
            for metric in NUMERIC_METRICS
        }

    for cohort in ["decision", "recovery", "neutral"]:
        summary["by_cohort"][cohort] = {}
        for condition in CONDITIONS:
            subset = [row for row in rows if row["condition"] == condition and row["cohort"] == cohort]
            summary["by_cohort"][cohort][condition] = {
                metric: statistics.mean(float(row[metric]) for row in subset)
                for metric in NUMERIC_METRICS
            }

    for comparison in COMPARISONS:
        summary["paired_vs_baseline"][comparison] = {
            metric: paired_stats(rows, metric, comparison)
            for metric in [
                "consecutive_searches_before_first_read",
                "total_searches",
                "total_tool_calls",
                "total_cost_usd",
                "wall_clock_ms",
            ]
        }

    design = {
        "source_full60_results": "public_release/benchmarks/entireio_cli_ranking_public60/full60/results",
        "result_dir_by_condition": RESULT_DIR_BY_CONDITION,
        "source_offline_first_search": "public_release/benchmarks/entireio_cli_offline_ir_public60/first_search/results.json",
        "target_total": TARGET_TOTAL,
        "condition_order": CONDITIONS,
        "cohort_definition": {
            "recovery": "baseline first search was a no-match and consecutive_searches_before_first_read >= 2",
            "decision": "baseline first search had weak relevance signal (MRR > 0) and consecutive_searches_before_first_read >= 2",
            "neutral": "remaining tasks filled by search pressure score",
        },
        "cohort_counts": {
            "recovery": sum(1 for item in selected if item["cohort"] == "recovery"),
            "decision": sum(1 for item in selected if item["cohort"] == "decision"),
            "neutral": sum(1 for item in selected if item["cohort"] == "neutral"),
        },
        "selected_tasks": selected,
    }

    (BENCHMARK_DIR / "design.json").write_text(json.dumps(design, indent=2))
    (BENCHMARK_DIR / "summary.json").write_text(json.dumps({"design": design, "rows": rows, "summary": summary}, indent=2))
    (BENCHMARK_DIR / "SUMMARY.md").write_text(build_summary_markdown(design, summary))


if __name__ == "__main__":
    main()
