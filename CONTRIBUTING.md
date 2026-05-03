# Contributing to pgr

Thank you for your interest in contributing to `pgr`.

This repository is intentionally small and public-facing. It contains the Rust MCP server, a minimal evaluation harness, and the benchmark and data artifacts referenced in the writeup. Contributions are welcome, and the fastest way to get something merged is to align with maintainers before writing code.

> New to the project? See the [README](README.md) for setup and usage documentation.

---

## Before You Code: Discuss First

Please open an issue before starting significant implementation work.

That is especially helpful for:

- new features
- changes to MCP tool behavior or output format
- benchmark methodology changes
- additions or removals under `public_release/`

Small documentation fixes, typo corrections, and narrowly scoped bug fixes can usually go straight to a pull request.

### Contribution Workflow

1. Open an issue describing the problem or proposal.
2. Wait for maintainer feedback if the change is substantial.
3. Get alignment before starting implementation.
4. Submit a PR that references the issue.
5. Address review feedback before merge.

---

## Good First Contributions

Good places to start:

- documentation improvements
- test additions or coverage improvements
- small bug fixes
- README examples and MCP setup clarifications

---

## Security

If you discover a security issue, do not open a public GitHub issue. Please follow the instructions in [SECURITY.md](SECURITY.md).

---

## Local Setup

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

---

## Repository Structure

- `src/`
  - Rust MCP server implementation
- `tests/`
  - integration tests for the MCP surface
- `eval/v2/`
  - minimal harness and backend adapters used by the public benchmark runners
- `public_release/`
  - public datasets, benchmark definitions, summaries, and saved results

---

## Code Style

Please keep changes simple, explicit, and easy to audit.

For Rust code:

- prefer small, readable functions over clever abstractions
- preserve the stateless stdio MCP model unless there is a strong reason not to
- keep tool behavior deterministic where practical
- keep tool output readable by both humans and models

---

## Testing and Validation

If you change behavior in `src/`, add or update tests when practical.

At minimum:

- run `cargo test`
- verify the MCP surface still initializes and lists tools correctly

If your change affects benchmark runners or public summaries, say clearly whether you:

- changed only documentation or labeling
- changed harness behavior
- regenerated benchmark outputs

---

## Public Benchmark Artifacts

Please be deliberate when editing files under `public_release/`.

These files are stable public artifacts referenced by external writing. If you change them:

- explain why in the PR description
- avoid unnecessary churn in generated files
- keep public links and package names stable unless there is a strong reason to change them

---

## Submitting a Pull Request

Before you submit:

- the scope is aligned for substantial changes
- `cargo test` passes
- `cargo fmt` has been run if needed
- new behavior is covered by tests when practical

When opening a PR, include:

- what changed
- why it changed
- how you tested it
- whether any public benchmark or dataset artifacts were modified

If the change affects MCP behavior, it is especially helpful to mention:

- which tool changed
- whether parameters changed
- whether output format changed

---

## License

By contributing to this repository, you agree that your contributions will be licensed under the same license as the project.
