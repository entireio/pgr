#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
REPOS_ROOT = Path(os.environ.get("PGR_EVAL_REPOS_ROOT", "/tmp/pgr-eval/repos"))
RESULTS_ROOT = REPO_ROOT / 'public_release/benchmarks/entireio_cli_ranking_public60/full60/results/baseline'
REPO_NAME = 'entireio-cli'


@dataclass(frozen=True)
class QueryCase:
    case_id: str
    run_id: str
    task_id: str
    repo: str
    prompt_category: str
    repeat: int
    query_index: int
    subset: str
    relevant_files: tuple[str, ...]
    tool_input: dict[str, Any]
    prompt: str


def _normalize_path(path: str) -> str:
    p = (path or '').strip()
    while p.startswith('./'):
        p = p[2:]
    return p


def _is_relevant(path: str, relevant_files: tuple[str, ...]) -> bool:
    normalized = _normalize_path(path)
    return any(rf == normalized or normalized.endswith(rf) or rf.endswith(normalized) for rf in relevant_files)


def _extract_paths(search_output: str) -> list[str]:
    if not search_output or search_output.strip() == 'No matches found.':
        return []
    paths = []
    seen = set()
    for raw_line in search_output.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.startswith(' ') or line.startswith('(') or line == 'No matches found.':
            continue
        if line.startswith('→ Read '):
            helper = line[len('→ Read '):]
            helper = re.split(r' \((?:only match|best match).*$| \[.*\]$', helper, maxsplit=1)[0]
            path = _normalize_path(helper)
            if path and path not in seen:
                seen.add(path)
                paths.append(path)
            continue
        path = _normalize_path(line)
        if path and path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


def _score_result(search_output: str, relevant_files: tuple[str, ...]) -> dict[str, Any]:
    paths = _extract_paths(search_output)
    first_rank = None
    for index, path in enumerate(paths, start=1):
        if _is_relevant(path, relevant_files):
            first_rank = index
            break
    return {
        'files_returned': len(paths),
        'output_chars': len(search_output),
        'first_relevant_rank': first_rank,
        'mrr': 0.0 if first_rank is None else 1.0 / first_rank,
        'hit_at_1': bool(first_rank == 1),
        'hit_at_3': bool(first_rank is not None and first_rank <= 3),
        'hit_at_5': bool(first_rank is not None and first_rank <= 5),
    }


def load_cases(subset: str) -> list[QueryCase]:
    cases: list[QueryCase] = []
    for result_path in sorted(RESULTS_ROOT.glob('*.json')):
        obj = json.loads(result_path.read_text())
        tool_calls = obj.get('tool_calls', [])
        read_paths = []
        seen_reads = set()
        first_read_idx = None
        for i, tc in enumerate(tool_calls):
            if tc.get('tool_name') == 'read_code':
                p = _normalize_path(tc.get('tool_input', {}).get('path', ''))
                if p and p not in seen_reads:
                    seen_reads.add(p)
                    read_paths.append(p)
                if first_read_idx is None:
                    first_read_idx = i
        if not read_paths:
            continue
        relevant_files = tuple(read_paths)
        search_index = 0
        for i, tc in enumerate(tool_calls):
            if tc.get('tool_name') != 'search_code':
                continue
            search_index += 1
            if subset == 'first_search' and search_index > 1:
                break
            if subset == 'pre_read' and first_read_idx is not None and i >= first_read_idx:
                break
            if subset == 'first_search' or (subset == 'pre_read' and first_read_idx is not None and i < first_read_idx):
                cases.append(QueryCase(
                    case_id=f"{obj['task_id']}_r{obj['repeat']}:q{search_index}",
                    run_id=f"{obj['task_id']}_r{obj['repeat']}",
                    task_id=obj['task_id'],
                    repo=obj.get('repo', REPO_NAME),
                    prompt_category=obj.get('task_type', 'unknown'),
                    repeat=int(obj.get('repeat', 0)),
                    query_index=search_index,
                    subset=subset,
                    relevant_files=relevant_files,
                    tool_input=dict(tc.get('tool_input', {})),
                    prompt=obj.get('prompt', ''),
                ))
    return cases


