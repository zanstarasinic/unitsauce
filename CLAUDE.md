# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**UnitSauce** is an AI-powered CLI tool and GitHub Action that automatically diagnoses failing pytest tests, generates minimal fixes using Claude, and posts suggestions to pull requests. It never auto-commits — all fixes are suggestions for human review unless `--apply` is used.

## Commands

```bash
# Install locally for development
pip install -e .

# Run the CLI
unitsauce .
unitsauce . --mode auto|code|test   # auto = let Claude decide code vs test fix
unitsauce . --output console|markdown|json
unitsauce . --apply                 # write successful fixes to disk (no commit)
unitsauce . --max-tests 5           # cap number of failures to process
unitsauce . --model claude-opus-4-20250514
unitsauce . --debug                 # sets DEBUG env var for verbose logging
unitsauce --version

# Run tests
pytest
pytest --tb=short --json-report     # how unitsauce internally runs tests

# Run a single test
pytest tests/path/to/test_file.py::test_name
```

**Required environment variable:** `ANTHROPIC_API_KEY` (see `.env.example`). Set `GITHUB_TOKEN` to enable PR commenting.

## Architecture

**Data flow:** Run pytest → parse `report.json` → get git diff → for each failure: diagnose → generate fix → verify temporarily → restore original (or persist with `--apply`) → format and post results

### Core modules

| Module | Responsibility |
|--------|---------------|
| `main.py` | CLI entry point; parses args, orchestrates workflow, handles exit codes |
| `analysis.py` | Parses pytest JSON reports, extracts git diffs, indexes functions via AST, maps failures to source locations |
| `fixer.py` | Attempts fixes; applies temporarily, verifies by running the test, always restores original |
| `llm.py` | Claude API calls (lazily initialized client with retries/timeout) for diagnosis and fix generation; XML/JSON response parsing |
| `prompts.py` | All LLM prompt templates: `SYSTEM_PROMPT`, `fix_code_prompt`, `fix_test_prompt`, `DIAGNOSIS_PROMPT` |
| `github.py` | Detects PR context via GitHub event JSON; posts/updates markdown comment via REST API (deduplicates via HTML marker) |
| `output.py` | Formats `FixResult` objects as console (rich), markdown (PR comment), or JSON |
| `models.py` | Dataclasses: `FixContext`, `Diagnosis`, `FixResult` |
| `utils.py` | `parse_json()`, `debug_log()`, `is_test_file()` |

### Two-phase LLM approach

1. **`diagnose()`** in `llm.py` — asks Claude for root cause, `fix_location` (`code` or `test`), and `confidence` (`high`/`medium`/`low`) as JSON. No fix code generated here. Has error handling that returns a safe fallback on failure.
2. **`call_llm()`** in `llm.py` — given the appropriate prompt template, asks Claude to return XML with `<explanation>`, `<imports>`, and `<fix>` (Python code block). Max tokens: 8192. Model configurable via `--model` flag, defaults to `claude-sonnet-4-20250514`.

### Fix application and verification (`fixer.py`)

- `attempt_fix()` prioritizes the **crash file** (where the test actually crashed) over changed files when deciding what to fix.
- `try_fix_temporarily()` saves the original file, applies the fix, runs the single test via subprocess, then **always restores the original** in a `finally` block — safe even on exception.
- `apply_fix()` replaces functions in **reverse line order** to avoid offset cascades when multiple functions change. It also detects and corrects indentation differences between generated and original code.
- Partial fixes are detected when the original crash message no longer appears in the test output but the test still fails.
- When `--apply` is used, successful fixes are re-applied to disk after verification (generated code and imports are carried through `FixResult`).

### LLM response format

Claude returns structured XML:
```xml
<explanation>Root cause description</explanation>
<imports>import os</imports>
<fix>
```python
def fixed_function(...):
    ...
```
</fix>
```
`parse_llm_response()` extracts these sections. Imports are added after existing imports in the target file, deduplicating by exact line match.

### GitHub Actions integration

- `check_if_pull_request()` reads `GITHUB_EVENT_NAME` (must be `pull_request`) and parses the event JSON at `GITHUB_EVENT_PATH` to get the PR number.
- `get_git_diff()` detects `GITHUB_BASE_REF` to diff against the PR base branch (fetching it first); locally it diffs against `HEAD~1`.
- The action installs unitsauce from `github.action_path` and pipes `--output markdown` to `$GITHUB_STEP_SUMMARY`. PR comment posting only happens with console output to avoid double output.
- PR comments are updated in-place (found via `<!-- unitsauce -->` marker) rather than creating new ones each run.
- `read_file_content()` resolves paths directly first, falling back to `rglob` only when the direct path doesn't exist.

### Output formatting

- **Console**: colored status symbols only (`✓`/`⚠`/`✗`) — no diffs shown. PR comments posted in this mode.
- **Markdown**: confidence badge + error excerpt (150 char limit) + root cause + diff block — used for step summary.
- **JSON**: full structured output including `new_error` for partial fixes.

## Key non-obvious behaviors

- `changed_lines()` in `analysis.py` only tracks **added** lines from diffs, not deleted ones.
- `gather_context()` finds functions whose line range overlaps with changed lines — used to give Claude context about what changed, not just the failing function.
- Debug logging via `debug_log()` uses plain `print()`, bypassing Rich formatting.
- Exit code 0 if all tests are fixed; exit code 1 otherwise.
- The Anthropic client is lazily initialized on first LLM call, so missing API keys don't crash `--help` or `--version`.
