import json
import pytest
from pathlib import Path
from unitsauce.utils import parse_json, is_test_file


class TestParseJson:
    def test_plain_json(self):
        assert parse_json('{"key": "value"}') == {"key": "value"}

    def test_json_in_markdown_block(self):
        text = '```json\n{"key": "value"}\n```'
        assert parse_json(text) == {"key": "value"}

    def test_json_in_bare_code_block(self):
        text = '```\n{"a": 1}\n```'
        assert parse_json(text) == {"a": 1}

    def test_json_embedded_in_text(self):
        text = 'Here is the result: {"cause": "bug", "fix_location": "code"} done.'
        result = parse_json(text)
        assert result["cause"] == "bug"

    def test_json_array(self):
        assert parse_json("[1, 2, 3]") == [1, 2, 3]

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No JSON found"):
            parse_json("no json here")

    def test_nested_json(self):
        text = '{"outer": {"inner": true}}'
        assert parse_json(text) == {"outer": {"inner": True}}

    def test_json_with_surrounding_whitespace(self):
        assert parse_json('  \n  {"a": 1}  \n  ') == {"a": 1}


class TestIsTestFile:
    def test_test_prefix(self):
        assert is_test_file("test_something.py") is True

    def test_test_suffix(self):
        assert is_test_file("something_test.py") is True

    def test_regular_python_file(self):
        assert is_test_file("utils.py") is False

    def test_non_python_file(self):
        assert is_test_file("test_something.js") is False

    def test_file_in_tests_dir(self):
        assert is_test_file("tests/helpers.py") is True

    def test_file_in_test_dir(self):
        assert is_test_file("test/helpers.py") is True

    def test_nested_test_dir(self):
        assert is_test_file("src/tests/conftest.py") is True

    def test_path_object(self):
        assert is_test_file(Path("test_foo.py")) is True

    def test_non_test_in_src(self):
        assert is_test_file("src/models.py") is False
