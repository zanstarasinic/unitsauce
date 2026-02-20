import argparse
import os
import subprocess
import sys
import time
import httpx
from dotenv import load_dotenv

from .github import check_if_pull_request, format_pr_comment, post_pr_comment
from .output import format_summary
from .fixer import attempt_fix
from .analysis import get_failing_tests, get_git_diff, run_tests
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
        parser.add_argument("path", nargs='?', default='.')
        parser.add_argument('--mode', choices=['auto', 'code', 'test'], default='auto', help='Fix mode (default: auto)')
        parser.add_argument('--output', choices=['console', 'markdown', 'json'], default='console', help='Output format (default: console)')
        parser.add_argument('--debug', action='store_true', help='Enable debug output')

        args = parser.parse_args()
    
        if args.debug:
            os.environ["DEBUG"] = "true"

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
        
        console.print(f"[green]✓[/green] Found {len(failures)} failing tests\n")

        changed_files = get_git_diff(path)
        changed_files = [f for f in changed_files if f.endswith('.py')]

        results = []
        for failure in failures:
            test_name = failure['function']
            
            with console.status(f"Fixing {test_name}..."):
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