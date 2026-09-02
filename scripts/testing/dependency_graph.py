"""Dependency graph builder for Python source files.

Builds a deterministic dependency graph from .py files in a directory tree,
tracks module and symbol-level edges, marks unresolved constructs, and
provides reverse-closure computation for impact analysis.

Built on Python stdlib ast only. No new dependencies.
"""

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Set, Tuple

__all__ = [
    "build_graph",
    "reverse_closure",
    "node_id",
    "split_node",
    "Graph",
    "Closure",
    "UNRESOLVED",
    "GraphError",
]

# Sentinel: marks nodes whose dependencies cannot be statically resolved.
UNRESOLVED = object()

# Custom exception for invariant violations inside the module.
class GraphError(Exception):
    pass


# ---------------------------------------------------------------------------
# Node identity helpers (language-neutral)
# ---------------------------------------------------------------------------


#: Directories that are never part of the repository's own code. Walking
#: them made the dependency graph and the test index treat
#: ``venv/lib/python3.12/site-packages/attrs/validators.py`` as a test of
#: this repository (51 such "tests" selected on 2026-09-02) and cost most
#: of the graph-build time.
_EXCLUDED_DIRS = frozenset({
    "venv", ".venv", "env", ".env", "node_modules", "__pycache__", ".git",
    "site-packages", "build", "dist", ".tox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".eggs",
})


