# UnitSauce

AI-powered test fixer for Python projects.

## What it does

Analyzes failing tests, identifies bugs in recent code changes, and suggests fixes using Claude.

## Install
```bash
pip install -r requirements.txt
cp .env.example .env
# Add your Anthropic API key to .env
```

## Usage
```bash
python main.py /path/to/your/project
```

The tool will:
1. Run pytest and detect failures
2. Analyze git diff to find recent changes
3. Ask if you want to fix the code or update the test
4. Generate and apply a fix
5. Verify the fix works

## Requirements

- Python 3.10+
- Anthropic API key
- Project must be a git repository