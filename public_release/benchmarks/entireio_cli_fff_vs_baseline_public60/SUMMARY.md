# Baseline vs fff on Public entireio/cli Search-Sensitive 60

This benchmark reruns the "faster search is not the bottleneck" comparison on a trace-derived public task set from `entireio/cli`.

## Setup

- Tasks: 60
- Repeats per condition: 1
- Conditions: `baseline` (raw ripgrep) vs `fff`
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

| Metric | Baseline | fff |
|---|---:|---:|
| Avg wall clock per run | 38.57s | 36.99s |
| Avg tool calls | 19.12 | 17.90 |
| Avg total tool execution time per run | 0.140s | 0.055s |
| Tool execution share of wall clock | 0.4% | 0.1% |
| Avg `search_code` duration | 15.5ms | 5.7ms |
| Median `search_code` duration | 14.7ms | 1.7ms |

## Interpretation

This public rerun uses a larger, trace-derived task set than the earlier 40-task benchmark, but the core pattern is the same: raw search latency is a tiny slice of end-to-end agent time.

- `fff` drove median `search_code` latency from 14.7ms to 1.7ms
- but end-to-end wall clock moved from 38.57s to 36.99s
