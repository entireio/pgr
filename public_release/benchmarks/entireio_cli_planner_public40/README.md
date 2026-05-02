# entireio/cli Public Planner Benchmark

This package builds a planner-focused benchmark from the saved public `entireio/cli`
60-task runs across four conditions:

- `baseline`
- `fff`
- `rg_ranked`
- `pgr_v4`

It does not rerun the model. Instead, it derives planner-local metrics from the saved
end-to-end traces in:

- `../entireio_cli_ranking_public60/full60/results`

And it uses the saved first-search offline replay results as a weak relevance signal:

- `../entireio_cli_offline_ir_public60/first_search/results.json`

The benchmark selects a fixed 40-task planner pool:

- `recovery`: baseline first search was a no-match and the agent searched again before the first read
- `decision`: baseline first search already had a weak relevant hit (`MRR > 0`) and the agent still searched again before the first read
- `neutral`: remaining tasks filled by search pressure score

Generated outputs:

- `design.json`
- `summary.json`
- `SUMMARY.md`

Rebuild with:

```bash
python3 public_release/benchmarks/entireio_cli_planner_public40/compute_planner_benchmark.py
```
