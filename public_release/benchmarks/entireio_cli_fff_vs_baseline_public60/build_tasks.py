#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

BENCHMARK_DIR = Path(__file__).resolve().parent
EXPORT_FILE = (
    BENCHMARK_DIR.parent.parent
    / 'data'
    / 'entireio_cli_checkpoints_2026_04_15'
    / 'checkpoint_transcripts.jsonl.gz'
)
TASKS_JSON = BENCHMARK_DIR / 'tasks.json'
DESIGN_JSON = BENCHMARK_DIR / 'design.json'

SELECTED_CHECKPOINT_IDS = [
    'eb5cdbdef570', '897eb280e769', '5eec47c03756', '61de2c90668f', '37f449ec7d97',
    'ea384d108347', 'a70d97c363c8', '1d44b085fc12', '3906e953d4ef', 'c283d360e6d5',
    '751884f8707a', '8b5b4eca788e', '9de3322f8275', '2458c3b38f2c', '2a075ef186b4',
    'f0c3dbdad0d8', 'cc90f6622c5b', '979a49177542', 'd7c8f8341919', '3afc9eb5cf12',
    'c0dbb5d73ef9', '77072abe499b', 'c07dfe9d6805', 'a768042b28b1', '69682d9f2992',
    '0b79e8932981', 'c6491956c19f', 'c08972f3adb1', '9d54ae3daa05', '209a37190167',
    '2baba34463b5', '87d00b47af3f', 'b6c45b0e881f', '5adf55c634da', '02d49af5bfe0',
    '30ff1132accf', '94de498254e2', '2084a83cf3a3', 'b02936744f3b', '97c75100bbac',
    '85df9ac94bc7', 'aa5afbf6c998', 'e30f791a2d4d', 'd1d3bff114fe', '9d45e0e8b9e7',
    'bea7d0b9e7b8', '8a01af2a474f', 'b82393d3cbc2', '6191df2265d1', 'f64fee85be5f',
    'c762fa015c6a', 'e58e27b1ba0d', '30646c347ecd', '7d66f047ac98', '2c5705f6152f',
    '68f26bfdf530', '9f325be721aa', '6dcf16e1b2ba', '4108db521b5d', '20388d3a424a',
]

SEARCH_BASH_PATTERNS = [
    r'\brg\b', r'\bgrep\b', r'\bfind\b', r'\bfd\b', r'\bag\b',
    r'\back\b', r'\bwc\b.*-l', r'\bls\b', r'\btree\b', r'\bgit\s+(log|show|diff|blame|grep)',
]


def extract_tool_uses(content):
    if not isinstance(content, list):
        return []
    out = []
    for block in content:
        if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name'):
            out.append((block.get('name'), block.get('input') or {}))
    return out


def tool_calls_from_transcript(raw):
    sessions = raw if isinstance(raw, dict) else json.loads(raw)
    calls = []
    for _, jsonl in sessions.items():
        if not isinstance(jsonl, str):
            continue
        for line in jsonl.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get('type') == 'assistant':
                msg = obj.get('message') or {}
                for name, inp in extract_tool_uses(msg.get('content')):
                    calls.append((name, inp))
    return calls


def is_search(name, inp):
    if name in {'Grep', 'Glob', 'Read'}:
        return True
    if name == 'Agent':
        prompt = (inp.get('prompt') or '') if isinstance(inp, dict) else ''
        return bool(re.search(r'search|find|grep|look for|locate|where is|definition of', prompt, re.I))
    if name == 'Bash':
        cmd = (inp.get('command') or '') if isinstance(inp, dict) else ''
        return any(re.search(p, cmd) for p in SEARCH_BASH_PATTERNS)
    return False


def categorize_prompt(prompt: str) -> str:
    s = prompt.lower()
    if any(k in s for k in ['what', 'why', 'how', 'where', 'explain', 'logic', 'summary', 'understand']):
        return 'code_understanding'
    if any(k in s for k in ['failing test', 'test', 'lint', 'warn', 'error', 'bug', 'issue', 'failing']):
        return 'debug_or_validation'
    if any(k in s for k in ['implement', 'add', 'update', 'support', 'fix', 'improve']):
        return 'implementation'
    return 'repo_task'


def load_rows():
    rows = {}
    with gzip.open(EXPORT_FILE, 'rt') as f:
        for line in f:
            obj = json.loads(line)
            checkpoint_id = obj['checkpoint_id']
            if checkpoint_id not in SELECTED_CHECKPOINT_IDS:
                continue
            prompt = ' '.join((obj.get('prompt') or '').split())
            calls = tool_calls_from_transcript(obj['transcript_stripped'])
            total = len(calls)
            search = sum(1 for n, inp in calls if is_search(n, inp))
            rows[checkpoint_id] = {
                'id': checkpoint_id,
                'repo': 'entireio-cli',
                'type': categorize_prompt(prompt),
                'prompt': prompt,
                'selection_meta': {
                    'checkpoint_id': checkpoint_id,
                    'agent': obj.get('agent'),
                    'session_id': obj.get('session_id'),
                    'checkpoint_created_at': obj.get('checkpoint_created_at'),
                    'total_tool_calls': total,
                    'search_related_tool_calls': search,
                    'source': 'public_release/data/entireio_cli_checkpoints_2026_04_15/checkpoint_transcripts.jsonl.gz',
                },
            }
    missing = [cid for cid in SELECTED_CHECKPOINT_IDS if cid not in rows]
    if missing:
        raise SystemExit(f'Missing checkpoints in export: {missing}')
    return [rows[cid] for cid in SELECTED_CHECKPOINT_IDS]


def main():
    tasks = load_rows()
    TASKS_JSON.write_text(json.dumps(tasks, indent=2) + '\n')
    design = {
        'name': 'entireio_cli_fff_vs_baseline_public60',
        'tasks_source': str(EXPORT_FILE),
        'selection': {
            'kind': 'trace_derived_public_prompts',
            'repo': 'entireio/cli',
            'task_count': len(tasks),
            'notes': [
                'Tasks are real checkpoint prompts drawn from the public entireio/cli transcript export.',
                'The suite was manually curated to prefer prompts answerable from the repository alone.',
                'Each task includes original checkpoint-level search pressure metadata from the source trace.',
            ],
        },
        'tasks': tasks,
        'conditions': ['baseline', 'fff'],
        'repeats': 1,
        'model': 'claude-sonnet-4-6',
        'max_turns': 12,
        'repo_root': '/tmp/pgr-eval/repos/entireio-cli',
    }
    DESIGN_JSON.write_text(json.dumps(design, indent=2) + '\n')
    print(f'wrote {len(tasks)} tasks to {TASKS_JSON}')


if __name__ == '__main__':
    main()
