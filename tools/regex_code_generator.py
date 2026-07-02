#!/usr/bin/env python3
"""
Regex Code Generator

Generates ready-to-run regular expression code snippets in multiple languages
(Python, JavaScript, Go, Java, C#, PHP, Ruby, Rust) for a given regex pattern.

Usage:
    python regex_code_generator.py "([a-zA-Z0-9]+)@([a-zA-Z]+)\\.com" -m extract
"""

import sys
import argparse

def escape_pattern(pattern, lang):
    """Escapes regex patterns for strings in different languages."""
    if lang == 'python':
        # Raw string r"pattern"
        return f'r"{pattern}"'
    elif lang == 'go':
        # Backtick raw string `pattern`
        # If pattern contains backticks, escape them or use double quotes
        if '`' not in pattern:
            return f'`{pattern}`'
        return f'"{pattern.replace("\\", "\\\\").replace("\"", "\\\"")}"'
    elif lang == 'javascript':
        # Regex literal /pattern/
        # Escape any forward slashes
        escaped = pattern.replace('/', '\\/')
        return f'/{escaped}/'
    elif lang in ('java', 'csharp'):
        # Double backslashes
        escaped = pattern.replace('\\', '\\\\').replace('"', '\\"')
        if lang == 'csharp':
            # Verbatim string @"pattern"
            return f'@"{pattern.replace("\"", "\"\"")}"'
        return f'"{escaped}"'
    elif lang == 'rust':
        # Raw string r"pattern"
        if '"' not in pattern:
            return f'r"{pattern}"'
        return f'r#"{pattern}"#'
    elif lang in ('php', 'ruby'):
        # Double quotes or slash-delimited
        escaped = pattern.replace('\\', '\\\\').replace('"', '\\"')
        if lang == 'php':
            return f'"/{escaped.replace("/", "\\/")}/"'
        return f'/{pattern.replace("/", "\\/")}/'
    return f'"{pattern}"'

def escape_replacement(replace_val, lang):
    """Escapes replacement strings depending on language."""
    if not replace_val:
        return '""'
    if lang == 'python':
        return f'r"{replace_val}"'
    elif lang == 'javascript':
        return f'"{replace_val}"'
    elif lang == 'go':
        return f'"{replace_val}"'
    elif lang == 'rust':
        return f'"{replace_val}"'
    return f'"{replace_val}"'

def generate_python(pattern, mode, replace_val):
    pat = escape_pattern(pattern, 'python')
    rep = escape_replacement(replace_val, 'python')
    
    code = "import re\n\n"
    code += 'text = "Sample text to match"\n'
    code += f'pattern = {pat}\n\n'
    
    if mode == 'match':
        code += 'if re.search(pattern, text):\n'
        code += '    print("Match found!")\n'
        code += 'else:\n'
        code += '    print("No match.")\n'
    elif mode == 'extract':
        code += 'matches = re.findall(pattern, text)\n'
        code += 'print(f"Extracted: {matches}")\n'
        code += '# For group captures:\n'
        code += 'match = re.search(pattern, text)\n'
        code += 'if match:\n'
        code += '    # print(match.group(1))\n'
        code += '    pass\n'
    elif mode == 'replace':
        code += f'result = re.sub(pattern, {rep}, text)\n'
        code += 'print(f"Replaced result: {result}")\n'
    return code

def generate_javascript(pattern, mode, replace_val):
    pat = escape_pattern(pattern, 'javascript')
    rep = escape_replacement(replace_val, 'javascript')
    
    code = 'const text = "Sample text to match";\n'
    code += f'const regex = {pat};\n\n'
    
    if mode == 'match':
        code += 'if (regex.test(text)) {\n'
        code += '    console.log("Match found!");\n'
        code += '} else {\n'
        code += '    console.log("No match.");\n'
        code += '}\n'
    elif mode == 'extract':
        code += 'const matches = text.match(regex);\n'
        code += 'console.log("Extracted:", matches);\n'
        code += '// For global capture groups:\n'
        code += f'const regexGlobal = {pat}g;\n'
        code += 'let match;\n'
        code += 'while ((match = regexGlobal.exec(text)) !== null) {\n'
        code += '    // console.log("Group 1:", match[1]);\n'
        code += '}\n'
    elif mode == 'replace':
        code += f'const result = text.replace(regex, {rep});\n'
        code += 'console.log("Replaced result:", result);\n'
    return code

