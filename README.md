![pgr repository cover](assets/gh-repo-cover.png)

# pgr

`pgr` is a stateless MCP code-search server for coding agents.

It wraps local code search with ranking and output shaping designed for agent
workflows: surfacing likely implementation files earlier, de-prioritizing tests
and low-value matches, and formatting results so a model can decide what to read
next with less thrashing.

This repository also includes the public datasets, benchmark packages, and saved
results used in the accompanying writeup on agentic code search.

- [Quick Start](#quick-start)
- [Usage Documentation](#usage-documentation)
- [Public Benchmarks and Data](#public-benchmarks-and-data)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [License](LICENSE)

## Quick Start

### 1. Install pgr

Install `pgr` from this repository:

```bash
git clone https://github.com/entireio/pgr.git
cd pgr
cargo install --path .
```

### 2. Add it to your MCP client

Then add it to any MCP client that can launch a stdio server:

```json
{
  "mcpServers": {
    "pgr": {
      "command": "pgr",
      "cwd": "/absolute/path/to/repo"
    }
  }
}
```

### 3. Point it at the repo to search

Set `cwd` to the repository you want your agent to search. `pgr` searches the
current working directory of the process that launches it.

### 4. Ask your agent to search

Once configured, ask your agent to search the repo. For example:

```text
search for where checkpoint commits are written
```

```text
find the code that handles MCP tool calls
```

If `pgr` is not yet on your shell `PATH` after install, use the binary directly
at:

```bash
~/.cargo/bin/pgr
```

## What pgr gives agents

`pgr` is not trying to replace `ripgrep`. It shells out to local `rg` for fast
content search and file listing, then ranks and shapes the results for coding
agents.

That means an agent is more likely to see implementation files before test
noise, repeated references, or lower-signal matches.

At a high level it provides tools for:

- `search_code`
- `read_code`
- `find_files`
- `list_dir`

The search output profile is controlled with `PGR_OUTPUT_PROFILE`. If it is
unset, the server defaults to the richer planner-oriented output profile used in
the public results.

There is no index to build, no background daemon, and no separate storage layer.
`pgr` starts, answers MCP tool calls over stdio, and exits when the client stops
it.

## Build from source

```bash
cargo build --release
```

The binary will be available at `target/release/pgr`.

If you want the binary on your `PATH`, you can also install it locally with:

```bash
cargo install --path .
```

For most first-time users, this is the easiest way to try `pgr`.

## Requirements

- Rust toolchain for building from source
- [`ripgrep`](https://github.com/BurntSushi/ripgrep) installed and available as
  `rg`

`pgr` shells out to local `rg` for both content search and file listing. If `rg`
is not installed, `pgr` will not be able to search.

## Why we built it

`pgr` is built around a simple idea: faster search alone is not enough. What
matters just as much is whether the search result helps the model choose a
better next action.

In the public benchmarks in this repository, the strongest effects did not come
from raw scan speed. They showed up in more local agent behavior:

- better first-query retrieval quality
- fewer redundant search loops before the first code read
- getting the agent into reading relevant files sooner

That is the problem `pgr` is designed to improve.

## Usage Documentation

- [docs/usage.md](docs/usage.md) - MCP setup, direct stdio smoke test, tool
  arguments, and output profiles

## Public benchmarks and data

The public artifacts referenced in the writeup live under
[`public_release/`](public_release/README.md).

Key packages:

- [`public_release/data/entireio_cli_checkpoints_2026_04_15/README.md`](public_release/data/entireio_cli_checkpoints_2026_04_15/README.md)
  - public `entireio/cli` checkpoint export used for the trace analysis
- [`public_release/benchmarks/entireio_cli_fff_vs_baseline_public60/README.md`](public_release/benchmarks/entireio_cli_fff_vs_baseline_public60/README.md)
  - speed-oriented benchmark comparing `ripgrep` and `fff`
- [`public_release/benchmarks/entireio_cli_ranking_public60/README.md`](public_release/benchmarks/entireio_cli_ranking_public60/README.md)
  - broad mixed-workload benchmark comparing `baseline`, `fff`, and `pgr`
- [`public_release/benchmarks/entireio_cli_offline_ir_public60/README.md`](public_release/benchmarks/entireio_cli_offline_ir_public60/README.md)
  - offline retrieval replay benchmark built from real agent-issued queries

## What is in this repo

- `src/`
  - the Rust MCP server
- `tests/`
  - integration tests for the MCP surface
- `eval/v2/`
  - the minimal evaluation harness and backend adapters used by the public
    benchmark runners
- `public_release/`
  - public datasets, benchmark definitions, summaries, and saved outputs
    referenced in the blog post

## Repository scope

This public repository is intentionally focused on:

- the Rust MCP search server
- the minimal benchmark harness needed by the public runners
- the public data and results packages cited in the writeup

Older internal drafts, duplicate exports, and superseded experimental outputs
have been removed so the repo stays small, inspectable, and externally
understandable.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [LICENSE](LICENSE).