def build_backends():
    sys.path.insert(0, str(REPO_ROOT / 'eval/v2'))
    from backends import baseline
    from backends import fff_backend
    from backends import rg_ranked
    from backends import pgr_v3_backend
    return {
        'baseline': baseline,
        'fff': fff_backend,
        'rg_ranked': rg_ranked,
        'pgr_v4': pgr_v3_backend,
    }


def evaluate_case(case: QueryCase, backend_name: str, backend_module: Any) -> dict[str, Any]:
    repo_root = str(REPOS_ROOT / case.repo)
    search_output = backend_module.search_code(
        repo_root=repo_root,
        query=case.tool_input['query'],
        path_glob=case.tool_input.get('path_glob', ''),
        file_type=case.tool_input.get('file_type', ''),
        max_files=case.tool_input.get('max_files', 10),
        max_matches_per_file=case.tool_input.get('max_matches_per_file', 3),
        context_before=case.tool_input.get('context_before', 2),
        context_after=case.tool_input.get('context_after', 2),
    )
    scored = _score_result(search_output, case.relevant_files)
    scored.update({
        'backend': backend_name,
        'case_id': case.case_id,
        'run_id': case.run_id,
        'task_id': case.task_id,
        'prompt_category': case.prompt_category,
        'repeat': case.repeat,
        'query_index': case.query_index,
        'query': case.tool_input['query'],
        'tool_input': case.tool_input,
        'relevant_files': list(case.relevant_files),
        'prompt': case.prompt,
    })
    return scored


def paired_stats(rows: list[dict[str, Any]], metric: str, group_key: str) -> dict[str, Any]:
    grouped: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        group = row[group_key]
        grouped.setdefault(group, {})
        grouped[group].setdefault(row['backend'], []).append(float(row[metric]))
    higher_is_better = metric not in {'output_chars', 'files_returned'}
    results: dict[str, Any] = {}
    backends = sorted({row['backend'] for row in rows})
    for other in [b for b in backends if b != 'baseline']:
        diffs = []
        for values in grouped.values():
            if 'baseline' not in values or other not in values:
                continue
            diffs.append(statistics.mean(values[other]) - statistics.mean(values['baseline']))
        if len(diffs) < 2:
            continue
        mean_diff = statistics.mean(diffs)
        sd = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
        se = sd / math.sqrt(len(diffs)) if sd else 0.0
        t_crit = 2.009 if len(diffs) > 50 else 2.023
        ci_low = mean_diff - t_crit * se
        ci_high = mean_diff + t_crit * se
        results[f'{other}_vs_baseline'] = {
            'n_groups': len(diffs),
            'mean_diff': mean_diff,
            'ci95': [ci_low, ci_high],
            'wins': sum(1 for d in diffs if (d > 0 if higher_is_better else d < 0)),
            'losses': sum(1 for d in diffs if (d < 0 if higher_is_better else d > 0)),
            'ties': sum(1 for d in diffs if d == 0),
        }
    return results


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = ['mrr', 'hit_at_1', 'hit_at_3', 'hit_at_5', 'output_chars', 'files_returned']
    summary: dict[str, Any] = {'overall': {}, 'by_prompt_category': {}, 'paired_by_run': {}, 'paired_by_task': {}}
    backends = sorted({row['backend'] for row in rows})
    for backend in backends:
        backend_rows = [row for row in rows if row['backend'] == backend]
        summary['overall'][backend] = {m: statistics.mean(float(r[m]) for r in backend_rows) for m in metrics}
    for cat in sorted({row['prompt_category'] for row in rows}):
        summary['by_prompt_category'][cat] = {}
        for backend in backends:
            backend_rows = [r for r in rows if r['backend'] == backend and r['prompt_category'] == cat]
            if not backend_rows:
                continue
            summary['by_prompt_category'][cat][backend] = {m: statistics.mean(float(r[m]) for r in backend_rows) for m in metrics}
    for metric in metrics:
        summary['paired_by_run'][metric] = paired_stats(rows, metric, 'run_id')
        summary['paired_by_task'][metric] = paired_stats(rows, metric, 'task_id')
    return summary


