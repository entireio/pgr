#!/usr/bin/env python3
"""Baseline vs fff benchmark on a public entireio/cli prompt suite."""

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
EVAL_V2_DIR = REPO_ROOT / 'eval' / 'v2'
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
TASKS_JSON = DEFAULT_OUTPUT_DIR / 'tasks.json'
DESIGN_JSON = DEFAULT_OUTPUT_DIR / 'design.json'
DEFAULT_REPO_ROOT = Path(os.environ.get("PGR_EVAL_REPO_ROOT", "/tmp/pgr-eval/repos/entireio-cli"))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def build_imports():
    sys.path.insert(0, str(EVAL_V2_DIR))
    from agent import run_task  # type: ignore
    from backends import fff_backend  # type: ignore
    return run_task, fff_backend


def run_single(run_task_fn: Any, task: dict[str, Any], condition: str, model: str, max_turns: int, repo_root: str) -> dict[str, Any]:
    result = run_task_fn(
        task_id=task['id'],
        repo=task['repo'],
        task_type=task['type'],
        prompt=task['prompt'],
        repo_root=repo_root,
        condition=condition,
        model=model,
        max_turns=max_turns,
    )
    return result.to_dict()


def tool_metrics(result: dict[str, Any]) -> dict[str, Any]:
    tool_calls = result.get('tool_calls', [])
    total_tool_duration_ms = sum(float(tc.get('duration_ms', 0.0)) for tc in tool_calls)
    search_calls = [tc for tc in tool_calls if tc.get('tool_name') == 'search_code']
    read_calls = [tc for tc in tool_calls if tc.get('tool_name') == 'read_code']
    return {
        'total_tool_duration_ms': total_tool_duration_ms,
        'tool_execution_share': (total_tool_duration_ms / result['wall_clock_ms']) if result['wall_clock_ms'] else 0.0,
        'search_call_count': len(search_calls),
        'avg_search_code_duration_ms': statistics.mean(float(tc.get('duration_ms', 0.0)) for tc in search_calls) if search_calls else 0.0,
        'median_search_code_duration_ms': statistics.median(float(tc.get('duration_ms', 0.0)) for tc in search_calls) if search_calls else 0.0,
        'avg_read_code_duration_ms': statistics.mean(float(tc.get('duration_ms', 0.0)) for tc in read_calls) if read_calls else 0.0,
        'median_read_code_duration_ms': statistics.median(float(tc.get('duration_ms', 0.0)) for tc in read_calls) if read_calls else 0.0,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {'overall': {}, 'by_type': {}, 'paired_by_task': {}}
    metrics = [
        'wall_clock_ms', 'total_tool_calls', 'total_cost_usd', 'tool_output_tokens',
        'total_tool_duration_ms', 'tool_execution_share', 'search_call_count',
        'avg_search_code_duration_ms', 'median_search_code_duration_ms',
        'avg_read_code_duration_ms', 'median_read_code_duration_ms',
    ]
    for condition in ['baseline', 'fff']:
        subset = [row for row in rows if row['condition'] == condition]
        summary['overall'][condition] = {metric: statistics.mean(float(row[metric]) for row in subset) for metric in metrics}

    for task_type in sorted({row['task_type'] for row in rows}):
        summary['by_type'][task_type] = {}
        for condition in ['baseline', 'fff']:
            subset = [row for row in rows if row['condition'] == condition and row['task_type'] == task_type]
            summary['by_type'][task_type][condition] = {metric: statistics.mean(float(row[metric]) for row in subset) for metric in metrics}

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in rows:
        grouped.setdefault(row['task_id'], {}).setdefault(row['condition'], []).append(row)

    for metric in metrics:
        diffs = []
        for conditions in grouped.values():
            if 'baseline' not in conditions or 'fff' not in conditions:
                continue
            base = statistics.mean(float(r[metric]) for r in conditions['baseline'])
            other = statistics.mean(float(r[metric]) for r in conditions['fff'])
            diffs.append(other - base)
        if diffs:
            summary['paired_by_task'][metric] = {
                'n_tasks': len(diffs),
                'mean_diff': statistics.mean(diffs),
                'median_diff': statistics.median(diffs),
            }
    return summary


def write_markdown(design: dict[str, Any], summary: dict[str, Any], out_path: Path) -> None:
    base = summary['overall']['baseline']
    fff = summary['overall']['fff']
    tasks = design['tasks']
    task_types = sorted({task['type'] for task in tasks})
    examples = tasks[:8]
    lines = [
        '# Baseline vs fff on Public entireio/cli Search-Sensitive 60',
        '',
        'This benchmark reruns the "faster search is not the bottleneck" comparison on a trace-derived public task set from `entireio/cli`.',
        '',
        '## Setup',
        '',
        f'- Tasks: {len(tasks)}',
        f"- Repeats per condition: {design['repeats']}",
        '- Conditions: `baseline` (raw ripgrep) vs `fff`',
        f"- Model: `{design['model']}`",
        f"- Max turns: {design['max_turns']}",
        '- Repo: `entireio/cli`',
        f"- Repo root: `{design['repo_root']}`",
        '',
        '## Prompt categories',
        '',
    ]
    lines.extend(f'- `{task_type}`' for task_type in task_types)
    lines.extend(['', '## Example tasks', ''])
    lines.extend(f"- `{task['id']}` ({task['type']}): {task['prompt'][:180]}" for task in examples)
    lines.extend([
        '',
        '## Overall',
        '',
        '| Metric | Baseline | fff |',
        '|---|---:|---:|',
        f"| Avg wall clock per run | {base['wall_clock_ms'] / 1000:.2f}s | {fff['wall_clock_ms'] / 1000:.2f}s |",
        f"| Avg tool calls | {base['total_tool_calls']:.2f} | {fff['total_tool_calls']:.2f} |",
        f"| Avg total tool execution time per run | {base['total_tool_duration_ms'] / 1000:.3f}s | {fff['total_tool_duration_ms'] / 1000:.3f}s |",
        f"| Tool execution share of wall clock | {base['tool_execution_share'] * 100:.1f}% | {fff['tool_execution_share'] * 100:.1f}% |",
        f"| Avg `search_code` duration | {base['avg_search_code_duration_ms']:.1f}ms | {fff['avg_search_code_duration_ms']:.1f}ms |",
        f"| Median `search_code` duration | {base['median_search_code_duration_ms']:.1f}ms | {fff['median_search_code_duration_ms']:.1f}ms |",
        '',
        '## Interpretation',
        '',
        'This public rerun uses a larger, trace-derived task set than the earlier 40-task benchmark, but the core pattern is the same: raw search latency is a tiny slice of end-to-end agent time.',
        '',
        f"- `fff` drove median `search_code` latency from {base['median_search_code_duration_ms']:.1f}ms to {fff['median_search_code_duration_ms']:.1f}ms",
        f"- but end-to-end wall clock moved from {base['wall_clock_ms'] / 1000:.2f}s to {fff['wall_clock_ms'] / 1000:.2f}s",
        '',
    ])
    out_path.write_text('\n'.join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description='Run baseline vs fff on public entireio/cli prompt suite')
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument('--parallel', type=int, default=2)
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--max-turns', type=int, default=12)
    parser.add_argument('--model', default='claude-sonnet-4-6')
    parser.add_argument('--env-file', type=Path, default=REPO_ROOT / '.env')
    parser.add_argument('--repo-root', type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument('--task-limit', type=int, default=0)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    load_env_file(args.env_file)
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise SystemExit('ANTHROPIC_API_KEY is not set. Use --env-file or export it before running.')
    if not args.repo_root.exists():
        raise SystemExit(f'repo root does not exist: {args.repo_root}')

    tasks = json.loads(TASKS_JSON.read_text())
    design = json.loads(DESIGN_JSON.read_text())
    if args.task_limit > 0:
        tasks = tasks[:args.task_limit]
        design = {**design, 'tasks': tasks}

    if args.dry_run:
        print(json.dumps({'task_count': len(tasks), 'repo_root': str(args.repo_root), 'first_tasks': tasks[:5]}, indent=2))
        return

    run_task_fn, _ = build_imports()
    output_dir = args.output_dir
    results_dir = output_dir / 'results'
    (results_dir / 'baseline').mkdir(parents=True, exist_ok=True)
    (results_dir / 'fff').mkdir(parents=True, exist_ok=True)

    jobs = []
    for repeat in range(args.repeats):
        for task in tasks:
            for condition in ['baseline', 'fff']:
                jobs.append((repeat, task, condition))

    rows = []
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        future_map = {
            ex.submit(run_single, run_task_fn, task, condition, args.model, args.max_turns, str(args.repo_root)): (repeat, task, condition)
            for repeat, task, condition in jobs
        }
        for future in as_completed(future_map):
            repeat, task, condition = future_map[future]
            result = future.result()
            row = {
                'repeat': repeat,
                'task_id': task['id'],
                'repo': task['repo'],
                'task_type': task['type'],
                'condition': condition,
                **result,
            }
            row.update(tool_metrics(result))
            rows.append(row)
            out_file = results_dir / condition / f"{task['id']}_r{repeat}.json"
            out_file.write_text(json.dumps(row, indent=2) + '\n')
            print(f"[{condition}] {task['id']} complete: wall={row['wall_clock_ms']/1000:.2f}s search={row['search_call_count']}", flush=True)

    summary = summarize(rows)
    (output_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    write_markdown(design, summary, output_dir / 'SUMMARY.md')
    print(json.dumps(summary['overall'], indent=2))


if __name__ == '__main__':
    main()
