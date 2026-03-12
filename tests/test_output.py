import json
from unitsauce.output import (
    get_confidence_badge,
    format_diff_section,
    format_summary,
    _format_json,
    _format_json_summary,
    _format_markdown,
    _format_markdown_summary,
)
from unitsauce.models import FixResult


def _make_result(**overrides):
    defaults = dict(
        test_file="tests/test_foo.py",
        test_function="test_bar",
        error_message="assert 1 == 2",
        fixed=True,
        fix_type="code",
        diff="- return 1\n+ return 2",
        file_changed="src/foo.py",
    )
    defaults.update(overrides)
    return FixResult(**defaults)


class TestGetConfidenceBadge:
    def test_high(self):
        assert "High" in get_confidence_badge("high")

    def test_medium(self):
        assert "Medium" in get_confidence_badge("medium")

    def test_low(self):
        assert "Low" in get_confidence_badge("low")

    def test_unknown(self):
        assert get_confidence_badge("unknown") == ""


class TestFormatDiffSection:
    def test_wraps_in_code_block(self):
        result = format_diff_section("- old\n+ new")
        assert result.startswith("```diff")
        assert result.endswith("```")

    def test_empty_diff(self):
        assert format_diff_section("") == ""

    def test_strips_existing_backticks(self):
        result = format_diff_section("```\n- old\n+ new\n```")
        assert result.count("```") == 2


class TestFormatJson:
    def test_includes_all_fields(self):
        result = _format_json(_make_result())
        assert result["test_file"] == "tests/test_foo.py"
        assert result["fixed"] is True
        assert result["fix_type"] == "code"

    def test_partial_result(self):
        result = _format_json(_make_result(fixed=False, partial=True, new_error="new"))
        assert result["partial"] is True
        assert result["new_error"] == "new"


class TestFormatJsonSummary:
    def test_summary_counts(self):
        results = [
            _make_result(fixed=True),
            _make_result(fixed=False, partial=True),
            _make_result(fixed=False),
        ]
        output = json.loads(_format_json_summary(results))
        assert output["summary"]["total"] == 3
        assert output["summary"]["fixed"] == 1
        assert output["summary"]["partial"] == 1
        assert output["summary"]["failed"] == 1


class TestFormatMarkdown:
    def test_fixed_result(self):
        md = _format_markdown(_make_result())
        assert "✅" in md
        assert "test_bar" in md

    def test_partial_result(self):
        md = _format_markdown(_make_result(fixed=False, partial=True, new_error="new err"))
        assert "⚠️" in md
        assert "new err" in md

    def test_unfixed_result(self):
        md = _format_markdown(_make_result(fixed=False))
        assert "❌" in md

    def test_truncates_long_error(self):
        long_error = "x" * 300
        md = _format_markdown(_make_result(error_message=long_error))
        assert len(long_error) > 150
        assert ("x" * 151) not in md


class TestFormatMarkdownSummary:
    def test_header(self):
        md = _format_markdown_summary([_make_result()])
        assert "UnitSauce" in md

    def test_all_fixed_message(self):
        md = _format_markdown_summary([_make_result(), _make_result()])
        assert "2/2" in md

    def test_none_fixed_message(self):
        md = _format_markdown_summary([_make_result(fixed=False)])
        assert "Could not fix" in md
