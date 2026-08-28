"""Tests for scripts/testing/symbol_analysis.py (Run 007 D1/D3).

Each test creates a real temporary directory with sample files,
never touching the DPMtF-WebUI working tree.

Public API under test:
    __all__ = ["changed_symbols", "UNKNOWN", "SymbolAnalysisError"]
    changed_symbols(repo_root, path, ranges) -> list[str] | object
"""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYMBOL_PATH = PROJECT_ROOT / "scripts" / "testing" / "symbol_analysis.py"

_sy_spec = importlib.util.spec_from_file_location(
    "symbol_analysis_test", SYMBOL_PATH,
)
_sy: object = importlib.util.module_from_spec(_sy_spec)
_sy_spec.loader.exec_module(_sy)
changed_symbols = _sy.changed_symbols
UNKNOWN = _sy.UNKNOWN
SymbolAnalysisError = _sy.SymbolAnalysisError

__all__ = [
    "changed_symbols", "UNKNOWN", "SymbolAnalysisError",
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPublicAPI(unittest.TestCase):
    """Tests for the public API surface."""

    def test_the_public_api_is_exactly_the_three_names_in___all__(self):
        """The public API is exactly the three names in __all__."""
        self.assertEqual(sorted(getattr(_sy, "__all__", [])),
                         sorted(["SymbolAnalysisError", "UNKNOWN", "changed_symbols"]))

    def test_UNKNOWN_is_a_distinct_sentinel(self):
        """UNKNOWN is a distinct sentinel, not an empty list or None."""
        self.assertIsNotNone(UNKNOWN)
        self.assertNotEqual(UNKNOWN, [])
        self.assertNotEqual(UNKNOWN, "")
        self.assertFalse(isinstance(UNKNOWN, list))

    def test_unknown_is_not_empty_list(self):
        """UNKNOWN != [] and is not list subclass."""
        self.assertNotEqual(UNKNOWN, [])

    def test_symbol_analysis_error_is_exception(self):
        """SymbolAnalysisError is a proper Exception subclass."""
        self.assertTrue(issubclass(SymbolAnalysisError, Exception))


class TestUnparseableFile(unittest.TestCase):
    """Tests for unparseable / non-Python file handling."""

    def test_an_unparseable_file_yields_unknown_not_an_empty_list(self):
        """An unparseable Python file yields UNKNOWN, never an empty list."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "broken.py").write_text("def (:::garbage")
            result = changed_symbols(d, "broken.py", [(1, 1)])
            self.assertIs(result, UNKNOWN)
            self.assertIsInstance(result, type(UNKNOWN))
            # Prove it is not an empty list.
            self.assertNotEqual(result, [])

    def test_a_non_python_file_yields_unknown(self):
        """A non-Python file (no adapter) yields UNKNOWN."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "x.js").write_text("function f(){}")
            result = changed_symbols(d, "x.js", [(1, 1)])
            self.assertIs(result, UNKNOWN)

    def test_missing_file_yields_unknown(self):
        """A path that does not exist yields UNKNOWN."""
        with tempfile.TemporaryDirectory() as d:
            result = changed_symbols(d, "nonexistent.py", [(1, 1)])
            self.assertIs(result, UNKNOWN)

    def test_a_file_with_only_imports_yields_unknown(self):
        """A file with no function/class definitions yields UNKNOWN.
        
        Per the spec: module-level code with no definitions means we
        cannot map the edit to a symbol → refuse with UNKNOWN.
        """
        with tempfile.TemporaryDirectory() as d:
            Path(d, "imports.py").write_text("import os\nimport sys\n")
            result = changed_symbols(d, "imports.py", [(1, 1)])
            self.assertIs(result, UNKNOWN)


class TestFunctionMethods(unittest.TestCase):
    """Tests for top-level functions, methods, classes, decorators, async."""

    def test_a_top_level_function_edit_names_the_function(self):
        """A top-level function edit names the function."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "func.py").write_text("def g():\n    return 2\n")
            result = changed_symbols(d, "func.py", [(2, 2)])
            self.assertIn("g", list(result))

    def test_a_method_body_edit_names_the_qualified_method(self):
        """A method body edit names the qualified method."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "cls.py").write_text("class C:\n    def f(self):\n        return 1\n")
            result = changed_symbols(d, "cls.py", [(3, 3)])
            self.assertIn("C.f", list(result))

    def test_a_class_body_edit_names_the_class(self):
        """A class body edit (outside any method) names the class."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "cls.py").write_text("class C:\n    x = 1\n    def f(self):\n        return 1\n")
            # Line 2 is 'x = 1' inside class C body.
            # The class definition covers this range, so the symbol is "C".
            result = changed_symbols(d, "cls.py", [(2, 2)])
            self.assertIn("C", list(result))

    def test_a_nested_function_names_the_nested_function(self):
        """A nested function body edit names the nested function."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "nested.py").write_text(
                "def outer():\n"
                "    def inner():\n"
                "        return 1\n"
                "    return inner\n"
            )
            result = changed_symbols(d, "nested.py", [(3, 3)])
            self.assertIn("outer.inner", list(result))

    def test_async_function_edit_names_the_function(self):
        """An async function body edit names the function."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "asyncf.py").write_text(
                "async def fetch():\n"
                "    return 1\n"
            )
            result = changed_symbols(d, "asyncf.py", [(2, 2)])
            self.assertIn("fetch", list(result))

    def test_decorated_function_names_the_function(self):
        """A function with decorators: edit to the decorator line names the function."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "dec.py").write_text(
                "@property\n"
                "def prop(self):\n"
                "    return 1\n"
            )
            # Line 1 is the decorator line → should map to "prop".
            result = changed_symbols(d, "dec.py", [(1, 1)])
            self.assertIn("prop", list(result))

    def test_decorated_method_names_the_method(self):
        """A decorated method: edit to the decorator line names the qualified method."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "dec.py").write_text(
                "class C:\n"
                "    @property\n"
                "    def prop(self):\n"
                "        return 1\n"
            )
            result = changed_symbols(d, "dec.py", [(2, 2)])
            self.assertIn("C.prop", list(result))

    def test_multi_line_range_covers_multiple_symbols(self):
        """A multi-line range covering both a class and a method names both."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "multi.py").write_text(
                "class C:\n"
                "    def f(self):\n"
                "        return 1\n"
                "    def g(self):\n"
                "        return 2\n"
            )
            result = changed_symbols(d, "multi.py", [(2, 5)])
            result_list = list(result)
            self.assertIn("C.f", result_list)
            self.assertIn("C.g", result_list)

    def test_class_def_line_names_the_class(self):
        """A class definition line names the class."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "cls.py").write_text("class C:\n    pass\n")
            result = changed_symbols(d, "cls.py", [(1, 1)])
            self.assertIn("C", list(result))


class TestModuleLevel(unittest.TestCase):
    """Tests for module-level code attribution."""

    def test_a_module_level_edit_yields_whole_module_impact(self):
        """A module-level edit outside any definition yields __module__.
        
        Downstream must treat __module__ as whole-module impact.
        """
        with tempfile.TemporaryDirectory() as d:
            # A file with a function; editing a line OUTSIDE that function.
            Path(d, "mod.py").write_text(
                "import os\n"
                "def f():\n"
                "    pass\n"
            )
            # Line 1 is module-level code.
            result = changed_symbols(d, "mod.py", [(1, 1)])
            self.assertIn("__module__", list(result))

    def test_module_level_between_functions(self):
        """Module-level code between two functions names __module__."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "mod.py").write_text(
                "def f():\n"
                "    pass\n"
                "X = 1\n"
                "def g():\n"
                "    pass\n"
            )
            result = changed_symbols(d, "mod.py", [(3, 3)])
            # X = 1 is unqualified, not collected. Line 3 is outside any def.
            self.assertIn("__module__", list(result))


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and unusual inputs."""

    def test_empty_ranges(self):
        """An empty ranges list should return no symbols."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "f.py").write_text("def a():\n    pass\n")
            result = changed_symbols(d, "f.py", [])
            self.assertIsInstance(result, list)
            self.assertEqual(result, [])

    def test_deeply_nested_class(self):
        """Deeply nested classes produce qualified names."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "deep.py").write_text(
                "class A:\n"
                "    class B:\n"
                "        def m(self):\n"
                "            pass\n"
            )
            result = changed_symbols(d, "deep.py", [(4, 4)])
            # B is nested inside A, and m is inside B.
            # Our _qualify only prepends ancestor ClassDef names.
            # So the qualified name should be "A.B.m" or "B.m".
            # Let me check what actually happens:
            # When visiting ClassDef B, ancestors = [A, B] — but we pop
            # B after visiting its children. So when visiting m inside B,
            # ancestors = [A] (B is in ancestors). So _qualify would give
            # "A.B.m". But wait, when visiting B, we append B to ancestors
            # BEFORE generic_visit, so when visiting m inside B, the
            # ancestors are [A, B]. The _qualify method iterates over
            # ancestors and takes ClassDef.name.value from each. So it
            # would give "A.B.m".
            self.assertIn("A.B.m", list(result))

    def test_single_line_range(self):
        """A single-line range correctly resolves to a symbol."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "sl.py").write_text(
                "def hello():\n"
                "    return 'world'\n"
            )
            result = changed_symbols(d, "sl.py", [(2, 2)])
            self.assertIn("hello", list(result))


