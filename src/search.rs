use std::env;
use std::collections::HashMap;
use std::process::Command;

/// A single match extracted from rg --json output.
struct RgMatch {
    line_number: u64,
    line_text: String,
    is_def: bool,
}

/// Aggregated data for one file.
struct FileMatches {
    path: String,
    matches: Vec<RgMatch>,
}

struct SearchSummary {
    total_files: usize,
    source_files: usize,
    test_files: usize,
    low_priority_files: usize,
    definition_files: usize,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum OutputProfile {
    V3,
    EmptyOnly,
    SummaryOnly,
    CountsEmpty,
    FullV4,
}

impl OutputProfile {
    fn from_env() -> Self {
        match env::var("PGR_OUTPUT_PROFILE").ok().as_deref() {
            Some("v3") => Self::V3,
            Some("empty_only") => Self::EmptyOnly,
            Some("summary_only") => Self::SummaryOnly,
            Some("counts_empty") => Self::CountsEmpty,
            Some("full_v4") => Self::FullV4,
            _ => Self::FullV4,
        }
    }

    fn uses_diagnostic_empty_state(self) -> bool {
        matches!(self, Self::EmptyOnly | Self::CountsEmpty | Self::FullV4)
    }

    fn uses_summary_header(self) -> bool {
        matches!(self, Self::SummaryOnly | Self::CountsEmpty | Self::FullV4)
    }

    fn uses_best_next_step(self) -> bool {
        matches!(self, Self::FullV4)
    }

    fn uses_file_reason(self) -> bool {
        matches!(self, Self::FullV4)
    }

    fn uses_truncation_note(self) -> bool {
        matches!(self, Self::CountsEmpty | Self::FullV4)
    }
}

fn build_legacy_no_matches_message() -> String {
    "No matches found.".to_string()
}

fn build_no_matches_message(query: &str, path_glob: &str, file_type: &str) -> String {
    let scope = describe_scope(path_glob, file_type);
    format!(
        "No matches found.\n  query: {}\n  scope: {}\n  hint: broaden the query, remove path_glob/file_type filters, or try a simpler symbol name.",
        query, scope
    )
}

fn describe_scope(path_glob: &str, file_type: &str) -> String {
    let mut parts: Vec<String> = Vec::new();
    if !path_glob.is_empty() {
        parts.push(format!("glob={}", path_glob));
    }
    if !file_type.is_empty() {
        parts.push(format!("type={}", file_type));
    }
    if parts.is_empty() {
        "all files".to_string()
    } else {
        parts.join(", ")
    }
}

fn summarize_files(files: &[FileMatches]) -> SearchSummary {
    let mut summary = SearchSummary {
        total_files: files.len(),
        source_files: 0,
        test_files: 0,
        low_priority_files: 0,
        definition_files: 0,
    };

    for file in files {
        match crate::ranking::file_priority(&file.path) {
            0 => summary.source_files += 1,
            1 => summary.test_files += 1,
            _ => summary.low_priority_files += 1,
        }

        if file.matches.iter().any(|m| m.is_def) {
            summary.definition_files += 1;
        }
    }

    summary
}

fn file_reason(file: &FileMatches) -> String {
    let kind = if file.matches.iter().any(|m| m.is_def) {
        "definition"
    } else {
        "reference"
    };

    let bucket = match crate::ranking::file_priority(&file.path) {
        0 => "source",
        1 => "test",
        _ => "low-priority",
    };

    format!("{}, {}", kind, bucket)
}

pub fn search_code(params: &serde_json::Value) -> String {
    let profile = OutputProfile::from_env();
    let query = match params.get("query").and_then(|v| v.as_str()) {
        Some(q) if !q.is_empty() => q.to_string(),
        _ => return "Error: query is required.\n  hint: pass a non-empty query string.".to_string(),
    };

    let path_glob = params
        .get("path_glob")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();

    let file_type = params
        .get("file_type")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();

    let max_files = params
        .get("max_files")
        .and_then(|v| v.as_u64())
        .unwrap_or(10) as usize;

    let max_matches_per_file = params
        .get("max_matches_per_file")
        .and_then(|v| v.as_u64())
        .unwrap_or(3) as usize;

    // Build rg command
    let mut cmd = Command::new("rg");
    cmd.arg("--json");

    if !path_glob.is_empty() {
        cmd.arg("--glob").arg(&path_glob);
    }

    if !file_type.is_empty() {
        cmd.arg("--type").arg(&file_type);
    }

    cmd.arg("--").arg(&query).arg(".");

    let output = match cmd.output() {
        Ok(o) => o,
        Err(_) => {
            return if profile.uses_diagnostic_empty_state() {
                build_no_matches_message(&query, &path_glob, &file_type)
            } else {
                build_legacy_no_matches_message()
            };
        }
    };

    if !output.status.success() && output.stdout.is_empty() {
        return if profile.uses_diagnostic_empty_state() {
            build_no_matches_message(&query, &path_glob, &file_type)
        } else {
            build_legacy_no_matches_message()
        };
    }

    let stdout = String::from_utf8_lossy(&output.stdout);

    // Parse rg JSON output; collect matches per file
    let mut file_map: HashMap<String, Vec<RgMatch>> = HashMap::new();
    let mut file_order: Vec<String> = Vec::new(); // preserve insertion order

    for line in stdout.lines() {
        let v: serde_json::Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(_) => continue,
        };

        if v.get("type").and_then(|t| t.as_str()) != Some("match") {
            continue;
        }

        let data = match v.get("data") {
            Some(d) => d,
            None => continue,
        };

        // Extract path
        let raw_path = match data
            .get("path")
            .and_then(|p| p.get("text"))
            .and_then(|t| t.as_str())
        {
            Some(p) => p,
            None => continue,
        };

        // Strip leading "./"
        let path = raw_path.strip_prefix("./").unwrap_or(raw_path).to_string();

        // Extract line number
        let line_number = match data.get("line_number").and_then(|n| n.as_u64()) {
            Some(n) => n,
            None => continue,
        };

        // Extract line text
        let line_text_raw = match data
            .get("lines")
            .and_then(|l| l.get("text"))
            .and_then(|t| t.as_str())
        {
            Some(t) => t,
            None => continue,
        };

        // Skip empty lines (binary file matches)
        let line_text = line_text_raw.trim_end_matches('\n').to_string();
        if line_text.is_empty() {
            continue;
        }

        let is_def = crate::ranking::is_definition(&line_text);

        let rg_match = RgMatch {
            line_number,
            line_text,
            is_def,
        };

        if !file_map.contains_key(&path) {
            file_order.push(path.clone());
        }
        file_map.entry(path).or_default().push(rg_match);
    }

