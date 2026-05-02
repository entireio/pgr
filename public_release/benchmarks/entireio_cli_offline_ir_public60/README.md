# entireio_cli_offline_ir_public60

Public offline retrieval benchmark built from the public `entireio/cli` checkpoint-derived benchmark runs.

This benchmark replays real `search_code` queries from the baseline condition of:

- `../entireio_cli_ranking_public60/full60/results/baseline`

against three backends:

- `baseline`
- `fff`
- `rg_ranked`
- `pgr_v4`

## Label source

The original private study used hand-labeled relevant files. For this public release, relevance is approximated with a weak but fully public signal: the unique files the baseline agent actually opened with `read_code` in that run.

This means the benchmark answers a slightly different question:

> Given the same search query, does a backend rank near the top the files the baseline agent ultimately chose to inspect?

## Subsets

### `first_search`

- First `search_code` query from each run that also had at least one `read_code`
- Cases: `50`
- Results: `first_search/results.json`
- Summary: `first_search/SUMMARY.md`

### `pre_read`

- Every `search_code` query before the first `read_code` in a run
- Cases: `132`
- Results: `pre_read/results.json`
- Summary: `pre_read/SUMMARY.md`

## Runner

- `run_offline_ir.py`

Example:

```bash
python3 public_release/benchmarks/entireio_cli_offline_ir_public60/run_offline_ir.py \
  --subset first_search \
  --out-dir /tmp/entireio_cli_offline_ir_first_search
```
