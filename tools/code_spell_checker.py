#!/usr/bin/env python3
"""
Code Spell Checker - Spot spelling errors in comments and string literals

Scans source code files recursively for spelling mistakes. It automatically
parses identifiers by splitting camelCase, snake_case, and PascalCase, and
checks sub-words against a built-in dictionary of common tech and English words.

Usage:
    python tools/code_spell_checker.py <path> [options]

Options:
    path                File or directory to scan
    -e, --exclude       Dir/file patterns to ignore (default: .git, __pycache__, node_modules, venv)
    -w, --add-word      Additional custom words to ignore (can be specified multiple times)
    -x, --ext           File extensions to check, comma-separated (default: py,js,ts,html,css,md,json,c,cpp,go,rs,java)
    -v, --verbose       Show scanned files even if no errors are found

Example:
    python tools/code_spell_checker.py tools/ -w customword -w anotherword
"""

import argparse
import sys
import re
import os

# ANSI escape codes
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"

# A basic dictionary of common English and programming words
# Built-in to make the script completely standalone and fast
COMMON_WORDS = {
    # Pronouns, prepositions, conjunctions, verbs
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself", "it", "its", "itself", "they", "them", "their",
    "theirs", "themselves", "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", "the",
    "and", "but", "if", "or", "because", "as", "until", "while", "of", "at", "by", "for", "with", "about", "against",
    "between", "into", "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", "in",
    "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "can", "will", "just", "should", "now", "get", "go", "make", "would",
    
    # Common English Nouns/Adjectives/Verbs
    "time", "year", "people", "way", "day", "man", "thing", "woman", "life", "child", "world", "school", "state",
    "family", "student", "group", "country", "problem", "hand", "part", "place", "case", "week", "company", "system",
    "program", "question", "work", "number", "night", "point", "home", "water", "room", "write", "read", "check",
    "list", "file", "path", "name", "type", "data", "size", "bytes", "bits", "error", "warning", "success", "fail",
    "run", "start", "stop", "begin", "end", "finish", "complete", "total", "count", "index", "key", "value", "item",
    "user", "admin", "client", "server", "host", "port", "network", "socket", "connection", "request", "response",
    "header", "body", "query", "param", "parameter", "arg", "argument", "option", "flag", "config", "configuration",
    "setting", "setup", "install", "update", "delete", "create", "remove", "add", "insert", "select", "find", "search",
    "replace", "match", "pattern", "regex", "regular", "expression", "string", "character", "char", "text", "line",
    "word", "sentence", "paragraph", "document", "image", "file", "directory", "folder", "path", "link", "url", "uri",
    "email", "address", "phone", "number", "date", "time", "second", "minute", "hour", "day", "month", "year",
    "format", "style", "color", "theme", "layout", "design", "width", "height", "margin", "padding", "border",
    "font", "size", "weight", "bold", "italic", "underline", "align", "text", "background", "foreground", "opacity",
    "visible", "hidden", "display", "position", "top", "bottom", "left", "right", "center", "middle", "vertical",
    "horizontal", "length", "range", "min", "max", "minimum", "maximum", "average", "sum", "math", "calculator",
    "number", "integer", "float", "double", "decimal", "binary", "octal", "hex", "hexadecimal", "boolean", "true",
    "false", "null", "none", "void", "empty", "valid", "invalid", "verify", "validate", "check", "test", "debug",
    "trace", "log", "logger", "print", "write", "output", "input", "read", "open", "close", "save", "load", "import",
    "export", "require", "include", "define", "class", "object", "instance", "method", "function", "variable",
    "constant", "literal", "array", "list", "dict", "dictionary", "map", "set", "tuple", "struct", "enum", "union",
    
    # Common Tech/Programming Terms
    "args", "kwargs", "init", "main", "self", "cls", "super", "utils", "helper", "helpers", "lib", "library",
    "module", "package", "dependency", "version", "build", "release", "deploy", "env", "environment", "global",
    "local", "scope", "closure", "lambda", "yield", "async", "await", "thread", "process", "task", "job", "queue",
    "stack", "heap", "buffer", "cache", "memory", "cpu", "gpu", "disk", "storage", "database", "sql", "sqlite",
    "mysql", "postgres", "nosql", "redis", "mongo", "json", "xml", "yaml", "yml", "toml", "ini", "csv", "tsv",
    "html", "css", "js", "ts", "jsx", "tsx", "py", "java", "cpp", "c", "go", "rs", "rust", "php", "ruby", "rb",
    "swift", "kotlin", "kt", "shell", "bash", "zsh", "powershell", "cmd", "git", "commit", "push", "pull", "clone",
    "fork", "branch", "merge", "rebase", "diff", "patch", "status", "stage", "stash", "repo", "repository",
    "github", "gitlab", "bitbucket", "docker", "container", "image", "compose", "kubernetes", "pod", "node",
    "api", "rest", "graphql", "grpc", "soap", "http", "https", "ftp", "ssh", "ssl", "tls", "tcp", "udp", "ip",
    "dns", "dhcp", "mac", "subnet", "gateway", "router", "switch", "ping", "pong", "payload", "token", "auth",
    "oauth", "jwt", "login", "logout", "signin", "signout", "register", "signup", "password", "username", "email",
    "otp", "totp", "mfa", "2fa", "key", "secret", "cert", "certificate", "crypto", "hash", "md5", "sha", "encrypt",
    "decrypt", "cipher", "salt", "iv", "signature", "uuid", "guid", "nanoid", "id", "identifier", "temp", "tmp",
    "unix", "linux", "macos", "windows", "android", "ios", "unix", "posix", "std", "stdout", "stderr", "stdin",
    "getattr", "setattr", "hasattr", "delattr", "repr", "str", "unicode", "ascii", "utf", "ansi", "ascii",
    "mock", "stub", "fake", "fixture", "pytest", "unittest", "assert", "assertion", "expect", "should",
    "lint", "linter", "prettier", "format", "formatter", "beautify", "minify", "minify", "gzip", "tar", "zip",
    "unzip", "compress", "decompress", "archive", "backup", "restore", "sync", "async", "callback", "promise",
    "observable", "stream", "event", "listener", "handler", "emitter", "trigger", "action", "reducer", "store",
    "state", "props", "context", "hook", "effect", "ref", "component", "element", "node", "tree", "graph",
    "node", "edge", "vertex", "path", "route", "router", "middleware", "controller", "model", "view", "template",
    "render", "mount", "unmount", "click", "hover", "focus", "blur", "submit", "change", "input", "keypress",
    "keydown", "keyup", "scroll", "resize", "load", "unload", "error", "abort", "timeout", "delay", "interval",
    "timer", "sleep", "wait", "defer", "schedule", "cron", "timezone", "tz", "utc", "gmt", "epoch", "timestamp",
    "parse", "stringify", "serialize", "deserialize", "encode", "decode", "escape", "unescape", "sanitize",
    "clean", "dirty", "raw", "safe", "unsafe", "strict", "lax", "warn", "info", "debug", "error", "critical",
    "fatal", "trace", "verbose", "quiet", "silent", "force", "dry", "run", "yes", "no", "always", "never",
    "default", "custom", "override", "extend", "inherit", "prototype", "factory", "singleton", "builder",
    "adapter", "decorator", "facade", "proxy", "observer", "strategy", "command", "mediator", "memento",
    "state", "visitor", "iterator", "generator", "yield", "iterable", "collection", "cursor", "query",
    "fetch", "axios", "ajax", "xhr", "cors", "origin", "header", "cookie", "session", "cache", "expire",
    "ttl", "max", "age", "keep", "alive", "agent", "browser", "chrome", "firefox", "safari", "edge", "opera",
    "webkit", "gecko", "blink", "engine", "platform", "os", "arch", "x86", "x64", "arm", "arm64", "m1", "m2",
    "intel", "amd", "nvidia", "cuda", "driver", "kernel", "shell", "terminal", "console", "tty", "pty",
    "stdin", "stdout", "stderr", "file", "descriptor", "fd", "pipe", "redirect", "stream", "buffer",
    "chunk", "blob", "buffer", "arraybuffer", "typedarray", "int8", "uint8", "int16", "uint16", "int32",
    "uint32", "float32", "float64", "bigint", "numeric", "number", "math", "abs", "ceil", "floor", "round",
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "log", "log10", "exp", "pow", "sqrt", "cbrt",
    "random", "rand", "seed", "uuid", "guid", "entropy", "hash", "md5", "sha1", "sha256", "sha512",
    "hmac", "kdf", "pbkdf2", "bcrypt", "scrypt", "argon2", "pbkdf", "pkcs", "rsa", "dsa", "ecdsa", "dh",
    "jwt", "jws", "jwe", "jwk", "jwks", "saml", "ldap", "active", "directory", "auth0", "firebase",
    "cognito", "okta", "keycloak", "identity", "provider", "access", "refresh", "token", "scope",
    "say", "hello", "world", "cli", "shebang", "mit", "license", "copyright", "author"
}

