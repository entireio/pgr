# Usage

This guide covers day-to-day `pgr` usage: MCP client setup, direct stdio smoke
testing, tool arguments, and output profiles.

For a faster first run, start with the repository [README](../README.md).

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

If you want to use the compiled release binary directly, it will usually look
like:

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
  | ~/.cargo/bin/pgr
```

That will:

- initialize the server
- list the exposed MCP tools
- run a `search_code` call against the current repository

If `pgr` is already on your `PATH`, you can replace `~/.cargo/bin/pgr` with
just:

```bash
pgr
```

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

- if the exact path does not exist, `pgr` falls back to suffix matching within
  the current repo
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
