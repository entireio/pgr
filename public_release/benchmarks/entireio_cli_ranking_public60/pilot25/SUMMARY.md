# entireio_cli_ranking_public25_pilot

This benchmark compares raw `ripgrep` against ranked-search variants on a public, trace-derived `entireio/cli` prompt suite.

## Setup

- Tasks: 25
- Repeats per condition: 1
- Conditions: `baseline`, `fff`, `rg_ranked`, `pgr_v4`
- Model: `claude-sonnet-4-6`
- Max turns: 12
- Repo: `entireio/cli`
- Repo root: `/tmp/pgr-eval/repos/entireio-cli`

## Prompt categories

- `code_understanding`
- `debug_or_validation`
- `implementation`

## Example tasks

- `eb5cdbdef570` (code_understanding): what's wrong with `entire explain`?
- `897eb280e769` (implementation): Can you read docs/architecture/shadow-branch-suffixes.md, I'd like to modify this approach: I don't think we need suffixes but instead we just use one branch, is there overlap in f
- `5eec47c03756` (debug_or_validation): The handling of trees via go-git seem to not be working effectively and erroring early, as not all objects are present. This is the current error:
- `61de2c90668f` (debug_or_validation): I think it's better to use `env.InitRepo()` instead of `git.PlainInit()` in tests.
- `37f449ec7d97` (code_understanding): how does auth work for codex with e2e
- `ea384d108347` (code_understanding): What does the nolint:ireturn linter rule refer to?
- `a70d97c363c8` (implementation): Improve the documentation so that it covers the signing of checkpoint commits. For this to work:
- `1d44b085fc12` (implementation): find parts which are talking to the entire API via HTTP - add a global request handler to use the bearer token obtained via the cli login flow

## Overall

| Metric | baseline | fff | rg_ranked | pgr_v4 |
|---|---:|---:|---:|---:|
| Avg wall clock per run | 38.21s | 36.25s | 36.15s | 36.88s |
| Avg tool calls | 20.20 | 20.00 | 20.24 | 20.92 |
| Avg cost per run | $0.5581 | $0.4161 | $0.4890 | $0.4824 |
| Avg search calls | 8.04 | 7.64 | 6.92 | 6.56 |
| Avg read calls | 8.44 | 8.88 | 10.04 | 11.12 |
| Avg output chars | 61836 | 51493 | 66371 | 61219 |
| Avg search_code duration | 16.9ms | 11.6ms | 18.3ms | 14.6ms |
| Median search_code duration | 16.2ms | 1.4ms | 15.9ms | 13.4ms |

## Paired Differences Vs Baseline

### `fff` vs `baseline`
- `total_tool_calls`: -0.20
- `total_cost_usd`: $-0.1420
- `search_call_count`: -0.40
- `wall_clock_ms`: -1.96s

### `rg_ranked` vs `baseline`
- `total_tool_calls`: 0.04
- `total_cost_usd`: $-0.0690
- `search_call_count`: -1.12
- `wall_clock_ms`: -2.06s

### `pgr_v4` vs `baseline`
- `total_tool_calls`: 0.72
- `total_cost_usd`: $-0.0757
- `search_call_count`: -1.48
- `wall_clock_ms`: -1.32s
