import argparse
import sys
import time
from dotenv import load_dotenv

from .github import check_if_pull_request, format_pr_comment, post_pr_comment
from .output import format_result, format_summary
from .fixer import attempt_fix
from .analysis import get_failing_tests, get_git_diff, run_tests
from .utils import console

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        prog='unitsauce',
        description='AI-powered test failure analysis and fix suggestions.',
        epilog='Examples:\n  unitsauce .\n  unitsauce . --mode code\n  unitsauce . --mode test',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", nargs='?', default='.')
    parser.add_argument('--mode', choices=['auto', 'code', 'test'], default='auto', help='Fix mode (default: auto)')
    parser.add_argument('--output', choices=['console', 'markdown', 'json'], default='console', help='Output format (default: console)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')

    args = parser.parse_args()
    
    if args.debug:
        import os
        os.environ["DEBUG"] = "true"

    start_time = time.time()
    path = args.path

    console.print("\n⠋ Running tests...")
    run_tests(path)
    failures = get_failing_tests(path)

    if not failures:
        console.print("[green]✓[/green] All tests pass!")
        sys.exit(0)
    
    console.print(f"[green]✓[/green] Found {len(failures)} failing tests\n")

    changed_files = get_git_diff(path)
    changed_files = [f for f in changed_files if f.endswith('.py')]

    results = []
    for failure in failures:
        test_name = failure['function']
        console.print(f"⠋ Fixing {test_name}...")
        
        result = attempt_fix(failure, changed_files, path, args.mode)
        results.append(result)
        
        if result.fixed:
            console.print(f"[green]✓[/green] Fixed\n")
        elif result.partial:
            console.print(f"[yellow]⚠[/yellow] Partial fix\n")
        else:
            console.print(f"[red]✗[/red] Could not fix\n")

    pr = check_if_pull_request()
    if pr:
        comment = format_pr_comment(results)
        post_pr_comment(pr['repo'], pr['number'], comment)

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
    
    elif args.output == 'markdown':
        print(format_summary(results, 'markdown'))
    
    elif args.output == 'json':
        print(format_summary(results, 'json'))

    sys.exit(0 if fixed == total else 1)


if __name__ == "__main__":
    main()