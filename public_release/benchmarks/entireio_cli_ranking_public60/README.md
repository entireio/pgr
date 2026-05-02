# Ranking Benchmark on Public `entireio/cli`

This package reruns the ranked-search story on a public, trace-derived task suite
from `entireio/cli`.

It compares:

- `baseline`: raw `ripgrep`
- `fff`: stateful indexed MCP search
- `rg_ranked`: Python ranking heuristics on top of `ripgrep`
- `pgr_v4`: the current Rust MCP implementation and output profile used in the public runs

Artifacts:

- `tasks_full60.json`: full 60-task public suite
- `tasks_pilot25.json`: explicit 25-task pilot subset
- `design_full60.json`: full-suite benchmark design
- `design_pilot25.json`: pilot benchmark design
- `run_benchmark.py`: generic runner for either task file
- `pilot25/`: pilot results and summary
- `full60/`: full benchmark results and summary, including `fff`

Source data:

- `../../data/entireio_cli_checkpoints_2026_04_15/checkpoint_transcripts.jsonl.gz`

Repo under test:

- a local checkout of `entireio/cli`

Saved results:

- `pilot25/results/`
- `full60/results/`