def _is_excluded(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    return any(part in _EXCLUDED_DIRS for part in rel.parts[:-1])


def node_id(path: str, symbol: Optional[str] = None) -> str:
    """Return a node identifier for the given path and optional symbol.

    When *symbol* is None, returns a module node.
    When *symbol* is provided, returns ``path<TAB>symbol`` (separator is
    an implementation detail; must round-trip with :func:`split_node`).

    The path is the file path as seen relative to the build root.
    This function is language-neutral: the symbol part is passed through
    unharmed.
    """
    if symbol is None:
        return path
    return f"{path}\t{symbol}"


def split_node(node: str) -> Tuple[str, Optional[str]]:
    """Exact inverse of :func:`node_id`.

    Returns ``(path, symbol_or_None)``.  Round-tripping is the contract:
    ``split_node(node_id(p)) == (p, None)`` and
    ``split_node(node_id(p, s)) == (p, s)`` for any symbol *s*.
    """
    idx = node.find("\t")
    if idx < 0:
        return node, None
    return node[:idx], node[idx + 1:]


# ---------------------------------------------------------------------------
# Graph data structure
# ---------------------------------------------------------------------------

class Graph:
    """Container holding the collected dependency evidence."""

    def __init__(self) -> None:
        # All nodes seen during build (including unresolved ones).
        self.nodes: Set[str] = set()

        # Forward edges: forward[node] = {dependent1, dependent2, ...}
        # Meaning: "these nodes depend ON node".
        self.forward: dict[str, set[str]] = {}

        # Reverse edges: reverse[node] = {dependency1, dependency2, ...}
        # Meaning: "node depends ON these".
        self.reverse: dict[str, set[str]] = {}

        # Nodes marked UNRESOLVED.
        self.unresolved: Set[str] = set()

    # -- internal helpers (not part of public API) --

    def _add_node(self, node: str, unresolved: bool = False) -> None:
        """Register *node* in the graph."""
        self.nodes.add(node)
        if unresolved:
            self.unresolved.add(node)
        # Ensure edge-map entries exist even for leaf nodes.
        if node not in self.forward:
            self.forward[node] = set()
        if node not in self.reverse:
            self.reverse[node] = set()

    def _add_edge(self, from_node: str, to_node: str) -> None:
        """Record a directed edge: *from_node* depends on *to_node*."""
        if from_node not in self.nodes:
            self._add_node(from_node)
        if to_node not in self.nodes:
            self._add_node(to_node)
        self.reverse[from_node].add(to_node)
        self.forward[to_node].add(from_node)

    def serialize_nodes(self) -> str:
        """Return a sorted newline-separated string of all nodes."""
        return "\n".join(sorted(self.nodes))

    def serialize_reverse(self) -> str:
        """Return a string of ``node -> dep1, dep2`` lines, sorted."""
        lines = []
        for node in sorted(self.reverse):
            deps = sorted(self.reverse[node])
            if deps:
                lines.append(f"{node} -> {', '.join(deps)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Closure data structure
# ---------------------------------------------------------------------------

@dataclass
class Closure:
    """Result of a reverse-closure traversal."""

    nodes: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    is_safe: bool = True


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _is_constant_string(node: ast.AST) -> bool:
    """Return True if *node* is a literal string constant."""
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _extract_module_symbols(tree: ast.Module) -> dict[str, str]:
    """Return a map from module-level name to its fully-qualified symbol id.

    Handles FunctionDef, AsyncFunctionDef, ClassDef, and attribute assignments
    (``obj.attr = value``) at module level.
    """
    symbols: dict[str, str] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols[node.name] = node.name
        elif isinstance(node, ast.ClassDef):
            symbols[node.name] = node.name
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    # Qualified assignment: obj.attr = value
                    prefix = _ast_name_str(target.value)
                    if prefix is not None:
                        qualified = f"{prefix}.{target.attr}"
                        symbols[qualified] = qualified
                elif isinstance(target, ast.Name):
                    symbols[target.id] = target.id
    return symbols


def _extract_class_scoped_symbols(
    class_node: ast.ClassDef,
) -> dict[str, str]:
    """Extract symbols defined inside a class body.

    Returns qualified names like ``ClassName.method``.
    """
    symbols: dict[str, str] = {}
    for node in ast.iter_child_nodes(class_node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols[node.name] = f"{class_node.name}.{node.name}"
        elif isinstance(node, ast.ClassDef):
            for sub_name, sub_sym in _extract_class_scoped_symbols(node).items():
                symbols[sub_name] = f"{class_node.name}.{sub_sym}"
    return symbols


def _ast_name_str(node: ast.AST) -> Optional[str]:
    """Return the dotted name of a Name or Attribute AST node, or None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _ast_name_str(node.value)
        if parent is not None:
            return f"{parent}.{node.attr}"
    return None


def _unqualified_name(node: ast.AST) -> Optional[str]:
    """Return just the last component of a Name/Attribute expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


# ---------------------------------------------------------------------------
# Cross-module index
# ---------------------------------------------------------------------------

def _build_cross_module_index(
    module_symbols: dict[str, dict[str, str]],
) -> dict[str, tuple[str, str]]:
    """Map an imported name to ``(module_path, definition_symbol)``.

    *module_symbols* is::

        { module_path: { local_name: qualified_symbol_id } }
    """
    index: dict[str, tuple[str, str]] = {}
    for mod_path, syms in module_symbols.items():
        for local_name, qual_id in syms.items():
            # Use the simple name (last component) as the import key.
            key = qual_id.split(".")[-1]
            if key not in index:
                index[key] = (mod_path, qual_id)
    return index


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

def build_graph(root_dir: str) -> Graph:
    """Build a dependency graph from all .py files under *root_dir*.

    Returns a :class:`Graph` instance.  Uses only Python stdlib (``ast``,
    ``os``).  Third-party / stdlib imports are silently ignored.

    Algorithm:
    1. Walk *root_dir*, collect .py files.
    2. First pass: parse each file, extract symbols, record module-level
       edges and call-site edges.
    3. Second pass: resolve cross-module symbol references.
    """
    g = Graph()
    root = Path(root_dir).resolve()

    # -- Step 1: discover .py files (sorted for determinism) --
    py_files: list[Path] = sorted(
        f for f in root.rglob("*.py") if not _is_excluded(f, root)
    )

    # -- Step 2: first pass — parse, build symbol map, record edges --
    # module_symbols[module_path] = { local_name: qualified_symbol_id }
    module_symbols: dict[str, dict[str, str]] = {}
    # Per-file data for second pass:
    # file_data[module_path] = {
    #   "names": set of imported simple names,
    #   "uses": set of names used but not defined locally,
    #   "defs": dict of locally defined names -> qualified ids,
    #   "is_unresolved": bool,
    # }
    file_data: dict[str, dict] = {}

    for fpath in py_files:
        rel = str(fpath.relative_to(root))
        mod_node = node_id(rel)
        g._add_node(mod_node)

        file_info: dict = {
            "names": set(),           # imported simple names
            "uses": set(),            # names used but not in defs
            "defs": {},               # local_name -> qualified_symbol_id
            "is_unresolved": False,
            "star_imports": False,
            "import_map": {},         # simple_name -> module_node
            "import_sym_map": {},     # simple_name -> symbol_node
        }

        try:
            source = fpath.read_text(encoding="utf-8")
        except OSError:
            g.unresolved.add(mod_node)
            file_info["is_unresolved"] = True
            module_symbols[rel] = file_info["defs"]
            file_data[rel] = file_info
            continue

        try:
            tree = ast.parse(source, filename=str(fpath))
        except SyntaxError:
            g.unresolved.add(mod_node)
            file_info["is_unresolved"] = True
            module_symbols[rel] = file_info["defs"]
            file_data[rel] = file_info
            continue

        # -- Extract module-level symbols --
        defs = _extract_module_symbols(tree)
        file_info["defs"] = defs

        # -- Walk AST for edges and unresolved triggers --
        _walk_file(
            tree=tree,
            mod_node=mod_node,
            defs=defs,
            root=root,
            rel=rel,
            file_info=file_info,
            g=g,
        )

        module_symbols[rel] = defs
        file_data[rel] = file_info

    # -- Step 3: second pass — cross-module symbol resolution --
    cross_index = _build_cross_module_index(module_symbols)

    for rel, info in file_data.items():
        mod_node = node_id(rel)
        # For star imports from a known source module, create a proper edge
        # so that reverse_closure of the source module includes the importer.
        if info["star_imports"] and info["import_map"]:
            source_mod = info["import_map"].get("*")
            if source_mod and source_mod != node_id("*.py") and source_mod != mod_node:
                g._add_edge(mod_node, source_mod)
        for imp_name in info["names"]:
            # Skip if the name is defined locally in this file.
            if imp_name in info["defs"]:
                continue
            # Try to resolve to a specific symbol.
            if imp_name in cross_index:
                target_mod, target_sym = cross_index[imp_name]
                if target_mod == rel:
                    # Same module, already handled.
                    continue
                target_mod_node = node_id(target_mod)
                target_sym_node = node_id(target_mod, target_sym.split(".")[-1])
                g._add_edge(mod_node, target_mod_node)
                g._add_edge(mod_node, target_sym_node)
            else:
                # Cannot resolve — add symbol -> module edge.
                target_mod_node = node_id(imp_name + ".py" if not imp_name.endswith(".py") else imp_name)
                # Conservative: just record the import target as a module.
                # The importing module depends on it.
                g._add_edge(mod_node, target_mod_node)

    return g


def _walk_file(
    tree: ast.Module,
    mod_node: str,
    defs: dict[str, str],
    root: Path,
    rel: str,
    file_info: dict,
    g: Graph,
) -> None:
    """Walk a parsed AST, recording edges and unresolved triggers.

    *defs* is the set of module-level names defined in the file.
    *file_info* is mutated in-place for the second pass.
    """
    # Collect class-scoped definitions.
    class_defs: dict[str, dict[str, str]] = {}
    for item in ast.iter_child_nodes(tree):
        if isinstance(item, ast.ClassDef):
            class_defs[item.name] = _extract_class_scoped_symbols(item)

    # Register all function/class symbol nodes.
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            g._add_node(node_id(rel, node.name))

    # Build line→caller mapping using a recursive visitor to track nesting.
    caller_at_line: dict[int, Optional[str]] = {}
    def _map_context(
        node: ast.AST, enclosing: Optional[str]
    ) -> None:
        nonlocal caller_at_line
        new_enclosing = enclosing
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sym = node_id(rel, node.name)
            g._add_node(sym)
            new_enclosing = sym
        for child in ast.iter_child_nodes(node):
            if hasattr(child, 'lineno'):
                caller_at_line[child.lineno] = new_enclosing
            _map_context(child, new_enclosing)
    _map_context(tree, None)

    # Walk ALL nodes and process with context.
    for node in ast.walk(tree):
        line = getattr(node, 'lineno', None)
        if line is not None:
            caller = caller_at_line.get(line)
        else:
            caller = None

        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_name = alias.asname or alias.name
                mod_part = alias.name.split(".")[0]
                candidate = node_id(mod_part + ".py" if not mod_part.endswith(".py") else mod_part)
                if candidate in g.nodes:
                    g._add_edge(mod_node, candidate)
                register_import(mod_name, file_info)
                # Track: name → module node for cross-module edges
                file_info["import_map"][mod_name] = candidate

        elif isinstance(node, ast.ImportFrom):
            mod_name = node.module or ""
            mod_part = mod_name.split(".")[0]
            target_mod = node_id(mod_part + ".py" if not mod_part.endswith(".py") else mod_part)
            if node.names and node.names[0].name == "*":
                file_info["star_imports"] = True
                g.unresolved.add(mod_node)
            for alias in node.names:
                imp_name = alias.asname or alias.name
                register_import(imp_name, file_info)
                register_use(imp_name, file_info)
                # Track: name → (source_module, symbol_name) for cross-module edges
                file_info["import_map"][imp_name] = target_mod
                # Also track: name → symbol node within source module
                if alias.name != "*":
                    sym = node_id(target_mod, alias.name)
                    file_info["import_sym_map"][imp_name] = sym

        elif isinstance(node, ast.Call):
            func = node.func
            unresolved = _detect_dynamic_call(node)
            if unresolved:
                file_info["is_unresolved"] = True
                g.unresolved.add(mod_node)
                # Add the caller symbol when known (e.g. getattr with
                # non-constant argument inside a function) so that
                # reverse_closure([function_symbol]) also sees the
                # caller as unresolved.
                if caller:
                    g.unresolved.add(caller)
                continue
            name = _unqualified_name(func)
            if name:
                if not is_local(name, defs, class_defs):
                    register_use(name, file_info)
                    # Check if it's an imported symbol → create cross-module edge
                    sym_target = file_info["import_sym_map"].get(name)
                    if sym_target and sym_target != mod_node:
                        edge_from = caller if caller else mod_node
                        g._add_edge(edge_from, sym_target)
                else:
                    target = resolve_name(name, defs, class_defs, rel)
                    if target and target != mod_node:
                        edge_from = caller if caller else mod_node
                        g._add_edge(edge_from, target)


def _detect_dynamic_call(node: ast.Call) -> bool:
    """Return True if the call is a dynamic/unresolvable trigger."""
    func = node.func
    if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
        return True
    if (isinstance(func, ast.Name)
            and func.id == "getattr"
            and len(node.args) >= 2
            and not _is_constant_string(node.args[1])):
        return True
    if (isinstance(func, ast.Name) and func.id == "getattr"):
        for kw in node.keywords:
            if kw.arg == "attr" and kw.value and not _is_constant_string(kw.value):
                return True
    if (isinstance(func, ast.Name)
            and func.id == "setattr"
            and len(node.args) >= 2
            and not _is_constant_string(node.args[1])):
        return True
    if isinstance(func, ast.Name) and func.id == "__import__":
        if node.args and not _is_constant_string(node.args[0]):
            return True
    if isinstance(func, ast.Call):
        cf = func.func
        if (isinstance(cf, ast.Attribute)
                and cf.attr == "eval"
                and isinstance(cf.value, ast.Call)):
            inner = cf.value
            if isinstance(inner.func, ast.Name) and inner.func.id == "globals":
                return True
    if isinstance(func, ast.Attribute) and func.attr == "import_module":
        if (isinstance(func.value, ast.Name)
                and func.value.id == "importlib"
                and node.args
                and not _is_constant_string(node.args[0])):
            return True
    return False


def register_import(simple_name: str, file_info: dict) -> None:
    """Record an imported simple name."""
    file_info["names"].add(simple_name)


def register_use(name: str, file_info: dict) -> None:
    """Record that a name is used."""
    file_info["uses"].add(name)


def is_local(name: str, defs: dict, class_defs: dict) -> bool:
    """Check if a name is defined locally in the current file."""
    return name in defs or any(
        name in cls_syms for cls_syms in class_defs.values()
    )


def resolve_name(
    name: str,
    defs: dict[str, str],
    class_defs: dict[str, dict[str, str]],
    rel: str,
) -> Optional[str]:
    """Resolve a simple name to a node id within the current file."""
    if name in defs:
        qual = defs[name]
        if qual != name:
            return node_id(rel, qual.split(".")[-1])
        return node_id(rel, name)
    for cls_name, cls_syms in class_defs.items():
        if name in cls_syms:
            qual = cls_syms[name]
            return node_id(rel, qual.split(".")[-1])
    return None


# ---------------------------------------------------------------------------
# reverse_closure
# ---------------------------------------------------------------------------

def reverse_closure(graph: Graph, seeds: list[str]) -> Closure:
    """Compute the reverse closure of *seeds* in *graph*.

    Traverses **forward** edges (i.e., finds all nodes that depend on the
    seeds, transitively) via BFS.

    Returns a :class:`Closure` with:
    - ``nodes``: sorted list of every reachable node.
    - ``unresolved``: sorted list of reachable nodes marked UNRESOLVED.
    - ``is_safe``: True iff ``unresolved`` is empty.

    A seed absent from the graph is included in ``.unresolved``.
    Cycles are handled via a visited set (traversal always terminates).
    """
    visited: set[str] = set()
    queue: list[str] = list(seeds)

    # Track which seeds were absent from the graph.
    missing_seeds: list[str] = []

    for seed in seeds:
        if seed not in graph.nodes:
            missing_seeds.append(seed)
        else:
            visited.add(seed)

    # BFS: follow forward edges (things that depend ON each node).
    idx = 0
    while idx < len(queue):
        current = queue[idx]
        idx += 1
        dependents = graph.forward.get(current, set())
        for dep in dependents:
            if dep not in visited:
                visited.add(dep)
                queue.append(dep)

    # Build result.
    result_nodes = sorted(visited)
    result_unresolved = sorted(
        n for n in result_nodes if n in graph.unresolved
    )

    # Add missing seeds to unresolved.
    all_unresolved = sorted(set(result_unresolved) | set(missing_seeds))

    return Closure(
        nodes=result_nodes,
        unresolved=all_unresolved,
        is_safe=len(all_unresolved) == 0,
    )
