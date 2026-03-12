from textwrap import dedent
from unitsauce.llm import parse_llm_response


class TestParseLlmResponse:
    def test_full_response(self):
        response = dedent("""\
            <explanation>The function returns wrong value</explanation>
            <imports>import os</imports>
            <fix>
            ```python
            def foo():
                return 2
            ```
            </fix>
        """)
        result = parse_llm_response(response)
        assert result["explanation"] == "The function returns wrong value"
        assert "def foo():" in result["code"]
        assert result["imports"] == ["import os"]

    def test_no_imports_needed(self):
        response = dedent("""\
            <explanation>Bug fix</explanation>
            <imports>none</imports>
            <fix>
            ```python
            def foo():
                pass
            ```
            </fix>
        """)
        result = parse_llm_response(response)
        assert result["imports"] == []

    def test_multiple_imports(self):
        response = dedent("""\
            <explanation>Need new imports</explanation>
            <imports>
            import os
            from pathlib import Path
            </imports>
            <fix>
            ```python
            def foo():
                pass
            ```
            </fix>
        """)
        result = parse_llm_response(response)
        assert len(result["imports"]) == 2
        assert "import os" in result["imports"]
        assert "from pathlib import Path" in result["imports"]

    def test_empty_code_block(self):
        response = dedent("""\
            <explanation>Cannot fix this</explanation>
            <imports>none</imports>
            <fix>
            ```python
            ```
            </fix>
        """)
        result = parse_llm_response(response)
        assert result["code"] is None

    def test_missing_all_tags(self):
        result = parse_llm_response("some random text")
        assert result["explanation"] == ""
        assert result["code"] is None
        assert result["imports"] == []

    def test_explanation_only(self):
        response = "<explanation>Cannot determine fix</explanation>"
        result = parse_llm_response(response)
        assert result["explanation"] == "Cannot determine fix"
        assert result["code"] is None

    def test_multiline_explanation(self):
        response = "<explanation>Line 1\nLine 2</explanation>"
        result = parse_llm_response(response)
        assert "Line 1" in result["explanation"]
        assert "Line 2" in result["explanation"]

    def test_code_with_indentation(self):
        response = dedent("""\
            <explanation>Fix</explanation>
            <imports>none</imports>
            <fix>
            ```python
            def foo():
                if True:
                    return 1
                return 2
            ```
            </fix>
        """)
        result = parse_llm_response(response)
        assert "    if True:" in result["code"]
        assert "        return 1" in result["code"]
