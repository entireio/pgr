# Baseline vs fff on Public entireio/cli Search-Sensitive 60

This package reruns the "faster search is not the bottleneck" experiment on a
public, trace-derived prompt suite from `entireio/cli`.

The benchmark compares:

- `baseline`: raw `ripgrep`
- `fff`: indexed stateful MCP search

on 60 prompts drawn from public checkpoint transcripts for the `entireio/cli`
repository.

## Files

- `build_tasks.py`: rebuilds `tasks.json` and `design.json` from the public export
- `run_benchmark.py`: benchmark runner
- `tasks.json`: explicit task list
- `design.json`: benchmark configuration
- `results/`: per-run outputs by condition
- `summary.json`: aggregate summary payload
- `SUMMARY.md`: human-readable summary

## Source data

- `../../data/entireio_cli_checkpoints_2026_04_15/checkpoint_transcripts.jsonl.gz`

## Repo under test

- a local checkout of `entireio/cli`

## Selection notes

- Tasks are real checkpoint prompts from the public transcript export.
- The suite prefers prompts that appear answerable from the repository alone.
- Each task keeps its original checkpoint-level search pressure metadata.
