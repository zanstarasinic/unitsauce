import json
import re
import art
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import os

console = Console()
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

def print_header():
    text = art.text2art("UnitSauce")

    print("```")
    print(text.rstrip())
    print("```")
    print("*AI-powered test fixer*")


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


def debug_log(title: str, content: str):
    if not DEBUG:
        return
    
    safe_content = content.replace('`', '\'')
    
    print()
    print("=" * 70)
    print(f"DEBUG: {title}")
    print("-" * 70)
    print(safe_content)
    print("=" * 70)
    print()