# Regex to capture string literals and comments in various languages
# Python-style: # comment, ''' docstring ''', """ docstring """, 'string', "string"
# C/JS style: // comment, /* comment */, 'string', "string", `string`
COMMENT_STRING_REGEX = re.compile(
    r'(?P<comment_single>#.*|//.*)|'
    r'(?P<comment_multi>/\*[\s\S]*?\*/|"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')|'
    r'(?P<string>\'(?:\\\\\'|[^\'\n])*\'|"(?:\\\\"|[^"\n])*"|`(?:\\\\`|[^`])*`)'
)

WORD_RE = re.compile(r'\b[a-zA-Z]{3,15}\b')

def split_identifier(identifier):
    """
    Split camelCase, snake_case, PascalCase, or UPPER_CASE into sub-words.
    e.g. 'xmlHttpResponse' -> ['xml', 'http', 'response']
    """
    # First split by underscores/hyphens
    parts = re.split(r'[-_]+', identifier)
    sub_words = []
    for part in parts:
        # Split by camel/Pascal case boundaries
        # e.g., 'xmlHttpResponse' -> 'xml', 'Http', 'Response'
        camel_parts = re.findall(r'[a-zA-Z][^A-Z]*', part)
        if camel_parts:
            sub_words.extend(camel_parts)
        else:
            if part:
                sub_words.append(part)
    return [w.lower() for w in sub_words if len(w) >= 3]