def write_summary_md(out_dir: Path, subset: str, payload: dict[str, Any]) -> None:
    s = payload['summary']['overall']
    e = payload['experiment']
    backends = [name for name in ['baseline', 'fff', 'rg_ranked', 'pgr_v4'] if name in s]
    lines = [
        f"# entireio_cli_offline_ir_public60_{subset}",
        '',
        'Public offline retrieval benchmark using weak labels from baseline `read_code` decisions.',
        '',
        '## Setup',
        '',
        f"- Query cases: {e['num_cases']}",
        f"- Runs: {e['num_runs']}",
        f"- Tasks: {e['num_tasks']}",
        '- Conditions: ' + ', '.join(f'`{name}`' for name in backends),
        '- Relevance signal: unique files the baseline agent opened with `read_code` in that run',
        '',
        '## Overall',
        '',
    ]
    lines.extend([
        '| Metric | ' + ' | '.join('Baseline' if name == 'baseline' else f'`{name}`' for name in backends) + ' |',
        '|---|' + '---:|' * len(backends),
        '| MRR | ' + ' | '.join(f"{s[name]['mrr']:.4f}" for name in backends) + ' |',
        '| Hit@1 | ' + ' | '.join(f"{100*s[name]['hit_at_1']:.1f}%" for name in backends) + ' |',
        '| Hit@3 | ' + ' | '.join(f"{100*s[name]['hit_at_3']:.1f}%" for name in backends) + ' |',
        '| Avg output chars | ' + ' | '.join(f"{s[name]['output_chars']:.1f}" for name in backends) + ' |',
        '',
        '## Paired by task',
        '',
    ])
    paired = payload['summary']['paired_by_task']
    for metric, label in [('mrr','MRR'),('hit_at_1','Hit@1'),('hit_at_3','Hit@3'),('output_chars','output chars')]:
        for comp in [key for key in paired[metric].keys() if key.endswith('_vs_baseline')]:
            stats = paired[metric].get(comp)
            if not stats:
                continue
            name = comp.replace('_vs_baseline','')
            diff = stats['mean_diff']
            if metric.startswith('hit_at_'):
                diff_str = f"{100*diff:+.1f} points"
                ci_str = f"[{100*stats['ci95'][0]:+.1f}, {100*stats['ci95'][1]:+.1f}]"
            elif metric == 'output_chars':
                diff_str = f"{diff:+.0f}"
                ci_str = f"[{stats['ci95'][0]:+.0f}, {stats['ci95'][1]:+.0f}]"
            else:
                diff_str = f"{diff:+.3f}"
                ci_str = f"[{stats['ci95'][0]:+.3f}, {stats['ci95'][1]:+.3f}]"
            lines.append(f"- **{label} {name} vs baseline:** {diff_str}, 95% CI {ci_str}")
    lines.append('')
    (out_dir / 'SUMMARY.md').write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--subset', choices=['first_search', 'pre_read'], required=True)
    parser.add_argument('--parallel', type=int, default=4)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    cases = load_cases(args.subset)
    backends = build_backends()
    rows = []

    def run_one(case, backend_name):
        return evaluate_case(case, backend_name, backends[backend_name])

    futures = {}
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        for case in cases:
            for backend_name in backends:
                fut = ex.submit(run_one, case, backend_name)
                futures[fut] = (case.case_id, backend_name)
        done = 0
        for fut in as_completed(futures):
            rows.append(fut.result())
            done += 1
            if done % 100 == 0 or done == len(futures):
                print(f'completed {done}/{len(futures)}', flush=True)
    rows.sort(key=lambda r: (r['case_id'], r['backend']))
    payload = {
        'experiment': {
            'subset': args.subset,
            'num_cases': len(cases),
            'num_runs': len({c.run_id for c in cases}),
            'num_tasks': len({c.task_id for c in cases}),
            'repo': REPO_NAME,
            'results_root': str(RESULTS_ROOT),
            'label_source': 'unique read_code paths from baseline run',
        },
        'cases': [asdict(c) for c in cases],
        'results': rows,
        'summary': aggregate(rows),
    }
    (args.out_dir / 'results.json').write_text(json.dumps(payload, indent=2))
    write_summary_md(args.out_dir, args.subset, payload)
    for backend_name in ('pgr_v4', 'fff'):
        backend = backends.get(backend_name)
        if backend and hasattr(backend, 'cleanup'):
            backend.cleanup()
    print('wrote', args.out_dir)

if __name__ == '__main__':
    main()
