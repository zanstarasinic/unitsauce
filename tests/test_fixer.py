import pytest
from pathlib import Path
from textwrap import dedent
from unitsauce.fixer import apply_fix


class TestApplyFix:
    def test_replaces_function(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("def foo():\n    return 1\n")
        generated = "def foo():\n    return 2\n"
        assert apply_fix(f, generated) is True
        assert "return 2" in f.read_text()

    def test_replaces_correct_function(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("def foo():\n    return 1\n\ndef bar():\n    return 2\n")
        generated = "def bar():\n    return 3\n"
        assert apply_fix(f, generated) is True
        content = f.read_text()
        assert "return 1" in content
        assert "return 3" in content
        assert "return 2" not in content

    def test_preserves_indentation_for_methods(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text(dedent("""\
            class MyClass:
                def method(self):
                    return 1
        """))
        generated = "def method(self):\n    return 2\n"
        assert apply_fix(f, generated) is True
        content = f.read_text()
        assert "        return 2" in content

    def test_unknown_function_name_is_ignored(self, tmp_path):
        f = tmp_path / "module.py"
        original = "def foo():\n    return 1\n"
        f.write_text(original)
        generated = "def nonexistent():\n    return 2\n"
        assert apply_fix(f, generated) is True
        assert "return 1" in f.read_text()

    def test_handles_async_function(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("async def fetch():\n    return 1\n")
        generated = "async def fetch():\n    return 2\n"
        assert apply_fix(f, generated) is True
        assert "return 2" in f.read_text()

    def test_handles_decorated_function(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("@decorator\ndef foo():\n    return 1\n")
        generated = "@decorator\ndef foo():\n    return 2\n"
        assert apply_fix(f, generated) is True
        content = f.read_text()
        assert "return 2" in content

    def test_preserves_trailing_newline(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("def foo():\n    return 1\n")
        generated = "def foo():\n    return 2\n"
        apply_fix(f, generated)
        assert f.read_text().endswith("\n")

    def test_multiple_functions_replaced(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("def foo():\n    return 1\n\ndef bar():\n    return 2\n")
        generated = "def foo():\n    return 10\n\ndef bar():\n    return 20\n"
        assert apply_fix(f, generated) is True
        content = f.read_text()
        assert "return 10" in content
        assert "return 20" in content

    def test_invalid_source_file(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("this is not valid python {{{}}")
        generated = "def foo():\n    return 1\n"
        assert apply_fix(f, generated) is False