def check_text(text, ignored_words):
    """Find spelling mistakes in raw text and return list of misspelled words."""
    misspelled = []
    # Find all words
    words = WORD_RE.findall(text)
    for w in words:
        # Lowercase for comparison
        w_lower = w.lower()
        if w_lower in COMMON_WORDS or w_lower in ignored_words:
            continue
            
        # Try splitting the word if it's composed of multiple parts (like camelCase or PascalCase)
        split_words = split_identifier(w)
        if len(split_words) > 1:
            all_parts_valid = True
            for part in split_words:
                if part not in COMMON_WORDS and part not in ignored_words:
                    all_parts_valid = False
                    break
            if all_parts_valid:
                continue
                
        misspelled.append(w)
    return misspelled

def scan_file(file_path, ignored_words):
    """Scan file for spelling mistakes in comments and strings."""
    issues = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        return [f"Error reading file: {e}"]
        
    # Split content into lines for line-number matching
    lines = content.split('\n')
    
    # We find all matches of comments and strings
    # To map matches back to line numbers, we scan line by line or use match offsets
    # A simple and robust line-by-line approach for finding comments/strings:
    for line_idx, line in enumerate(lines, start=1):
        # Scan each line for matches
        for match in COMMENT_STRING_REGEX.finditer(line):
            matched_text = match.group()
            # Clean matched text from syntax markers
            if matched_text.startswith('#'):
                text_to_check = matched_text[1:]
            elif matched_text.startswith('//'):
                text_to_check = matched_text[2:]
            elif matched_text.startswith('/*') and matched_text.endswith('*/'):
                text_to_check = matched_text[2:-2]
            elif matched_text.startswith('"""') and matched_text.endswith('"""'):
                text_to_check = matched_text[3:-3]
            elif matched_text.startswith("'''") and matched_text.endswith("'''"):
                text_to_check = matched_text[3:-3]
            elif matched_text.startswith("'") or matched_text.startswith('"') or matched_text.startswith('`'):
                text_to_check = matched_text[1:-1]
            else:
                text_to_check = matched_text
                
            typos = check_text(text_to_check, ignored_words)
            for typo in typos:
                issues.append({
                    "line": line_idx,
                    "word": typo,
                    "snippet": line.strip()
                })
                
    return issues

