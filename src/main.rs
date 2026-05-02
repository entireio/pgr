mod ranking;
mod read;
mod search;
mod tools;

use serde::Deserialize;
use serde_json::Value;
use std::io::{self, BufRead, Write};

#[derive(Deserialize)]
struct JsonRpcRequest {
    #[allow(dead_code)]
    jsonrpc: String,
    id: Option<Value>,
    method: String,
    #[serde(default)]
    params: Value,
}

fn respond(id: &Value, result: Value) {
    let response = serde_json::json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": result
    });
    let mut stdout = io::stdout();
    let _ = writeln!(stdout, "{}", response);
    let _ = stdout.flush();
}

fn respond_error(id: &Value, code: i64, message: &str) {
    let response = serde_json::json!({
        "jsonrpc": "2.0",
        "id": id,
        "error": {
            "code": code,
            "message": message
        }
    });
    let mut stdout = io::stdout();
    let _ = writeln!(stdout, "{}", response);
    let _ = stdout.flush();
}

fn main() {
    let stdin = io::stdin();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };

        // Skip empty lines
        if line.trim().is_empty() {
            continue;
        }

        // Skip unparseable JSON
        let request: JsonRpcRequest = match serde_json::from_str(&line) {
            Ok(r) => r,
            Err(_) => continue,
        };

        match request.method.as_str() {
            "initialize" => {
                let id = request.id.unwrap_or(Value::Null);
                respond(
                    &id,
                    serde_json::json!({
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "pgr",
                            "version": "3.0.0"
                        }
                    }),
                );
            }
            "notifications/initialized" => {
                // Notification — no response
            }
            "tools/list" => {
                let id = request.id.unwrap_or(Value::Null);
                respond(&id, tools::tool_definitions());
            }
            "tools/call" => {
                let id = request.id.unwrap_or(Value::Null);
                let name = request
                    .params
                    .get("name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let arguments = request
                    .params
                    .get("arguments")
                    .cloned()
                    .unwrap_or(Value::Object(serde_json::Map::new()));
                let result = tools::handle_tool_call(name, &arguments);
                respond(
                    &id,
                    serde_json::json!({
                        "content": [
                            {
                                "type": "text",
                                "text": result
                            }
                        ]
                    }),
                );
            }
            other => {
                // Only respond if there's an id (not a notification)
                if let Some(id) = request.id {
                    respond_error(&id, -32601, &format!("Unknown method: {}", other));
                }
            }
        }
    }
}
