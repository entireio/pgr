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

If you want the binary on your `PATH`, you can also install it locally with:

```bash
cargo install --path .
```

## Running `pgr`

`pgr` is designed to run as an MCP server over stdio.

At a high level it provides tools for:

- `search_code`
- `read_code`
- `find_files`
- `list_dir`

The search output profile is controlled with `PGR_OUTPUT_PROFILE`. If it is unset, the server defaults to the richer planner-oriented output profile used in the public results.

## Requirements

- Rust toolchain for building from source
- [`ripgrep`](https://github.com/BurntSushi/ripgrep) installed and available as `rg`

`pgr` shells out to local `rg` for both content search and file listing. If `rg` is not installed, `pgr` will not be able to search.

## How to use it

The most important thing to know is that `pgr` searches the **current working directory** of the process that launches it.

That means:

- start `pgr` from the repository you want to search, or
- configure your MCP client to launch `pgr` with that repository as its working directory

There is no index to build, no background daemon, and no separate storage layer. `pgr` just starts, answers MCP tool calls over stdio, and exits when the client stops it.

## MCP client setup

Any MCP client that can launch a stdio server can use `pgr`.

A generic configuration looks like this:

```json
{
  "mcpServers": {
    "pgr": {
      "command": "/absolute/path/to/pgr",
      "args": [],
      "cwd": "/absolute/path/to/repo",
      "env": {
        "PGR_OUTPUT_PROFILE": "full_v4"
      }
    }
  }
}
```

If you have already run `cargo install --path .`, `command` can just be `pgr`.

If you want to use the compiled release binary directly, it will usually look like:

```json
{
  "mcpServers": {
    "pgr": {
      "command": "/absolute/path/to/target/release/pgr",
      "cwd": "/absolute/path/to/repo"
    }
  }
}
```

## Try it directly

You can smoke-test `pgr` without a full MCP client by talking to it over stdio.

From the repository you want to search:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_code","arguments":{"query":"fn main","max_files":3}}}' \
  | /absolute/path/to/pgr
```

That will:

- initialize the server
- list the exposed MCP tools
- run a `search_code` call against the current repository

## Tool reference

`pgr` exposes four MCP tools.

### `search_code`

Searches file contents with `ripgrep`, then ranks the results for agent use.

Arguments:

- `query` (required): regex or literal search string
- `path_glob`: optional glob filter such as `**/*.rs`
- `file_type`: optional ripgrep type such as `rust`, `py`, or `js`
- `max_files`: maximum files to return, default `10`
- `max_matches_per_file`: maximum matches per file, default `3`

Behavior:

- definitions are ranked ahead of plain references
- source files are ranked ahead of tests and lower-priority paths
- output is grouped by file and formatted for downstream tool-use decisions

Example:

```json
{
  "name": "search_code",
  "arguments": {
    "query": "CheckpointStore",
    "file_type": "rs",
    "max_files": 5
  }
}
```

### `read_code`

Reads a file with line numbers and optional range limits.

Arguments:

- `path` (required): exact path or suffix match
- `start_line`: default `1`
- `end_line`: default `0`, which means auto-size from `start_line`
- `max_lines`: default `80`

Notes:

- if the exact path does not exist, `pgr` falls back to suffix matching within the current repo
- output includes the resolved path and the returned line range

### `find_files`

Lists files using `rg --files` with optional filtering.

Arguments:

- `pattern`: case-insensitive substring filter
- `glob`: optional glob such as `**/*.ts`
- `file_type`: optional ripgrep type
- `max_results`: default `50`

### `list_dir`

Lists directory contents relative to the current repo.

Arguments:

- `path`: directory path, default `.`
- `recursive`: default `false`
- `max_results`: default `100`

## Output profiles

`pgr` supports a few output profiles through `PGR_OUTPUT_PROFILE`:

- `full_v4`: the default, richer planner-oriented output
- `v3`: a more minimal output format
- `empty_only`
- `summary_only`
- `counts_empty`

For most users, the default is the right starting point.

## Public benchmark packages

The public artifacts referenced in the writeup live under [`public_release/`](public_release/README.md).

Key packages:

- [`public_release/data/entireio_cli_checkpoints_2026_04_15/README.md`](public_release/data/entireio_cli_checkpoints_2026_04_15/README.md)
  - public `entireio/cli` checkpoint export used for the trace analysis
- [`public_release/benchmarks/entireio_cli_fff_vs_baseline_public60/README.md`](public_release/benchmarks/entireio_cli_fff_vs_baseline_public60/README.md)
  - speed-oriented benchmark comparing `ripgrep` and `fff`
- [`public_release/benchmarks/entireio_cli_ranking_public60/README.md`](public_release/benchmarks/entireio_cli_ranking_public60/README.md)
  - broad mixed-workload benchmark comparing `baseline`, `fff`, and `pgr`
- [`public_release/benchmarks/entireio_cli_offline_ir_public60/README.md`](public_release/benchmarks/entireio_cli_offline_ir_public60/README.md)
  - offline retrieval replay benchmark built from real agent-issued queries

## Repository scope

This public repository is intentionally focused on:

- the Rust MCP search server
- the minimal benchmark harness needed by the public runners
- the public data and results packages cited in the writeup

Older internal drafts, duplicate exports, and superseded experimental outputs have been removed so the repo stays small, inspectable, and externally understandable.
