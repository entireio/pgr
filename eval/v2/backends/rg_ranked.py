"""rg_ranked backend: rg + smart post-processing (no index).

Same search engine as baseline (ripgrep), but with:
- rg --json for structured output
- File priority ranking (source > test > example)
- Definition detection via regex heuristics
- Grouped output with ranked file ordering

Tests whether pgr's eval wins come from the index or from output quality.
"""

import json
import os
import re
import subprocess
from collections import defaultdict, OrderedDict

# Patterns that indicate a definition (not just a reference)
_DEF_PATTERNS = [
    # Go
    re.compile(r'^\s*func\s'),
    re.compile(r'^\s*type\s+\w+\s+(struct|interface)'),
    # Python
    re.compile(r'^\s*(class|def)\s'),
    # JavaScript/TypeScript
    re.compile(r'^\s*(function|class|const|let|var)\s'),
    re.compile(r'^\s*(export\s+)?(default\s+)?(function|class)\s'),
    re.compile(r'^\s*module\.exports\s*='),
    # C/C++
    re.compile(r'^\s*class\s+\w+'),
    re.compile(r'^\s*(struct|enum|union|typedef)\s'),
    # Rust
    re.compile(r'^\s*(pub\s+)?(fn|struct|enum|trait|impl|type|mod)\s'),
]

# Path components that indicate lower-priority files
_LOW_PRIORITY = {'test', 'tests', 'testing', '_test', 'spec', 'specs',
                 'example', 'examples', '_examples', 'sample', 'samples',
                 'fixture', 'fixtures', 'mock', 'mocks', 'testdata',
                 'vendor', 'node_modules', 'third_party', '__pycache__'}


def _file_priority(path: str) -> int:
    """Score a file path: lower = higher priority (shown first).
    0 = core source, 1 = test, 2 = example/vendor.
    """
    parts = set(path.lower().replace("\\", "/").split("/"))
    # Check if any path component is a low-priority directory
    if parts & _LOW_PRIORITY:
        # Distinguish test from example/vendor
        if parts & {'test', 'tests', 'testing', '_test', 'spec', 'specs'}:
            return 1
        return 2
    # Check filename patterns
    basename = os.path.basename(path).lower()
    if '_test.' in basename or 'test_' in basename or '.test.' in basename or '.spec.' in basename:
        return 1
    return 0


def _is_definition(content: str) -> bool:
    """Check if a match line looks like a definition."""
    for pat in _DEF_PATTERNS:
        if pat.search(content):
            return True
    return False


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
    """Search using rg --json, then rank and group results."""
    args = ["rg", "--json"]

    if path_glob:
        args.extend(["--glob", path_glob])
    if file_type:
        args.extend(["--type", file_type])

    args.append("--")
    args.append(query)
    args.append(".")

    raw = _run(args, cwd=repo_root)
    if not raw.strip():
        return "No matches found."

    # Parse rg --json output
    file_matches = defaultdict(list)
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        if data.get("type") != "match":
            continue

        d = data["data"]
        path = d["path"]["text"]
        # Strip leading ./ for consistency
        if path.startswith("./"):
            path = path[2:]
        line_num = d["line_number"]
        lines_data = d.get("lines", {})
        content = lines_data.get("text", "").rstrip("\n")
        if not content:
            # Binary match or missing text field
            continue

        is_def = _is_definition(content)
        file_matches[path].append({
            "line": line_num,
            "content": content,
            "is_def": is_def,
        })

    if not file_matches:
        return "No matches found."

    # Rank files: definitions first, then by file priority, then alphabetical
    def file_sort_key(path):
        matches = file_matches[path]
        has_def = any(m["is_def"] for m in matches)
        priority = _file_priority(path)
        return (0 if has_def else 1, priority, path)

    ranked_files = sorted(file_matches.keys(), key=file_sort_key)

    # Format grouped output
    output_lines = []
    files_shown = 0

    for filepath in ranked_files:
        if files_shown >= max_files:
            output_lines.append(f"\n(truncated to top {max_files} files)")
            break

        matches = file_matches[filepath]
        output_lines.append(f"\n{filepath}")

        snippets_shown = 0
        for match in matches:
            if snippets_shown >= max_matches_per_file:
                break

            line_num = match["line"]
            content = match["content"]

            # Single line — no context (matches pgr behavior in eval)
            output_lines.append(f"  {line_num}-{line_num}:")
            output_lines.append(f"    {line_num}| {content}")
            snippets_shown += 1

        files_shown += 1

    result = "\n".join(output_lines).strip()
    return result if result else "No matches found."


# read_code, find_files, list_dir are identical to baseline — rg_ranked
# only changes search_code ranking. Import from baseline.

def read_code(
    repo_root: str,
    path: str,
    start_line: int = 1,
    end_line: int = 0,
    max_lines: int = 80,
) -> str:
    """Read a file section using filesystem."""
    full_path = os.path.join(repo_root, path)
    if not os.path.isfile(full_path):
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
    start = max(1, start_line) - 1
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
    """Find files using rg --files."""
    args = ["rg", "--files", "."]
    if glob:
        args.extend(["--glob", glob])
    if file_type:
        args.extend(["--type", file_type])

    raw = _run(args, cwd=repo_root)
    if not raw.strip():
        return "No files found."

    paths = raw.strip().splitlines()

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
    """Find a file by suffix match."""
    suffix_lower = suffix.lower()
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                   ("node_modules", "vendor", "target", "__pycache__", ".git")]
        for f in files:
            full = os.path.relpath(os.path.join(root, f), repo_root)
            if full.lower().endswith(suffix_lower):
                return full
    return None
