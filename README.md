# 🍝 UnitSauce

**Your tests break. We fix them.**

UnitSauce diagnoses failing pytest tests, generates minimal fixes, and posts suggestions directly to your PR. You review, you merge.

```bash
pip install unitsauce
```

---

## What It Does

1. **Runs your tests** — finds what's failing
2. **Reads your diff** — understands what changed
3. **Diagnoses the failure** — explains *why* it broke
4. **Generates a fix** — minimal diff, not a rewrite
5. **Verifies it works** — runs the test again
6. **Posts to your PR** — with confidence score

You stay in control. It never auto-commits unless you use `--apply`.

---

## Quick Start

### CLI

```bash
# In your project directory
unitsauce .

# Specify mode
unitsauce . --mode auto    # Let it decide (default)
unitsauce . --mode code    # Only fix source code
unitsauce . --mode test    # Only update tests

# Apply fixes to disk
unitsauce . --apply

# Limit processing
unitsauce . --max-tests 5

# Use a different model
unitsauce . --model claude-opus-4-20250514

# Output formats
unitsauce . --output console   # Default, colored terminal output
unitsauce . --output markdown  # For CI step summaries
unitsauce . --output json      # Structured output with usage stats
```

### GitHub Action

```yaml
name: UnitSauce
on: [pull_request]

jobs:
  fix:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: zanstarasinic/unitsauce@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

---

## Example Output

When a test fails, UnitSauce posts a comment like this:

> ## 🍝 UnitSauce
>
> Fixed **3/3** failing tests
>
> ---
>
> ### ✅ tests/test_api.py::test_user_discount
>
> **Suggested Fix** · ✓ High Confidence
>
> > `AttributeError: 'User' object has no attribute 'get_discount_percentage'`
>
> **Root cause:** Method renamed from `get_discount_percentage()` to `get_tier_discount()`
>
> 📁 `src/api.py`
>
> ```diff
> - discount = user.get_discount_percentage()
> + discount = user.get_tier_discount()
> ```

---

## Features

| Feature | Description |
|---------|-------------|
| **Root Cause Diagnosis** | Explains *why* the test failed, not just that it failed |
| **Confidence Scoring** | High / Medium / Low — know when to trust the fix |
| **Cross-File Detection** | Catches bugs in files you didn't change |
| **Fixture Awareness** | Includes conftest.py fixtures in analysis context |
| **Failure Deduplication** | Groups identical failures, fixes once per group |
| **Smart Imports** | Adds missing imports when needed |
| **Parametrized Tests** | Handles `test_foo[param]` style tests |
| **Async Support** | Works with `async def` test functions and source code |
| **Apply Mode** | `--apply` writes fixes to disk without committing |
| **Cost Visibility** | Reports API calls and token usage per run |
| **Safe by Default** | Never auto-commits. Always human-in-the-loop |

---

## Modes

| Mode | When to Use |
|------|-------------|
| `auto` | Let UnitSauce decide if the bug is in code or tests |
| `code` | You trust your tests — only fix source code |
| `test` | Intentional refactor — only update test expectations |

---

## Requirements

- Python 3.10+
- pytest
- Anthropic API key — [get one here](https://console.anthropic.com/)

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   pytest ──▶ failures ──▶ git diff ──▶ diagnose ──▶ fix        │
│                                                                 │
│                              │                                  │
│                              ▼                                  │
│                         verify fix                              │
│                              │                                  │
│                              ▼                                  │
│                       post to PR                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

1. Runs `pytest --json-report` to get structured failure data
2. Gets `git diff` to see what changed
3. Groups duplicate failures to avoid redundant API calls
4. Extracts the failing test, relevant source code, and conftest.py fixtures
5. Sends context to Claude with a focused prompt
6. Validates the generated fix compiles
7. Applies fix temporarily, runs test to verify
8. If it passes, formats and posts to PR (updates existing comment)

---

## Limitations

**Works best on:**

- ✅ Value/assertion mismatches
- ✅ Renamed methods or changed signatures
- ✅ Updated return types (dict → dataclass)
- ✅ Missing imports

**Won't solve:**

- ❌ Complex logic bugs
- ❌ Architectural issues
- ❌ Tests that were wrong to begin with

---

## Contributing

```bash
pip install -e .
pytest
```

Issues and PRs welcome.

---

## License

MIT
