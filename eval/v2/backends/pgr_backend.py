"""pgr backend: uses pgr binary with --json for structured data.

Implements the 4 tools using pgr's indexed search.
All calls use subprocess with programmatic arg lists — no shell construction.
Output is normalized to the same format as the baseline backend.
"""

import json
import os
import subprocess
from pathlib import Path

DEFAULT_PGR_BIN = Path(__file__).resolve().parents[3] / "target" / "release" / "pgr"
PGR_BIN = os.environ.get("PGR_BIN", str(DEFAULT_PGR_BIN))


def _run_pgr(args: list[str], cwd: str, timeout: int = 10) -> str:
    """Run pgr with programmatic args. No shell."""
    cmd = [PGR_BIN] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.stdout
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""


def search_code(
    repo_root: str,
    query: str,
    path_glob: str = "",
    file_type: str = "",
    max_files: int = 10,
    max_matches_per_file: int = 3,
    context_before: int = 2,
    context_after: int = 2,
) -> str:
    """Search using pgr's indexed search, flat JSON grouped in Python.

    NOTE: pgr --group-by-file has a ranking bug that drops results.
    We use flat --json output and group by file ourselves.
    """
    args = [query, "--json"]

    # NOTE: pgr -C (context lines) has a bug that drops results.
    # Skip context — the agent can use read_code for surrounding lines.
    if path_glob:
        args.extend(["-g", path_glob])
    if file_type:
        args.extend(["-t", file_type])
    args.extend(["--max-results", str(max_files * max_matches_per_file * 10)])

    raw = _run_pgr(args, cwd=repo_root)
    if not raw.strip():
        return "No matches found."

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip() if raw.strip() else "No matches found."

    if not data:
        return "No matches found."

    # Flat JSON: list of {path, line, col, content, score, kind}
    # Group by file, preserving score-based order
    from collections import OrderedDict
    file_matches = OrderedDict()
    for match in data:
        path = match.get("path", "")
        if path not in file_matches:
            file_matches[path] = []
        file_matches[path].append(match)

    output_lines = []
    files_shown = 0

    for filepath, matches in file_matches.items():
        if files_shown >= max_files:
            output_lines.append(f"\n(truncated to top {max_files} files)")
            break

        output_lines.append(f"\n{filepath}")

        snippets_shown = 0
        for match in matches:
            if snippets_shown >= max_matches_per_file:
                break

            line_num = match.get("line", 0)
            content = match.get("content", "")

            # With context, content may span multiple lines
            content_lines = content.splitlines()
            start_line = max(1, line_num - context_before)
            end_line = start_line + len(content_lines) - 1

            output_lines.append(f"  {start_line}-{end_line}:")
            for i, line in enumerate(content_lines):
                output_lines.append(f"    {start_line + i}| {line}")
            snippets_shown += 1

        files_shown += 1

    result = "\n".join(output_lines).strip()
    return result if result else "No matches found."


def read_code(
    repo_root: str,
    path: str,
    start_line: int = 1,
    end_line: int = 0,
    max_lines: int = 80,
) -> str:
    """Read file using pgr --cat (suffix match + index lookup)."""
    args = ["--cat", path]

    start = max(1, start_line)
    args.extend(["--offset", str(start)])

    if end_line > 0:
        limit = end_line - start + 1
    else:
        limit = max_lines
    args.extend(["--limit", str(limit)])

    raw = _run_pgr(args, cwd=repo_root)
    if not raw.strip():
        # Try filesystem fallback
        return _read_filesystem(repo_root, path, start, end_line, max_lines)

    # Normalize output: pgr --cat outputs "  N\tcontent" lines
    lines = raw.splitlines()
    if not lines:
        return f"File not found: {path}"

    # Re-format to standard "  N| content"
    content_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            content_lines.append("")
            continue
        # pgr format: "  123\tcontent" — split on first tab
        parts = stripped.split("\t", 1)
        if len(parts) == 2 and parts[0].strip().isdigit():
            lineno = parts[0].strip()
            content = parts[1]
            content_lines.append(f"  {lineno}| {content}")
        else:
            content_lines.append(f"  {stripped}")

    actual_end = start + len(content_lines) - 1
    header = f"{path}:{start}-{actual_end}"
    return header + "\n" + "\n".join(content_lines)


