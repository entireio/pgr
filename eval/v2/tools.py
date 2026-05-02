"""Unified tool definitions for the v2 eval.

Both conditions (baseline and pgr) use identical tool names, schemas, and output formats.
Only the backend implementation differs.
"""

# Tool definitions in Anthropic API format
TOOL_DEFINITIONS = [
    {
        "name": "search_code",
        "description": (
            "Search code for a pattern. Returns matches grouped by file with line numbers and context. "
            "Use this to find symbol definitions, references, usages, or any code pattern."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search pattern. Literal string match by default. Use regex syntax for patterns.",
                },
                "path_glob": {
                    "type": "string",
                    "description": "Filter files by glob pattern, e.g. '*.go', 'middleware/*.py'",
                },
                "file_type": {
                    "type": "string",
                    "description": "Filter by language: go, python, javascript, typescript, cpp, rust, java",
                },
                "max_files": {
                    "type": "integer",
                    "description": "Max files to return. Default 10.",
                },
                "max_matches_per_file": {
                    "type": "integer",
                    "description": "Max matches per file. Default 3.",
                },
                "context_before": {
                    "type": "integer",
                    "description": "Lines of context before each match. Default 2.",
                },
                "context_after": {
                    "type": "integer",
                    "description": "Lines of context after each match. Default 2.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_code",
        "description": (
            "Read a bounded section of a file. Returns numbered lines. "
            "Use this to inspect code after finding it with search_code."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path (exact or partial — suffix matching supported).",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to read (1-based). Default 1.",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to read (inclusive). Overrides max_lines if set.",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Max lines to return. Default 80.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "find_files",
        "description": (
            "Find files by name pattern, glob, or language. Returns a list of file paths. "
            "Use this to locate files before reading them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Filename or path substring to match.",
                },
                "glob": {
                    "type": "string",
                    "description": "Glob pattern, e.g. '**/*.go', 'src/**/*.ts'",
                },
                "file_type": {
                    "type": "string",
                    "description": "Filter by language: go, python, javascript, typescript, cpp, rust, java",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results. Default 50.",
                },
            },
        },
    },
    {
        "name": "list_dir",
        "description": (
            "List contents of a directory. Returns sorted file and directory names. "
            "Use this to understand project structure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list. Default is repo root.",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "List recursively. Default false.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max entries. Default 100.",
                },
            },
        },
    },
]

# System prompt for the agent — identical for both conditions
SYSTEM_PROMPT = """You are a code search assistant. Answer questions about codebases using the available tools.

Tools available:
- search_code: find code patterns, definitions, references
- read_code: read a bounded section of a file
- find_files: locate files by name or pattern
- list_dir: list directory contents

When searching:
- Start narrow, broaden only if needed
- Prefer grouped search results over full-file reads
- Read only bounded windows, not entire files
"""