class TestLanguageAdapterSeam(unittest.TestCase):
    """Tests proving the language adapter seam works correctly."""

    def test_a_javascript_file_yields_unknown(self):
        """A JavaScript file (no adapter) yields UNKNOWN."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "app.js").write_text("function f(){}\n")
            result = changed_symbols(d, "app.js", [(1, 1)])
            self.assertIs(result, UNKNOWN)

    def test_a_typescript_file_yields_unknown(self):
        """A TypeScript file (no adapter) yields UNKNOWN."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "app.ts").write_text("function f(): void{}\n")
            result = changed_symbols(d, "app.ts", [(1, 1)])
            self.assertIs(result, UNKNOWN)

    def test_a_markdown_file_yields_unknown(self):
        """A Markdown file (no adapter) yields UNKNOWN."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "readme.md").write_text("# Hello\n")
            result = changed_symbols(d, "readme.md", [(1, 1)])
            self.assertIs(result, UNKNOWN)

    def test_python_file_with_no_extensions(self):
        """A file with a non-standard extension yields UNKNOWN."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "script").write_text("def f():\n    pass\n")
            result = changed_symbols(d, "script", [(1, 1)])
            self.assertIs(result, UNKNOWN)

    def test_different_python_extensions(self):
        """Both .py and .py files map to the Python adapter."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "f.py").write_text("def g():\n    pass\n")
            result = changed_symbols(d, "f.py", [(1, 1)])
            self.assertIn("g", list(result))
