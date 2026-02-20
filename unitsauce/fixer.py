from pathlib import Path
from .llm import call_llm, diagnose
from .analysis import (
    add_imports_to_file,
    extract_function_source,
    gather_context,
    get_single_file_diff,
    index_file_functions,
    read_file_content,
    run_single_test,
    show_diff,
    split_functions_raw,
    validate_generated_code
)
from .models import FixContext, FixResult
from .prompts import fix_code_prompt, fix_test_prompt
from .utils import debug_log, is_test_file


def apply_fix(file_path, generated_code) -> bool:
    """
    Apply generated code fix to a file.
    
    Replaces existing functions with their fixed versions while
    preserving indentation for class methods.
    
    Args:
        file_path: Path object to the file to modify
        generated_code: String containing the fixed function(s)
    
    Returns:
        True if fix was applied successfully, False otherwise
    """
    try:
        source = file_path.read_text()
        file_funcs_list = index_file_functions(source)
        file_funcs = {f["name"]: f for f in file_funcs_list}

        lines = source.splitlines()
        raw_funcs = split_functions_raw(generated_code)

        for name, raw_text in sorted(raw_funcs.items(), key=lambda x: file_funcs.get(x[0], {}).get("start", 0), reverse=True):
            if name in file_funcs:
                old = file_funcs[name]
                start = old["start"] - 1
                end = old["end"]

                original_line = lines[start]
                original_indent = len(original_line) - len(original_line.lstrip())
                
                generated_lines = raw_text.splitlines()
                generated_indent = len(generated_lines[0]) - len(generated_lines[0].lstrip())
                
                indent_diff = original_indent - generated_indent
                if indent_diff > 0:
                    fixed_lines = [(" " * indent_diff) + line if line.strip() else line 
                                for line in generated_lines]
                    raw_text = "\n".join(fixed_lines)
                lines[start:end] = raw_text.splitlines()

        file_path.write_text("\n".join(lines))
        return True
        
    except (SyntaxError, PermissionError, IOError, UnicodeDecodeError) as e:
        debug_log("Apply fix error", f"{type(e).__name__}: {e}")
        return False

    except Exception as e:
        debug_log("Apply fix error - unexpected", f"{type(e).__name__}: {e}")
        return False


def fix(ctx: FixContext, max_attempts=2) -> dict[str, bool | str]:
    """
    Attempt to fix a failing test using LLM-generated code.
    
    Retries up to max_attempts times if the fix doesn't work.
    
    Args:
        ctx: FixContext containing all necessary context for the fix
        max_attempts: Maximum number of fix attempts (default: 2)
    
    Returns:
        Dict with keys: fixed (bool), diff (str), new_error (str)
    """
    previous_error = None

    for attempt in range(max_attempts):
        llm_result = call_llm(ctx.prompt, ctx.affected, ctx.test_code, ctx.error_message, ctx.diff, ctx.test_function, previous_error)

        if llm_result["code"] is None:
            debug_log("LLM returned no code", llm_result.get("explanation", ""))
            return {"fixed": False, "diff": "", "new_error": "", "explanation": llm_result["explanation"]}

        if not validate_generated_code(llm_result["code"]):
            previous_error = "Code parsing failed due to incomplete code structure"
            continue

        result = try_fix_temporarily(
            file_path=ctx.file_path,
            generated_code=llm_result["code"],
            nodeid=ctx.nodeid,
            repo_path=ctx.repo_path,
            original_error=ctx.error_message,
            new_imports=llm_result.get("imports", [])
        )
        debug_log("Fix result", result)

        if result["fixed"]:
            return result
        
        if result["new_error"] and result["new_error"] != ctx.error_message:
            return result
        
        previous_error = f"Attempt {attempt + 1} failed with same error"
        debug_log("Retry", f"Attempt {attempt + 1} failed, retrying...")
    
    return {"fixed": False, "diff": "", "new_error": ""}


def try_fix(failure, test_file_path, test_code, source_path, source_code, path, diff, affected_functions, target) -> dict[str, bool | str]:
    """
    Attempt to fix either the test file or source code.
    
    Args:
        failure: Dict containing failure info (file, function, error, etc.)
        test_file_path: Path to the test file
        test_code: Content of the test file
        source_path: Path to the source file
        source_code: Content of the source file
        path: Repository root path
        diff: Git diff string
        affected_functions: List of functions affected by changes
        target: What to fix - 'test' or 'code'
    
    Returns:
        Dict with keys: fixed (bool), diff (str), new_error (str)
    """
    if target == 'test':
        prompt = fix_test_prompt
        function_name = failure['function']
        file_path = test_file_path
    else:
        prompt = fix_code_prompt
        function_name = source_path
        file_path = source_path

    context = FixContext(
        prompt=prompt,
        function_name=function_name,
        file_path=file_path,
        function_code=source_code,
        test_code=test_code,
        error_message=failure['error'],
        repo_path=path,
        test_file=failure['file'],
        test_function=failure['function'],
        fix_type=target,
        diff=diff,
        affected=affected_functions,
        nodeid=failure['nodeid']
    )
    return fix(context)

