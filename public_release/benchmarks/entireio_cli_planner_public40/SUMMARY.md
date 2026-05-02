# entireio/cli Public Planner Benchmark

This benchmark is derived from the saved public `entireio/cli` 60-task runs across four conditions.

## Design

- Selected tasks: `40`
- Cohorts: `recovery=7`, `decision=13`, `neutral=20`
- Conditions: `baseline`, `fff`, `rg_ranked`, `pgr_v4`
- Selection rule:
  - `recovery`: baseline first search was a no-match and the agent searched again before first read
  - `decision`: baseline first search already had a weak relevant hit (`MRR > 0`) and the agent still searched again before first read
  - `neutral`: remaining tasks filled by search pressure score

## Overall

| Metric | Baseline | `fff` | `rg_ranked` | `pgr_v4` |
|---|---:|---:|---:|---:|
| Total searches | 8.50 | 7.85 | 7.85 | 7.67 |
| Total tool calls | 20.75 | 20.98 | 20.85 | 21.45 |
| Total cost | $0.4071 | $0.3859 | $0.4734 | $0.3786 |
| Tool output tokens | 50.6k | 49.4k | 64.3k | 45.2k |
| Consecutive searches before first read | 3.10 | 2.05 | 2.48 | 2.52 |
| Wall clock | 36.74s | 36.50s | 37.89s | 36.73s |

## Paired vs baseline

### `fff`

- **consecutive_searches_before_first_read:** `-1.05`, 95% CI `[-1.79, -0.31]`
- **total_searches:** `-0.65`, 95% CI `[-1.90, +0.60]`
- **total_tool_calls:** `+0.23`, 95% CI `[-1.42, +1.87]`
- **total_cost_usd:** `-0.0212`, 95% CI `[-0.0636, +0.0212]`
- **wall_clock_ms:** `-0.24s`, 95% CI `[-4.59s, +4.11s]`

### `rg_ranked`

- **consecutive_searches_before_first_read:** `-0.62`, 95% CI `[-1.52, +0.27]`
- **total_searches:** `-0.65`, 95% CI `[-1.92, +0.62]`
- **total_tool_calls:** `+0.10`, 95% CI `[-1.10, +1.30]`
- **total_cost_usd:** `+0.0663`, 95% CI `[-0.1062, +0.2388]`
- **wall_clock_ms:** `+1.15s`, 95% CI `[-3.53s, +5.84s]`

### `pgr_v4`

- **consecutive_searches_before_first_read:** `-0.57`, 95% CI `[-1.17, +0.02]`
- **total_searches:** `-0.82`, 95% CI `[-2.19, +0.54]`
- **total_tool_calls:** `+0.70`, 95% CI `[-0.62, +2.02]`
- **total_cost_usd:** `-0.0285`, 95% CI `[-0.0772, +0.0202]`
- **wall_clock_ms:** `-0.01s`, 95% CI `[-3.65s, +3.63s]`

## By cohort

### `decision`

| Metric | Baseline | `fff` | `rg_ranked` | `pgr_v4` |
|---|---:|---:|---:|---:|
| Total searches | 7.15 | 7.00 | 7.23 | 7.31 |
| Total tool calls | 18.00 | 18.08 | 18.92 | 19.08 |
| Total cost | $0.4334 | $0.3621 | $0.3970 | $0.3352 |
| Consecutive searches before first read | 2.46 | 1.85 | 2.54 | 2.38 |

### `recovery`

| Metric | Baseline | `fff` | `rg_ranked` | `pgr_v4` |
|---|---:|---:|---:|---:|
| Total searches | 10.43 | 9.71 | 9.43 | 10.14 |
| Total tool calls | 19.86 | 22.57 | 19.57 | 23.43 |
| Total cost | $0.3357 | $0.3894 | $0.3489 | $0.3737 |
| Consecutive searches before first read | 5.57 | 3.14 | 3.43 | 5.00 |

### `neutral`

| Metric | Baseline | `fff` | `rg_ranked` | `pgr_v4` |
|---|---:|---:|---:|---:|
| Total searches | 8.70 | 7.75 | 7.70 | 7.05 |
| Total tool calls | 22.85 | 22.30 | 22.55 | 22.30 |
| Total cost | $0.4149 | $0.4001 | $0.5666 | $0.4085 |
| Consecutive searches before first read | 2.65 | 1.80 | 2.10 | 1.75 |
