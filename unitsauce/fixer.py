import os
import re
import shutil
from .analysis import gather_context, get_single_file_diff, index_file_functions, read_file_content, run_single_test, run_tests, show_diff, split_functions_raw
from anthropic import Anthropic
from dotenv import load_dotenv

from .models import FixContext, FixResult, VerifyContext
from .prompts import fix_code_prompt, fix_test_prompt
from rich.spinner import Spinner
from rich.live import Live
from .utils import backup_file, console

load_dotenv()

client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

def call_llm(fix_prompt, functions, test_code, error_message, diff):
    with Live(Spinner("dots", text="Generating solution..."), console=console):
        response = client.messages.create(
                        max_tokens=8192*2,
                        messages=[
                            {
                                "role": "user",
                                "content": fix_prompt.format(function_code=functions, test_code=test_code, error_message=error_message, diff=diff),
                            }
                        ],
                        model="claude-opus-4-5-20251101",
                    )
    code = response.content[0].text
    match = re.search(r'```python(.*?)```', code, re.DOTALL)

    if match:
        return match.group(1)
    return None


def apply_fix(file_path, generated_code):
    backup = backup_file(file_path)

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
                lines[start:end] = raw_text.splitlines()

                file_path.write_text("\n".join(lines))

        return {"success": True, "backup": backup}
        
    except SyntaxError as e:
        console.print(f"[red]Claude returned invalid code: {e}[/red]")
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {"success": False, "backup": None}

def verify_fix(ctx: VerifyContext):
    test_passed, new_changes_result = run_single_test(ctx.repo_path, ctx.test_file, ctx.test_function)
    if test_passed:
        diff = show_diff(ctx.original_function_code, ctx.generated_code, ctx.test_function)
        result = run_tests(ctx.repo_path)
        if result.returncode == 0:
            ctx.backup_path.unlink()
            return {"fixed": True, "diff": diff}
        else:
            return {"fixed": False, "diff": ""}
    else:
        if new_changes_result == ctx.original_error_message:
            shutil.copy2(ctx.backup_path, ctx.file_path)
            ctx.backup_path.unlink()
            console.print("[red]Fix didn't work, restored original[/red]")

        else:
            ctx.backup_path.unlink()
            console.print("[yellow]Different error now - keeping changes[/yellow]")
        return {"fixed": False, "diff": ""}

def fix(ctx: FixContext):
    diff = get_single_file_diff(ctx.repo_path, ctx.function_name)
    
    affected = gather_context(diff, ctx.function_code)

    generated_code = call_llm(ctx.prompt, affected, ctx.test_code, ctx.error_message, diff)

    if generated_code is None:
        console.print("[red]LLM returned no code block[/red]")
        return False
    
    successful_fix = apply_fix(ctx.file_path, generated_code)
    if not successful_fix["success"]:
        return False
    else:
        verify_ctx = VerifyContext(
            repo_path=ctx.repo_path,
            file_path=ctx.file_path,
            test_file=ctx.test_file,
            test_function=ctx.test_function,
            original_function_code=ctx.function_code,
            generated_code=generated_code,
            backup_path=successful_fix["backup"],
            original_error_message=ctx.error_message,
        )
        return verify_fix(verify_ctx)

def try_fix_test(failure, test_file_path, test_code, source_file, source_code, path):
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
        test_function=failure['function']
    )
    return fix(context)


def try_fix_code(failure, test_code, source_file, source_code, path):
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
        test_function=failure['function']
    )
    return fix(context)

def attempt_fix(failure, changed_files, path, mode):
    test_file_path, test_code = read_file_content(failure['file'], path)

    guessed_name = failure['file'].split("/")[-1].replace("test_", "")

    if guessed_name in changed_files:
        files_to_try = [guessed_name] + [f for f in changed_files if f != guessed_name]
    else:
        files_to_try = changed_files

    for source_file in files_to_try:
        source_path, source_code = read_file_content(source_file, path)
        if not source_path:
            continue
        
        if mode == 'test':
            result = try_fix_test(failure, test_file_path, test_code, source_path, source_code, path)
            if result["fixed"]:
                return FixResult(
                    test_file=failure['file'],
                    test_function=failure['function'],
                    error_message=failure['error'],
                    fixed=result["fixed"],
                    fix_type='test',
                    file_changed=str(test_file_path),
                    diff=result["diff"]
                )
                
        elif mode == 'code':
            result = try_fix_code(failure, test_file_path, test_code, source_path, source_code, path)
            if result["fixed"]:
                return FixResult(
                    test_file=failure['file'],
                    test_function=failure['function'],
                    error_message=failure['error'],
                    fixed=result["fixed"],
                    fix_type='test',
                    file_changed=str(test_file_path),
                    diff=result["diff"]
                )
                
        elif mode == 'auto':
            result = try_fix_test(failure, test_file_path, test_code, source_path, source_code, path)
            if result["fixed"]:
                return FixResult(
                    test_file=failure['file'],
                    test_function=failure['function'],
                    error_message=failure['error'],
                    fixed=result["fixed"],
                    fix_type='test',
                    file_changed=str(test_file_path),
                    diff=result["diff"]
                )
    
    return FixResult(
                    test_file=failure['file'],
                    test_function=failure['function'],
                    error_message=failure['error'],
                    fixed=False,
                    fix_type='auto',
                    file_changed=str(test_file_path),
                    diff=""
                )