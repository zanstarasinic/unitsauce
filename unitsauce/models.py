
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class FixContext:
    # --- LLM / reasoning ---
    prompt: str
    error_message: str

    # --- Code under fix ---
    function_name: str
    function_code: str
    file_path: Path

    # --- Test context ---
    test_code: str
    test_file: Path
    test_function: str

    # --- Repo / execution ---
    repo_path: Path
    fix_type: str

    nodeid: str

    diff: str = ""
    affected: list = None



@dataclass
class Diagnosis:
    cause: str
    fix_location: str
    confidence: str

@dataclass
class FixResult:
    test_file: str
    test_function: str
    error_message: str
    fixed: bool
    fix_type: str
    diff: str
    file_changed: str
    partial: bool = False
    new_error: str | None = None
    cause: str = ""
    confidence: str = "low",
    failure_reason: str = ""

