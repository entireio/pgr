use serde_json::json;

/// Returns the MCP tool list JSON.
pub fn tool_definitions() -> serde_json::Value {
    json!({
        "tools": [
            {
                "name": "search_code",
                "description": "Search for code patterns using ripgrep. Returns ranked matches with file paths and line numbers.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query (regex or literal string)"
                        },
                        "path_glob": {
                            "type": "string",
                            "description": "Glob pattern to filter files (e.g. '**/*.rs'). Default: empty (all files)"
                        },
                        "file_type": {
                            "type": "string",
                            "description": "File type filter for ripgrep (e.g. 'rust', 'py', 'js'). Default: empty (all types)"
                        },
                        "max_files": {
                            "type": "integer",
                            "description": "Maximum number of files to return. Default: 10"
                        },
                        "max_matches_per_file": {
                            "type": "integer",
                            "description": "Maximum number of matches per file. Default: 3"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "read_code",
                "description": "Read lines from a file with optional line range. Supports exact path or suffix-based fuzzy matching.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path to read (exact or suffix match)"
                        },
                        "start_line": {
                            "type": "integer",
                            "description": "Starting line number (1-indexed). Default: 1"
                        },
                        "end_line": {
                            "type": "integer",
                            "description": "Ending line number (0 = auto based on max_lines). Default: 0"
                        },
                        "max_lines": {
                            "type": "integer",
                            "description": "Maximum number of lines to return. Default: 80"
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "find_files",
                "description": "Find files matching a pattern using ripgrep's file listing.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Substring pattern to filter file paths (case-insensitive). Default: empty (all files)"
                        },
                        "glob": {
                            "type": "string",
                            "description": "Glob pattern passed to ripgrep (e.g. '**/*.rs'). Default: empty"
                        },
                        "file_type": {
                            "type": "string",
                            "description": "File type filter for ripgrep (e.g. 'rust', 'py'). Default: empty"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return. Default: 50"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "list_dir",
                "description": "List directory contents, optionally recursively.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list. Default: '.'"
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "Whether to list recursively. Default: false"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of entries to return. Default: 100"
                        }
                    },
                    "required": []
                }
            }
        ]
    })
}

/// Dispatches a tool call by name to the appropriate handler.
pub fn handle_tool_call(name: &str, arguments: &serde_json::Value) -> String {
    match name {
        "search_code" => crate::search::search_code(arguments),
        "read_code" => crate::read::read_code(arguments),
        "find_files" => crate::read::find_files(arguments),
        "list_dir" => crate::read::list_dir(arguments),
        _ => format!("Unknown tool: {}", name),
    }
}
