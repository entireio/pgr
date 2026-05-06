# Contributing to pgr

Thanks for helping improve `pgr`.

This repository is intentionally small and public-facing. `pgr` is a working
prototype and public research artifact, not a polished product. The repo
contains the experimental, stateless Rust MCP server, a minimal evaluation
harness, and the benchmark and data artifacts referenced in the writeup.

New to the project? Start with the [README](README.md). For MCP setup, direct
stdio smoke testing, tool arguments, and output profiles, see
[docs/usage.md](docs/usage.md).

## Before you start

Fork the repo:

1. Click [**Fork**](https://github.com/entireio/pgr/fork).
2. Clone your fork:

```bash
git clone https://github.com/YOUR-USERNAME/pgr.git
cd pgr
```

Create a descriptive branch from `main`:

```bash
git checkout main
git pull origin main
git checkout -b improve-search-ranking
```

Please open an issue before starting changes that affect public behavior or
public research artifacts.

That includes:

- adding a new MCP tool
- changing an existing tool's arguments, behavior, or output format
- changing how benchmarks are run or measured
- adding, removing, or regenerating files under `public_release/`

Small documentation fixes, typo corrections, and narrowly scoped bug fixes can
usually go straight to a pull request.

## Good first contributions

Good places to start:

- documentation improvements
- README examples and MCP setup clarifications
- test additions or coverage improvements
- small bug fixes

## Local setup

### Prerequisites

- Rust toolchain
- [`ripgrep`](https://github.com/BurntSushi/ripgrep) installed as `rg`

### Build

```bash
cargo build --release
```

### Test

```bash
cargo test
```

If you are changing formatting-sensitive Rust code, please also run:

```bash
cargo fmt
```

## Repository structure

- `src/`
  - Rust MCP server implementation
- `tests/`
  - integration tests for the MCP surface
- `eval/v2/`
  - minimal harness and backend adapters used by the public benchmark runners
- `public_release/`
  - public datasets, benchmark definitions, summaries, and saved results
- `docs/`
  - usage documentation for MCP setup, smoke tests, tools, and output profiles

## Changing MCP behavior

If you change an MCP tool, keep the PR focused and explain the behavior change
clearly.

In the PR description, mention:

- which tool changed
- whether parameters changed
- whether output format changed
- whether existing clients need to update anything

When practical, add or update tests for behavior changes in `src/` and
`tests/`.

At minimum, verify that the MCP surface still initializes and lists tools. The
direct stdio smoke test in [docs/usage.md](docs/usage.md#try-it-directly) is a
good starting point.

## Changing docs only

For Markdown-only changes, read the rendered Markdown or preview it in GitHub
before submitting.

Also check for whitespace issues:

```bash
git diff --check README.md CONTRIBUTING.md docs/usage.md
```

If you add more docs, include them in the command or run:

```bash
git diff --check
```

## Public benchmark artifacts

Please be deliberate when editing files under `public_release/`.

These files are stable public artifacts referenced by external writing. If you
change them:

- explain why in the PR description
- say whether you changed documentation, harness behavior, or generated outputs
- avoid unnecessary churn in generated files
- keep public links and package names stable unless there is a strong reason to
  change them

## Style

Please keep changes simple, explicit, and easy to audit.

For Rust code:

- prefer small, readable functions over clever abstractions
- preserve the stateless stdio MCP model unless there is a strong reason not to
- keep tool behavior deterministic where practical
- keep tool output readable by both humans and models

For docs and examples:

- use exact commands when setup depends on a command
- keep examples generic unless a specific repo or benchmark package is required
- avoid private paths, local agent state, logs, and machine-specific config

## Pull requests

Push your branch:

```bash
git push origin improve-search-ranking
```

Open a pull request against `entireio/pgr` and include:

- what changed
- why it changed
- how you tested it
- whether any MCP behavior changed
- whether any public benchmark or dataset artifacts were modified

Before submitting, make sure:

- the scope is aligned for substantial changes
- `cargo test` passes for Rust behavior changes
- `cargo fmt` has been run if needed
- docs-only changes have been previewed or read back
- new behavior is covered by tests when practical

## Security

If you discover a security issue, do not open a public GitHub issue. Please
follow the instructions in [SECURITY.md](SECURITY.md).

## License

By contributing to this repository, you agree that your contributions will be
licensed under the same license as the project.
