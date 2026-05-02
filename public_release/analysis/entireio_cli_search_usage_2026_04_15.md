# entireio/cli search usage analysis

Generated from the public checkpoint transcript export for `entireio/cli`.

Source data:
- `../data/entireio_cli_checkpoints_2026_04_15/checkpoint_transcripts.jsonl.gz`
- `../data/entireio_cli_checkpoints_2026_04_15/summary.json`

## Top-line counts

- Total checkpoints: `2,182`
- Transcript-backed checkpoints: `1,983`
- Distinct sessions with transcripts: `766`
- Total tool calls analyzed: `202,142`
- Search-related tool calls: `98,555` (`48.8%` of all tool calls)

## Search-related tool calls

| Category | Count | Percentage |
|---|---:|---:|
| Read / file retrieval | 48,322 | 49.0% |
| Bash search fallback | 23,180 | 23.5% |
| Grep / content search | 23,136 | 23.5% |
| Agent search | 2,086 | 2.1% |
| Glob / file search | 1,831 | 1.9% |

The three dominant search-related categories are still read/file retrieval, bash search fallback, and grep/content search. Together they account for `95.9%` of all search-related tool calls in the public `entireio/cli` dataset.

## Blog-ready replacement text

Here is a direct public-data replacement for the original opening stats section:

- **Total transcript-backed checkpoints analyzed:** `1,983`
- **Total tool calls analyzed:** `202,142`
- **Search-related tool calls:** `98,555` (`48.8%` of all tool calls)

Within search-related tool calls:

| Category | Count | Percentage |
|---|---:|---:|
| Read / file retrieval | 48,322 | 49.0% |
| Bash search fallback | 23,180 | 23.5% |
| Grep / content search | 23,136 | 23.5% |

If you want to preserve the original narrative shape, this public dataset supports the same top-line claim: search is a first-order part of coding-agent behavior, accounting for just under half of all tool calls.
