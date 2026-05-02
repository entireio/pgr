"""fff backend: uses fff-mcp (stateful indexed MCP server) for search.

fff-mcp provides grep, find_files, and multi_grep via MCP JSON-RPC over stdio.
read_code and list_dir fall back to filesystem (fff doesn't have these tools).

fff-mcp is stateful — it indexes the repo on startup and maintains frecency state.
We keep one subprocess per repo_root for the lifetime of the eval.
"""

import json
import os
import subprocess
import threading

FFF_BIN = os.path.expanduser("~/.local/bin/fff-mcp")

# Process pool: repo_root -> (process, lock, request_id_counter)
_processes: dict[str, tuple[subprocess.Popen, threading.Lock, list[int]]] = {}
_pool_lock = threading.Lock()


def _get_process(repo_root: str) -> tuple[subprocess.Popen, threading.Lock, list[int]]:
    """Get or create an fff-mcp process for a repo."""
    with _pool_lock:
        if repo_root in _processes:
            proc, lock, counter = _processes[repo_root]
            if proc.poll() is None:  # still alive
                return proc, lock, counter

        # Start new process — fff-mcp takes repo path as positional arg
        proc = subprocess.Popen(
            [FFF_BIN, repo_root],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        lock = threading.Lock()
        counter = [10]  # start at 10 to avoid collision with handshake ids

        # MCP handshake
        _send_raw(proc, json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pgr-eval", "version": "0.1"},
            }
        }))
        _read_line(proc)  # consume initialize response

        _send_raw(proc, json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }))

        # Give fff-mcp time to index the repo before accepting queries.
        # fff builds an in-memory index on startup; without this delay,
        # the first search returns 0 results.
        import time
        time.sleep(2)

        _processes[repo_root] = (proc, lock, counter)
        return proc, lock, counter


def _send_raw(proc: subprocess.Popen, msg: str):
    """Send a raw JSON-RPC message."""
    proc.stdin.write(msg + "\n")
    proc.stdin.flush()


def _read_line(proc: subprocess.Popen, timeout: float = 30.0) -> str:
    """Read a line from the process stdout."""
    import select
    # Simple blocking read — fff-mcp responds quickly
    line = proc.stdout.readline()
    return line.strip() if line else ""


def _call_tool(repo_root: str, tool_name: str, arguments: dict) -> str:
    """Call an fff-mcp tool via MCP JSON-RPC."""
    proc, lock, counter = _get_process(repo_root)

    with lock:
        req_id = counter[0]
        counter[0] += 1

        request = json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            }
        })
        _send_raw(proc, request)
        raw = _read_line(proc)

    if not raw:
        return "fff-mcp: no response"

    try:
        resp = json.loads(raw)
    except json.JSONDecodeError:
        return f"fff-mcp: invalid JSON: {raw[:200]}"

    # Extract text from MCP tool result
    result = resp.get("result", {})
    content = result.get("content", [])
    texts = []
    for block in content:
        if block.get("type") == "text":
            texts.append(block["text"])
    return "\n".join(texts) if texts else "No results."


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
    """Search using fff-mcp grep tool."""
    # Build fff grep query with constraints
    # fff uses inline constraints: "*.go query" or "src/ query"
    constraints = ""
    if file_type:
        # Map language names to extensions
        ext_map = {
            "go": "*.go", "python": "*.py", "py": "*.py",
            "javascript": "*.js", "js": "*.js",
            "typescript": "*.ts", "ts": "*.ts",
            "rust": "*.rs", "rs": "*.rs",
            "cpp": "*.{cc,cpp,h,hpp}", "c": "*.{c,h}",
            "java": "*.java",
        }
        ext = ext_map.get(file_type.lower(), f"*.{file_type}")
        constraints += ext + " "
    if path_glob:
        constraints += path_glob + " "

    fff_query = constraints + query

    return _call_tool(repo_root, "grep", {
        "query": fff_query,
        "maxResults": max_files * max_matches_per_file,
    })


def find_files(
    repo_root: str,
    pattern: str = "",
    glob: str = "",
    file_type: str = "",
    max_results: int = 50,
) -> str:
    """Find files using fff-mcp find_files tool."""
    # Build query from pattern + constraints
    parts = []
    if glob:
        parts.append(glob)
    if file_type:
        ext_map = {
            "go": "*.go", "python": "*.py", "py": "*.py",
            "javascript": "*.js", "js": "*.js",
            "typescript": "*.ts", "ts": "*.ts",
            "rust": "*.rs", "rs": "*.rs",
            "cpp": "*.{cc,cpp,h,hpp}", "c": "*.{c,h}",
            "java": "*.java",
        }
        ext = ext_map.get(file_type.lower(), f"*.{file_type}")
        parts.append(ext)
    if pattern:
        parts.append(pattern)

    query = " ".join(parts) if parts else "*"

    return _call_tool(repo_root, "find_files", {
        "query": query,
        "maxResults": max_results,
    })


# read_code and list_dir: fff-mcp doesn't have these, use filesystem

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


def cleanup():
    """Kill all fff-mcp processes."""
    with _pool_lock:
        for repo_root, (proc, lock, counter) in _processes.items():
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        _processes.clear()
