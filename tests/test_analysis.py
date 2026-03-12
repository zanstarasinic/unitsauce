import json
import pytest
from pathlib import Path
from textwrap import dedent
from unitsauce.analysis import (
    changed_lines,
    extract_function_source,
    gather_context,
    index_file_functions,
    normalize,
    read_file_content,
    show_diff,
    split_functions_raw,
    validate_generated_code,
    add_imports_to_file,
    get_failing_tests,
)


class TestNormalize:
    def test_strips_trailing_whitespace(self):
        assert normalize("hello   \nworld  ") == ["hello", "world"]

    def test_handles_crlf(self):
        assert normalize("a\r\nb\r\n") == ["a", "b"]

    def test_empty_string(self):
        assert normalize("") == []


class TestShowDiff:
    def test_identical_content(self):
        assert show_diff("hello", "hello", "test.py") == ""

    def test_produces_unified_diff(self):
        diff = show_diff("line1\nline2", "line1\nline3", "test.py")
        assert "-line2" in diff
        assert "+line3" in diff
        assert "before/test.py" in diff
        assert "after/test.py" in diff


class TestChangedLines:
    def test_single_hunk(self):
        diff = dedent("""\
            --- a/file.py
            +++ b/file.py
            @@ -1,3 +1,3 @@
             unchanged
            -old
            +new
             unchanged
        """)
        assert changed_lines(diff) == [2]

    def test_multiple_additions(self):
        diff = dedent("""\
            --- a/file.py
            +++ b/file.py
            @@ -1,2 +1,4 @@
             unchanged
            +added1
            +added2
             unchanged
        """)
        assert changed_lines(diff) == [2, 3]

    def test_deletion_only(self):
        diff = dedent("""\
            --- a/file.py
            +++ b/file.py
            @@ -1,3 +1,2 @@
             unchanged
            -removed
             unchanged
        """)
        assert changed_lines(diff) == []

    def test_multiple_hunks(self):
        diff = dedent("""\
            --- a/file.py
            +++ b/file.py
            @@ -1,3 +1,3 @@
             a
            -b
            +B
             c
            @@ -10,3 +10,3 @@
             x
            -y
            +Y
             z
        """)
        assert changed_lines(diff) == [2, 11]

    def test_empty_diff(self):
        assert changed_lines("") == []


class TestIndexFileFunctions:
    def test_simple_function(self):
        code = "def foo():\n    pass\n"
        funcs = index_file_functions(code)
        assert len(funcs) == 1
        assert funcs[0]["name"] == "foo"
        assert funcs[0]["start"] == 1
        assert funcs[0]["end"] == 2

    def test_multiple_functions(self):
        code = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        funcs = index_file_functions(code)
        names = {f["name"] for f in funcs}
        assert names == {"foo", "bar"}

    def test_class_methods(self):
        code = dedent("""\
            class MyClass:
                def method_a(self):
                    pass

                def method_b(self):
                    pass
        """)
        funcs = index_file_functions(code)
        names = {f["name"] for f in funcs}
        assert "method_a" in names
        assert "method_b" in names

    def test_async_function(self):
        code = "async def fetch():\n    pass\n"
        funcs = index_file_functions(code)
        assert len(funcs) == 1
        assert funcs[0]["name"] == "fetch"

    def test_nested_function(self):
        code = dedent("""\
            def outer():
                def inner():
                    pass
                return inner()
        """)
        funcs = index_file_functions(code)
        names = {f["name"] for f in funcs}
        assert "outer" in names
        assert "inner" in names


class TestExtractFunctionSource:
    def test_extracts_correct_lines(self):
        code = "import os\n\ndef foo():\n    return 1\n\ndef bar():\n    return 2\n"
        funcs = index_file_functions(code)
        foo = next(f for f in funcs if f["name"] == "foo")
        source = extract_function_source(code, foo)
        assert "def foo():" in source
        assert "return 1" in source
        assert "def bar" not in source


class TestSplitFunctionsRaw:
    def test_single_function(self):
        code = "def foo():\n    return 1\n"
        result = split_functions_raw(code)
        assert "foo" in result
        assert "return 1" in result["foo"]

    def test_multiple_functions(self):
        code = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        result = split_functions_raw(code)
        assert "foo" in result
        assert "bar" in result

    def test_async_function(self):
        code = "async def fetch():\n    await something()\n"
        result = split_functions_raw(code)
        assert "fetch" in result
        assert "async def" in result["fetch"]

    def test_decorated_function(self):
        code = "@decorator\ndef foo():\n    pass\n"
        result = split_functions_raw(code)
        assert "foo" in result
        assert "@decorator" in result["foo"]

    def test_multiple_decorators(self):
        code = "@app.route('/')\n@login_required\ndef index():\n    pass\n"
        result = split_functions_raw(code)
        assert "index" in result
        assert "@app.route" in result["index"]
        assert "@login_required" in result["index"]

    def test_ignores_nested_functions(self):
        code = dedent("""\
            def outer():
                def inner():
                    pass
                return inner()
        """)
        result = split_functions_raw(code)
        assert "outer" in result
        assert "inner" not in result

    def test_docstring_with_def(self):
        code = dedent('''\
            def foo():
                """
                This is not a def statement.
                def fake():
                    pass
                """
                return 1
        ''')
        result = split_functions_raw(code)
        assert "foo" in result
        assert "fake" not in result

    def test_invalid_syntax_returns_empty(self):
        assert split_functions_raw("def broken(") == {}

    def test_preserves_comments(self):
        code = dedent("""\
            def foo():
                # important comment
                return 1
        """)
        result = split_functions_raw(code)
        assert "# important comment" in result["foo"]


