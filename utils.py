from pathlib import Path
import shutil
import art
from rich.console import Console

console = Console()

def print_header():
    text = art.text2art("UnitSauce")
    console.print(f"[bold blue] {text} [/bold blue]")

    console.print("[dim]AI-powered test fixer[/dim]\n")

def backup_file(file_path):
    src = Path(file_path)

    if not src.exists():
        raise FileNotFoundError(src)

    backup = src.with_suffix(src.suffix + ".bak")
    shutil.copy2(src, backup)

    return backup