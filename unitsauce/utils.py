import json
import re
import os
from rich.console import Console

console = Console()
DEBUG = os.getenv("DEBUG", "False").lower() == "true"


def parse_json(text: str):
    text = re.sub(r"```(?:json)?|```", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found")

    return json.loads(match.group(1))


def debug_log(title: str, content):
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