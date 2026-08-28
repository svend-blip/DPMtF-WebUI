"""Tests for scripts/testing/dependency_graph.py.

Exercises all six public names plus Graph and Closure internals using
temporary directory trees only. No new dependencies - stdlib imports
only. Tests never execute dependency_graph.py via subprocess/coverage/
pytest plugins; all functions are imported and called directly.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Load dependency_graph.py via importlib (no sys.path tricks).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DG_PATH = _PROJECT_ROOT / "scripts" / "testing" / "dependency_graph.py"

_spec = importlib.util.spec_from_file_location("dependency_graph", DG_PATH)
dg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dg)

Graph = dg.Graph
Closure = dg.Closure
build_graph = dg.build_graph
reverse_closure = dg.reverse_closure
node_id = dg.node_id
split_node = dg.split_node
UNRESOLVED = dg.UNRESOLVED
GraphError = dg.GraphError


def test_a_same_module_symbol_dependency_is_traversable():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "a.py").write_text(
            "def foo():\n"
            "    pass\n"
            "\n"
            "def bar():\n"
            "    foo()\n"
        )
        g = build_graph(tmpdir)
        closure = reverse_closure(g, [node_id("a.py", "foo")])
        assert node_id("a.py", "foo") in closure.nodes, (
            f"foo should be in closure; nodes={closure.nodes}"
        )
        assert node_id("a.py", "bar") in closure.nodes, (
            f"bar should depend on foo; closure nodes: {closure.nodes}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_a_cross_module_symbol_dependency_is_traversable():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "utils.py").write_text(
            "def fn():\n"
            "    pass\n"
        )
        (Path(tmpdir) / "main.py").write_text(
            "from utils import fn\n"
            "\n"
            "fn()\n"
        )
        g = build_graph(tmpdir)
        closure = reverse_closure(g, [node_id("utils.py", "fn")])
        assert "main.py" in closure.nodes, (
            f"main.py should depend on utils.py.fn; nodes={closure.nodes}"
        )
        assert node_id("utils.py", "fn") in closure.nodes
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_reverse_closure_reaches_a_transitive_dependent():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "leaf.py").write_text(
            "def compute(x):\n"
            "    return x + 1\n"
        )
        (Path(tmpdir) / "middle.py").write_text(
            "from leaf import compute\n"
            "\n"
            "def process(val):\n"
            "    return compute(val)\n"
        )
        (Path(tmpdir) / "top.py").write_text(
            "from middle import process\n"
            "\n"
            "def run():\n"
            "    return process(42)\n"
        )
        g = build_graph(tmpdir)
        closure = reverse_closure(g, [node_id("leaf.py", "compute")])
        assert node_id("leaf.py", "compute") in closure.nodes
        assert "middle.py" in closure.nodes, (
            f"middle.py should be in closure; nodes={closure.nodes}"
        )
        assert "top.py" in closure.nodes, (
            f"top.py should be transitively in closure; nodes={closure.nodes}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_a_dynamic_call_target_is_unresolved_not_absent():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "unsafe.py").write_text("eval('code')\n")
        g = build_graph(tmpdir)
        assert node_id("unsafe.py") in g.unresolved, (
            f"unsafe.py should be marked UNRESOLVED; unresolved={g.unresolved}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_a_seed_absent_from_the_graph_is_unresolved_not_empty():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "a.py").write_text("pass\n")
        g = build_graph(tmpdir)
        closure = reverse_closure(g, ["nonexistent.py"])
        assert "nonexistent.py" in closure.unresolved, (
            f"Absent seed should appear in unresolved; "
            f"unresolved={closure.unresolved}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_the_closure_is_identical_across_repeated_builds():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "a.py").write_text(
            "def x():\n    pass\n"
            "def y():\n    x()\n"
        )
        results = []
        for _ in range(5):
            g = build_graph(tmpdir)
            c = reverse_closure(g, [node_id("a.py", "x")])
            results.append((list(c.nodes), list(c.unresolved), c.is_safe))
        assert all(r == results[0] for r in results), (
            f"Closures should be identical across runs; got {results}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_two_symbols_in_one_large_module_have_distinct_closures():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "alpha.py").write_text(
            "def alpha_fn():\n    pass\n"
            "def beta_fn():\n    pass\n"
        )
        (Path(tmpdir) / "user.py").write_text(
            "from alpha import alpha_fn, beta_fn\n"
            "\n"
            "alpha_fn()\n"
            "beta_fn()\n"
        )
        g = build_graph(tmpdir)
        c_alpha = reverse_closure(g, [node_id("alpha.py", "alpha_fn")])
        c_beta = reverse_closure(g, [node_id("alpha.py", "beta_fn")])
        assert node_id("alpha.py", "alpha_fn") in c_alpha.nodes
        assert node_id("alpha.py", "beta_fn") in c_beta.nodes
        assert "user.py" in c_alpha.nodes
        assert "user.py" in c_beta.nodes
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_unresolved_node_keeps_resolvable_edges():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "mixed.py").write_text(
            "import os\n"
            "import sys\n"
            "\n"
            "eval(user_input)\n"
        )
        g = build_graph(tmpdir)
        mod = node_id("mixed.py")
        assert mod in g.unresolved, (
            f"mixed.py should be unresolved; unresolved={g.unresolved}"
        )
        rev = g.reverse.get(mod, set())
        assert len(rev) > 0, (
            f"mixed.py should have reverse edges despite being unresolved; "
            f"reverse={g.reverse}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_star_import_marks_importing_module_unresolved():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "lib.py").write_text(
            "def exported():\n    pass\n"
        )
        (Path(tmpdir) / "client.py").write_text(
            "from lib import *\n"
            "exported()\n"
        )
        g = build_graph(tmpdir)
        client_node = node_id("client.py")
        assert client_node in g.unresolved, (
            f"client.py should be unresolved due to star import; "
            f"unresolved={g.unresolved}"
        )
        # The symbol used in the star-imported module should be in graph nodes
        lib_exported = node_id("lib.py", "exported")
        assert lib_exported in g.nodes, (
            f"lib.py's exported symbol should be a node; nodes={g.nodes}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_import_cycle_terminates():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "a.py").write_text(
            "from b import fn_b\n"
            "def fn_a():\n    fn_b()\n"
        )
        (Path(tmpdir) / "b.py").write_text(
            "from a import fn_a\n"
            "def fn_b():\n    fn_a()\n"
        )
        g = build_graph(tmpdir)
        closure = reverse_closure(g, [node_id("a.py")])
        assert len(closure.nodes) > 0, "Closure must be non-empty"
        assert len(closure.nodes) <= 10, (
            f"Cycle closure should be finite; got {len(closure.nodes)} nodes"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_closure_serialization_is_deterministic():
    import json
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "x.py").write_text(
            "def foo():\n    pass\n"
            "def bar():\n    foo()\n"
        )
        g = build_graph(tmpdir)
        c1 = reverse_closure(g, [node_id("x.py", "foo")])
        c2 = reverse_closure(g, [node_id("x.py", "foo")])
        s1 = json.dumps({"nodes": c1.nodes, "unresolved": c1.unresolved, "is_safe": c1.is_safe}, sort_keys=True)
        s2 = json.dumps({"nodes": c2.nodes, "unresolved": c2.unresolved, "is_safe": c2.is_safe}, sort_keys=True)
        assert s1 == s2, (
            f"Closure serialization should be deterministic; "
            f"{s1} != {s2}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_parse_failure_marks_file_unresolved():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "bad.py").write_text("def broken(\n")
        g = build_graph(tmpdir)
        bad_node = node_id("bad.py")
        assert bad_node in g.unresolved, (
            f"bad.py should be unresolved due to SyntaxError; "
            f"unresolved={g.unresolved}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_class_scoped_symbol_dependency():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "klass.py").write_text(
            "class MyClass:\n"
            "    def method(self):\n"
            "        pass\n"
            "\n"
            "def caller():\n"
            "    obj = MyClass()\n"
            "    obj.method()\n"
        )
        g = build_graph(tmpdir)
        assert node_id("klass.py", "caller") in g.nodes
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_nested_class_scoped_symbol():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "nested.py").write_text(
            "class A:\n"
            "    class B:\n"
            "        def m(self):\n"
            "            pass\n"
        )
        g = build_graph(tmpdir)
        # Nested class methods should be registered as nodes
        assert node_id("nested.py", "m") in g.nodes, (
            f"nested class method node should exist; nodes={g.nodes}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_module_level_attribute_assignment():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "registry.py").write_text(
            "class Registry:\n"
            "    pass\n"
            "\n"
            "registry = Registry()\n"
            "registry.fn = lambda: None\n"
        )
        g = build_graph(tmpdir)
        assert node_id("registry.py") in g.nodes
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_importlib_dynamic_import_marked_unresolved():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "dynamic_mod.py").write_text(
            "import importlib\n"
            "mod_name = get_module_name()\n"
            "importlib.import_module(mod_name)\n"
        )
        g = build_graph(tmpdir)
        dyn_node = node_id("dynamic_mod.py")
        assert dyn_node in g.unresolved, (
            f"dynamic_mod.py should be UNRESOLVED; "
            f"unresolved={g.unresolved}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_setattr_dynamic_unresolved():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "setattr_mod.py").write_text(
            "setattr(obj, computed_name, val)\n"
        )
        g = build_graph(tmpdir)
        setattr_node = node_id("setattr_mod.py")
        assert setattr_node in g.unresolved, (
            f"setattr_mod.py should be UNRESOLVED; "
            f"unresolved={g.unresolved}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_globals_eval_dynamic_unresolved():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "globals_mod.py").write_text(
            "(lambda: eval('code'))()\n"
        )
        g = build_graph(tmpdir)
        globals_node = node_id("globals_mod.py")
        assert globals_node in g.unresolved, (
            f"globals_mod.py should be UNRESOLVED; "
            f"unresolved={g.unresolved}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_graph_add_node_is_idempotent():
    g = Graph()
    g._add_node("x.py")
    g._add_node("x.py")
    assert len(g.nodes) == 1, (
        f"Adding same node twice should not duplicate; nodes={g.nodes}"
    )


def test_graph_add_edge_creates_both_directions():
    g = Graph()
    a = node_id("a.py")
    b = node_id("b.py")
    g._add_edge(a, b)
    assert b in g.reverse[a], "reverse[a] should contain b"
    assert a in g.forward[b], "forward[b] should contain a"


def test_isolated_module_has_no_edges():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "isolated.py").write_text("X = 42\n")
        g = build_graph(tmpdir)
        mod = node_id("isolated.py")
        assert mod in g.nodes
        assert len(g.forward.get(mod, set())) == 0, (
            f"isolated.py should have no forward edges; forward={g.forward.get(mod, set())}"
        )
        assert len(g.reverse.get(mod, set())) == 0, (
            f"isolated.py should have no reverse edges; reverse={g.reverse.get(mod, set())}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cross_module_static_import_creates_module_edge():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "foo.py").write_text("pass\n")
        (Path(tmpdir) / "main.py").write_text(
            "import foo\n"
            "foo.something()\n"
        )
        g = build_graph(tmpdir)
        main_mod = node_id("main.py")
        foo_mod = node_id("foo.py")
        assert main_mod in g.nodes
        assert foo_mod in g.nodes
        assert foo_mod in g.reverse[main_mod], (
            f"main.py should depend on foo.py; reverse={g.reverse.get(main_mod, set())}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_unknown_call_target_is_unresolved():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "orphan.py").write_text(
            "does_not_exist()\n"
        )
        g = build_graph(tmpdir)
        mod = node_id("orphan.py")
        assert mod in g.nodes, (
            f"orphan.py should be a node; nodes={g.nodes}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_closure_is_safe_when_no_unresolved():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "safe.py").write_text(
            "import os\n"
            "os.path.join('a', 'b')\n"
        )
        g = build_graph(tmpdir)
        mod = node_id("safe.py")
        closure = reverse_closure(g, [mod])
        assert closure.is_safe, (
            f"closure should be safe; unresolved={closure.unresolved}"
        )
        assert len(closure.unresolved) == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_closure_is_not_safe_with_unresolved():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "unsafe.py").write_text(
            "def do_eval():\n    eval('code')\n"
        )
        (Path(tmpdir) / "caller.py").write_text(
            "from unsafe import do_eval\n"
            "do_eval()\n"
        )
        g = build_graph(tmpdir)
        unsafe_mod = node_id("unsafe.py")
        # The module itself should be marked unresolved due to eval()
        assert unsafe_mod in g.unresolved, (
            f"unsafe.py should be in g.unresolved; unresolved={g.unresolved}"
        )
        # Starting reverse_closure from the unresolved module node should
        # produce a closure where is_safe is False.
        closure = reverse_closure(g, [unsafe_mod])
        assert unsafe_mod in closure.nodes, (
            f"unsafe.py should be in closure nodes; nodes={closure.nodes}"
        )
        assert unsafe_mod in closure.unresolved, (
            f"unsafe.py should be in closure.unresolved; "
            f"unresolved={closure.unresolved}"
        )
        assert not closure.is_safe, "closure should not be safe"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_node_id_round_trip():
    for path, sym in [
        ("a.py", None),
        ("a.py", "foo"),
        ("sub/b.py", "bar.baz"),
        ("deep/path/to/module.py", "ClassName.method"),
    ]:
        nid = node_id(path, sym)
        result_path, result_sym = split_node(nid)
        assert (result_path, result_sym) == (path, sym), (
            f"Round-trip failed for ({path}, {sym})"
        )


def test_build_graph_returns_graph_instance():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "a.py").write_text("pass\n")
        g = build_graph(tmpdir)
        assert isinstance(g, Graph), (
            f"build_graph should return Graph instance; got {type(g)}"
        )
        assert "a.py" in g.nodes
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_closure_contains_only_reachable_nodes():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "a.py").write_text("pass\n")
        (Path(tmpdir) / "b.py").write_text("pass\n")
        g = build_graph(tmpdir)
        closure = reverse_closure(g, [node_id("a.py")])
        assert "a.py" in closure.nodes
        assert "b.py" not in closure.nodes, (
            f"b.py should not be reachable from a.py; "
            f"closure.nodes={closure.nodes}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_graph_nodes_set_contains_unresolved():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "broken.py").write_text("def bad(\n")
        g = build_graph(tmpdir)
        broken_mod = node_id("broken.py")
        assert broken_mod in g.nodes, (
            f"broken.py should be in nodes; nodes={g.nodes}"
        )
        assert broken_mod in g.unresolved
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_reverse_closure_with_empty_seeds():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "a.py").write_text("pass\n")
        g = build_graph(tmpdir)
        closure = reverse_closure(g, [])
        assert len(closure.nodes) == 0, (
            f"Empty seeds should produce empty closure; nodes={closure.nodes}"
        )
        assert closure.is_safe
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_node_id_with_tab_separator():
    a = node_id("a.py", "foo")
    assert "\t" in a, f"node_id should contain tab separator; got: {repr(a)}"
    path, sym = split_node(a)
    assert path == "a.py"
    assert sym == "foo"
    module_only = node_id("a.py")
    assert "\t" not in module_only


def test_module_symbols_are_registered_as_nodes():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "funcs.py").write_text(
            "def hello():\n    pass\n"
            "def world():\n    pass\n"
        )
        g = build_graph(tmpdir)
        assert node_id("funcs.py", "hello") in g.nodes
        assert node_id("funcs.py", "world") in g.nodes
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_duplicate_imports_dont_create_duplicate_edges():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "dep.py").write_text("pass\n")
        (Path(tmpdir) / "multi.py").write_text(
            "import dep\n"
            "import dep\n"
            "dep.foo()\n"
            "dep.bar()\n"
        )
        g = build_graph(tmpdir)
        multi_mod = node_id("multi.py")
        dep_mod = node_id("dep.py")
        edge_count = len(g.reverse.get(multi_mod, set()))
        assert dep_mod in g.reverse.get(multi_mod, set()), (
            f"multi.py should depend on dep.py; reverse={g.reverse.get(multi_mod, set())}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_serialize_nodes_returns_sorted_string():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "c.py").write_text("pass\n")
        (Path(tmpdir) / "a.py").write_text("pass\n")
        (Path(tmpdir) / "b.py").write_text("pass\n")
        g = build_graph(tmpdir)
        serialized = g.serialize_nodes()
        lines = serialized.split("\n")
        assert lines == sorted(lines), (
            f"serialize_nodes should return sorted output; got {lines}"
        )
        assert len(lines) == 3
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_graph_error_inherits_from_exception():
    assert issubclass(GraphError, Exception)
    try:
        raise GraphError("test")
    except Exception as e:
        assert str(e) == "test"


def test_closure_unresolved_sorted():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "z.py").write_text("eval('x')\n")
        (Path(tmpdir) / "a.py").write_text("from z import x\n")
        g = build_graph(tmpdir)
        closure = reverse_closure(g, [node_id("a.py")])
        assert closure.unresolved == sorted(closure.unresolved), (
            f"closure.unresolved should be sorted; got {closure.unresolved}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_closure_nodes_sorted():
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "z.py").write_text("pass\n")
        (Path(tmpdir) / "a.py").write_text("pass\n")
        g = build_graph(tmpdir)
        closure = reverse_closure(g, [node_id("a.py"), node_id("z.py")])
        assert closure.nodes == sorted(closure.nodes), (
            f"closure.nodes should be sorted; got {closure.nodes}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_edge_direction_reverse_vs_forward():
    g = Graph()
    a = node_id("a.py")
    b = node_id("b.py")
    g._add_edge(a, b)
    assert a in g.forward[b], "forward[b] should contain a (a depends on b)"
    assert b in g.reverse[a], "reverse[a] should contain b (a depends on b)"
    assert b not in g.reverse[b], "b should not depend on itself"
    assert a not in g.forward[a], "a should not depend on itself"


def test_getattr_dynamic_call_target_marks_function_unresolved():
    """Regression: getattr(o, computed_name)() must leave the caller unresolved."""
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "mod.py").write_text(
            "def f(o, n):\n"
            "    return getattr(o, n)()\n"
        )
        g = build_graph(tmpdir)
        closure = reverse_closure(g, [node_id("mod.py", "f")])
        assert node_id("mod.py", "f") in closure.unresolved, (
            f"Function containing dynamic getattr must be unresolved; "
            f"unresolved={closure.unresolved}"
        )
        assert not closure.is_safe, (
            f"Closure with dynamic getattr must not be safe; "
            f"is_safe={closure.is_safe}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_star_import_creates_dependency_from_source_to_importer():
    """Regression: reverse_closure of a star-import source module must include the importer."""
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "lib.py").write_text(
            "def exported():\n    pass\n"
            "CONST = 42\n"
        )
        (Path(tmpdir) / "client.py").write_text(
            "from lib import *\n"
            "exported()\n"
        )
        g = build_graph(tmpdir)
        closure = reverse_closure(g, [node_id("lib.py")])
        assert "client.py" in closure.nodes, (
            f"client.py must be in closure of lib.py; "
            f"nodes={closure.nodes}"
        )
        assert "client.py" in closure.unresolved, (
            f"client.py (star import) must be in closure.unresolved; "
            f"unresolved={closure.unresolved}"
        )
        assert not closure.is_safe, (
            f"Closure with star-import dependent must not be safe"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_getattr_module_level_dynamic_call():
    """Regression: module-level getattr must mark the module unresolved."""
    tmpdir = tempfile.mkdtemp()
    try:
        (Path(tmpdir) / "mod.py").write_text(
            "x = 1\n"
            "def get():\n"
            "    return input()\n"
            "obj = get()\n"
            "getattr(obj, obj.attr)()\n"
        )
        g = build_graph(tmpdir)
        closure = reverse_closure(g, [node_id("mod.py")])
        assert node_id("mod.py") in closure.unresolved or any(
            n in closure.unresolved for n in closure.nodes
        ), (
            f"getattr with non-constant attr must produce unresolved; "
            f"unresolved={closure.unresolved}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
