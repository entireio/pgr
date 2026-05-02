use std::fs;
use std::io::Write;
use std::process::{Command, Stdio};
use serde_json::{json, Value};
use tempfile::TempDir;

/// Spawn the pgr binary, write all messages to stdin, close stdin,
/// collect stdout lines, parse each as a JSON Value.
fn pgr_mcp(messages: &[Value]) -> Vec<Value> {
    let binary = env!("CARGO_BIN_EXE_pgr");
    let mut child = Command::new(binary)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("failed to spawn pgr binary");

    let stdin = child.stdin.as_mut().expect("failed to open stdin");
    for msg in messages {
        let line = serde_json::to_string(msg).expect("failed to serialize message");
        writeln!(stdin, "{}", line).expect("failed to write to stdin");
    }
    // Drop stdin to close it
    drop(child.stdin.take());

    let output = child.wait_with_output().expect("failed to wait on child");
    let stdout = String::from_utf8_lossy(&output.stdout);

    stdout
        .lines()
        .filter(|l| !l.trim().is_empty())
        .filter_map(|l| serde_json::from_str::<Value>(l).ok())
        .collect()
}

/// Send initialize + notifications/initialized + tools/call,
/// return the tool call response (index 1 of responses, since
/// notifications/initialized produces no response).
fn init_and_call(tool_name: &str, arguments: Value) -> Value {
    let messages = vec![
        json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.0.1"}
            }
        }),
        json!({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }),
        json!({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }),
    ];

    let responses = pgr_mcp(&messages);
    // responses[0] = initialize response
    // responses[1] = tools/call response (notifications/initialized has no response)
    assert!(
        responses.len() >= 2,
        "expected at least 2 responses, got {}: {:?}",
        responses.len(),
        responses
    );
    responses[1].clone()
}

/// Extract response["result"]["content"][0]["text"] as String.
fn tool_text(response: &Value) -> String {
    response["result"]["content"][0]["text"]
        .as_str()
        .unwrap_or_else(|| panic!("no text in response: {:?}", response))
        .to_string()
}

#[test]
fn test_initialize() {
    let messages = vec![json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.0.1"}
        }
    })];

    let responses = pgr_mcp(&messages);
    assert_eq!(responses.len(), 1, "expected 1 response");

    let result = &responses[0]["result"];
    assert_eq!(result["serverInfo"]["name"], "pgr");
    assert_eq!(result["serverInfo"]["version"], "3.0.0");
    assert_eq!(result["protocolVersion"], "2024-11-05");
}

#[test]
fn test_tools_list() {
    let messages = vec![
        json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.0.1"}
            }
        }),
        json!({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }),
        json!({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }),
    ];

    let responses = pgr_mcp(&messages);
    assert!(responses.len() >= 2, "expected at least 2 responses");

    let tools_response = &responses[1];
    let tools = tools_response["result"]["tools"]
        .as_array()
        .expect("tools should be an array");

    assert_eq!(tools.len(), 4, "expected 4 tools, got {}", tools.len());

    let tool_names: Vec<&str> = tools
        .iter()
        .filter_map(|t| t["name"].as_str())
        .collect();

    assert!(tool_names.contains(&"search_code"), "missing search_code");
    assert!(tool_names.contains(&"read_code"), "missing read_code");
    assert!(tool_names.contains(&"find_files"), "missing find_files");
    assert!(tool_names.contains(&"list_dir"), "missing list_dir");
}

#[test]
fn test_unknown_method() {
    let messages = vec![json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "bogus/method",
        "params": {}
    })];

    let responses = pgr_mcp(&messages);
    assert_eq!(responses.len(), 1, "expected 1 response");

    let error_code = responses[0]["error"]["code"]
        .as_i64()
        .expect("expected numeric error code");
    assert_eq!(error_code, -32601, "expected -32601 method-not-found error code");
}

#[test]
fn test_search_code_finds_results() {
    let response = init_and_call(
        "search_code",
        json!({ "query": "fn main" }),
    );

    let text = tool_text(&response);
    assert!(
        text.contains("main.rs"),
        "expected 'main.rs' in output, got: {}",
        text
    );
    assert!(
        text.contains("summary:"),
        "expected summary header in output, got: {}",
        text
    );
    assert!(
        text.contains("best_next_step:"),
        "expected best_next_step hint in output, got: {}",
        text
    );
    assert!(
        text.contains("why:"),
        "expected per-file rationale in output, got: {}",
        text
    );
}

#[test]
fn test_search_code_no_matches() {
    // Use a path_glob restricted to src/ so neither test files nor docs
    // can accidentally contain the literal query string.
    let response = init_and_call(
        "search_code",
        json!({ "query": "XYZZY_NO_MATCH_SENTINEL_42", "path_glob": "src/**" }),
    );

    let text = tool_text(&response);
    assert!(
        text.contains("No matches found."),
        "expected 'No matches found.' in output, got: {}",
        text
    );
    assert!(
        text.contains("hint:"),
        "expected recovery hint in output, got: {}",
        text
    );
}

#[test]
fn test_read_code_reads_file() {
    let response = init_and_call(
        "read_code",
        json!({ "path": "src/main.rs", "max_lines": 5 }),
    );

    let text = tool_text(&response);
    // Should contain a line range header
    assert!(
        text.contains("Lines") || text.contains("lines") || text.contains("1-") || text.contains("src/main.rs"),
        "expected line range header or file path in output, got: {}",
        text
    );
    // Should contain actual Rust content from main.rs
    assert!(
        text.contains("mod") || text.contains("use") || text.contains("fn"),
        "expected Rust source content, got: {}",
        text
    );
}

