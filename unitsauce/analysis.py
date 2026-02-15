import ast
import difflib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback

from rich.syntax import Syntax
from rich.panel import Panel
from rich.spinner import Spinner
from rich.live import Live
from .utils import console, debug_log

def normalize(content: str):
    return [
        line.rstrip().replace("\r\n", "\n").replace("\r", "\n")
        for line in content.splitlines()
    ]

def show_diff(original, new, file_name):
    original_lines = normalize(original)
    new_lines = normalize(new)

    diff = difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=f"before/{file_name}",
        tofile=f"after/{file_name}",
        lineterm=""
    )

    diff_text = "\n".join(diff)

    if diff_text:
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title="Changes", border_style="green"))

    return diff_text

def changed_lines(diff):
    lines = []
    new_ln = None

    for line in diff.splitlines():
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            new_ln = int(m.group(1)) - 1
            continue
        
        if new_ln is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            new_ln += 1
            lines.append(new_ln)
        elif line.startswith("-") and not line.startswith("---"):
            pass
        else:
            new_ln += 1

    return lines

def get_failing_tests(path):
    with open(path + "/report.json") as f:
        report = json.load(f)

    failures = []
    for test in report["tests"]:
        if test["outcome"] == "failed":
            print("JSON DUMPS")
            print(json.dumps(test["call"], indent=2))

            failures.append({
                "file": test["nodeid"].split("::")[0],
                "nodeid": test["nodeid"],
                "function": test["nodeid"].split("::")[-1],
                "error": test["call"]["crash"]["message"],
                "crash_file": test["call"]["crash"]["path"],
            })

    return failures

def get_git_diff(path):
    changed_files = subprocess.run(
                    ["git", "diff", "--name-only", "HEAD~1", "--", ".", ":(exclude)tests"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    check=True
                )

    return changed_files.stdout.splitlines()

def get_single_file_diff(path, changed_file_path):
    changed_file_diff = subprocess.run(
                    ["git", "diff", "HEAD~1", "--", changed_file_path],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    check=True
                )

    return changed_file_diff.stdout

def index_file_functions(source):
    tree = ast.parse(source)
    funcs = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            funcs.append({
                "name": node.name,
                "start": node.lineno,
                "end": node.end_lineno,
                "node": node,
            })

    return funcs

def extract_function_source(code: str, func):
    lines = code.splitlines()
    return "\n".join(lines[func["start"] - 1 : func["end"]])


def split_functions_raw(code):
    """Split code into functions, keeping raw text with comments."""
    lines = code.splitlines()
    functions = {}
    current_name = None
    current_lines = []
    
    for line in lines:
        stripped_line = line.lstrip()
        if stripped_line.startswith('def '):
            if current_name:
                functions[current_name] = '\n'.join(current_lines)
            current_name = line.split('(')[0].replace('def ', '').strip()
            current_lines = [line]
        elif current_name:
            current_lines.append(line)
    
    if current_name:
        functions[current_name] = '\n'.join(current_lines)
    
    return functions

def read_file_content(file, path, is_file_path=False):
    if is_file_path:
        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
            file_content = f.read()
        return file, file_content
    
    file_path = next(Path(path).rglob(file), None)
    if not file_path:
        return None, None
    
    with open(file_path, encoding='utf-8', errors='ignore') as open_file:
        file_content = open_file.read()
    
    return file_path, file_content

def gather_context(diff, function_code):
    lines = changed_lines(diff)
    funcs = index_file_functions(function_code)

    affected = [] 

    for f in funcs:
        if any(f["start"] <= ln <= f["end"] for ln in lines):
            affected.append(extract_function_source(function_code, f))

    return affected

def run_tests(path):
    if os.path.exists(path):
            with Live(Spinner("dots", text="Running tests..."), console=console):
                result = subprocess.run(
                    ["python", "-m", "pytest", "--tb=short", "--json-report", "--json-report-file=report.json"],
                    cwd=path,
                    capture_output=True,
                    text=True
                )
            console.print()
            return result

def run_single_test(path, nodeid):
    result = subprocess.run(
        ["python", "-m", "pytest", nodeid, "-v"],
        cwd=path,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return True, ""
    else:
        return False, result.stderr
    

def validate_generated_code(code):
    try:
        tree = ast.parse(code)

    except SyntaxError as se:
        return False
    
    return True


def add_imports_to_file(file_path, new_imports):
    """Add imports to file after existing imports."""
    if not new_imports:
        return
    
    content = file_path.read_text()
    lines = content.splitlines()
    
    last_import_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            last_import_idx = i
    
    new_imports = [imp for imp in new_imports if imp not in content]
    
    if not new_imports:
        return
    
    insert_idx = last_import_idx + 1 if last_import_idx >= 0 else 0
    for imp in new_imports:
        lines.insert(insert_idx, imp)
        insert_idx += 1
    
    file_path.write_text('\n'.join(lines))


def extract_failure_file(traceback_text: str):
    pattern = r'File "([^"]+)", line (\d+)'
    matches = re.findall(pattern, traceback_text)

    if not matches:
        return None

    file_path, line_number = matches[-1]
    return {
        "file": file_path,
        "line": int(line_number)
    }