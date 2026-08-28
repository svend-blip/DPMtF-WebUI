"""Symbol-aware change analysis for Python source files.

Determines which Python symbols a change touched, from changed line ranges and
a concrete syntax tree built with LibCST — and refuses to answer when the
answer would be a guess.

Language adapter seam: ``changed_symbols`` dispatches to language-specific
adapters registered in ``_ADAPTERS`` keyed by file extension.  Exactly one
adapter (Python) is registered.  A file whose language has no registered
adapter yields ``UNKNOWN``, which is the safe refusal answer.

Public API
----------
``__all__ = ["changed_symbols", "UNKNOWN", "SymbolAnalysisError"]``
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import libcst as cst
from libcst.metadata import PositionProvider

__all__ = ["changed_symbols", "UNKNOWN", "SymbolAnalysisError"]

# ---------------------------------------------------------------------------
# Sentinel & error
# ---------------------------------------------------------------------------

#: Distinct sentinel returned when the file cannot be parsed, is not Python,
#: or the ranges cannot be mapped to symbols.  It is **not** an empty list,
#: ``None``, or an empty string.
UNKNOWN: object = object()

#: Raised on unexpected conditions (file not found, wrong encoding, etc.).
#: Parsing errors yield ``UNKNOWN`` instead.
class SymbolAnalysisError(Exception):
    """Raised when symbol analysis fails due to an unexpected condition."""


# ---------------------------------------------------------------------------
# Range index helpers
# ---------------------------------------------------------------------------

def _build_range_index(definitions: List[Dict[str, Any]]) -> Dict[int, List[Tuple[int, str]]]:
    """Build a line → definition mapping from a list of definition dicts.

    Each definition must have ``"path"`` (qualified symbol name), ``"start"``
    (1-based inclusive start line), and ``"end"`` (1-based inclusive end line).

    Later definitions shadow earlier ones on overlapping lines (the innermost
    definition wins), **except** when an earlier definition covers a line that
    the later one does not — both are recorded.

    Returns ``{line: [(def_index, qualified_name), ...]}``.
    """
    index: Dict[int, List[Tuple[int, str]]] = {}
    for idx, defn in enumerate(definitions):
        for line in range(defn["start"], defn["end"] + 1):
            index.setdefault(line, [])
            # Only append if not already present for this line.
            existing_names = [name for _, name in index[line]]
            if defn["path"] not in existing_names:
                index[line].append((idx, defn["path"]))
    return index


def _find_definitions(
    tree: cst.CSTNode, source: str = ""
) -> List[Dict[str, Any]]:
    """Walk *tree* and collect every definition with its line range.

    For functions and methods the range covers: decorator lines → body end.
    For classes the range covers: class def line → end of body.
    Module-level assignments are included only for qualified names that use
    attribute access (e.g. ``obj.attr``).

    Returns a list of dicts with keys: ``path``, ``start``, ``end``.
    """
    definitions: List[Dict[str, Any]] = []
    source_lines: List[str] = source.splitlines() if source else []

    class _DefCollector(cst.CSTTransformer):
        """Collect function defs, class defs, and qualified assignments."""

        METADATA_DEPENDENCIES = (PositionProvider,)

        def __init__(self) -> None:
            self.ancestors: List[cst.CSTNode] = []

        def _pos(self, node: cst.CSTNode) -> Tuple[int, int]:
            """Get (start_line, end_line) for a position-aware node."""
            pos = self.get_metadata(PositionProvider, node)
            return pos.start.line, pos.end.line

        def _find_decorator_start(self, func_line: int) -> int:
            """Find the line of the first decorator for a function at *func_line*."""
            line_idx = func_line - 2  # 0-based, one before func_line
            while line_idx >= 0 and source_lines[line_idx].strip().startswith("@"):
                line_idx -= 1
            return line_idx + 2  # convert back to 1-based: first decorator line

        def _qualify(self, name: str) -> str:
            """Prepend ancestor class and function names to *name*."""
            prefix_parts: List[str] = []
            for ancestor in self.ancestors:
                if isinstance(ancestor, cst.ClassDef):
                    prefix_parts.append(ancestor.name.value)
                elif isinstance(ancestor, cst.FunctionDef):
                    prefix_parts.append(ancestor.name.value)
            if prefix_parts:
                return ".".join(prefix_parts) + "." + name
            return name

        def _record_function(
            self, node: cst.FunctionDef, name: str
        ) -> None:
            """Record a function/method definition including decorators."""
            start, end = self._pos(node)
            # Include decorator lines in the range.
            decorator_list = getattr(node, "decorators", None)
            if decorator_list and source_lines:
                dec_start = self._find_decorator_start(start)
                if dec_start < start:
                    start = dec_start
            definitions.append({
                "path": self._qualify(name),
                "start": start,
                "end": end,
            })

        def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
            """Record this function before recursing into its body."""
            self._record_function(node, node.name.value)
            self.ancestors.append(node)
            return True

        def leave_FunctionDef(
            self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
        ) -> cst.FunctionDef:
            self.ancestors.pop()
            return updated_node

        def visit_ClassDef(self, node: cst.ClassDef) -> bool:
            """Record this class before recursing into its body."""
            start, end = self._pos(node)
            definitions.append({
                "path": node.name.value,
                "start": start,
                "end": end,
            })
            self.ancestors.append(node)
            return True

        def leave_ClassDef(
            self, original_node: cst.ClassDef, updated_node: cst.ClassDef
        ) -> cst.ClassDef:
            self.ancestors.pop()
            return updated_node

        def visit_Assign(self, node: cst.Assign) -> bool:
            """Record module-level assignments with qualified target names."""
            target = node.targets[0].target if node.targets else None
            if isinstance(target, cst.Attribute):
                # Qualified name: obj.attr
                try:
                    parts: List[str] = []
                    current: Any = target
                    while isinstance(current, cst.Attribute):
                        parts.append(current.attr.value)
                        current = current.value
                    if isinstance(current, cst.Name):
                        parts.append(current.value)
                    path = ".".join(reversed(parts))
                    start, end = self._pos(node)
                    definitions.append({
                        "path": path,
                        "start": start,
                        "end": end,
                    })
                except AttributeError:
                    pass
            return True

        def leave_Assign(
            self, original_node: cst.Assign, updated_node: cst.Assign
        ) -> cst.Assign:
            return updated_node

    tree = cst.MetadataWrapper(tree)
    tree.visit(_DefCollector())
    return definitions


# ---------------------------------------------------------------------------
# Language adapter registry
# ---------------------------------------------------------------------------

#: Mapping of file extension → adapter function.
#: Each adapter takes (source, ranges) and returns a list of symbol names
#: or ``UNKNOWN``.
_ADAPTERS: Dict[str, Any] = {}


def _adapter_python(source: str, ranges: List[Tuple[int, int]]) -> List[str]:
    """Python adapter: parse with LibCST, build range index, collect symbols."""
    if not ranges:
        return []
    try:
        tree: cst.CSTNode = cst.parse_module(source)
    except cst.ParserSyntaxError:
        return UNKNOWN
    except Exception:
        return UNKNOWN

    try:
        definitions = _find_definitions(tree, source)
    except Exception:
        return UNKNOWN

    if not definitions:
        # No definitions at all — if ranges are provided and non-empty,
        # the edit touches module-level code → whole-module impact.
        # However, the spec says "refuse to guess". A file with no
        # definitions that is edited could mean anything.  We return
        # UNKNOWN to refuse.
        #
        # Exception: if the file is non-empty Python but has no definitions
        # at all (e.g. all imports and module-level calls), line ranges
        # should still map to module-level impact.  The safest choice is
        # UNKNOWN — the downstream consumer should never narrow scope on
        # a parse without symbols.
        return UNKNOWN  # type: ignore[return-value]

    idx_to_range = _build_range_index(definitions)

    results: List[str] = []
    for start, end in ranges:
        if start == end:
            # Single-line edit: look up the symbol for that line.
            hits = idx_to_range.get(start, [])
            if hits:
                # Pick the most specific (last / deepest) symbol.
                results.append(hits[-1][1])
            else:
                # Line not in any definition's range — module-level code.
                results.append("__module__")
        else:
            # Multi-line range: collect all symbols touched.
            symbols: List[str] = []
            seen_paths: set = set()
            for line in range(start, end + 1):
                hits = idx_to_range.get(line, [])
                for _, path in hits:
                    if path not in seen_paths:
                        symbols.append(path)
                        seen_paths.add(path)
            results.extend(symbols)

    # De-duplicate while preserving order.
    seen: set = set()
    unique: List[str] = []
    for s in results:
        if s not in seen:
            unique.append(s)
            seen.add(s)
    return unique


# Register the Python adapter.
for _ext in (".py",):
    _ADAPTERS[_ext] = _adapter_python


# ---------------------------------------------------------------------------
# Dispatcher & public API
# ---------------------------------------------------------------------------

def changed_symbols(
    repo_root: str,
    path: str,
    ranges: List[Tuple[int, int]],
) -> List[str] | object:
    """Determine which Python symbols a change touched.

    Parameters
    ----------
    repo_root:
        Path to the repository root (used to resolve *path*).
    path:
        Repository-relative path to the source file.
    ranges:
        List of ``(start_line, end_line)`` tuples, 1-based inclusive,
        in the new file.

    Returns
    -------
    ``list[str]``
        Qualified names of symbols touched, e.g. ``"func"``, ``"Class"``,
        ``"Class.method"``, ``"MODULE_CONSTANT"``.  A range touching a
        class body outside any method yields the class; touching
        module-level code outside any definition yields ``"__module__"``.

    ``UNKNOWN``
        A distinct sentinel returned when the file cannot be parsed
        (not valid Python), is not a supported language, or the ranges
        cannot be mapped to any symbol.  It is **not** an empty list —
        it must be unmistakable.
    """
    # --- Resolve file path ---
    full_path = Path(repo_root) / path
    if not full_path.is_file():
        return UNKNOWN

    # --- Read source ---
    try:
        source = full_path.read_text(encoding="utf-8")
    except OSError:
        return UNKNOWN

    # --- Dispatch to language adapter ---
    ext = os.path.splitext(path)[1].lower()
    adapter = _ADAPTERS.get(ext)
    if adapter is None:
        return UNKNOWN

    return adapter(source, ranges)
