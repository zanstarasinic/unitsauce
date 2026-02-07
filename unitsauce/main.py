
import argparse
import sys
from dotenv import load_dotenv
from unitsauce.github import check_if_pull_request, format_pr_comment_summary, post_pr_comment
from unitsauce.output import format_result, format_summary

from .fixer import attempt_fix
from .analysis import get_failing_tests, get_git_diff, run_tests
from .utils import print_header, console


load_dotenv()


def main():

    parser = argparse.ArgumentParser(
        prog='unitsauce',
        description='AI-powered test failure analysis and fix suggestions. Analyzes git diffs, identifies bugs causing test failures, and generates fixes.',
        epilog='Examples:\n  unitsauce ./my-project\n  unitsauce ./my-project --mode code\n  unitsauce ./my-project --mode test --output markdown',
        formatter_class=argparse.RawDescriptionHelpFormatter  # Preserves newlines in epilog
    )
    parser.add_argument("path")
    parser.add_argument('--mode', choices=['auto', 'code', 'test'], default='auto', help='Fix mode (default: auto)')
    parser.add_argument('--output', choices=['console', 'markdown', 'json'], default='console', help='Output format (default: console)')

    args = parser.parse_args()

    if len(sys.argv) < 2:
        console.print("[yellow]Usage: python test_fixer.py <project_path>[/yellow]")
        return

    print_header()
    
    path = args.path
    run_tests(path)
    failures = get_failing_tests(path)

    results = []
    markdown_output = ""

    if not failures:
        console.print("[green]All tests pass![/green]")
        return
    
    console.print(f"[yellow]Found {len(failures)} failing test(s)[/yellow]\n")
    changed_files = get_git_diff(args.path)
    changed_files = [f for f in changed_files if f.endswith('.py')]

    for failure in failures:
        console.print(f"[red]FAILING:[/red] {failure['file']}::{failure['function']}")
        console.print(f"[red]ERROR:[/red] {failure['error']}\n")
        
        result = attempt_fix(failure, changed_files, args.path, args.mode)
        results.append(result)

        if args.output == 'console':
            format_result(result, 'console')
        elif args.output == 'markdown':
            markdown_output += format_result(result, 'markdown') + "\n"
    final_result = run_tests(args.path)
    all_tests_pass = final_result.returncode == 0
    if args.output == 'console':
        format_summary(results, 'console')
        if all_tests_pass:
            console.print("[green]All tests now pass![/green]")
        else:
            console.print("[yellow]Some tests still failing[/yellow]")

    pr = check_if_pull_request()

    if pr:
        comment = format_pr_comment_summary(results)
        response = post_pr_comment(pr['repo'], pr['number'], comment)



    if args.output == 'console':
        format_summary(results, 'console')
    elif args.output == 'markdown':
        markdown_output += format_summary(results, 'markdown')
        print(markdown_output)
    elif args.output == 'json':
        print(format_summary(results, 'json'))
        
    sys.exit(0 if all_tests_pass else 1)


if __name__ == "__main__":
    main()