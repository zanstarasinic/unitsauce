import ast
import difflib
import json
import os
from pathlib import Path
import re
import subprocess
from .utils import console

def normalize(content: str):
    """
    Normalize line endings in content for consistent diff comparison.
    
    Args:
        content: String content to normalize
        
    Returns:
        List of lines with trailing whitespace and line endings normalized
    """
    return [
        line.rstrip().replace("\r\n", "\n").replace("\r", "\n")
        for line in content.splitlines()
    ]

def show_diff(original, new, file_name):
    """
    Generate and display a unified diff between original and new content.
    
    Args:
        original: Original file content
        new: New file content
        file_name: Name of the file (for diff header)
        
    Returns:
        Diff string in unified format
    """

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


    return diff_text

def changed_lines(diff):
    """
    Extract line numbers that were added or modified from a unified diff.
    
    Parses diff hunk headers to track line positions, then collects
    line numbers for all added lines (lines starting with '+').
    
    Args:
        diff: Unified diff string
        
    Returns:
        List of line numbers (in the new file) that were modified
    """
    modified_lines = []
    current_line = 0

    for line in diff.splitlines():
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            if match:
                current_line = int(match.group(1))
            continue
        
        if current_line == 0:
            continue
        
        if line.startswith("+") and not line.startswith("+++"):
            modified_lines.append(current_line)
            current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        else:
            current_line += 1

    return modified_lines

def get_failing_tests(path):
    """
    Parse pytest JSON report to extract failing test information.
    
    Args:
        path: Repository root path containing report.json
        
    Returns:
        List of dicts with keys: file, nodeid, function, error, crash_file, crash_line
    """
    failures = []
    try:
        with open(Path(path) / "report.json") as f:
            report = json.load(f)

        for test in report["tests"]:
            if test["outcome"] == "failed":
                failures.append({
                    "file": test["nodeid"].split("::")[0],
                    "nodeid": test["nodeid"],
                    "function": test["nodeid"].split("::")[-1],
                    "error": test["call"]["crash"]["message"],
                    "crash_file": test["call"]["crash"]["path"],
                    "crash_line": test["call"]["crash"]["lineno"]
                })
    except Exception as e:
        console.print("report.json doesn't exist or is malformed")

    return failures

def get_git_diff(path):
    """
    Get list of changed Python files from git diff.
    
    In GitHub Actions PR context, compares against base branch.
    Otherwise, compares against previous commit (HEAD~1).
    
    Args:
        path: Repository root path
        
    Returns:
        List of changed file paths (excluding tests directory)
    """
    base_ref = os.environ.get("GITHUB_BASE_REF")
    
    if base_ref:
        subprocess.run(
            ["git", "fetch", "origin", base_ref],
            cwd=path,
            capture_output=True,
            check=True
        )
        compare_target = f"origin/{base_ref}"
    else:
        compare_target = "HEAD~1"
    
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", compare_target, "--", ".", ":(exclude)tests"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.splitlines()
    
    except subprocess.CalledProcessError:
        return []

def get_single_file_diff(path, changed_file_path):
    """
    Get the full diff for a single file.
    
    In GitHub Actions PR context, compares against base branch.
    Otherwise, compares against previous commit (HEAD~1).
    
    Args:
        path: Repository root path
        changed_file_path: Path to the file relative to repo root
        
    Returns:
        Diff string for the specified file
    """
    base_ref = os.environ.get("GITHUB_BASE_REF")
    
    if base_ref:
        compare_target = f"origin/{base_ref}"
    else:
        compare_target = "HEAD~1"
    
    try:
        result = subprocess.run(
            ["git", "diff", compare_target, "--", changed_file_path],
            cwd=path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    
    except subprocess.CalledProcessError:
        return ""

def index_file_functions(source):
    """
    Parse source code and extract all function definitions with their locations.
    
    Args:
        source: Python source code string
        
    Returns:
        List of dicts with keys: name, start, end, node
    """
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
    """
    Extract the source code of a function given its location info.
    
    Args:
        code: Full source code string
        func: Dict with 'start' and 'end' line numbers
        
    Returns:
        String containing the function's source code
    """
    lines = code.splitlines()
    return "\n".join(lines[func["start"] - 1 : func["end"]])


def split_functions_raw(code):
    """
    Split code into individual functions, preserving raw text with comments.
    
    Unlike AST parsing, this keeps comments and formatting intact.
    
    Args:
        code: Python source code containing one or more functions
        
    Returns:
        Dict mapping function names to their raw source code
    """
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

def read_file_content(filename, search_path):
    """
    Read content from a file, searching by name..
    
    Args:
        filename: Filename to search for
        search_path: Directory to search in
        
    Returns:
        Tuple of (file_path, file_content) or (None, None) if not found
    """
    file_path = next(Path(search_path).rglob(filename), None)
    if not file_path:
        return None, None
    
    with open(file_path, encoding='utf-8', errors='ignore') as open_file:
        file_content = open_file.read()
    
    return file_path, file_content

    

def gather_context(diff, function_code):
    """
    Find functions that were affected by changes in a diff.
    
    Cross-references changed line numbers with function boundaries
    to identify which functions contain modifications.
    
    Args:
        diff: Unified diff string
        function_code: Full source code of the file
        
    Returns:
        List of source code strings for affected functions
    """
    lines = changed_lines(diff)
    funcs = index_file_functions(function_code)

    affected = [] 

    for f in funcs:
        if any(f["start"] <= ln <= f["end"] for ln in lines):
            affected.append(extract_function_source(function_code, f))

    return affected

def run_tests(path):
    """
    Run pytest and generate JSON report.
    
    Args:
        path: Repository root path
        
    Returns:
        CompletedProcess result from pytest execution
    """
    if Path(path).exists():
        result = subprocess.run(
            ["python", "-m", "pytest", "--tb=short", "--json-report", "--json-report-file=report.json"],
            cwd=path,
            capture_output=True,
            text=True)
        return result

def run_single_test(path, nodeid):
    """
    Run a single test by its pytest node ID.
    
    Args:
        path: Repository root path
        nodeid: Pytest node ID (e.g., 'tests/test_foo.py::test_bar')
        
    Returns:
        Tuple of (passed: bool, error: str)
    """
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
    """
    Check if generated code is valid Python syntax.
    
    Args:
        code: Python source code string
        
    Returns:
        True if code parses successfully, False otherwise
    """
    try:
        ast.parse(code)

    except SyntaxError as se:
        return False
    
    return True


def add_imports_to_file(file_path, new_imports):
    """
    Add import statements to a file after existing imports.
    
    Avoids duplicates by checking if import already exists in file.
    
    Args:
        file_path: Path object to the file
        new_imports: List of import statement strings to add
    """
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