def _create_fix_result(failure, result, diagnosis, fix_type, file_changed) -> FixResult:
    """
    Create a FixResult object from fix attempt data.
    
    Args:
        failure: Dict containing failure info (file, function, error)
        result: Dict with fix results (fixed, diff, new_error)
        diagnosis: Diagnosis object with cause and confidence
        fix_type: Type of fix applied ('test', 'code', 'none')
        file_changed: Path to the file that was modified
    
    Returns:
        FixResult object
    """
    return FixResult(
        test_file=failure['file'],
        test_function=failure['function'],
        error_message=failure['error'],
        fixed=result.get("fixed", False),
        fix_type=fix_type,
        file_changed=str(file_changed) if file_changed else "",
        diff=result.get("diff", ""),
        new_error=result.get("new_error", ""),
        cause=diagnosis.cause if diagnosis else "",
        confidence=diagnosis.confidence if diagnosis else "low"
    )

def attempt_fix(failure, changed_files, path, mode) -> FixResult:
    """
    Main entry point for fixing a single test failure.
    
    Diagnoses the failure, determines fix location, and attempts repair.
    Handles cross-file bugs by checking the crash file first.
    
    Args:
        failure: Dict with keys: file, function, error, crash_file, crash_line, nodeid
        changed_files: List of files changed in the git diff
        path: Repository root path
        mode: Fix mode - 'auto', 'code', or 'test'
    
    Returns:
        FixResult object with fix status and details
    """
    test_file_path, test_code = read_file_content(failure['file'], path)
    repo_path = Path(path).resolve()
    crash_path = Path(failure['crash_file'])

    result = {"fixed": False, "diff": "", "new_error": ""}
    diagnosis = None
    
    try:
        crash_file = str(crash_path.relative_to(repo_path))
    except ValueError:
        crash_file = crash_path.name

    if not is_test_file(crash_file):
        files_to_try = [crash_file]
    else:
        files_to_try = []

    for f in changed_files:
        if f not in files_to_try:
            files_to_try.append(f)

    debug_log("Files to try", files_to_try)

    for source_file in files_to_try:
        source_path, source_code = read_file_content(source_file, path)
        if not source_path:
            continue

        diff = get_single_file_diff(path, source_file)
        if diff:
            affected = gather_context(diff, source_code)
        else:
            if source_file == crash_file:
                funcs = index_file_functions(source_code)
                crash_line = failure['crash_line']
                affected = []
                for f in funcs:
                    if f["start"] <= crash_line <= f["end"]:
                        affected.append(extract_function_source(source_code, f))
                        break
            else:
                continue
        
        diagnosis = diagnose(
            functions=affected,
            test_code=test_code,    
            error_message=failure['error'],
            diff=diff
        )
        debug_log("Diagnosis", {"cause": diagnosis.cause, "fix_location": diagnosis.fix_location, "confidence": diagnosis.confidence})

        if mode == 'test':
            target = 'test'
        elif mode == 'code':
            target = 'code'
        else:
            target = diagnosis.fix_location

        file_changed = test_file_path if target == 'test' else source_path

        result = try_fix(failure, test_file_path, test_code, source_path, source_code, path, diff, affected, target=target)
        if result["fixed"]:
            return _create_fix_result(failure, result, diagnosis, target, file_changed)
    
    return _create_fix_result(failure, result, diagnosis, 'none', "")


def try_fix_temporarily(file_path, generated_code, nodeid, repo_path, original_error, new_imports=None) -> dict[str, bool | str]:
    """
    Apply fix temporarily, verify it works, then restore original.
    
    Uses a try/finally block to ensure the original file is always restored,
    regardless of whether the fix worked or an error occurred.
    
    Args:
        file_path: Path object to the file to modify
        generated_code: String containing the fixed function(s)
        nodeid: Pytest node ID for running the specific test
        repo_path: Repository root path
        original_error: The original error message to compare against
        new_imports: Optional list of import statements to add
    
    Returns:
        Dict with keys: fixed (bool), diff (str), new_error (str)
    """
    original_content = file_path.read_text()    
    try:
        if new_imports:
            add_imports_to_file(file_path, new_imports)
        apply_result = apply_fix(file_path, generated_code)
        if not apply_result:
            return {"fixed": False, "diff": "", "new_error": ""}
        
        new_content = file_path.read_text()
        diff = show_diff(original_content, new_content, file_path.name)
        
        passed, error = run_single_test(repo_path, nodeid)
        if passed:
            return {"fixed": True, "diff": diff, "new_error": ""}
        
        if error != original_error:
            return {"fixed": False, "diff": diff, "new_error": error}
        
        return {"fixed": False, "diff": "", "new_error": ""}
    
    finally:
        file_path.write_text(original_content)