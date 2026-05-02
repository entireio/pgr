# Public release artifacts

This directory contains the public datasets, benchmark packages, and analysis artifacts referenced in the `pgr` writeup.

Everything here is intended to be shareable and inspectable without access to any private repositories or customer data.

## Layout

- `data/`
  - exported public datasets used in the analysis
- `analysis/`
  - benchmark notes and derived summaries used in the writeup
- `benchmarks/`
  - reproducible benchmark definitions, scripts, summaries, and saved outputs

## Main artifacts

- `data/entireio_cli_checkpoints_2026_04_15/`
  - public `entireio/cli` checkpoint export used for the search-usage analysis
- `benchmarks/entireio_cli_fff_vs_baseline_public60/`
  - speed-oriented benchmark comparing `ripgrep` and `fff`
- `benchmarks/entireio_cli_ranking_public60/`
  - broad end-to-end benchmark comparing `baseline`, `fff`, `rg_ranked`, and the current `pgr` output profile
- `benchmarks/entireio_cli_offline_ir_public60/`
  - offline retrieval replay benchmark built from real agent-issued queries
- `benchmarks/entireio_cli_planner_public40/`
  - planner-focused benchmark derived from the saved public runs