def generate_go(pattern, mode, replace_val):
    pat = escape_pattern(pattern, 'go')
    rep = escape_replacement(replace_val, 'go')
    
    code = "package main\n\nimport (\n\t\"fmt\"\n\t\"regexp\"\n)\n\n"
    code += "func main() {\n"
    code += "\ttext := \"Sample text to match\"\n"
    code += f"\tpattern := {pat}\n\n"
    
    if mode == 'match':
        code += "\tmatched, _ := regexp.MatchString(pattern, text)\n"
        code += "\tif matched {\n\t\tfmt.Println(\"Match found!\")\n\t} else {\n\t\tfmt.Println(\"No match.\")\n\t}\n"
    elif mode == 'extract':
        code += "\tre := regexp.MustCompile(pattern)\n"
        code += "\tmatches := re.FindStringSubmatch(text)\n"
        code += "\tfmt.Println(\"Extracted:\", matches)\n"
        code += "\tif len(matches) > 1 {\n\t\t// fmt.Println(\"Group 1:\", matches[1])\n\t}\n"
    elif mode == 'replace':
        code += "\tre := regexp.MustCompile(pattern)\n"
        code += f"\tresult := re.ReplaceAllString(text, {rep})\n"
        code += "\tfmt.Println(\"Replaced result:\", result)\n"
    code += "}\n"
    return code

def generate_rust(pattern, mode, replace_val):
    pat = escape_pattern(pattern, 'rust')
    rep = escape_replacement(replace_val, 'rust')
    
    code = "// Add dependency: regex = \"1.9\"\n"
    code += "use regex::Regex;\n\n"
    code += "fn main() {\n"
    code += "    let text = \"Sample text to match\";\n"
    code += f"    let re = Regex::new({pat}).unwrap();\n\n"
    
    if mode == 'match':
        code += "    if re.is_match(text) {\n"
        code += "        println!(\"Match found!\");\n"
        code += "    } else {\n"
        code += "        println!(\"No match.\");\n"
        code += "    }\n"
    elif mode == 'extract':
        code += "    if let Some(caps) = re.captures(text) {\n"
        code += "        println!(\"Extracted Group 0: {}\", &caps[0]);\n"
        code += "        if caps.len() > 1 {\n"
        code += "            // println!(\"Extracted Group 1: {}\", &caps[1]);\n"
        code += "        }\n"
        code += "    }\n"
    elif mode == 'replace':
        code += f"    let result = re.replace_all(text, {rep});\n"
        code += "    println!(\"Replaced result: {}\", result);\n"
    code += "}\n"
    return code

def generate_java(pattern, mode, replace_val):
    pat = escape_pattern(pattern, 'java')
    rep = escape_replacement(replace_val, 'java')
    
    code = "import java.util.regex.Matcher;\n"
    code += "import java.util.regex.Pattern;\n\n"
    code += "public class RegexExample {\n"
    code += "    public static void main(String[] args) {\n"
    code += "        String text = \"Sample text to match\";\n"
    code += f"        String patternString = {pat};\n"
    code += "        Pattern pattern = Pattern.compile(patternString);\n"
    code += "        Matcher matcher = pattern.matcher(text);\n\n"
    
    if mode == 'match':
        code += "        if (matcher.find()) {\n"
        code += "            System.out.println(\"Match found!\");\n"
        code += "        } else {\n"
        code += "            System.out.println(\"No match.\");\n"
        code += "        }\n"
    elif mode == 'extract':
        code += "        while (matcher.find()) {\n"
        code += "            System.out.println(\"Extracted: \" + matcher.group(0));\n"
        code += "            if (matcher.groupCount() >= 1) {\n"
        code += "                // System.out.println(\"Group 1: \" + matcher.group(1));\n"
        code += "            }\n"
        code += "        }\n"
    elif mode == 'replace':
        code += f"        String result = matcher.replaceAll({rep});\n"
        code += "        System.out.println(\"Replaced result: \" + result);\n"
    code += "    }\n"
    code += "}\n"
    return code

def generate_csharp(pattern, mode, replace_val):
    pat = escape_pattern(pattern, 'csharp')
    rep = escape_replacement(replace_val, 'csharp')
    
    code = "using System;\n"
    code += "using System.Text.RegularExpressions;\n\n"
    code += "class Program {\n"
    code += "    static void Main() {\n"
    code += "        string text = \"Sample text to match\";\n"
    code += f"        string pattern = {pat};\n\n"
    
    if mode == 'match':
        code += "        if (Regex.IsMatch(text, pattern)) {\n"
        code += "            Console.WriteLine(\"Match found!\");\n"
        code += "        } else {\n"
        code += "            Console.WriteLine(\"No match.\");\n"
        code += "        }\n"
    elif mode == 'extract':
        code += "        Match match = Regex.Match(text, pattern);\n"
        code += "        if (match.Success) {\n"
        code += "            Console.WriteLine(\"Extracted: \" + match.Value);\n"
        code += "            if (match.Groups.Count > 1) {\n"
        code += "                // Console.WriteLine(\"Group 1: \" + match.Groups[1].Value);\n"
        code += "            }\n"
        code += "        }\n"
    elif mode == 'replace':
        code += f"        string result = Regex.Replace(text, pattern, {rep});\n"
        code += "        Console.WriteLine(\"Replaced result: \" + result);\n"
    code += "    }\n"
    code += "}\n"
    return code

