import argparse
import os
import subprocess
import sys
import time
import httpx
from dotenv import load_dotenv

from .github import check_if_pull_request, format_pr_comment, post_pr_comment
from .output import format_summary
from .fixer import apply_fix, attempt_fix
from .analysis import add_imports_to_file, get_failing_tests, get_git_diff, run_tests
from .utils import console

load_dotenv()


def main():
    """
    CLI entry point for UnitSauce.
    
    Parses arguments, runs tests, attempts fixes, and outputs results.
    Posts PR comments when running in GitHub Actions context.
    
    Exit codes:
        0 - All failing tests were fixed
        1 - Some tests could not be fixed or an error occurred
        130 - Interrupted by user (Ctrl+C)
    """
    try:
        parser = argparse.ArgumentParser(
            prog='unitsauce',
            description='Diagnoses failing pytest tests, generates minimal fixes, and posts to your PR',
            epilog='Examples:\n  unitsauce .\n  unitsauce . --mode code\n  unitsauce . --mode test',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        parser.add_argument('--version', action='version', version='%(prog)s 0.1.1')
        parser.add_argument("path", nargs='?', default='.')
        parser.add_argument('--mode', choices=['auto', 'code', 'test'], default='auto', help='Fix mode (default: auto)')
        parser.add_argument('--output', choices=['console', 'markdown', 'json'], default='console', help='Output format (default: console)')
        parser.add_argument('--apply', action='store_true', help='Apply successful fixes to disk (does not commit)')
        parser.add_argument('--max-tests', type=int, default=None, help='Maximum number of failing tests to process')
        parser.add_argument('--model', type=str, default=None, help='Claude model to use (default: claude-sonnet-4-20250514)')
        parser.add_argument('--debug', action='store_true', help='Enable debug output')

        args = parser.parse_args()

        if args.debug:
            os.environ["DEBUG"] = "true"

        if args.model:
            from . import llm
            llm.LLM_MODEL = args.model

        start_time = time.time()
        path = args.path

        if not path:
            return False

        with console.status("Running tests..."):
            run_tests(path)
            failures = get_failing_tests(path)

        if not failures:
            console.print("[green]✓[/green] All tests pass!")
            sys.exit(0)
        
        if args.max_tests and len(failures) > args.max_tests:
            console.print(f"[yellow]⚠[/yellow] {len(failures)} failing tests, processing first {args.max_tests}\n")
            failures = failures[:args.max_tests]
        else:
            console.print(f"[green]✓[/green] Found {len(failures)} failing tests\n")

        changed_files = get_git_diff(path)
        changed_files = [f for f in changed_files if f.endswith('.py')]

        if not changed_files:
            console.print("[yellow]⚠[/yellow] No changed Python files detected. Fixes will be limited to crash-site analysis only.\n")

        groups = {}
        for failure in failures:
            key = (failure.get('crash_file', ''), failure.get('error', ''))
            groups.setdefault(key, []).append(failure)

        deduped = sum(1 for g in groups.values() if len(g) > 1)
        if deduped:
            console.print(f"[dim]Grouped into {len(groups)} unique failures ({deduped} duplicates)[/dim]\n")

        results = []
        fix_cache = {}
        for key, group in groups.items():
            representative = group[0]
            test_name = representative['function']

            with console.status(f"Fixing {test_name}..."):
                result = attempt_fix(representative, changed_files, path, args.mode)
            fix_cache[key] = result

            if result.fixed:
                console.print(f"[green]✓[/green] Fixed\n")
            elif result.partial:
                console.print(f"[yellow]⚠[/yellow] Partial fix\n")
            else:
                console.print(f"[red]✗[/red] Could not fix\n")

        for failure in failures:
            key = (failure.get('crash_file', ''), failure.get('error', ''))
            cached = fix_cache[key]
            if failure is groups[key][0]:
                results.append(cached)
            else:
                from .models import FixResult
                results.append(FixResult(
                    test_file=failure['file'],
                    test_function=failure['function'],
                    error_message=failure['error'],
                    fixed=cached.fixed,
                    fix_type=cached.fix_type,
                    diff=cached.diff,
                    file_changed=cached.file_changed,
                    partial=cached.partial,
                    new_error=cached.new_error,
                    cause=cached.cause,
                    confidence=cached.confidence,
                    generated_code=cached.generated_code,
                    new_imports=cached.new_imports,
                    file_path=cached.file_path,
                ))

        if args.apply:
            applied = 0
            for result in results:
                if result.fixed and result.generated_code:
                    if result.new_imports:
                        add_imports_to_file(result.file_path, result.new_imports)
                    apply_fix(result.file_path, result.generated_code)
                    applied += 1
            if applied:
                console.print(f"[green]✓[/green] Applied {applied} fix(es) to disk\n")

        if args.output == 'console':
            pr = check_if_pull_request()
            if pr:
                with console.status("Posting to PR..."):
                    comment = format_pr_comment(results)
                    post_pr_comment(pr['repo'], pr['number'], comment)
                console.print(f"[green]✓[/green] Posted to PR #{pr['number']}")

        elapsed = time.time() - start_time
        total = len(results)
        fixed = sum(1 for r in results if r.fixed)

        if args.output == 'console':
            if fixed == total:
                console.print(f"[green]✓[/green] Fixed {fixed}/{total} tests in {elapsed:.1f}s")
            elif fixed > 0:
                console.print(f"[yellow]⚠[/yellow] Fixed {fixed}/{total} tests in {elapsed:.1f}s")
            else:
                console.print(f"[red]✗[/red] Fixed {fixed}/{total} tests in {elapsed:.1f}s")

            from .llm import get_usage
            usage = get_usage()
            if usage["calls"] > 0:
                total_tokens = usage["input_tokens"] + usage["output_tokens"]
                console.print(f"[dim]  {usage['calls']} API calls · {total_tokens:,} tokens ({usage['input_tokens']:,} in / {usage['output_tokens']:,} out)[/dim]")
        
        elif args.output == 'markdown':
            print(format_summary(results, 'markdown'))
        
        elif args.output == 'json':
            print(format_summary(results, 'json'))

        sys.exit(0 if fixed == total else 1)
    except FileNotFoundError:
        console.print("[red]✗[/red] Path not found")
        sys.exit(1)

    except subprocess.CalledProcessError as e:
        if "pytest" in str(e.cmd):
            console.print("[red]✗[/red] pytest not found. Install with: pip install pytest")
        elif "git" in str(e.cmd):
            console.print("[red]✗[/red] Not a git repository")
        else:
            console.print(f"[red]✗[/red] Command failed: {e}")
        sys.exit(1)

    except httpx.HTTPError as e:
        console.print(f"[red]✗[/red] API error: {e}")
        sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
        sys.exit(130)

    except Exception as e:
        if args.debug:
            console.print_exception()
        else:
            console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()