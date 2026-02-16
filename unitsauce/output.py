import json
from .utils import console


# === HELPERS ===

def get_confidence_display(confidence: str) -> str:
    """Return confidence text with emoji."""
    displays = {
        "high": "High 🟢",
        "medium": "Medium 🟡",
        "low": "Low 🔴"
    }
    return displays.get(confidence, "Unknown ⚪")


def format_diff_section(diff: str) -> str:
    """Format diff for markdown output."""
    if not diff:
        return ""
    
    diff = diff.strip()
    
    if diff.startswith("```"):
        lines = diff.split("\n")
        diff = "\n".join(lines[1:])
    if diff.endswith("```"):
        lines = diff.split("\n")
        diff = "\n".join(lines[:-1])
    
    diff = diff.strip()
    return f"```diff\n{diff}\n```"


# === MAIN FORMATTERS ===

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


# === CONSOLE OUTPUT ===

def _format_console(result):
    """Format a single fix result for console output."""
    if result.fixed:
        console.print(f"[green]✓[/green] {result.test_file}::{result.test_function}")
    elif result.partial:
        console.print(f"[yellow]⚠[/yellow] {result.test_file}::{result.test_function}")
    else:
        console.print(f"[red]✗[/red] {result.test_file}::{result.test_function}")


def _format_console_summary(results):
    """Format summary for console output."""
    total = len(results)
    fixed = sum(1 for r in results if r.fixed)
    partial = sum(1 for r in results if r.partial)
    
    console.print()
    
    if fixed == total:
        console.print(f"[green]✓[/green] Fixed {fixed}/{total} tests")
    elif fixed > 0 or partial > 0:
        msg = f"[yellow]⚠[/yellow] Fixed {fixed}/{total} tests"
        if partial > 0:
            msg += f" ({partial} partial)"
        console.print(msg)
    else:
        console.print(f"[red]✗[/red] Fixed {fixed}/{total} tests")


# === MARKDOWN OUTPUT ===

def _format_markdown(result):
    """Format a single fix result for markdown."""
    confidence_display = get_confidence_display(result.confidence)
    cause_text = result.cause if result.cause else "Unknown cause"
    error_short = result.error_message[:150] if result.error_message else "Unknown error"
    
    if result.fixed:
        md = f"### ✅ {result.test_file}::{result.test_function}\n\n"
        md += f"**Error:** `{error_short}`\n\n"
        md += f"**Why it failed:** {cause_text}\n\n"
        md += f"**Confidence:** {confidence_display}\n\n"
        md += f"**Suggested fix** ({result.fix_type}):\n\n"
        md += format_diff_section(result.diff)
        md += "\n\n"
    
    elif result.partial:
        md = f"### ⚠️ {result.test_file}::{result.test_function}\n\n"
        md += f"**Error:** `{error_short}`\n\n"
        md += f"**Why it failed:** {cause_text}\n\n"
        md += f"**Confidence:** {confidence_display}\n\n"
        new_error_short = result.new_error[:150] if result.new_error else "Unknown error"
        md += f"**Partial fix** - new error occurred:\n\n`{new_error_short}`\n\n"
        md += format_diff_section(result.diff)
        md += "\n\n"
    
    else:
        md = f"### ❌ {result.test_file}::{result.test_function}\n\n"
        md += f"**Error:** `{error_short}`\n\n"
        md += f"**Why it failed:** {cause_text}\n\n"
        md += f"**Confidence:** {confidence_display}\n\n"
        md += "Could not auto-fix this failure.\n\n"
    
    return md


def _format_markdown_summary(results):
    """Format summary header for markdown."""
    total = len(results)
    fixed = sum(1 for r in results if r.fixed)
    partial = sum(1 for r in results if r.partial)
    
    md = "## 🍝 UnitSauce\n\n"
    
    if fixed == total:
        md += f"Fixed **{fixed}/{total}** failing tests\n\n"
    elif fixed > 0 or partial > 0:
        md += f"Fixed **{fixed}/{total}** failing tests"
        if partial > 0:
            md += f" ({partial} partial)"
        md += "\n\n"
    else:
        md += f"Could not fix **{total}** failing tests\n\n"
    
    md += "---\n\n"
    
    # Add each result
    for result in results:
        md += _format_markdown(result)
        md += "---\n\n"
    
    return md


# === JSON OUTPUT ===

def _format_json(result):
    """Format a single result as JSON dict."""
    return {
        "test_file": result.test_file,
        "test_function": result.test_function,
        "error_message": result.error_message,
        "fixed": result.fixed,
        "partial": result.partial,
        "fix_type": result.fix_type,
        "file_changed": result.file_changed,
        "diff": result.diff,
        "cause": result.cause,
        "confidence": result.confidence,
        "new_error": result.new_error
    }


def _format_json_summary(results):
    """Format all results as JSON."""
    total = len(results)
    fixed = sum(1 for r in results if r.fixed)
    partial = sum(1 for r in results if r.partial)
    
    output = {
        "results": [_format_json(r) for r in results],
        "summary": {
            "total": total,
            "fixed": fixed,
            "partial": partial,
            "failed": total - fixed - partial
        }
    }
    
    return json.dumps(output, indent=2)