    if file_map.is_empty() {
        return if profile.uses_diagnostic_empty_state() {
            build_no_matches_message(&query, &path_glob, &file_type)
        } else {
            build_legacy_no_matches_message()
        };
    }

    // Build FileMatches list
    let mut files: Vec<FileMatches> = file_order
        .into_iter()
        .map(|path| {
            let matches = file_map.remove(&path).unwrap_or_default();
            FileMatches { path, matches }
        })
        .collect();

    // Sort files:
    // 1. Files with ANY definition match sort before files with only references
    // 2. Within each tier: by file_priority() (0=source, 1=test, 2=vendor)
    // 3. Within each priority: alphabetical
    files.sort_by(|a, b| {
        let a_has_def = a.matches.iter().any(|m| m.is_def);
        let b_has_def = b.matches.iter().any(|m| m.is_def);

        // Tier: definitions first
        let tier_cmp = b_has_def.cmp(&a_has_def); // true > false, so reverse
        if tier_cmp != std::cmp::Ordering::Equal {
            return tier_cmp;
        }

        // Within tier: by file priority
        let a_prio = crate::ranking::file_priority(&a.path);
        let b_prio = crate::ranking::file_priority(&b.path);
        let prio_cmp = a_prio.cmp(&b_prio);
        if prio_cmp != std::cmp::Ordering::Equal {
            return prio_cmp;
        }

        // Within priority: alphabetical
        a.path.cmp(&b.path)
    });

    // Capture total before truncation to know whether to show the notice
    let total_files = files.len();

    // Truncate to max_files
    files.truncate(max_files);

    // Build output
    let mut output_parts: Vec<String> = Vec::new();

    if profile.uses_summary_header() {
        let summary = summarize_files(&files);
        let mut header = String::new();
        header.push_str("  summary:\n");
        header.push_str(&format!("    query: {}\n", query));
        header.push_str(&format!(
            "    scope: {}\n",
            describe_scope(&path_glob, &file_type)
        ));
        header.push_str(&format!(
            "    files: {} total, {} shown\n",
            summary.total_files,
            total_files.min(max_files)
        ));
        header.push_str(&format!(
            "    buckets: {} source, {} test, {} low-priority\n",
            summary.source_files,
            summary.test_files,
            summary.low_priority_files
        ));
        header.push_str(&format!(
            "    definition_candidates: {}\n",
            summary.definition_files
        ));

        if profile.uses_best_next_step() {
            if let Some(best) = files.first() {
                if let Some(best_match) = best.matches.first() {
                    header.push_str(&format!(
                        "    best_next_step: read {} around line {}\n",
                        best.path, best_match.line_number
                    ));
                }
            }
        }

        output_parts.push(header);
    }

    for file in &mut files {
        // Sort matches within file: definitions first, then by line number
        file.matches.sort_by(|a, b| {
            let def_cmp = b.is_def.cmp(&a.is_def); // definitions first
            if def_cmp != std::cmp::Ordering::Equal {
                return def_cmp;
            }
            a.line_number.cmp(&b.line_number)
        });

        // Truncate to max_matches_per_file
        file.matches.truncate(max_matches_per_file);

        let mut file_block = file.path.clone();
        file_block.push('\n');
        if profile.uses_file_reason() {
            file_block.push_str(&format!("  why: {}\n", file_reason(file)));
        }

        for m in &file.matches {
            let ln = m.line_number;
            let truncated = crate::ranking::truncate_line(&m.line_text);
            // Format: "  60-60:\n    60| <content>"
            file_block.push_str(&format!("  {}-{}:\n", ln, ln));
            file_block.push_str(&format!("    {}| {}\n", ln, truncated));
        }

        output_parts.push(file_block);
    }

    let mut result = output_parts.join("\n");

    // Append truncation notice only if there were more files than max_files
    if total_files > max_files && profile.uses_truncation_note() {
        result.push_str(&format!(
            "\n  note: truncated to top {} files; refine the query or filters to narrow further.",
            max_files
        ));
    }

    result
}
