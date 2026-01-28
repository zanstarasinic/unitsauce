
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


@dataclass(frozen=True)
class VerifyContext:
    # --- Repo / execution ---
    repo_path: Path
    file_path: Path

    # --- Test ---
    test_file: Path
    test_function: str

    # --- Code ---
    original_function_code: str
    generated_code: str
    backup_path: Path

    # --- Failure ---
    original_error_message: Optional[str] = None