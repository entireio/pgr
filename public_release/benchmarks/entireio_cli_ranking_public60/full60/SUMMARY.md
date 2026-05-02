# entireio_cli_ranking_public60

This benchmark compares raw `ripgrep` against ranked-search variants on a public, trace-derived `entireio/cli` prompt suite.

## Setup

- Tasks: 60
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
- `repo_task`

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
| Avg wall clock per run | 34.98s | 34.97s | 36.32s | 33.67s |
| Avg tool calls | 18.45 | 18.72 | 18.65 | 18.90 |
| Avg cost per run | $0.4030 | $0.3797 | $0.5317 | $0.3698 |
| Avg search calls | 6.12 | 5.70 | 5.72 | 5.53 |
| Avg read calls | 8.55 | 9.60 | 9.50 | 9.98 |
| Avg output chars | 54762 | 51676 | 68459 | 47380 |
| Avg search_code duration | 16.3ms | 28.2ms | 17.7ms | 14.1ms |
| Median search_code duration | 16.0ms | 17.3ms | 16.1ms | 13.2ms |

## Paired Differences Vs Baseline

### `fff` vs `baseline`
- `total_tool_calls`: 0.27
- `total_cost_usd`: $-0.0233
- `search_call_count`: -0.42
- `wall_clock_ms`: -0.01s

### `rg_ranked` vs `baseline`
- `total_tool_calls`: 0.20
- `total_cost_usd`: $0.1287
- `search_call_count`: -0.40
- `wall_clock_ms`: 1.33s

### `pgr_v4` vs `baseline`
- `total_tool_calls`: 0.45
- `total_cost_usd`: $-0.0332
- `search_call_count`: -0.58
- `wall_clock_ms`: -1.31s
