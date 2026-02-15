import ast
from unitsauce.llm import call_llm, diagnose
from .analysis import add_imports_to_file, gather_context, get_error_file_from_exception, get_single_file_diff, index_file_functions, read_file_content, run_single_test, run_tests, show_diff, split_functions_raw, validate_generated_code
from .models import FixContext, FixResult
from .prompts import fix_code_prompt, fix_test_prompt

from .utils import console, debug_log



def apply_fix(file_path, generated_code):
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
        
    except SyntaxError as e:
        console.print(f"[red]Claude returned invalid code: {e}[/red]")
        return False

def fix(ctx: FixContext, max_attempts = 2):

    previous_error = None

    for attempt in range(max_attempts):
        llm_result = call_llm(ctx.prompt, ctx.affected, ctx.test_code, ctx.error_message, ctx.diff, ctx.test_function, previous_error)

        if llm_result["code"] is None:
            console.print("[red]LLM returned no code block[/red]")
            if llm_result["explanation"]:
                console.print(f"[yellow]Reason: {llm_result['explanation']}[/yellow]")
            return {"fixed": False, "diff": "", "new_error": "", "explanation": llm_result["explanation"]}

        if not validate_generated_code(llm_result["code"]):
            previous_error = "Code parsing failied due to incomplete code structure"
            continue

        result = try_fix_temporarily(
            file_path=ctx.file_path,
            generated_code=llm_result["code"],
            nodeid=ctx.nodeid,
            repo_path=ctx.repo_path,
            original_error=ctx.error_message,
            new_imports=llm_result.get("imports", [])
        )
        debug_log("Result of fixing: ", result)

        if result["fixed"]:
            return result
        
        if result["new_error"] and result["new_error"] != ctx.error_message:
            return result
        
        previous_error = f"Attempt {attempt + 1} failed with same error"
        console.print(f"[yellow]Attempt {attempt + 1} failed, retrying...[/yellow]")
    
    return {"fixed": False, "diff": "", "new_error": ""}

def try_fix_test(failure, test_file_path, test_code, source_code, path, fix_type, diff, affected_functions):
    """Attempt to fix the test file."""
    context = FixContext(
        prompt=fix_test_prompt,
        function_name=failure['function'],
        file_path=test_file_path,
        function_code=source_code,
        test_code=test_code,
        error_message=failure['error'],
        repo_path=path,
        test_file=failure['file'],
        test_function=failure['function'],
        fix_type=fix_type,
        diff=diff,
        affected=affected_functions,
        nodeid=failure['nodeid']
    )
    return fix(context)


def try_fix_code(failure, test_code, source_file, source_code, path, fix_type, diff, affected_functions):
    """Attempt to fix the source code."""
    context = FixContext(
        prompt=fix_code_prompt,
        function_name=source_file,
        file_path=source_file,
        function_code=source_code,
        test_code=test_code,
        error_message=failure['error'],
        repo_path=path,
        test_file=failure['file'],
        test_function=failure['function'],
        fix_type=fix_type,
        diff=diff,
        affected=affected_functions,
        nodeid=failure['nodeid']

    )
    return fix(context)

def attempt_fix(failure, changed_files, path, mode):
    test_file_path, test_code = read_file_content(failure['file'], path)

    guessed_name = failure['file'].split("/")[-1].replace("test_", "")
    matching_file = None
    for f in changed_files:
        if f.endswith(guessed_name):
            matching_file = f
            break


    if matching_file:
        files_to_try = [matching_file] + [f for f in changed_files if f != matching_file]
    else:
        files_to_try = changed_files

    failing_file_name = get_error_file_from_exception()
    if failing_file_name not in files_to_try:
        files_to_try = [failing_file_name] + files_to_try

    for source_file in files_to_try:
        source_path, source_code = read_file_content(source_file, path)
        if not source_path:
            continue

        diff = get_single_file_diff(path, source_file)
        affected = gather_context(diff, source_code)
        
        diagnosis = diagnose(
            functions=affected,
            test_code=test_code,    
            error_message=failure['error'],
            diff=diff
        )

        if mode == 'test':
            result = try_fix_test(failure, test_file_path, test_code, source_code, path, mode, diff, affected)
            if result["fixed"]:
                return FixResult(
                    test_file=failure['file'],
                    test_function=failure['function'],
                    error_message=failure['error'],
                    fixed=result["fixed"],
                    fix_type='test',
                    file_changed=str(test_file_path),
                    diff=result["diff"],
                    new_error=result["new_error"],
                    cause=diagnosis.cause,
                    confidence=diagnosis.confidence
                )
            elif result["new_error"]:
                break

        elif mode == 'code':
            result = try_fix_code(failure, test_code, source_path, source_code, path, mode, diff, affected)
            if result["fixed"]:
                return FixResult(
                    test_file=failure['file'],
                    test_function=failure['function'],
                    error_message=failure['error'],
                    fixed=result["fixed"],
                    fix_type='code',
                    file_changed=str(test_file_path),
                    diff=result["diff"],
                    new_error=result["new_error"],
                    cause=diagnosis.cause,
                    confidence=diagnosis.confidence
                )
                
        elif mode == 'auto':
            if diagnosis.fix_location == "test":
                result = try_fix_test(failure, test_file_path, test_code, source_code, path, mode, diff, affected)
            else:
                result = try_fix_code(failure, test_code, source_path, source_code, path, mode, diff, affected)

            if result["fixed"]:
                return FixResult(
                    test_file=failure['file'],
                    test_function=failure['function'],
                    error_message=failure['error'],
                    fixed=result["fixed"],
                    fix_type='test',
                    file_changed=str(test_file_path),
                    diff=result["diff"],
                    new_error=result["new_error"],
                    cause=diagnosis.cause,
                    confidence=diagnosis.confidence
                )
    
        return FixResult(
                        test_file=failure['file'],
                        test_function=failure['function'],
                        error_message=failure['error'],
                        fixed=False,
                        fix_type='auto',
                        file_changed=str(test_file_path),
                        diff="",
                        new_error=result["new_error"],
                        cause=diagnosis.cause,
                        confidence=diagnosis.confidence
                    )

def try_fix_temporarily(file_path, generated_code, nodeid, repo_path, original_error, new_imports=None):
    """Apply fix, test it, restore original, return result."""
    
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