def main():
    parser = argparse.ArgumentParser(description="Code Spell Checker for comments and string literals")
    parser.add_argument("path", help="File or directory path to scan")
    parser.add_argument("-e", "--exclude", action="append", default=[], help="Directories/files to exclude")
    parser.add_argument("-w", "--add-word", action="append", default=[], help="Words to ignore")
    parser.add_argument("-x", "--ext", default="py,js,ts,html,css,md,json,c,cpp,go,rs,java", 
                        help="Extensions to scan (comma-separated)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show scanned files with no issues")
    
    args = parser.parse_args()
    
    # Build list of extensions
    extensions = {f".{ext.strip().lower()}" for ext in args.ext.split(",")}
    
    # Default excludes
    default_excludes = {".git", "__pycache__", "node_modules", "venv", ".idea", ".vscode"}
    excludes = default_excludes.union({p.strip() for p in args.exclude})
    
    # User-defined words to ignore
    ignored_words = {w.strip().lower() for w in args.add_word}
    
    target_path = args.path
    if not os.path.exists(target_path):
        print(f"{RED}Error: Path '{target_path}' does not exist.{RESET}", file=sys.stderr)
        return 1
        
    print(f"{BOLD}{GREEN}========================================={RESET}")
    print(f"{BOLD}{GREEN}            CODE SPELL CHECKER           {RESET}")
    print(f"{BOLD}{GREEN}========================================={RESET}")
    print(f"Scanning: {target_path}")
    print(f"Extensions: {', '.join(extensions)}")
    print(f"Excluding patterns: {', '.join(excludes)}")
    if ignored_words:
        print(f"Custom ignored words: {', '.join(ignored_words)}")
    print()
    
    files_scanned = 0
    total_issues = 0
    
    def walk_and_scan(path):
        nonlocal files_scanned, total_issues
        if os.path.isfile(path):
            _, ext = os.path.splitext(path)
            if ext.lower() in extensions:
                files_scanned += 1
                file_issues = scan_file(path, ignored_words)
                if file_issues:
                    total_issues += len(file_issues)
                    print(f"{BOLD}{YELLOW}📄 {path}{RESET}")
                    for issue in file_issues:
                        snippet = issue['snippet']
                        word = issue['word']
                        # Highlight the word in the snippet
                        highlighted_snippet = snippet.replace(word, f"{RED}{BOLD}{word}{RESET}")
                        print(f"  Line {issue['line']}: Misspelled '{RED}{word}{RESET}' in:")
                        print(f"    {highlighted_snippet}")
                    print()
                elif args.verbose:
                    print(f"{GREEN}📄 {path}: OK{RESET}")
        else:
            # Walk directory
            for root, dirs, files in os.walk(path):
                # Filter directories in-place for os.walk
                dirs[:] = [d for d in dirs if d not in excludes]
                
                for file in files:
                    _, ext = os.path.splitext(file)
                    if ext.lower() in extensions:
                        file_path = os.path.join(root, file)
                        files_scanned += 1
                        file_issues = scan_file(file_path, ignored_words)
                        if file_issues:
                            total_issues += len(file_issues)
                            print(f"{BOLD}{YELLOW}📄 {file_path}{RESET}")
                            for issue in file_issues:
                                snippet = issue['snippet']
                                word = issue['word']
                                highlighted_snippet = snippet.replace(word, f"{RED}{BOLD}{word}{RESET}")
                                print(f"  Line {issue['line']}: Misspelled '{RED}{word}{RESET}'")
                                print(f"    {highlighted_snippet}")
                            print()
                        elif args.verbose:
                            print(f"{GREEN}📄 {file_path}: OK{RESET}")

    walk_and_scan(target_path)
    
    print(f"{BOLD}{GREEN}========================================={RESET}")
    print(f"Scanned files: {files_scanned}")
    if total_issues > 0:
        print(f"Total potential typos found: {RED}{total_issues}{RESET}")
        return 1
    else:
        print(f"Spelling check passed! No errors found.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
