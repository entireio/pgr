"""Baseline backend: rg, cat, find, ls.

Implements the 4 tools using conventional CLI tools (ripgrep, cat, find).
No shell construction — all calls use subprocess with programmatic arg lists.
"""

import os
import subprocess
from pathlib import Path
from collections import defaultdict


def _run(cmd: list[str], cwd: str, timeout: int = 10) -> str:
    """Run a command with programmatic args. No shell."""
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
    """Search using ripgrep, then format as grouped output."""
    args = ["rg", "--no-heading", "--line-number", "--with-filename"]

    if context_before > 0:
        args.extend(["-B", str(context_before)])
    if context_after > 0:
        args.extend(["-A", str(context_after)])
    if path_glob:
        args.extend(["--glob", path_glob])
    if file_type:
        args.extend(["--type", file_type])

    # Cap total output
    args.extend(["--max-count", str(max_matches_per_file * 2)])
    args.append("--")  # separator: everything after is pattern/path
    args.append(query)
    args.append(".")  # explicit path — rg reads stdin without it in some environments

    raw = _run(args, cwd=repo_root)
    if not raw.strip():
        return "No matches found."

    # Parse rg output and group by file
    groups = defaultdict(list)
    file_order = []
    current_file = None

    for line in raw.splitlines():
        if not line.strip() or line == "--":
            continue

        # rg format: file:line:content or file-line-content (context)
        parts = line.split(":", 2) if ":" in line else line.split("-", 2)
        if len(parts) >= 3:
            filepath = parts[0]
            try:
                lineno = int(parts[1])
            except ValueError:
                continue
            content = parts[2]

            if filepath not in groups:
                file_order.append(filepath)
            groups[filepath].append((lineno, content))

    if not groups:
        return "No matches found."

    # Format grouped output, capped
    output_lines = []
    files_shown = 0
    for filepath in file_order:
        if files_shown >= max_files:
            output_lines.append(f"\n(truncated to top {max_files} files)")
            break

        matches = groups[filepath][:max_matches_per_file * 5]  # include context lines
        output_lines.append(f"\n{filepath}")

        # Group consecutive lines into snippet windows
        snippets_shown = 0
        i = 0
        while i < len(matches) and snippets_shown < max_matches_per_file:
            start_line = matches[i][0]
            snippet = []
            while i < len(matches) and (not snippet or matches[i][0] <= snippet[-1][0] + 1):
                snippet.append(matches[i])
                i += 1
            end_line = snippet[-1][0]
            output_lines.append(f"  {start_line}-{end_line}:")
            for lineno, content in snippet:
                output_lines.append(f"    {lineno}| {content}")
            snippets_shown += 1

        files_shown += 1

    return "\n".join(output_lines).strip()


def read_code(
    repo_root: str,
    path: str,
    start_line: int = 1,
    end_line: int = 0,
    max_lines: int = 80,
) -> str:
    """Read a file section using cat/filesystem."""
    # Resolve path — try exact, then search
    full_path = os.path.join(repo_root, path)
    if not os.path.isfile(full_path):
        # Try suffix match
        found = _find_by_suffix(repo_root, path)
        if found:
            full_path = os.path.join(repo_root, found)
            path = found
        else:
            return f"File not found: {path}"

    try:
        with open(full_path, "r", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading file: {e}"

    total = len(lines)
    start = max(1, start_line) - 1  # 0-based
    if end_line > 0:
        end = min(end_line, total)
    else:
        end = min(start + max_lines, total)

    if start >= total:
        return f"{path}: file has {total} lines, start_line={start_line} is past end."

    selected = lines[start:end]

    output = [f"{path}:{start+1}-{end}"]
    for i, line in enumerate(selected):
        lineno = start + 1 + i
        output.append(f"  {lineno}| {line.rstrip()}")

    if end < total:
        output.append(f"  ({total - end} more lines)")

    return "\n".join(output)


def find_files(
    repo_root: str,
    pattern: str = "",
    glob: str = "",
    file_type: str = "",
    max_results: int = 50,
) -> str:
    """Find files using find/rg --files."""
    args = ["rg", "--files", "."]
    if glob:
        args.extend(["--glob", glob])
    if file_type:
        args.extend(["--type", file_type])

    raw = _run(args, cwd=repo_root)
    if not raw.strip():
        return "No files found."

    paths = raw.strip().splitlines()

    # Filter by pattern if provided
    if pattern:
        pattern_lower = pattern.lower()
        paths = [p for p in paths if pattern_lower in p.lower()]

    paths.sort()
    if len(paths) > max_results:
        paths = paths[:max_results]
        paths.append(f"(truncated to {max_results} results)")

    if not paths:
        return "No files found."

    return "\n".join(paths)


def list_dir(
    repo_root: str,
    path: str = ".",
    recursive: bool = False,
    max_results: int = 100,
) -> str:
    """List directory contents."""
    target = os.path.join(repo_root, path)
    if not os.path.isdir(target):
        return f"Not a directory: {path}"

    try:
        if recursive:
            entries = []
            for root, dirs, files in os.walk(target):
                # Skip hidden/vendor dirs
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                           ("node_modules", "vendor", "target", "__pycache__", ".git")]
                rel = os.path.relpath(root, target)
                for f in sorted(files):
                    if rel == ".":
                        entries.append(f)
                    else:
                        entries.append(os.path.join(rel, f))
                    if len(entries) >= max_results:
                        break
                if len(entries) >= max_results:
                    break
        else:
            raw_entries = sorted(os.listdir(target))
            entries = []
            for e in raw_entries:
                full = os.path.join(target, e)
                if os.path.isdir(full):
                    entries.append(e + "/")
                else:
                    entries.append(e)
    except Exception as e:
        return f"Error listing directory: {e}"

    if not entries:
        return "(empty directory)"

    if len(entries) > max_results:
        entries = entries[:max_results]
        entries.append(f"(truncated to {max_results} entries)")

    return "\n".join(entries)


def _find_by_suffix(repo_root: str, suffix: str):
    """Find a file by suffix match (walk the tree)."""
    suffix_lower = suffix.lower()
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                   ("node_modules", "vendor", "target", "__pycache__", ".git")]
        for f in files:
            full = os.path.relpath(os.path.join(root, f), repo_root)
            if full.lower().endswith(suffix_lower):
                return full
    return None
