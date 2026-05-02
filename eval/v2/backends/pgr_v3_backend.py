"""pgr_v3 backend: uses the pgr v3 MCP binary for all tools.

pgr v3 is stateless — no index, no daemon. Each tool call spawns the binary,
sends initialize + tools/call, reads the response. This is the actual production
binary we're shipping.

Unlike fff, pgr v3 supports all 4 tools natively (search_code, read_code,
find_files, list_dir), so no filesystem fallback is needed.
"""

import json
import os
import subprocess
import threading

# Path to the pgr v3 binary — use release build
PGR_BIN = os.path.join(os.path.dirname(__file__), "..", "..", "..", "target", "release", "pgr")

# Process pool: repo_root -> (process, lock, request_id_counter)
# pgr v3 is stateless but keeping a long-lived process avoids startup overhead
_processes: dict = {}
_pool_lock = threading.Lock()


def _get_process(repo_root: str):
    """Get or create a pgr v3 process for a repo."""
    with _pool_lock:
        if repo_root in _processes:
            proc, lock, counter = _processes[repo_root]
            if proc.poll() is None:  # still alive
                return proc, lock, counter

        bin_path = os.path.abspath(PGR_BIN)
        if not os.path.isfile(bin_path):
            raise FileNotFoundError(f"pgr v3 binary not found at {bin_path}. Run: cargo build --release")

        proc = subprocess.Popen(
            [bin_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=repo_root,  # pgr searches cwd
        )
        lock = threading.Lock()
        counter = [10]

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

        # No sleep needed — pgr v3 is stateless, no index to build

        _processes[repo_root] = (proc, lock, counter)
        return proc, lock, counter


def _send_raw(proc, msg: str):
    """Send a raw JSON-RPC message."""
    proc.stdin.write(msg + "\n")
    proc.stdin.flush()


def _read_line(proc, timeout: float = 30.0) -> str:
    """Read a line from the process stdout."""
    line = proc.stdout.readline()
    return line.strip() if line else ""


def _call_tool(repo_root: str, tool_name: str, arguments: dict) -> str:
    """Call a pgr v3 tool via MCP JSON-RPC."""
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
        return "pgr-v3: no response"

    try:
        resp = json.loads(raw)
    except json.JSONDecodeError:
        return f"pgr-v3: invalid JSON: {raw[:200]}"

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
    """Search using pgr v3 search_code tool."""
    args = {"query": query}
    if path_glob:
        args["path_glob"] = path_glob
    if file_type:
        args["file_type"] = file_type
    if max_files != 10:
        args["max_files"] = max_files
    if max_matches_per_file != 3:
        args["max_matches_per_file"] = max_matches_per_file
    return _call_tool(repo_root, "search_code", args)


def read_code(
    repo_root: str,
    path: str,
    start_line: int = 1,
    end_line: int = 0,
    max_lines: int = 80,
) -> str:
    """Read a file section using pgr v3 read_code tool."""
    args = {"path": path}
    if start_line != 1:
        args["start_line"] = start_line
    if end_line != 0:
        args["end_line"] = end_line
    if max_lines != 80:
        args["max_lines"] = max_lines
    return _call_tool(repo_root, "read_code", args)


def find_files(
    repo_root: str,
    pattern: str = "",
    glob: str = "",
    file_type: str = "",
    max_results: int = 50,
) -> str:
    """Find files using pgr v3 find_files tool."""
    args = {}
    if pattern:
        args["pattern"] = pattern
    if glob:
        args["glob"] = glob
    if file_type:
        args["file_type"] = file_type
    if max_results != 50:
        args["max_results"] = max_results
    return _call_tool(repo_root, "find_files", args)


def list_dir(
    repo_root: str,
    path: str = ".",
    recursive: bool = False,
    max_results: int = 100,
) -> str:
    """List directory using pgr v3 list_dir tool."""
    args = {"path": path}
    if recursive:
        args["recursive"] = True
    if max_results != 100:
        args["max_results"] = max_results
    return _call_tool(repo_root, "list_dir", args)


def cleanup():
    """Kill all pgr v3 processes."""
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
