# UnitSauce

AI-powered test failure analysis and auto-fix for Python projects.

UnitSauce analyzes failing tests, identifies bugs in your code changes, and generates fixes using Claude AI. Works as a CLI tool or GitHub Action.

---

## Features

- **Automatic failure detection** — Runs pytest and identifies failing tests
- **AI-powered analysis** — Uses Claude to understand the bug from git diff
- **Smart fixes** — Generates minimal code or test fixes
- **Verification** — Confirms the fix actually works before reporting
- **PR comments** — Posts fix suggestions directly to your pull request

---

## Quick Start

### CLI Usage
```bash
pip install unitsauce
```
```bash
# Auto-detect whether to fix code or test
unitsauce /path/to/project

# Force fix code only
unitsauce /path/to/project --mode code

# Force fix test only
unitsauce /path/to/project --mode test

# Output as markdown
unitsauce /path/to/project --output markdown
```

### GitHub Action

Add to your workflow (`.github/workflows/test.yml`):
```yaml
name: Tests
on:
  pull_request:

permissions:
  pull-requests: write

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install pytest
      
      - name: Run tests
        run: pytest
      
      - name: UnitSauce Analysis
        if: failure()
        uses: zanstarasinic/unitsauce@main
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

---

## Configuration

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--mode` | `auto`, `code`, or `test` | `auto` |
| `--output` | `console`, `markdown`, or `json` | `console` |

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `GITHUB_TOKEN` | For PR comments | Provided automatically by GitHub Actions |

---

## Requirements

- Python 3.10+
- Git repository
- Anthropic API key
- pytest

---

## How It Works

1. Detects failures — Runs pytest and collects failing tests
2. Analyzes changes — Gets git diff to see what changed
3. Identifies affected code — Maps failures to modified functions
4. Generates fix — Sends context to Claude, gets minimal fix
5. Verifies — Applies fix, runs test again to confirm
6. Reports — Shows diff or posts PR comment

---

## Example PR Comment
```
UnitSauce Analysis

Found 1 failing test(s), fixed 1.

---

test_calculator.py::test_add

Error: assert 6 == 5

Fixed by: Updating test in test_calculator.py

- assert add(2, 3) == 5
+ assert add(2, 3) == 6
```

---

## Local Development
```bash
git clone https://github.com/zanstarasinic/unitsauce.git
cd unitsauce
pip install -e .
```

---

## License

MIT
