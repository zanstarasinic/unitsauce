import json
import re
import os
from pathlib import Path
from rich.console import Console

console = Console()
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

TEST_FILE_PATTERNS = [
    r"^test_.*\.py$",      # test_something.py
    r".*_test\.py$",       # something_test.py
]

TEST_DIR_NAMES = {"test", "tests"}


def parse_json(text: str) -> json:
    text = re.sub(r"```(?:json)?|```", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found")

    return json.loads(match.group(1))


def debug_log(title: str, content: str):
    if not DEBUG:
        return
    
    if isinstance(content, dict):
        content = json.dumps(content, indent=2, default=str)
    elif not isinstance(content, str):
        content = str(content)
    
    content = content.replace('`', '\'')
    
    print()
    print("=" * 70)
    print(f"DEBUG: {title}")
    print("-" * 70)
    print(content)
    print("=" * 70)
    print()


def is_test_file(path: str | Path) -> bool:
    p = Path(path)

    if p.suffix != ".py":
        return False

    if p.name.startswith("test_") or p.name.endswith("_test.py"):
        return True

    if any(part in TEST_DIR_NAMES for part in p.parts):
        return True

    return False