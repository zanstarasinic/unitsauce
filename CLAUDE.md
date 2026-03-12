# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**UnitSauce** is an AI-powered CLI tool and GitHub Action that diagnoses failing pytest tests, generates minimal fixes using Claude, and posts suggestions to pull requests.

## Commands

```bash
pip install -e .                    # Install for development
pytest                              # Run test suite (94 tests)
pytest tests/test_analysis.py -v    # Run one test file
unitsauce . --debug                 # Run with verbose logging
```

**Required env:** `ANTHROPIC_API_KEY`. Optional: `GITHUB_TOKEN` for PR comments.

## Architecture

**Flow:** pytest → parse report.json → git diff → group duplicates → for each group: diagnose → fix → verify → restore (or apply with --apply)

### Modules

| Module | Role |
|--------|------|
| `main.py` | CLI entry, arg parsing, dedup grouping, orchestration |
| `analysis.py` | Pytest report parsing, git diff, AST indexing, function extraction |
| `fixer.py` | Fix attempts, conftest gathering, temporary apply/verify/restore |
| `llm.py` | Anthropic API (lazy client, retries, timeout), response parsing, usage tracking |
| `prompts.py` | Prompt templates: `SYSTEM_PROMPT`, `fix_code_prompt`, `fix_test_prompt`, `DIAGNOSIS_PROMPT` |
| `github.py` | PR detection, comment posting/updating (deduped via HTML marker) |
| `output.py` | Console/markdown/JSON formatting |
| `models.py` | Dataclasses: `FixContext`, `Diagnosis`, `FixResult` |
| `utils.py` | `parse_json()`, `debug_log()`, `is_test_file()` |

### Key design details

- **Two LLM calls per failure:** `diagnose()` → JSON with cause/location/confidence. `call_llm()` → XML with explanation/imports/fix code.
- **Failure dedup:** Groups by (crash_file, error_message), fixes once per group, reuses result.
- **Conftest awareness:** `_gather_conftest()` walks up from test file to repo root collecting all conftest.py files.
- **`split_functions_raw()`** uses AST (not regex) to find top-level function boundaries including decorators. Handles async functions.
- **`apply_fix()`** replaces functions in reverse line order to avoid offset cascades. Adjusts indentation for class methods.
- **`try_fix_temporarily()`** always restores the original file in a `finally` block.
- **PR comments** are updated in-place via `<!-- unitsauce -->` marker, not spammed.
- **Parametrized tests:** `test_foo[params]` is stripped to `test_foo` for function lookup, full nodeid kept for running.
- **Token tracking:** `_track_usage()` accumulates across all API calls, reported at end.
- **Lazy client init** with 3 retries and 120s timeout.
