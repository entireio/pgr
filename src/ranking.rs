/// Truncate a line to at most 180 characters.
/// If truncated, append the ellipsis character '…'.
/// Truncation respects UTF-8 char boundaries.
pub fn truncate_line(line: &str) -> String {
    const MAX_CHARS: usize = 180;
    let char_count = line.chars().count();
    if char_count <= MAX_CHARS {
        return line.to_string();
    }
    // Collect first MAX_CHARS chars, then append ellipsis
    let truncated: String = line.chars().take(MAX_CHARS).collect();
    format!("{}…", truncated)
}

/// Detect whether `content` (a single line or small snippet) looks like a
/// code definition.  Detection is language-agnostic and works by prefix-matching
/// the trimmed line against a fixed set of keywords.
///
/// Lines that start a comment (`//`, `#`, `/*`, `*`) are skipped immediately
/// and return `false`.
pub fn is_definition(content: &str) -> bool {
    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        // Skip comment lines
        if trimmed.starts_with("//")
            || trimmed.starts_with('#')
            || trimmed.starts_with("/*")
            || trimmed.starts_with('*')
        {
            continue;
        }
        if matches_definition_prefix(trimmed) {
            return true;
        }
    }
    false
}

fn matches_definition_prefix(trimmed: &str) -> bool {
    // Rust
    if trimmed.starts_with("fn ")
        || trimmed.starts_with("pub fn ")
        || trimmed.starts_with("pub(crate) fn ")
        || trimmed.starts_with("struct ")
        || trimmed.starts_with("pub struct ")
        || trimmed.starts_with("enum ")
        || trimmed.starts_with("pub enum ")
        || trimmed.starts_with("trait ")
        || trimmed.starts_with("pub trait ")
        || trimmed.starts_with("impl ")
        || trimmed.starts_with("impl<")
        || trimmed.starts_with("type ")
        || trimmed.starts_with("pub type ")
        || trimmed.starts_with("mod ")
        || trimmed.starts_with("pub mod ")
    {
        return true;
    }

    // Go
    if trimmed.starts_with("func ") {
        return true;
    }
    // Go: `type Foo struct` / `type Foo interface`
    if trimmed.starts_with("type ") {
        let rest = trimmed.strip_prefix("type ").unwrap_or("");
        // rest should contain "struct" or "interface" somewhere after the name
        if rest.contains(" struct") || rest.contains(" interface") {
            return true;
        }
    }

    // Python
    if trimmed.starts_with("class ") || trimmed.starts_with("def ") {
        return true;
    }

    // JS / TS
    if trimmed.starts_with("function ")
        || trimmed.starts_with("class ")
        || trimmed.starts_with("export ")
        || trimmed.starts_with("const ")
        || trimmed.starts_with("let ")
        || trimmed.starts_with("var ")
        || trimmed.starts_with("interface ")
        || trimmed.starts_with("module.exports")
    {
        return true;
    }

    // C / C++
    if trimmed.starts_with("struct ")
        || trimmed.starts_with("enum ")
        || trimmed.starts_with("union ")
        || trimmed.starts_with("typedef ")
    {
        return true;
    }

    false
}

/// Classify a file path into a priority bucket.
///
/// | Value | Meaning |
/// |-------|---------|
/// | 0     | Regular source file (highest rank – shown first) |
/// | 1     | Test file |
/// | 2     | Low-priority file (examples, vendor, fixtures, …) |
pub fn file_priority(path: &str) -> u8 {
    // Low-priority directory components (checked before test so that e.g.
    // "vendor/testdata/foo_test.go" is still low-priority).
    const LOW_DIRS: &[&str] = &[
        "example",
        "examples",
        "sample",
        "samples",
        "fixture",
        "fixtures",
        "mock",
        "mocks",
        "testdata",
        "vendor",
        "node_modules",
        "third_party",
    ];

    const TEST_DIRS: &[&str] = &["test", "tests", "testing", "spec", "specs"];

    // Split the path into components using both Unix and Windows separators
    let components: Vec<&str> = path.split(['/', '\\']).collect();

    // Filename is the last component
    let filename = components.last().copied().unwrap_or("");

    // Check low-priority directories first
    for component in &components {
        let c = component.to_ascii_lowercase();
        if LOW_DIRS.contains(&c.as_str()) {
            return 2;
        }
    }

    // Check test directories
    for component in &components[..components.len().saturating_sub(1)] {
        let c = component.to_ascii_lowercase();
        if TEST_DIRS.contains(&c.as_str()) {
            return 1;
        }
    }

    // Check test filename patterns
    let fname_lower = filename.to_ascii_lowercase();
    if fname_lower.contains("_test.")
        || fname_lower.starts_with("test_")
        || fname_lower.contains(".test.")
        || fname_lower.contains(".spec.")
    {
        return 1;
    }

    0
}