class TestGatherContext:
    def test_finds_affected_function(self):
        source = dedent("""\
            def foo():
                return 1

            def bar():
                return 2
        """)
        diff = dedent("""\
            --- a/file.py
            +++ b/file.py
            @@ -4,2 +4,2 @@
             def bar():
            -    return 2
            +    return 3
        """)
        affected = gather_context(diff, source)
        assert len(affected) == 1
        assert "bar" in affected[0]

    def test_no_affected_functions(self):
        source = "def foo():\n    return 1\n"
        diff = dedent("""\
            --- a/file.py
            +++ b/file.py
            @@ -10,1 +10,1 @@
            +unrelated
        """)
        affected = gather_context(diff, source)
        assert affected == []


class TestValidateGeneratedCode:
    def test_valid_code(self):
        assert validate_generated_code("def foo():\n    return 1") is True

    def test_invalid_syntax(self):
        assert validate_generated_code("def foo(") is False

    def test_empty_string(self):
        assert validate_generated_code("") is True

    def test_async_function(self):
        assert validate_generated_code("async def foo():\n    pass") is True


class TestReadFileContent:
    def test_reads_by_relative_path(self, tmp_path):
        f = tmp_path / "src" / "module.py"
        f.parent.mkdir()
        f.write_text("content")
        path, content = read_file_content("src/module.py", str(tmp_path))
        assert content == "content"

    def test_falls_back_to_rglob(self, tmp_path):
        f = tmp_path / "deep" / "nested" / "module.py"
        f.parent.mkdir(parents=True)
        f.write_text("found")
        path, content = read_file_content("module.py", str(tmp_path))
        assert content == "found"

    def test_returns_none_for_missing(self, tmp_path):
        path, content = read_file_content("nonexistent.py", str(tmp_path))
        assert path is None
        assert content is None


class TestAddImportsToFile:
    def test_adds_after_existing_imports(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("import os\nimport sys\n\ndef foo():\n    pass\n")
        add_imports_to_file(f, ["import json"])
        content = f.read_text()
        lines = content.splitlines()
        assert lines[2] == "import json"

    def test_skips_duplicate_imports(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("import os\n\ndef foo():\n    pass\n")
        add_imports_to_file(f, ["import os"])
        content = f.read_text()
        assert content.count("import os") == 1

    def test_no_imports_is_noop(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    pass\n")
        original = f.read_text()
        add_imports_to_file(f, [])
        assert f.read_text() == original

    def test_whole_line_match_not_substring(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("import os.path\n\ndef foo():\n    pass\n")
        add_imports_to_file(f, ["import os"])
        content = f.read_text()
        assert "import os\n" in content

    def test_preserves_trailing_newline(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("import os\n\ndef foo():\n    pass\n")
        add_imports_to_file(f, ["import json"])
        assert f.read_text().endswith("\n")


class TestGetFailingTests:
    def test_parses_report(self, tmp_path):
        report = {
            "tests": [
                {
                    "outcome": "failed",
                    "nodeid": "tests/test_foo.py::test_bar",
                    "call": {
                        "crash": {
                            "message": "assert 1 == 2",
                            "path": "/abs/src/foo.py",
                            "lineno": 10,
                        }
                    },
                },
                {
                    "outcome": "passed",
                    "nodeid": "tests/test_foo.py::test_ok",
                },
            ]
        }
        (tmp_path / "report.json").write_text(json.dumps(report))
        failures = get_failing_tests(str(tmp_path))
        assert len(failures) == 1
        assert failures[0]["function"] == "test_bar"
        assert failures[0]["crash_line"] == 10

    def test_missing_report(self, tmp_path):
        failures = get_failing_tests(str(tmp_path))
        assert failures == []

    def test_malformed_json(self, tmp_path):
        (tmp_path / "report.json").write_text("not json")
        failures = get_failing_tests(str(tmp_path))
        assert failures == []

    def test_parametrized_test_strips_params(self, tmp_path):
        report = {
            "tests": [
                {
                    "outcome": "failed",
                    "nodeid": "tests/test_math.py::test_add[1-2-3]",
                    "call": {
                        "crash": {
                            "message": "assert 1 + 2 == 4",
                            "path": "/abs/src/math.py",
                            "lineno": 5,
                        }
                    },
                },
            ]
        }
        (tmp_path / "report.json").write_text(json.dumps(report))
        failures = get_failing_tests(str(tmp_path))
        assert failures[0]["function"] == "test_add"
        assert failures[0]["nodeid"] == "tests/test_math.py::test_add[1-2-3]"