def generate_php(pattern, mode, replace_val):
    pat = escape_pattern(pattern, 'php')
    rep = escape_replacement(replace_val, 'php')
    
    code = "<?php\n"
    code += "$text = \"Sample text to match\";\n"
    code += f"$pattern = {pat};\n\n"
    
    if mode == 'match':
        code += "if (preg_match($pattern, $text)) {\n"
        code += "    echo \"Match found!\\n\";\n"
        code += "} else {\n"
        code += "    echo \"No match.\\n\";\n"
        code += "}\n"
    elif mode == 'extract':
        code += "$matches = [];\n"
        code += "preg_match($pattern, $text, $matches);\n"
        code += "print_r($matches);\n"
        code += "if (count($matches) > 1) {\n"
        code += "    // echo \"Group 1: \" . $matches[1] . \"\\n\";\n"
        code += "}\n"
    elif mode == 'replace':
        code += f"$result = preg_replace($pattern, {rep}, $text);\n"
        code += "echo \"Replaced result: \" . $result . \"\\n\";\n"
    return code

def generate_ruby(pattern, mode, replace_val):
    pat = escape_pattern(pattern, 'ruby')
    rep = escape_replacement(replace_val, 'ruby')
    
    code = "text = \"Sample text to match\"\n"
    code += f"regex = {pat}\n\n"
    
    if mode == 'match':
        code += "if text.match?(regex)\n"
        code += "  puts \"Match found!\"\n"
        code += "else\n"
        code += "  puts \"No match.\"\n"
        code += "end\n"
    elif mode == 'extract':
        code += "match = text.match(regex)\n"
        code += "if match\n"
        code += "  puts \"Extracted: #{match[0]}\"\n"
        code += "  # puts \"Group 1: #{match[1]}\"\n"
        code += "end\n"
    elif mode == 'replace':
        code += f"result = text.gsub(regex, {rep})\n"
        code += "puts \"Replaced result: #{result}\"\n"
    return code

def main():
    parser = argparse.ArgumentParser(
        description="Generate copy-pasteable regex code snippets in multiple programming languages.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "pattern",
        help="Regular expression pattern to generate code for."
    )
    
    parser.add_argument(
        "-m", "--mode",
        choices=['match', 'extract', 'replace'],
        default='match',
        help="Regular expression operation mode (default: 'match')"
    )
    
    parser.add_argument(
        "-r", "--replace-value",
        default="",
        help="Replacement value (required for 'replace' mode)"
    )
    
    parser.add_argument(
        "-l", "--languages",
        help="Comma-separated list of languages to restrict to (e.g. 'python,javascript,go')"
    )
    
    args = parser.parse_args()
    
    # Restrict languages if needed
    lang_map = {
        'python': ('Python', generate_python),
        'javascript': ('JavaScript (Node.js/Web)', generate_javascript),
        'go': ('Go (Golang)', generate_go),
        'rust': ('Rust', generate_rust),
        'java': ('Java', generate_java),
        'csharp': ('C# (.NET)', generate_csharp),
        'php': ('PHP', generate_php),
        'ruby': ('Ruby', generate_ruby),
    }
    
    selected_langs = list(lang_map.keys())
    if args.languages:
        input_langs = [l.strip().lower() for l in args.languages.split(',')]
        selected_langs = [l for l in input_langs if l in lang_map]
        if not selected_langs:
            print("Error: No valid languages selected.", file=sys.stderr)
            return 1

    print("Regex Code Generator")
    print(f"Pattern : {args.pattern}")
    print(f"Mode    : {args.mode.upper()}")
    if args.mode == 'replace':
        print(f"Replace : {args.replace_value}")
    print("=" * 60 + "\n")
    
    for lang in selected_langs:
        label, generator = lang_map[lang]
        print(f"// --- {label} " + "-" * (50 - len(label)))
        code = generator(args.pattern, args.mode, args.replace_value)
        # Highlight code blocks
        print(code.strip())
        print("-" * 60 + "\n")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