def find_files(
    repo_root: str,
    pattern: str = "",
    glob: str = "",
    file_type: str = "",
    max_results: int = 50,
) -> str:
    """Find files using pgr's path index."""
    if pattern:
        # Use pgr -f for file search
        args = ["-f", pattern]
        if file_type:
            args.extend(["-t", file_type])
        if glob:
            args.extend(["-g", glob])
        args.extend(["--max-results", str(max_results)])
    elif glob or file_type:
        # Use pgr --files with filters
        args = ["--files"]
        if file_type:
            args.extend(["-t", file_type])
        if glob:
            args.extend(["-g", glob])
    else:
        args = ["--files"]

    raw = _run_pgr(args, cwd=repo_root)
    if not raw.strip():
        return "No files found."

    paths = [p.strip() for p in raw.strip().splitlines() if p.strip()]
    paths.sort()

    if len(paths) > max_results:
        paths = paths[:max_results]
        paths.append(f"(truncated to {max_results} results)")

    return "\n".join(paths) if paths else "No files found."


def list_dir(
    repo_root: str,
    path: str = ".",
    recursive: bool = False,
    max_results: int = 100,
) -> str:
    """List directory using pgr's file index filtered by prefix."""
    if path == ".":
        prefix = None
    else:
        prefix = path.rstrip("/") + "/"

    args = ["--files"]
    if prefix:
        args.extend(["--prefix", prefix])

    raw = _run_pgr(args, cwd=repo_root)
    if not raw.strip():
        # Fallback to filesystem
        return _list_dir_fs(repo_root, path, recursive, max_results)

    all_paths = [p.strip() for p in raw.strip().splitlines() if p.strip()]

    if not recursive and prefix:
        # Filter to immediate children only
        entries = set()
        for p in all_paths:
            # Remove prefix to get relative path
            rel = p[len(prefix):] if p.startswith(prefix) else p
            # Take only the first component
            parts = rel.split("/", 1)
            if len(parts) == 1:
                entries.add(parts[0])
            else:
                entries.add(parts[0] + "/")
    elif not recursive:
        entries = set()
        for p in all_paths:
            parts = p.split("/", 1)
            if len(parts) == 1:
                entries.add(parts[0])
            else:
                entries.add(parts[0] + "/")
    else:
        entries = set(all_paths)

    sorted_entries = sorted(entries)
    if len(sorted_entries) > max_results:
        sorted_entries = sorted_entries[:max_results]
        sorted_entries.append(f"(truncated to {max_results} entries)")

    return "\n".join(sorted_entries) if sorted_entries else "(empty directory)"


def _read_filesystem(repo_root: str, path: str, start: int, end_line: int, max_lines: int) -> str:
    """Fallback file read from filesystem."""
    full_path = os.path.join(repo_root, path)
    if not os.path.isfile(full_path):
        return f"File not found: {path}"
    try:
        with open(full_path, "r", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading file: {e}"

    total = len(lines)
    s = max(1, start) - 1
    if end_line > 0:
        e = min(end_line, total)
    else:
        e = min(s + max_lines, total)

    output = [f"{path}:{s+1}-{e}"]
    for i, line in enumerate(lines[s:e]):
        output.append(f"  {s+1+i}| {line.rstrip()}")
    return "\n".join(output)


def _list_dir_fs(repo_root: str, path: str, recursive: bool, max_results: int) -> str:
    """Fallback directory listing from filesystem."""
    target = os.path.join(repo_root, path)
    if not os.path.isdir(target):
        return f"Not a directory: {path}"
    try:
        raw = sorted(os.listdir(target))
        entries = []
        for e in raw:
            full = os.path.join(target, e)
            if os.path.isdir(full):
                entries.append(e + "/")
            else:
                entries.append(e)
        if len(entries) > max_results:
            entries = entries[:max_results]
            entries.append(f"(truncated to {max_results} entries)")
        return "\n".join(entries) if entries else "(empty directory)"
    except Exception as e:
        return f"Error: {e}"