// ---------------------------------------------------------------------------
// Unit tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -----------------------------------------------------------------------
    // truncate_line
    // -----------------------------------------------------------------------

    #[test]
    fn truncate_short_line_unchanged() {
        let short = "hello, world";
        assert_eq!(truncate_line(short), short);
    }

    #[test]
    fn truncate_exactly_180_chars_unchanged() {
        let line: String = "a".repeat(180);
        assert_eq!(truncate_line(&line), line);
    }

    #[test]
    fn truncate_181_chars() {
        let line: String = "a".repeat(181);
        let result = truncate_line(&line);
        // Should be 180 'a's followed by '…'
        assert!(result.ends_with('…'));
        assert_eq!(result.chars().count(), 181); // 180 + ellipsis char
        assert!(result.starts_with(&"a".repeat(180)));
    }

    #[test]
    fn truncate_long_line() {
        let line: String = "x".repeat(300);
        let result = truncate_line(&line);
        assert!(result.ends_with('…'));
        assert_eq!(result.chars().count(), 181);
    }

    #[test]
    fn truncate_empty_string() {
        assert_eq!(truncate_line(""), "");
    }

    #[test]
    fn truncate_multibyte_chars() {
        // Each '日' is 3 bytes; build a string of 200 such chars
        let line: String = "日".repeat(200);
        let result = truncate_line(&line);
        assert!(result.ends_with('…'));
        // First 180 chars should all be '日'
        let body: String = result.chars().take(180).collect();
        assert_eq!(body, "日".repeat(180));
    }

    #[test]
    fn truncate_mixed_ascii_and_multibyte() {
        // 100 ascii + 100 multibyte = 200 chars, should be truncated
        let line: String = "a".repeat(100) + &"é".repeat(100);
        let result = truncate_line(&line);
        assert!(result.ends_with('…'));
        assert_eq!(result.chars().count(), 181);
    }

    // -----------------------------------------------------------------------
    // is_definition — Go
    // -----------------------------------------------------------------------

    #[test]
    fn go_func_definition() {
        assert!(is_definition("func main() {"));
        assert!(is_definition("func (r *Receiver) Method() error {"));
    }

    #[test]
    fn go_type_struct() {
        assert!(is_definition("type Point struct {"));
        // Go type aliases also start with "type " and are treated as definitions
        // (they match the same `type ` prefix used by Rust type aliases)
        assert!(is_definition("type MyMap map[string]int"));
    }

    #[test]
    fn go_type_interface() {
        assert!(is_definition("type Reader interface {"));
    }

    // -----------------------------------------------------------------------
    // is_definition — Python
    // -----------------------------------------------------------------------

    #[test]
    fn python_def() {
        assert!(is_definition("def my_func(x, y):"));
        assert!(is_definition("    def inner():"));
    }

    #[test]
    fn python_class() {
        assert!(is_definition("class MyClass(Base):"));
    }

    // -----------------------------------------------------------------------
    // is_definition — Rust
    // -----------------------------------------------------------------------

    #[test]
    fn rust_fn() {
        assert!(is_definition("fn helper() -> bool {"));
        assert!(is_definition("pub fn public_fn() {"));
        assert!(is_definition("pub(crate) fn crate_fn() {"));
    }

    #[test]
    fn rust_struct() {
        assert!(is_definition("struct MyStruct {"));
        assert!(is_definition("pub struct PublicStruct {"));
    }

    #[test]
    fn rust_enum() {
        assert!(is_definition("enum Color {"));
        assert!(is_definition("pub enum Color {"));
    }

    #[test]
    fn rust_trait() {
        assert!(is_definition("trait Animal {"));
        assert!(is_definition("pub trait Animal {"));
    }

    #[test]
    fn rust_impl() {
        assert!(is_definition("impl MyStruct {"));
        assert!(is_definition("impl<T> Foo<T> {"));
    }

    #[test]
    fn rust_type_alias() {
        assert!(is_definition("type Result<T> = std::result::Result<T, Error>;"));
        assert!(is_definition("pub type Alias = u32;"));
    }

    #[test]
    fn rust_mod() {
        assert!(is_definition("mod utils;"));
        assert!(is_definition("pub mod api {"));
    }

    // -----------------------------------------------------------------------
    // is_definition — JS / TS
    // -----------------------------------------------------------------------

    #[test]
    fn js_function() {
        assert!(is_definition("function greet(name) {"));
    }

    #[test]
    fn js_class() {
        assert!(is_definition("class Animal {"));
    }

    #[test]
    fn js_export() {
        assert!(is_definition("export default function() {}"));
        assert!(is_definition("export const PI = 3.14;"));
    }

    #[test]
    fn js_const_let_var() {
        assert!(is_definition("const x = 42;"));
        assert!(is_definition("let mutable = 'hello';"));
        assert!(is_definition("var legacy = true;"));
    }

    #[test]
    fn ts_interface() {
        assert!(is_definition("interface Props {"));
    }

    #[test]
    fn js_module_exports() {
        assert!(is_definition("module.exports = { foo };"));
        assert!(is_definition("module.exports.bar = function() {};"));
    }

    // -----------------------------------------------------------------------
    // is_definition — C / C++
    // -----------------------------------------------------------------------

    #[test]
    fn c_struct() {
        assert!(is_definition("struct Point {"));
    }

    #[test]
    fn c_enum() {
        assert!(is_definition("enum Direction { NORTH, SOUTH };"));
    }

    #[test]
    fn c_union() {
        assert!(is_definition("union Data {"));
    }

    #[test]
    fn c_typedef() {
        assert!(is_definition("typedef unsigned long size_t;"));
    }

    // -----------------------------------------------------------------------
    // is_definition — comment skipping
    // -----------------------------------------------------------------------

    #[test]
    fn comment_line_slash_slash() {
        assert!(!is_definition("// func not_a_real_func() {}"));
        assert!(!is_definition("// def ignored():"));
    }

    #[test]
    fn comment_line_hash() {
        assert!(!is_definition("# def ignored():"));
        assert!(!is_definition("# class Nope:"));
    }

    #[test]
    fn comment_line_block() {
        assert!(!is_definition("/* struct hidden { */"));
        assert!(!is_definition("* fn also_ignored() {}"));
    }

    #[test]
    fn non_definition_line() {
        assert!(!is_definition("x = 1 + 2;"));
        assert!(!is_definition("return result;"));
        assert!(!is_definition(""));
    }

    #[test]
    fn multiline_content_with_definition() {
        // Only the line that starts with a definition keyword should trigger true
        let content = "// some comment\nx = 42;\nfn my_func() {";
        assert!(is_definition(content));
    }

    #[test]
    fn multiline_content_no_definition() {
        let content = "// some comment\nx = 42;\nreturn x;";
        assert!(!is_definition(content));
    }

    // -----------------------------------------------------------------------
    // file_priority
    // -----------------------------------------------------------------------

    #[test]
    fn priority_source_file() {
        assert_eq!(file_priority("src/main.rs"), 0);
        assert_eq!(file_priority("lib/foo.py"), 0);
        assert_eq!(file_priority("cmd/server/main.go"), 0);
    }

    #[test]
    fn priority_test_dir() {
        assert_eq!(file_priority("tests/integration.rs"), 1);
        assert_eq!(file_priority("test/helpers.py"), 1);
        assert_eq!(file_priority("spec/models/user_spec.rb"), 1);
        assert_eq!(file_priority("specs/api.ts"), 1);
        assert_eq!(file_priority("testing/mock_client.go"), 1);
    }

    #[test]
    fn priority_test_filename_underscore_test() {
        assert_eq!(file_priority("src/foo_test.go"), 1);
        assert_eq!(file_priority("src/bar_test.rs"), 1);
    }

    #[test]
    fn priority_test_filename_test_prefix() {
        assert_eq!(file_priority("src/test_utils.py"), 1);
    }

    #[test]
    fn priority_test_filename_dot_test() {
        assert_eq!(file_priority("src/app.test.ts"), 1);
        assert_eq!(file_priority("src/app.test.js"), 1);
    }

    #[test]
    fn priority_test_filename_dot_spec() {
        assert_eq!(file_priority("src/app.spec.ts"), 1);
        assert_eq!(file_priority("src/component.spec.jsx"), 1);
    }

    #[test]
    fn priority_vendor_dir() {
        assert_eq!(file_priority("vendor/github.com/foo/bar.go"), 2);
        assert_eq!(file_priority("node_modules/lodash/index.js"), 2);
        assert_eq!(file_priority("third_party/zlib/zlib.h"), 2);
    }

    #[test]
    fn priority_example_dir() {
        assert_eq!(file_priority("examples/hello_world.rs"), 2);
        assert_eq!(file_priority("example/demo.py"), 2);
    }

    #[test]
    fn priority_sample_dir() {
        assert_eq!(file_priority("samples/basic.go"), 2);
        assert_eq!(file_priority("sample/demo.ts"), 2);
    }

    #[test]
    fn priority_fixture_dir() {
        assert_eq!(file_priority("fixtures/data.json"), 2);
        assert_eq!(file_priority("fixture/response.xml"), 2);
    }

    #[test]
    fn priority_mock_dir() {
        assert_eq!(file_priority("mocks/client.go"), 2);
        assert_eq!(file_priority("mock/db.rs"), 2);
    }

    #[test]
    fn priority_testdata_dir() {
        assert_eq!(file_priority("testdata/input.txt"), 2);
    }

    #[test]
    fn priority_low_beats_test_dir() {
        // vendor/tests/* should be low-priority (2) since vendor check comes first
        assert_eq!(file_priority("vendor/tests/foo.go"), 2);
    }

    #[test]
    fn priority_nested_source() {
        assert_eq!(file_priority("src/core/engine/scheduler.rs"), 0);
    }

    #[test]
    fn priority_windows_style_path() {
        assert_eq!(file_priority("src\\main.rs"), 0);
        assert_eq!(file_priority("tests\\integration.rs"), 1);
        assert_eq!(file_priority("vendor\\lib\\foo.rs"), 2);
    }
}
