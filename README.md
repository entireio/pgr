# pgr

`pgr` is a stateless MCP code-search server for coding agents.

It is built around a simple idea: faster search alone is not enough. What matters just as much is whether the search result helps the model choose a better next action.

`pgr` wraps local code search with ranking and output shaping designed for agent workflows: surfacing likely implementation files earlier, de-prioritizing tests and low-value matches, and formatting results so a model can decide what to read next with less thrashing.

This repository also includes the public datasets, benchmark packages, and saved results used in the accompanying writeup on agentic code search.

## What is in this repo

- `src/`
  - the Rust MCP server
- `tests/`
  - integration tests for the MCP surface
- `eval/v2/`
  - the minimal evaluation harness and backend adapters used by the public benchmark runners
- `public_release/`
  - public datasets, benchmark definitions, summaries, and saved outputs referenced in the blog post

## Why we built it

In the public benchmarks in this repository, the strongest effects did not come from raw scan speed. They showed up in more local agent behavior:

- better first-query retrieval quality
- fewer redundant search loops before the first code read
- getting the agent into reading relevant files sooner

That is the problem `pgr` is designed to improve.

## Build

```bash
cargo build --release
```

The binary will be available at `target/release/pgr`.

## Running `pgr`

`pgr` is designed to run as an MCP server over stdio.

At a high level it provides tools for:

- `search_code`
- `read_code`
- `find_files`
- `list_dir`

The search output profile is controlled with `PGR_OUTPUT_PROFILE`.

Supported profiles include:

- `v3`
- `empty_only`
- `summary_only`
- `counts_empty`
- `full_v4`

If `PGR_OUTPUT_PROFILE` is unset, the server defaults to `full_v4`.

## Public benchmark packages

The public artifacts referenced in the writeup live under [`public_release/`](public_release/README.md).

Key packages:

- [`public_release/data/entireio_cli_checkpoints_2026_04_15/README.md`](public_release/data/entireio_cli_checkpoints_2026_04_15/README.md)
  - public `entireio/cli` checkpoint export used for the trace analysis
- [`public_release/benchmarks/entireio_cli_fff_vs_baseline_public60/README.md`](public_release/benchmarks/entireio_cli_fff_vs_baseline_public60/README.md)
  - speed-oriented benchmark comparing `ripgrep` and `fff`
- [`public_release/benchmarks/entireio_cli_ranking_public60/README.md`](public_release/benchmarks/entireio_cli_ranking_public60/README.md)
  - broad mixed-workload benchmark comparing `baseline`, `fff`, `rg_ranked`, and `pgr_v4`
- [`public_release/benchmarks/entireio_cli_offline_ir_public60/README.md`](public_release/benchmarks/entireio_cli_offline_ir_public60/README.md)
  - offline retrieval replay benchmark built from real agent-issued queries
- [`public_release/benchmarks/entireio_cli_planner_public40/README.md`](public_release/benchmarks/entireio_cli_planner_public40/README.md)
  - planner-focused benchmark derived from the saved public runs

## Repository scope

This public repository is intentionally focused on:

- the Rust MCP search server
- the minimal benchmark harness needed by the public runners
- the public data and results packages cited in the writeup

Older internal drafts, duplicate exports, and superseded experimental outputs have been removed so the repo stays small, inspectable, and externally understandable.
