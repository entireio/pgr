"""rg_expanded backend: rg_ranked + definition expansion + line truncation.

Same as rg_ranked but with two enhancements:
1. Definition matches include 6 lines of body context from the file
2. Lines truncated to 180 chars to save tokens

Tests whether richer search output further reduces agent tool calls.
"""

import json
import os
import re
import subprocess
from collections import defaultdict

# ── Definition detection ──────────────────────────────────────────

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

_LOW_PRIORITY = {'test', 'tests', 'testing', '_test', 'spec', 'specs',
                 'example', 'examples', '_examples', 'sample', 'samples',
                 'fixture', 'fixtures', 'mock', 'mocks', 'testdata',
                 'vendor', 'node_modules', 'third_party', '__pycache__'}

MAX_LINE_LEN = 180
DEF_CONTEXT_LINES = 20  # max cap for brace-counted bodies
DEF_MODE = "brace"  # "fixed" or "brace"


def _file_priority(path):
    parts = set(path.lower().replace("\\", "/").split("/"))
    if parts & _LOW_PRIORITY:
        if parts & {'test', 'tests', 'testing', '_test', 'spec', 'specs'}:
            return 1
        return 2
    basename = os.path.basename(path).lower()
    if '_test.' in basename or 'test_' in basename or '.test.' in basename or '.spec.' in basename:
        return 1
    return 0


def _is_definition(content):
    for pat in _DEF_PATTERNS:
        if pat.search(content):
            return True
    return False


def _truncate(line):
    if len(line) <= MAX_LINE_LEN:
        return line
    return line[:MAX_LINE_LEN] + "…"


def _find_body_end(file_lines, start_idx, max_lines=DEF_CONTEXT_LINES):
    """Find the end of a definition body using brace counting or indentation.

    For brace-delimited languages: count { and } from the definition line.
    For Python (detected by 'def ' or 'class ' + colon): track indentation.
    Returns the 0-based index of the last line of the body (inclusive).
    """
    if start_idx >= len(file_lines):
        return start_idx

    first_line = file_lines[start_idx]
    cap = min(start_idx + max_lines, len(file_lines))

    # Python: indent-based
    stripped = first_line.lstrip()
    if (stripped.startswith("def ") or stripped.startswith("class ")) and ":" in first_line:
        # Find the indentation of the def/class line
        base_indent = len(first_line) - len(first_line.lstrip())
        end = start_idx
        for i in range(start_idx + 1, cap):
            line = file_lines[i]
            # Skip blank lines
            if not line.strip():
                end = i
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= base_indent:
                break  # dedented = end of body
            end = i
        return end

    # Brace-delimited: count { }
    depth = 0
    found_open = False
    for i in range(start_idx, cap):
        line = file_lines[i]
        for ch in line:
            if ch == '{':
                depth += 1
                found_open = True
            elif ch == '}':
                depth -= 1
                if found_open and depth <= 0:
                    return i
    # If we never found braces or didn't close, fall back to fixed context
    return min(start_idx + 3, cap - 1)


def _run(cmd, cwd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.stdout
    except (subprocess.TimeoutExpired, Exception):
        return ""


# ── File line cache (avoids re-reading same file for multiple defs) ──

_file_cache = {}


def _get_file_lines(repo_root, path):
    """Read file lines, cached for duration of one search_code call."""
    full_path = os.path.join(repo_root, path)
    if full_path in _file_cache:
        return _file_cache[full_path]
    try:
        with open(full_path, "r", errors="replace") as f:
            lines = f.readlines()
        _file_cache[full_path] = lines
        return lines
    except Exception:
        _file_cache[full_path] = []
        return []


def _clear_file_cache():
    _file_cache.clear()


# ── search_code ───────────────────────────────────────────────────

def search_code(
    repo_root,
    query,
    path_glob="",
    file_type="",
    max_files=10,
    max_matches_per_file=3,
    context_before=2,
    context_after=2,
):
    """Search using rg --json, rank, and expand definitions inline."""
    _clear_file_cache()

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
        if path.startswith("./"):
            path = path[2:]
        line_num = d["line_number"]
        lines_data = d.get("lines", {})
        content = lines_data.get("text", "").rstrip("\n")
        if not content:
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

    # Format grouped output with definition expansion
    output_lines = []
    files_shown = 0

    for filepath in ranked_files:
        if files_shown >= max_files:
            output_lines.append(f"\n(truncated to top {max_files} files)")
            break

        matches = file_matches[filepath]
        # Within a file, show definitions first, then other matches
        matches.sort(key=lambda m: (0 if m["is_def"] else 1, m["line"]))
        output_lines.append(f"\n{filepath}")

        snippets_shown = 0
        for match in matches:
            if snippets_shown >= max_matches_per_file:
                break

            line_num = match["line"]
            content = match["content"]
            is_def = match["is_def"]

            if is_def:
                # Expand definition: show full body via brace/indent counting
                file_lines = _get_file_lines(repo_root, filepath)
                start_idx = line_num - 1  # 0-based
                end_idx = _find_body_end(file_lines, start_idx) + 1  # exclusive

                output_lines.append(f"  {line_num}-{end_idx}: [def]")
                output_lines.append(f"    {line_num}| {_truncate(content)}")
                for i in range(start_idx + 1, end_idx):
                    ctx_line = file_lines[i].rstrip("\n")
                    output_lines.append(f"    {i+1}| {_truncate(ctx_line)}")
            else:
                # Regular match: single line, truncated
                output_lines.append(f"  {line_num}-{line_num}:")
                output_lines.append(f"    {line_num}| {_truncate(content)}")

            snippets_shown += 1

        files_shown += 1

    result = "\n".join(output_lines).strip()
    return result if result else "No matches found."


# ── read_code, find_files, list_dir — identical to rg_ranked ─────

def read_code(repo_root, path, start_line=1, end_line=0, max_lines=80):
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


def find_files(repo_root, pattern="", glob="", file_type="", max_results=50):
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


def list_dir(repo_root, path=".", recursive=False, max_results=100):
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


def _find_by_suffix(repo_root, suffix):
    suffix_lower = suffix.lower()
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                   ("node_modules", "vendor", "target", "__pycache__", ".git")]
        for f in files:
            full = os.path.relpath(os.path.join(root, f), repo_root)
            if full.lower().endswith(suffix_lower):
                return full
    return None
