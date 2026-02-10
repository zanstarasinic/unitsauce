import json
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from .utils import console

def format_result(result, format_type):
    if format_type == 'console':
        return _format_console(result)
    elif format_type == 'markdown':
        return _format_markdown(result)
    elif format_type == 'json':
        return _format_json(result)
    
def format_summary(results, format_type):
    if format_type == 'console':
        return _format_console_summary(results)
    elif format_type == 'markdown':
        return _format_markdown_summary(results)
    elif format_type == 'json':
        return _format_json_summary(results)
    

def _format_console(result):
    """Format a single fix result for console output."""
    if result.fixed:
        status = "[green]✓ FIXED[/green]"
    else:
        status = "[red]✗ NOT FIXED[/red]"
    
    console.print(f"\n{status} [bold]{result.test_file}::{result.test_function}[/bold]")
    
    console.print(f"[dim]Error:[/dim] {result.error_message[:100]}...")
    
    if result.fixed:
        console.print(f"[dim]Fixed by:[/dim] Updating [cyan]{result.fix_type}[/cyan] in [cyan]{result.file_changed}[/cyan]")
        
        if result.diff:
            syntax = Syntax(result.diff, "diff", theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title="Changes", border_style="green"))

def _format_console_summary(results):
    total = len(results)
    fixed = sum(1 for r in results if r.fixed)
    failed = total - fixed
    
    table = Table(title="Summary")
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")
    table.add_row("[green]Fixed[/green]", str(fixed))
    table.add_row("[red]Failed[/red]", str(failed))
    table.add_row("Total", str(total))
    
    console.print("\n")
    console.print(table)

def _format_markdown(result):
    if result.fixed:
        status = "✅ FIXED"
    else:
        status = "❌ NOT FIXED"
    
    md = f"## {status}: `{result.test_file}::{result.test_function}`\n\n"
    md += f"**Error:** `{result.error_message[:100]}...`\n\n"
    
    if result.fixed:
        md += f"**Fixed by:** Updating `{result.fix_type}` in `{result.file_changed}`\n\n"
        if result.diff:
            md += f"```diff\n{result.diff}\n```\n"
    
    return md

def _format_markdown_summary(results):
    total = len(results)
    fixed = sum(1 for r in results if r.fixed)
    failed = total - fixed
    
    md = "## Summary\n\n"
    md += f"| Status | Count |\n"
    md += f"|--------|-------|\n"
    md += f"| ✅ Fixed | {fixed} |\n"
    md += f"| ❌ Failed | {failed} |\n"
    md += f"| Total | {total} |\n"
    
    return md

def _format_json(result):
    return {
        "test_file": result.test_file,
        "test_function": result.test_function,
        "error_message": result.error_message,
        "fixed": result.fixed,
        "fix_type": result.fix_type,
        "file_changed": result.file_changed,
        "diff": result.diff
    }

def _format_json_summary(results):
    total = len(results)
    fixed = sum(1 for r in results if r.fixed)
    
    output = {
        "failures": [_format_json(r) for r in results],
        "summary": {
            "total": total,
            "fixed": fixed,
            "failed": total - fixed
        }
    }
    
    return json.dumps(output, indent=2)