#[test]
fn test_read_code_file_not_found() {
    let response = init_and_call(
        "read_code",
        json!({ "path": "nonexistent_file.xyz" }),
    );

    let text = tool_text(&response);
    assert!(
        text.contains("File not found") || text.contains("not found") || text.contains("No file"),
        "expected 'File not found' in output, got: {}",
        text
    );
}

#[test]
fn test_find_files() {
    let response = init_and_call(
        "find_files",
        json!({ "pattern": "main" }),
    );

    let text = tool_text(&response);
    assert!(
        text.contains("main.rs"),
        "expected 'main.rs' in output, got: {}",
        text
    );
}

#[test]
fn test_find_files_with_glob() {
    let response = init_and_call(
        "find_files",
        json!({ "glob": "*.toml" }),
    );

    let text = tool_text(&response);
    assert!(
        text.contains("Cargo.toml"),
        "expected 'Cargo.toml' in output, got: {}",
        text
    );
}

#[test]
fn test_list_dir() {
    let response = init_and_call(
        "list_dir",
        json!({ "path": "." }),
    );

    let text = tool_text(&response);
    assert!(
        text.contains("src/") || text.contains("src"),
        "expected 'src/' in output, got: {}",
        text
    );
    assert!(
        text.contains("Cargo.toml"),
        "expected 'Cargo.toml' in output, got: {}",
        text
    );
}

#[test]
fn test_list_dir_not_found() {
    let response = init_and_call(
        "list_dir",
        json!({ "path": "nonexistent_dir" }),
    );

    let text = tool_text(&response);
    assert!(
        text.contains("Not a directory") || text.contains("not found") || text.contains("No such"),
        "expected directory error in output, got: {}",
        text
    );
}

#[test]
fn test_unknown_tool() {
    let response = init_and_call(
        "bogus_tool",
        json!({}),
    );

    let text = tool_text(&response);
    assert!(
        text.contains("Unknown tool"),
        "expected 'Unknown tool' in output, got: {}",
        text
    );
}

/// Create a temporary repo with three files to exercise search ranking:
/// - src/handler.go  (source file with a function definition)
/// - tests/handler_test.go  (test file that calls the function)
/// - examples/demo.go  (example file that also calls the function)
fn setup_ranking_repo() -> TempDir {
    let dir = tempfile::tempdir().expect("failed to create tempdir");

    // src/handler.go — source file with definition
    let src_dir = dir.path().join("src");
    fs::create_dir_all(&src_dir).expect("failed to create src/");
    fs::write(
        src_dir.join("handler.go"),
        "package handler\n\nfunc HandleRequest(w http.ResponseWriter) {\n    w.Write([]byte(\"ok\"))\n}\n",
    )
    .expect("failed to write src/handler.go");

    // tests/handler_test.go — test file with reference
    let tests_dir = dir.path().join("tests");
    fs::create_dir_all(&tests_dir).expect("failed to create tests/");
    fs::write(
        tests_dir.join("handler_test.go"),
        "package handler\n\nimport \"testing\"\n\nfunc TestHandleRequest(t *testing.T) {\n    HandleRequest(nil)\n}\n",
    )
    .expect("failed to write tests/handler_test.go");

    // examples/demo.go — example file with reference
    let examples_dir = dir.path().join("examples");
    fs::create_dir_all(&examples_dir).expect("failed to create examples/");
    fs::write(
        examples_dir.join("demo.go"),
        "package main\n\nfunc main() {\n    HandleRequest(nil)\n}\n",
    )
    .expect("failed to write examples/demo.go");

    dir
}

#[test]
fn test_ranking_definitions_first() {
    let repo = setup_ranking_repo();

    let binary = env!("CARGO_BIN_EXE_pgr");
    let messages = vec![
        json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.0.1"}
            }
        }),
        json!({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }),
        json!({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "search_code",
                "arguments": { "query": "HandleRequest" }
            }
        }),
    ];

    let mut child = Command::new(binary)
        .current_dir(repo.path())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("failed to spawn pgr binary");

    let stdin = child.stdin.as_mut().expect("failed to open stdin");
    for msg in &messages {
        let line = serde_json::to_string(msg).expect("failed to serialize message");
        writeln!(stdin, "{}", line).expect("failed to write to stdin");
    }
    drop(child.stdin.take());

    let output = child.wait_with_output().expect("failed to wait on child");
    let stdout = String::from_utf8_lossy(&output.stdout);

    let responses: Vec<Value> = stdout
        .lines()
        .filter(|l| !l.trim().is_empty())
        .filter_map(|l| serde_json::from_str::<Value>(l).ok())
        .collect();

    assert!(
        responses.len() >= 2,
        "expected at least 2 responses, got {}: {:?}",
        responses.len(),
        responses
    );

    let tool_response = &responses[1];
    let text = tool_response["result"]["content"][0]["text"]
        .as_str()
        .unwrap_or_else(|| panic!("no text in response: {:?}", tool_response))
        .to_string();

    let pos_src = text
        .find("src/handler.go")
        .unwrap_or_else(|| panic!("'src/handler.go' not found in output:\n{}", text));
    let pos_tests = text
        .find("tests/handler_test.go")
        .unwrap_or_else(|| panic!("'tests/handler_test.go' not found in output:\n{}", text));
    let pos_examples = text
        .find("examples/demo.go")
        .unwrap_or_else(|| panic!("'examples/demo.go' not found in output:\n{}", text));

    assert!(
        pos_src < pos_tests,
        "expected src/handler.go (pos {}) before tests/handler_test.go (pos {})\nOutput:\n{}",
        pos_src,
        pos_tests,
        text
    );
    assert!(
        pos_tests < pos_examples,
        "expected tests/handler_test.go (pos {}) before examples/demo.go (pos {})\nOutput:\n{}",
        pos_tests,
        pos_examples,
        text
    );
}
