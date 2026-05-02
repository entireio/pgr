use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

// Directories to skip during recursive directory walks
const SKIP_DIRS: &[&str] = &[
    "node_modules",
    "vendor",
    "target",
    "__pycache__",
    ".git",
];

/// Read lines from a file, with optional line range and max_lines cap.
/// Supports exact path lookup and suffix-based fuzzy matching.
pub fn read_code(params: &serde_json::Value) -> String {
    let path = match params.get("path").and_then(|v| v.as_str()) {
        Some(p) => p.to_string(),
        None => return "Error: 'path' parameter is required".to_string(),
    };
    let start_line = params
        .get("start_line")
        .and_then(|v| v.as_u64())
        .unwrap_or(1)
        .max(1) as usize;
    let end_line = params
        .get("end_line")
        .and_then(|v| v.as_u64())
        .unwrap_or(0) as usize; // 0 = auto
    let max_lines = params
        .get("max_lines")
        .and_then(|v| v.as_u64())
        .unwrap_or(80)
        .max(1) as usize;

    // Resolve the file path (exact first, then suffix match)
    let resolved = resolve_path(&path);
    let file_path = match resolved {
        Some(p) => p,
        None => return format!("File not found: {}", path),
    };

    let content = match fs::read_to_string(&file_path) {
        Ok(c) => c,
        Err(e) => return format!("Error reading file: {}", e),
    };

    let all_lines: Vec<&str> = content.lines().collect();
    let total_lines = all_lines.len();

    // Clamp start_line to valid range
    let start = start_line.min(total_lines.max(1));

    // Compute end: if end_line is 0 (auto), use start + max_lines - 1
    let computed_end = if end_line == 0 {
        start + max_lines - 1
    } else {
        end_line
    };
    let end = computed_end.min(total_lines);

    // Number of lines to actually show is capped at max_lines
    let show_count = (end.saturating_sub(start - 1)).min(max_lines);
    let display_end = (start + show_count).saturating_sub(1);

    let display_path = file_path.display().to_string();
    let mut output = format!("{}:{}-{}\n", display_path, start, display_end);

    for (i, line) in all_lines
        .iter()
        .enumerate()
        .skip(start - 1)
        .take(show_count)
    {
        let line_num = i + 1;
        output.push_str(&format!("{:3}| {}\n", line_num, line));
    }

    let remaining = total_lines.saturating_sub(display_end);
    if remaining > 0 {
        output.push_str(&format!("  ({} more lines)\n", remaining));
    }

    output
}

/// Resolve a path: try exact match first, then suffix match across the cwd tree.
fn resolve_path(path: &str) -> Option<PathBuf> {
    let p = Path::new(path);

    // Exact path
    if p.exists() && p.is_file() {
        return Some(p.to_path_buf());
    }

    // Suffix match: walk from current directory
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let suffix_lower = path.to_ascii_lowercase();
    find_by_suffix(&cwd, &suffix_lower)
}

/// Recursively walk `dir`, skipping hidden dirs and known large/irrelevant dirs,
/// returning the first file whose path (relative to cwd) ends with `suffix`.
fn find_by_suffix(dir: &Path, suffix: &str) -> Option<PathBuf> {
    let entries = match fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return None,
    };

    let mut subdirs: Vec<PathBuf> = Vec::new();

    for entry in entries.flatten() {
        let entry_path = entry.path();
        let name = entry
            .file_name()
            .to_string_lossy()
            .to_ascii_lowercase();

        // Skip hidden entries
        if name.starts_with('.') {
            continue;
        }

        if entry_path.is_dir() {
            // Skip known irrelevant dirs
            if SKIP_DIRS.contains(&name.as_str()) {
                continue;
            }
            subdirs.push(entry_path);
        } else if entry_path.is_file() {
            let path_str = entry_path.to_string_lossy().to_ascii_lowercase();
            if path_str.ends_with(suffix) {
                return Some(entry_path);
            }
        }
    }

    // Recurse into subdirectories
    for subdir in subdirs {
        if let Some(found) = find_by_suffix(&subdir, suffix) {
            return Some(found);
        }
    }

    None
}

/// Find files matching a pattern using ripgrep's file listing.
pub fn find_files(params: &serde_json::Value) -> String {
    let pattern = params
        .get("pattern")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    let glob = params
        .get("glob")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let file_type = params
        .get("file_type")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let max_results = params
        .get("max_results")
        .and_then(|v| v.as_u64())
        .unwrap_or(50) as usize;

    // Build rg command
    let mut cmd = Command::new("rg");
    cmd.arg("--files").arg(".");

    if !glob.is_empty() {
        cmd.arg("--glob").arg(&glob);
    }
    if !file_type.is_empty() {
        cmd.arg("--type").arg(&file_type);
    }

    let output = match cmd.output() {
        Ok(o) => o,
        Err(e) => return format!("Error running rg: {}", e),
    };

    let stdout = String::from_utf8_lossy(&output.stdout);

    let mut files: Vec<String> = stdout
        .lines()
        .filter(|line| {
            if pattern.is_empty() {
                true
            } else {
                line.to_ascii_lowercase().contains(&pattern)
            }
        })
        .map(|s| s.to_string())
        .collect();

    if files.is_empty() {
        return "No files found.".to_string();
    }

    files.sort();

    let total = files.len();
    let truncated = total > max_results;
    files.truncate(max_results);

    let mut result = files.join("\n");
    if truncated {
        result.push_str(&format!("\n(truncated to {} results)", max_results));
    }
    result
}

/// List directory contents, optionally recursively.
pub fn list_dir(params: &serde_json::Value) -> String {
    let path = params
        .get("path")
        .and_then(|v| v.as_str())
        .unwrap_or(".")
        .to_string();
    let recursive = params
        .get("recursive")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let max_results = params
        .get("max_results")
        .and_then(|v| v.as_u64())
        .unwrap_or(100) as usize;

    let dir_path = Path::new(&path);

    if !dir_path.is_dir() {
        return format!("Not a directory: {}", path);
    }

    let mut entries: Vec<String> = Vec::new();
    collect_dir_entries(dir_path, dir_path, recursive, &mut entries);

    if entries.is_empty() {
        return "(empty directory)".to_string();
    }

    entries.sort();
    entries.truncate(max_results);
    entries.join("\n")
}

/// Recursively (or not) collect directory entries relative to `base`.
fn collect_dir_entries(
    base: &Path,
    dir: &Path,
    recursive: bool,
    entries: &mut Vec<String>,
) {
    let read = match fs::read_dir(dir) {
        Ok(r) => r,
        Err(_) => return,
    };

    for entry in read.flatten() {
        let entry_path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();

        // Skip hidden files/dirs
        if name.starts_with('.') {
            continue;
        }

        // Compute display path relative to base
        let rel = entry_path
            .strip_prefix(base)
            .unwrap_or(&entry_path)
            .to_string_lossy()
            .to_string();

        if entry_path.is_dir() {
            // Skip known irrelevant dirs in recursive mode
            if recursive && SKIP_DIRS.contains(&name.as_str()) {
                continue;
            }
            entries.push(format!("{}/", rel));
            if recursive {
                collect_dir_entries(base, &entry_path, recursive, entries);
            }
        } else {
            entries.push(rel);
        }
    }
}
