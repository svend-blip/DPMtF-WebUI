"""LibCST-backed implementation of the structural_python patch mode.

Spec sections owned by this handoff:

  §2.1  LibCST as the preferred deterministic structural engine.
  §12   Initial LibCST operations (Phase 1B subset).
  §13   Target identification: precise and unique.
  §15   Dry-run / check mode (never mutates).
  §16   Apply mode (atomic on failure).
  §17   Atomicity across multiple operations.
  §27   Idempotency for `add_import`.
  §28   Idempotency is the explicit design goal.
  §36   Engine abstraction (`LibCSTEngine(PatchEngine)`).
  §37   Phase 1C completes the seven §37 operations. The spec §12
        name `replace_import` is NOT in §37 and stays unsupported;
        any other name outside this list returns
        PATCH_UNSUPPORTED_OPERATION.

The engine never imports any model allocator, bridge code, or LLM
client — it is pure deterministic infrastructure (spec §6, §23–§24).
"""

from __future__ import annotations

import dataclasses
import difflib
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import libcst as cst

from patcher.audit import (
    AuditInputs,
    audit_inputs_from_request,
    build_audit_block,
    utc_now_iso,
)
from patcher.engines.base import PatchEngine
from patcher.errors import (
    PATCH_APPLIED,
    PATCH_APPLY_FAILED,
    PATCH_CONFLICT,
    PATCH_FILE_NOT_FOUND,
    PATCH_INVALID,
    PATCH_TARGET_AMBIGUOUS,
    PATCH_TARGET_NOT_FOUND,
    PATCH_UNSUPPORTED_OPERATION,
)
from patcher.models import PatchRequest, PatchResult
from patcher.policy import (
    PatchPathRejected,
    record_repo_state,
    validate_target_paths,
)
from patcher.verification import run_verification


# All seven spec §37 operations now ship (Phase 1B + 1C). Anything
# else returns PATCH_UNSUPPORTED_OPERATION — notably the spec §12
# name `replace_import` is NOT in §37 and stays outside the supported
# set.
SUPPORTED_OPERATIONS = frozenset(
    {
        "add_import",
        "remove_import",
        "replace_function",
        "add_function",
        "replace_method",
        "add_method",
        "replace_assignment",
    }
)


class _OperationError(Exception):
    """Raised by an operation handler to short-circuit with a structured result.

    The wrapping engine catches this and returns the carried PatchResult.
    Using an exception is the cleanest way to abort a multi-operation
    pipeline partway through while preserving the rejected-state machinery
    built around PatchResult (spec §17 atomicity).
    """

    def __init__(self, result: PatchResult) -> None:
        super().__init__(result.error)
        self.result = result


# ── Result helpers ──────────────────────────────────────────────────────


def _rejected(
    error_code: str,
    error: str,
    *,
    files_rejected: Optional[List[str]] = None,
) -> PatchResult:
    """Build a `status="rejected"` PatchResult for the LibCST engine.

    `files_rejected` defaults to None — converted to an empty list at
    the field level — so the existing call sites keep their behaviour.
    The PathValidation catch site passes
    `[exc.offending_path]` (or `[]` when the exception did not surface
    a meaningful repo-relative path) so the review side can see which
    file the engine refused, not only read about it in the error
    string.
    """
    return PatchResult(
        status="rejected",
        applied=False,
        engine="libcst",
        files_changed=[],
        files_rejected=list(files_rejected) if files_rejected else [],
        operations_requested=0,
        operations_applied=0,
        resulting_diff=None,
        error_code=error_code,
        error=error,
    )


def _ok(
    files_changed: List[str],
    operations_requested: int,
    operations_applied: int,
    resulting_diff: Optional[str],
    status: str,
    applied: bool,
) -> PatchResult:
    return PatchResult(
        status=status,
        applied=applied,
        engine="libcst",
        files_changed=files_changed,
        files_rejected=[],
        operations_requested=operations_requested,
        operations_applied=operations_applied,
        resulting_diff=resulting_diff,
        error_code=PATCH_APPLIED,
        error=None,
    )


# ── LibCST helpers ─────────────────────────────────────────────────────


def _module_dotted(node: cst.CSTNode) -> str:
    """Render a Name / Attribute node as a dotted string."""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        return _module_dotted(node.value) + "." + node.attr.value
    raise TypeError(f"unexpected module node: {type(node).__name__}")


def _import_already_present(
    tree: cst.Module, module: str, name: Optional[str]
) -> bool:
    """Detect if a matching import is already present.

    Semantics:

      * `name is None` → matches `import <module>` OR
        `from <module> import …` (either is considered "the symbol is
        already pulled in").
      * `name` is a string → matches `from <module> import <name>`.

    Star imports (`from X import *`) are treated as matches for any
    name within X — they cannot be disambiguated at this layer and
    are rare enough that false positives are harmless.
    """
    for stmt in tree.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for small in stmt.body:
            if isinstance(small, cst.ImportFrom):
                if small.module is None:
                    continue
                if _module_dotted(small.module) != module:
                    continue
                if name is None:
                    return True
                for alias in small.names:
                    alias_name = cst.ensure_type(alias.name, cst.Name).value
                    if alias_name == name:
                        return True
            elif isinstance(small, cst.Import):
                if name is not None:
                    continue
                for alias in small.names:
                    alias_name = cst.ensure_type(alias.name, cst.Name).value
                    if alias_name == module:
                        return True
    return False


def _build_import_node(
    module: str, name: Optional[str]
) -> cst.SimpleStatementLine:
    """Construct the CST node for `import X` or `from X import Y`."""
    if name is None:
        return cst.parse_statement(f"import {module}")
    return cst.parse_statement(f"from {module} import {name}")


def _insert_after_imports(
    tree: cst.Module, new_stmt: cst.CSTNode
) -> cst.Module:
    """Insert `new_stmt` after the docstring + import block of `tree`.

    Insertion policy (matches PEP 8 / `isort` convention):

      1. Skip a leading `Expr` containing a string literal (docstring).
      2. Skip contiguous `Import` / `ImportFrom` statements.
      3. Insert at the resulting index.
    """
    body = list(tree.body)
    insert_idx = 0
    if (
        insert_idx < len(body)
        and isinstance(body[insert_idx], cst.SimpleStatementLine)
        and len(body[insert_idx].body) == 1
        and isinstance(body[insert_idx].body[0], cst.Expr)
        and isinstance(
            body[insert_idx].body[0].value,
            (cst.SimpleString, cst.ConcatenatedString, cst.FormattedString),
        )
    ):
        insert_idx += 1
    while insert_idx < len(body):
        stmt = body[insert_idx]
        if not isinstance(stmt, cst.SimpleStatementLine):
            break
        is_import = any(
            isinstance(s, (cst.Import, cst.ImportFrom)) for s in stmt.body
        )
        if not is_import:
            break
        insert_idx += 1
    body.insert(insert_idx, new_stmt)
    return tree.with_changes(body=body)


# ── Function find / replace helpers ────────────────────────────────────


def _inherit_leading_lines(
    new_stmt: cst.BaseStatement, old_stmt: cst.CSTNode
) -> cst.BaseStatement:
    """Preserve the replaced node's leading blank/comment lines.

    cst.parse_statement() yields a node with empty leading_lines, so a
    bare `body[idx] = new_stmt` silently deletes the blank lines that
    separated the old definition from its neighbor. Measured live on
    2026-08-16: replace_method ate the single blank line before a
    method, replace_function ate BOTH blank lines before a module-level
    function (PEP8 E302). When the replacement author supplies leading
    lines explicitly, theirs win — the engine must not stack the
    original's on top.
    """
    if not new_stmt.leading_lines and getattr(old_stmt, "leading_lines", ()):
        return new_stmt.with_changes(leading_lines=old_stmt.leading_lines)
    return new_stmt


def _find_module_function_idx(
    tree: cst.Module, name: str
) -> Optional[int]:
    """Return the body index of the unique module-level `FunctionDef`
    with the given name, or None if no such function exists.

    Raises _OperationError(PATCH_TARGET_AMBIGUOUS) when the name
    matches more than one module-level FunctionDef — we never guess
    (spec §13).
    """
    matches: List[int] = []
    for idx, stmt in enumerate(tree.body):
        if isinstance(stmt, cst.FunctionDef) and stmt.name.value == name:
            matches.append(idx)
    if len(matches) > 1:
        raise _OperationError(
            _rejected(
                PATCH_TARGET_AMBIGUOUS,
                f"replace_function: {len(matches)} module-level definitions "
                f"of {name!r}; cannot disambiguate",
            )
        )
    if not matches:
        return None
    return matches[0]


def _count_module_functions_named(
    tree: cst.Module, name: str
) -> int:
    """Count module-level FunctionDef nodes with the given name."""
    return sum(
        1
        for stmt in tree.body
        if isinstance(stmt, cst.FunctionDef) and stmt.name.value == name
    )


# ── Class / method find / replace helpers ───────────────────────────────


def _find_module_class_idx(
    tree: cst.Module, name: str
) -> Optional[int]:
    """Return the body index of the unique module-level `ClassDef`
    with the given name, or None if no such class exists.

    Raises _OperationError(PATCH_TARGET_AMBIGUOUS) when the name
    matches more than one module-level ClassDef — we never guess
    (spec §13).
    """
    matches: List[int] = []
    for idx, stmt in enumerate(tree.body):
        if isinstance(stmt, cst.ClassDef) and stmt.name.value == name:
            matches.append(idx)
    if len(matches) > 1:
        raise _OperationError(
            _rejected(
                PATCH_TARGET_AMBIGUOUS,
                f"replace_method: {len(matches)} module-level classes named "
                f"{name!r}; cannot disambiguate",
            )
        )
    if not matches:
        return None
    return matches[0]


def _count_methods_named(
    class_node: cst.ClassDef, method_name: str
) -> int:
    """Count FunctionDef children of `class_node` with the given name.

    Method bodies are stored as a flat sequence of statements under
    `class_node.body.body` — LibCST does not wrap them in
    SimpleStatementLine at this depth, so a simple type check is
    sufficient. Decorators are part of the FunctionDef node and do
    not affect name matching (a method's identity is its `name`).
    """
    return sum(
        1
        for stmt in class_node.body.body
        if isinstance(stmt, cst.FunctionDef)
        and stmt.name.value == method_name
    )


def _find_method_idx(
    class_node: cst.ClassDef, method_name: str
) -> Optional[int]:
    """Return the index of the unique method with `method_name` inside
    `class_node`, or None if no such method exists.

    Raises _OperationError(PATCH_TARGET_AMBIGUOUS) when the name
    matches more than one method inside the class (spec §13).
    """
    matches: List[int] = []
    for idx, stmt in enumerate(class_node.body.body):
        if isinstance(stmt, cst.FunctionDef) and stmt.name.value == method_name:
            matches.append(idx)
    if len(matches) > 1:
        raise _OperationError(
            _rejected(
                PATCH_TARGET_AMBIGUOUS,
                f"replace_method: {len(matches)} methods named "
                f"{method_name!r} inside class; cannot disambiguate",
            )
        )
    if not matches:
        return None
    return matches[0]


# ── Assignment find / replace helpers ───────────────────────────────────


def _is_module_level_assign(
    stmt: cst.CSTNode, target_name: str
) -> bool:
    """True iff `stmt` is a module-level `Assign` whose single target
    is the Name `target_name`.

    Only SimpleStatementLine nodes that wrap a plain `Assign` (not
    `AnnAssign`, not `AugAssign`) qualify; chained assignments
    (`a = b = 1`) are out of scope (multiple targets) and excluded.
    """
    if not isinstance(stmt, cst.SimpleStatementLine):
        return False
    if len(stmt.body) != 1:
        return False
    inner = stmt.body[0]
    if not isinstance(inner, cst.Assign):
        return False
    if len(inner.targets) != 1:
        return False
    tgt = inner.targets[0].target
    return isinstance(tgt, cst.Name) and tgt.value == target_name


def _find_module_assignment_idx(
    tree: cst.Module, name: str
) -> Optional[int]:
    """Return the body index of the unique module-level simple
    assignment to `name`, or None.

    Raises _OperationError(PATCH_TARGET_AMBIGUOUS) when more than
    one module-level simple assignment targets `name`. Class/instance
    attribute assignments are deliberately NOT considered — the
    spec's §37 `replace_assignment` covers the module level only;
    `replace_class_attribute` is Phase 2. A request that only
    matches inside a class body therefore falls through to None and
    surfaces as PATCH_TARGET_NOT_FOUND.
    """
    matches: List[int] = []
    for idx, stmt in enumerate(tree.body):
        if _is_module_level_assign(stmt, name):
            matches.append(idx)
    if len(matches) > 1:
        raise _OperationError(
            _rejected(
                PATCH_TARGET_AMBIGUOUS,
                f"replace_assignment: {len(matches)} module-level assignments "
                f"to {name!r}; cannot disambiguate",
            )
        )
    if not matches:
        return None
    return matches[0]


# ── Import removal helpers ──────────────────────────────────────────────


def _remove_import_from_tree(
    tree: cst.Module, module: str, name: Optional[str]
) -> Tuple[cst.Module, bool]:
    """Remove the matching import from `tree`. Returns (new_tree, applied).

    Matching semantics (mirrors `_import_already_present`):

      * `name is None` → match any `import <module>` line AND any
        `from <module> import …` line. For `import <module>, ...` we
        remove only the requested alias and leave siblings; if it is
        the only alias the line is dropped entirely.
      * `name` is a string → match `from <module> import <name>`
        specifically. For multi-name `from` lines we remove the named
        alias only.

    Returns applied=False when no matching import is present
    (idempotent no-op per spec §28).
    """
    new_body: List[cst.CSTNode] = []
    touched = False
    for stmt in tree.body:
        keep, replaced = _try_strip_import(stmt, module, name)
        if replaced:
            touched = True
        if keep is not None:
            new_body.append(keep)
    if not touched:
        return tree, False
    return tree.with_changes(body=new_body), True


def _try_strip_import(
    stmt: cst.CSTNode, module: str, name: Optional[str]
) -> Tuple[Optional[cst.CSTNode], bool]:
    """Try to remove the requested import from `stmt`.

    Returns `(keep, touched)`:

      * `keep` is the (possibly mutated) statement to retain in the
        body, or None if the entire statement should be dropped.
      * `touched` is True iff this call matched and stripped an alias.

    Statement types:

      * `SimpleStatementLine` wrapping `Import`: handles
        `import X` and `import X, Y, Z`. When `name is None`, the
        requested alias is the module name itself.
      * `SimpleStatementLine` wrapping `ImportFrom`: handles
        `from X import Y[, Z, ...]`. When `name is None`, the whole
        line is removed (any symbol pulled in from `module` matches).
    """
    if not isinstance(stmt, cst.SimpleStatementLine):
        return stmt, False

    if len(stmt.body) != 1:
        return stmt, False

    inner = stmt.body[0]

    # ── `import X[, Y, Z]` ───────────────────────────────────────────
    if isinstance(inner, cst.Import) and name is None:
        # Find the alias whose name equals `module`.
        kept_aliases = []
        matched = False
        for alias in inner.names:
            alias_name = cst.ensure_type(alias.name, cst.Name).value
            if alias_name == module and not matched:
                matched = True
                continue
            kept_aliases.append(alias)
        if not matched:
            return stmt, False
        if not kept_aliases:
            # Whole statement disappears.
            return None, True
        # Strip the trailing comma on the new last alias. LibCST
        # forbids a trailing comma when an Import statement has only
        # one name, so we reset `comma` on the survivor to
        # MaybeSentinel.DEFAULT ("no comma").
        kept_aliases[-1] = kept_aliases[-1].with_changes(
            comma=cst.MaybeSentinel.DEFAULT
        )
        new_inner = inner.with_changes(names=kept_aliases)
        return stmt.with_changes(body=[new_inner]), True

    # ── `from X import Y[, Z, ...]` ──────────────────────────────────
    if isinstance(inner, cst.ImportFrom):
        if inner.module is None:
            return stmt, False
        if _module_dotted(inner.module) != module:
            return stmt, False
        if name is None:
            # Any import from this module counts; the whole line goes.
            return None, True
        kept_aliases = []
        matched = False
        for alias in inner.names:
            alias_name = cst.ensure_type(alias.name, cst.Name).value
            if alias_name == name and not matched:
                matched = True
                continue
            kept_aliases.append(alias)
        if not matched:
            return stmt, False
        if not kept_aliases:
            return None, True
        # Same trailing-comma normalisation as above for the Import
        # branch. ImportFrom has the same single-name restriction.
        kept_aliases[-1] = kept_aliases[-1].with_changes(
            comma=cst.MaybeSentinel.DEFAULT
        )
        new_inner = inner.with_changes(names=kept_aliases)
        return stmt.with_changes(body=[new_inner]), True

    return stmt, False


# ── Operation handlers ─────────────────────────────────────────────────


def _op_add_import(
    tree: cst.Module, op: Dict[str, Any]
) -> Tuple[cst.Module, bool]:
    """Apply `add_import`. Returns (new_tree, applied).

    `applied` is False iff the import was already present (idempotent
    no-op per spec §27–§28).
    """
    if "module" not in op:
        raise _OperationError(
            _rejected(PATCH_INVALID, "add_import requires a 'module' field")
        )
    module = op["module"]
    name = op.get("name")
    if not isinstance(module, str) or not module:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "add_import: 'module' must be a non-empty string",
            )
        )
    if name is not None and (not isinstance(name, str) or not name):
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "add_import: 'name' must be a non-empty string when provided",
            )
        )
    if _import_already_present(tree, module, name):
        return tree, False
    new_stmt = _build_import_node(module, name)
    return _insert_after_imports(tree, new_stmt), True


def _op_replace_function(
    tree: cst.Module, op: Dict[str, Any]
) -> Tuple[cst.Module, bool]:
    """Apply `replace_function`. Returns (new_tree, applied)."""
    if "function" not in op or "replacement" not in op:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_function requires 'function' and 'replacement' fields",
            )
        )
    target_name = op["function"]
    replacement = op["replacement"]
    if not isinstance(target_name, str) or not target_name:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_function: 'function' must be a non-empty string",
            )
        )
    if not isinstance(replacement, str) or not replacement.strip():
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_function: 'replacement' must be a non-empty string",
            )
        )

    idx = _find_module_function_idx(tree, target_name)
    if idx is None:
        raise _OperationError(
            _rejected(
                PATCH_TARGET_NOT_FOUND,
                f"replace_function: no module-level function named "
                f"{target_name!r}",
            )
        )

    try:
        new_stmt = cst.parse_statement(replacement)
    except cst.ParserSyntaxError as exc:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                f"replace_function: replacement source is not valid Python: "
                f"{exc}",
            )
        )
    if not isinstance(new_stmt, cst.FunctionDef):
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_function: replacement is not a function definition",
            )
        )
    if new_stmt.name.value != target_name:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                f"replace_function: replacement function name "
                f"{new_stmt.name.value!r} does not match target "
                f"{target_name!r}",
            )
        )

    body = list(tree.body)
    body[idx] = _inherit_leading_lines(new_stmt, body[idx])
    return tree.with_changes(body=body), True


def _op_add_function(
    tree: cst.Module, op: Dict[str, Any]
) -> Tuple[cst.Module, bool]:
    """Apply `add_function`. Returns (new_tree, applied).

    Fails with PATCH_TARGET_AMBIGUOUS when a same-named function
    already exists — adding is not replacing (spec §28 + handoff §3e).
    """
    if "code" not in op:
        raise _OperationError(
            _rejected(PATCH_INVALID, "add_function requires a 'code' field")
        )
    code = op["code"]
    if not isinstance(code, str) or not code.strip():
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "add_function: 'code' must be a non-empty string",
            )
        )
    try:
        new_stmt = cst.parse_statement(code)
    except cst.ParserSyntaxError as exc:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                f"add_function: code is not valid Python: {exc}",
            )
        )
    if not isinstance(new_stmt, cst.FunctionDef):
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "add_function: code is not a function definition",
            )
        )

    new_name = new_stmt.name.value
    if _count_module_functions_named(tree, new_name) > 0:
        raise _OperationError(
            _rejected(
                PATCH_TARGET_AMBIGUOUS,
                f"add_function: a module-level function named {new_name!r} "
                f"already exists; adding is not replacing — use "
                f"replace_function",
            )
        )

    return tree.with_changes(body=list(tree.body) + [new_stmt]), True


def _functiondefs_equivalent(a: cst.FunctionDef, b: cst.FunctionDef) -> bool:
    """Semantic equivalence for two `FunctionDef` nodes, ignoring
    whitespace metadata that doesn't affect parsing or behaviour.

    `LibCST.FunctionDef.deep_equals` is too strict — it descends into
    `leading_lines`, `lines_after_decorators`, `whitespace_after_def`
    and similar formatting fields, so two FunctionDefs that render to
    identical Python and behave identically compare unequal whenever
    one has an empty leading line and the other does not. We compare
    only the semantically meaningful fields: name, params, body,
    decorators, return annotation, `async` keyword, type parameters.
    """
    if a.name.value != b.name.value:
        return False
    if not a.params.deep_equals(b.params):
        return False
    if not a.body.deep_equals(b.body):
        return False
    if len(a.decorators) != len(b.decorators):
        return False
    if not all(x.deep_equals(y) for x, y in zip(a.decorators, b.decorators)):
        return False
    if (a.returns is None) != (b.returns is None):
        return False
    if a.returns is not None and not a.returns.deep_equals(b.returns):
        return False
    if a.asynchronous != b.asynchronous:
        return False
    if (a.type_parameters is None) != (b.type_parameters is None):
        return False
    if a.type_parameters is not None and not a.type_parameters.deep_equals(
        b.type_parameters
    ):
        return False
    return True


def _op_remove_import(
    tree: cst.Module, op: Dict[str, Any]
) -> Tuple[cst.Module, bool]:
    """Apply `remove_import`. Returns (new_tree, applied).

    Semantics mirror `add_import` for the matching rules (see
    `_import_already_present`). When the requested import is not
    present the call returns `(tree, False)` — the idempotent
    no-change outcome that `add_import` uses (spec §28).
    """
    if "module" not in op:
        raise _OperationError(
            _rejected(
                PATCH_INVALID, "remove_import requires a 'module' field"
            )
        )
    module = op["module"]
    name = op.get("name")
    if not isinstance(module, str) or not module:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "remove_import: 'module' must be a non-empty string",
            )
        )
    if name is not None and (not isinstance(name, str) or not name):
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "remove_import: 'name' must be a non-empty string "
                "when provided",
            )
        )
    return _remove_import_from_tree(tree, module, name)


def _op_replace_method(
    tree: cst.Module, op: Dict[str, Any]
) -> Tuple[cst.Module, bool]:
    """Apply `replace_method`. Returns (new_tree, applied).

    Spec §13: method targets include class identity. Both `class`
    and `method` are required; missing either is PATCH_INVALID
    (the payload is malformed). Once the class is resolved, the
    method must be unique inside it — same-named module-level
    functions do NOT satisfy a method target because we never look
    outside `class_node.body.body`.
    """
    if "class" not in op or "method" not in op or "replacement" not in op:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_method requires 'class', 'method', and "
                "'replacement' fields",
            )
        )
    class_name = op["class"]
    method_name = op["method"]
    replacement = op["replacement"]
    if not isinstance(class_name, str) or not class_name:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_method: 'class' must be a non-empty string",
            )
        )
    if not isinstance(method_name, str) or not method_name:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_method: 'method' must be a non-empty string",
            )
        )
    if not isinstance(replacement, str) or not replacement.strip():
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_method: 'replacement' must be a non-empty string",
            )
        )

    cls_idx = _find_module_class_idx(tree, class_name)
    if cls_idx is None:
        raise _OperationError(
            _rejected(
                PATCH_TARGET_NOT_FOUND,
                f"replace_method: no module-level class named "
                f"{class_name!r}",
            )
        )
    cls = tree.body[cls_idx]
    if not isinstance(cls, cst.ClassDef):
        # Defensive: _find_module_class_idx only returns indices of
        # ClassDef nodes, so this branch is unreachable.
        raise _OperationError(  # pragma: no cover - defensive
            _rejected(
                PATCH_INVALID,
                f"replace_method: index {cls_idx} is not a ClassDef",
            )
        )

    method_idx = _find_method_idx(cls, method_name)
    if method_idx is None:
        raise _OperationError(
            _rejected(
                PATCH_TARGET_NOT_FOUND,
                f"replace_method: class {class_name!r} has no method "
                f"named {method_name!r}",
            )
        )

    try:
        new_stmt = cst.parse_statement(replacement)
    except cst.ParserSyntaxError as exc:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                f"replace_method: replacement source is not valid "
                f"Python: {exc}",
            )
        )
    if not isinstance(new_stmt, cst.FunctionDef):
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_method: replacement is not a function "
                "definition",
            )
        )
    if new_stmt.name.value != method_name:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                f"replace_method: replacement method name "
                f"{new_stmt.name.value!r} does not match target "
                f"{method_name!r}",
            )
        )

    new_class_body = list(cls.body.body)
    new_class_body[method_idx] = _inherit_leading_lines(
        new_stmt, new_class_body[method_idx])
    new_indented = cls.body.with_changes(body=new_class_body)
    new_cls = cls.with_changes(body=new_indented)
    body = list(tree.body)
    body[cls_idx] = new_cls
    return tree.with_changes(body=body), True


def _op_add_method(
    tree: cst.Module, op: Dict[str, Any]
) -> Tuple[cst.Module, bool]:
    """Apply `add_method`. Returns (new_tree, applied).

    Requires `class` and `code`. Idempotency and conflict handling
    follow spec §28 + Mission Contract O4:

      * If a method with the same name already exists in the target
        class AND its body is deep-equal to the requested one →
        `(tree, False)` (idempotent no-change).
      * If a same-named method exists and is NOT equivalent →
        PATCH_CONFLICT, mutate nothing.
      * Otherwise the new method is appended to the class body.
    """
    if "class" not in op or "code" not in op:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "add_method requires 'class' and 'code' fields",
            )
        )
    class_name = op["class"]
    code = op["code"]
    if not isinstance(class_name, str) or not class_name:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "add_method: 'class' must be a non-empty string",
            )
        )
    if not isinstance(code, str) or not code.strip():
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "add_method: 'code' must be a non-empty string",
            )
        )

    try:
        new_stmt = cst.parse_statement(code)
    except cst.ParserSyntaxError as exc:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                f"add_method: code is not valid Python: {exc}",
            )
        )
    if not isinstance(new_stmt, cst.FunctionDef):
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "add_method: code is not a function definition",
            )
        )
    new_name = new_stmt.name.value

    cls_idx = _find_module_class_idx(tree, class_name)
    if cls_idx is None:
        raise _OperationError(
            _rejected(
                PATCH_TARGET_NOT_FOUND,
                f"add_method: no module-level class named {class_name!r}",
            )
        )
    cls = tree.body[cls_idx]
    if not isinstance(cls, cst.ClassDef):
        raise _OperationError(  # pragma: no cover - defensive
            _rejected(
                PATCH_INVALID,
                f"add_method: index {cls_idx} is not a ClassDef",
            )
        )

    # Idempotency / conflict check.
    count = _count_methods_named(cls, new_name)
    if count > 0:
        # Locate the existing method. There may be more than one; a
        # single semantically-equivalent match is enough for
        # idempotency, but a non-equivalent match short-circuits as
        # PATCH_CONFLICT regardless of multiplicity.
        existing_match_equivalent = False
        for stmt in cls.body.body:
            if (
                isinstance(stmt, cst.FunctionDef)
                and stmt.name.value == new_name
            ):
                if _functiondefs_equivalent(stmt, new_stmt):
                    existing_match_equivalent = True
                    break
        if existing_match_equivalent:
            return tree, False
        raise _OperationError(
            _rejected(
                PATCH_CONFLICT,
                f"add_method: class {class_name!r} already has a method "
                f"named {new_name!r} with different code; adding is not "
                f"replacing — use replace_method",
            )
        )

    new_class_body = list(cls.body.body) + [new_stmt]
    new_indented = cls.body.with_changes(body=new_class_body)
    new_cls = cls.with_changes(body=new_indented)
    body = list(tree.body)
    body[cls_idx] = new_cls
    return tree.with_changes(body=body), True


def _op_replace_assignment(
    tree: cst.Module, op: Dict[str, Any]
) -> Tuple[cst.Module, bool]:
    """Apply `replace_assignment`. Returns (new_tree, applied).

    Targets module-level simple assignments of the form
    `NAME = <expr>`. Multiple module-level assignments to the same
    name → PATCH_TARGET_AMBIGUOUS. No such assignment at the
    module level → PATCH_TARGET_NOT_FOUND (this is the deliberate
    out-of-scope boundary for `replace_class_attribute`, which is
    Phase 2 per spec §12).
    """
    if "name" not in op or "replacement" not in op:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_assignment requires 'name' and 'replacement' "
                "fields",
            )
        )
    target_name = op["name"]
    replacement = op["replacement"]
    if not isinstance(target_name, str) or not target_name:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_assignment: 'name' must be a non-empty string",
            )
        )
    if not isinstance(replacement, str) or not replacement.strip():
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_assignment: 'replacement' must be a non-empty "
                "string",
            )
        )

    idx = _find_module_assignment_idx(tree, target_name)
    if idx is None:
        raise _OperationError(
            _rejected(
                PATCH_TARGET_NOT_FOUND,
                f"replace_assignment: no module-level assignment to "
                f"{target_name!r}",
            )
        )

    try:
        new_stmt = cst.parse_statement(replacement)
    except cst.ParserSyntaxError as exc:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                f"replace_assignment: replacement source is not valid "
                f"Python: {exc}",
            )
        )
    if not isinstance(new_stmt, cst.SimpleStatementLine):
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_assignment: replacement is not a simple "
                "statement line",
            )
        )
    if len(new_stmt.body) != 1 or not isinstance(
        new_stmt.body[0], cst.Assign
    ):
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_assignment: replacement is not a single "
                "`NAME = expr` assignment",
            )
        )
    new_assign = new_stmt.body[0]
    if len(new_assign.targets) != 1 or not isinstance(
        new_assign.targets[0].target, cst.Name
    ):
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "replace_assignment: replacement must target exactly "
                "one simple Name",
            )
        )
    if new_assign.targets[0].target.value != target_name:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                f"replace_assignment: replacement target name "
                f"{new_assign.targets[0].target.value!r} does not match "
                f"{target_name!r}",
            )
        )

    body = list(tree.body)
    body[idx] = _inherit_leading_lines(new_stmt, body[idx])
    return tree.with_changes(body=body), True


def _apply_op(
    tree: cst.Module, op: Dict[str, Any]
) -> Tuple[cst.Module, bool]:
    """Dispatch a single operation to its handler.

    Returns (new_tree, applied). Raises _OperationError on failure.
    """
    if not isinstance(op, dict):
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                f"operation must be a dict, got {type(op).__name__}",
            )
        )
    op_name = op.get("operation")
    if not isinstance(op_name, str) or not op_name:
        raise _OperationError(
            _rejected(
                PATCH_INVALID,
                "operation requires a non-empty 'operation' field",
            )
        )
    if op_name not in SUPPORTED_OPERATIONS:
        raise _OperationError(
            _rejected(
                PATCH_UNSUPPORTED_OPERATION,
                f"operation {op_name!r} is not supported in this handoff; "
                f"supported: {sorted(SUPPORTED_OPERATIONS)}",
            )
        )

    if op_name == "add_import":
        return _op_add_import(tree, op)
    if op_name == "remove_import":
        return _op_remove_import(tree, op)
    if op_name == "replace_function":
        return _op_replace_function(tree, op)
    if op_name == "add_function":
        return _op_add_function(tree, op)
    if op_name == "replace_method":
        return _op_replace_method(tree, op)
    if op_name == "add_method":
        return _op_add_method(tree, op)
    if op_name == "replace_assignment":
        return _op_replace_assignment(tree, op)
    # Unreachable: SUPPORTED_OPERATIONS is closed above.
    raise _OperationError(  # pragma: no cover - defensive
        _rejected(
            PATCH_UNSUPPORTED_OPERATION,
            f"operation {op_name!r} is not implemented",
        )
    )


# ── Diff helpers ───────────────────────────────────────────────────────


def _unified_diff(
    old_source: str, new_source: str, target_path: str
) -> str:
    """Build a unified diff between two source strings.

    Returns an empty string when the sources are byte-identical. The
    output uses `a/<path>` and `b/<path>` headers, matching the
    convention the rest of the patcher suite emits. We use
    `difflib.unified_diff` rather than shelling out to `git diff` so
    the result is self-contained and reproducible regardless of the
    host's git configuration.
    """
    if old_source == new_source:
        return ""
    old_lines = old_source.splitlines(keepends=True)
    new_lines = new_source.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{target_path}",
        tofile=f"b/{target_path}",
    )
    return "".join(diff)


# ── git helpers (apply phase only) ─────────────────────────────────────


def _run_git(
    repo_path: str,
    *args: str,
    check: bool = True,
    input_text: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """Run `git <args>` inside repo_path and return the CompletedProcess.

    We deliberately do not use `shell=True` (auto-fail pattern: silent
    failure if the wrong command is substituted).
    """
    return subprocess.run(
        ["git", "-C", repo_path, *args],
        capture_output=True,
        text=True,
        check=check,
        input=input_text,
    )


def _capture_porcelain(repo_path: str) -> str:
    proc = _run_git(repo_path, "status", "--porcelain", check=False)
    return proc.stdout or ""


def _porcelain_paths(text: str) -> set:
    """Extract the set of paths from `git status --porcelain` output."""
    out = set()
    for line in text.splitlines():
        if not line.strip():
            continue
        path_field = line[3:] if len(line) >= 4 else ""
        if " -> " in path_field:
            path_field = path_field.split(" -> ", 1)[1]
        path_field = path_field.strip().strip('"')
        if path_field:
            out.add(path_field)
    return out


def _capture_diff_for_file(repo_path: str, file_path: str) -> str:
    """Capture `git diff -- <file>` for the given file in the repo."""
    proc = _run_git(repo_path, "diff", "--", file_path, check=False)
    return proc.stdout or ""


# ── The engine ──────────────────────────────────────────────────────────


class LibCSTEngine(PatchEngine):
    """LibCST-backed implementation of the structural_python patch mode.

    Phase 1B + 1C ship all seven spec §37 operations: `add_import`,
    `remove_import`, `replace_function`, `add_function`,
    `replace_method`, `add_method`, `replace_assignment`. Any
    other operation name — including the spec §12 name
    `replace_import` that is NOT in the §37 list — returns
    PATCH_UNSUPPORTED_OPERATION.

    `check()` performs the in-memory transformation and reports a
    proposed diff; it writes NOTHING to disk (spec §15). `apply()`
    performs the same transformation and, only on full success,
    persists it (spec §16). A failure at any point leaves the tree
    byte-identical to its pre-call state.
    """

    name = "libcst"

    # ── check ──────────────────────────────────────────────────────────
    def check(self, request: PatchRequest) -> PatchResult:
        """Dry-run validation. NEVER writes to disk."""
        started_at = utc_now_iso()
        audit_inputs = audit_inputs_from_request(
            request, engine=self.name, started_at=started_at
        )

        validation = self._validate_request(request)
        if validation is not None:
            return _with_audit(
                validation,
                audit_inputs,
                verification_status="not_run",
            )

        result = self._execute(request, write=False)
        return _with_audit(
            result,
            audit_inputs,
            files_changed=result.files_changed,
            operations_applied=result.operations_applied,
            resulting_diff=result.resulting_diff,
            verification_status="not_run",
        )

    # ── apply ──────────────────────────────────────────────────────────
    def apply(self, request: PatchRequest) -> PatchResult:
        """Apply the requested mutation. Atomic on failure.

        On successful mutation the post-apply verification pipeline
        (spec §18–§21) runs: syntax-check the changed `.py` files
        (in-process `compile()`, no .pyc / __pycache__ artefacts) and
        execute any configured commands verbatim. A verification
        failure escalates the result to `PATCH_APPLIED_SYNTAX_FAILED`
        or `PATCH_APPLIED_TEST_FAILED`; the change stays on disk per
        spec §20.
        """
        started_at = utc_now_iso()
        audit_inputs = audit_inputs_from_request(
            request, engine=self.name, started_at=started_at
        )

        validation = self._validate_request(request)
        if validation is not None:
            return _with_audit(
                validation,
                audit_inputs,
                verification_status="not_run",
            )

        result = self._execute(request, write=True)

        # Verification only runs on a successful apply that produced
        # files. Pre-mutation failures (rejections from the engine
        # itself) already returned above with verification_status=
        # "not_run"; here we cover PATCH_APPLIED with at least one
        # changed file.
        verification_status = "not_run"
        if result.applied and result.files_changed:
            v_outcome = run_verification(
                request.repo_path,
                result.files_changed,
                request.verification,
            )
            verification_status = v_outcome.verdict
            if v_outcome.verdict == "passed":
                result = dataclasses.replace(
                    result,
                    verification=v_outcome.verification_dict,
                )
            elif v_outcome.verdict == "failed":
                result = dataclasses.replace(
                    result,
                    verification=v_outcome.verification_dict,
                    error_code=v_outcome.new_error_code,
                    error=v_outcome.failure_message,
                )
            else:
                # "not_run" — advertise the empty verdict so callers
                # can read `result.verification["syntax"]`.
                result = dataclasses.replace(
                    result,
                    verification=v_outcome.verification_dict,
                )

        return _with_audit(
            result,
            audit_inputs,
            files_changed=result.files_changed,
            operations_applied=result.operations_applied,
            resulting_diff=result.resulting_diff,
            verification_status=verification_status,
        )

    # ── internal ───────────────────────────────────────────────────────
    def _validate_request(
        self, request: PatchRequest
    ) -> Optional[PatchResult]:
        """Reject malformed structural_python requests BEFORE parsing any file.

        Returns a rejection PatchResult if validation fails, or None
        to proceed to the per-file execution phase. Path security is
        intentionally NOT done here: `_execute()` validates every path
        atomically before reading any file, mirroring the
        GitDiffEngine's flow and preserving spec §17 atomicity.
        """
        if request.patch_mode != "structural_python":
            return _rejected(
                PATCH_INVALID,
                f"LibCSTEngine received patch_mode={request.patch_mode!r}",
            )
        ops = request.operations
        if not isinstance(ops, list) or not ops:
            return _rejected(
                PATCH_INVALID,
                "LibCSTEngine requires a non-empty operations list",
            )
        for idx, op in enumerate(ops):
            if not isinstance(op, dict):
                return _rejected(
                    PATCH_INVALID,
                    f"operations[{idx}] must be a dict",
                )
            if "file" not in op or not isinstance(op["file"], str) or not op["file"]:
                return _rejected(
                    PATCH_INVALID,
                    f"operations[{idx}] requires a non-empty 'file' field",
                )
            op_name = op.get("operation")
            if not isinstance(op_name, str) or not op_name:
                return _rejected(
                    PATCH_INVALID,
                    f"operations[{idx}] requires a non-empty 'operation' field",
                )
            if op_name not in SUPPORTED_OPERATIONS:
                return _rejected(
                    PATCH_UNSUPPORTED_OPERATION,
                    f"operations[{idx}]: operation {op_name!r} is not "
                    f"supported in this handoff (supported: "
                    f"{sorted(SUPPORTED_OPERATIONS)})",
                )
        return None

    def _execute(
        self, request: PatchRequest, write: bool
    ) -> PatchResult:
        """Run the in-memory transformation; on `write`, persist it.

        Failure at any point leaves the working tree byte-identical to
        its pre-call state.

        Multi-operation / multi-file atomicity is enforced via a two-pass
        scheme (spec §17):

          Pass 1 (in-memory): for every target file, parse, apply every
            operation in order, validate the resulting source still
            parses, and collect the new source string. If ANY operation
            fails on ANY file, return the failure result WITHOUT writing
            anything.

          Pass 2 (write): only on the write path, only after the full
            in-memory pass succeeded, write each transformed source.
            Refuse any file that was already dirty (spec §32). If the
            write of a later file fails, the earlier writes have already
            landed; we report PATCH_APPLY_FAILED with an explicit note.
            (For the most common failure shape — an operation handler
            rejecting mid-pass — the in-memory pass catches it first
            and no write ever occurs.)
        """
        ops = request.operations
        repo_path = request.repo_path

        # Validate every target path atomically BEFORE reading any file.
        try:
            validated_files = validate_target_paths(
                repo_path,
                [op["file"] for op in ops],
                request.allowed_paths,
            )
        except PatchPathRejected as exc:
            return _rejected(
                exc.error_code,
                str(exc),
                files_rejected=(
                    [exc.offending_path] if exc.offending_path else []
                ),
            )

        # Group ops by validated file path, preserving original order.
        groups: Dict[str, List[Dict[str, Any]]] = {}
        order: List[str] = []
        for op, vf in zip(ops, validated_files):
            if vf not in groups:
                groups[vf] = []
                order.append(vf)
            groups[vf].append(op)

        # Pre-state (apply phase only) lets us refuse to overwrite
        # pre-existing dirty work (spec §32). check() does not need it.
        state = record_repo_state(repo_path) if write else None

        operations_requested = len(ops)
        operations_applied = 0

        # ── Pass 1: in-memory transformation across ALL files ────────
        #
        # `pending_writes` is the (path, new_source) pairs we will
        # commit in pass 2 if every in-memory transformation succeeds.
        pending_writes: List[Tuple[Path, str, str]] = []
        all_diffs: List[str] = []
        files_changed_in_memory: List[str] = []

        for vf in order:
            full_path = Path(repo_path) / vf
            if not full_path.exists():
                return _rejected(
                    PATCH_FILE_NOT_FOUND,
                    f"target file does not exist: {vf}",
                )
            try:
                source = full_path.read_text(encoding="utf-8")
            except OSError as exc:
                return _rejected(
                    PATCH_APPLY_FAILED,
                    f"cannot read target file {vf}: {exc}",
                )

            try:
                tree = cst.parse_module(source)
            except cst.ParserSyntaxError as exc:
                return _rejected(
                    PATCH_INVALID,
                    f"target file is not valid Python: {vf}: {exc}",
                )

            new_tree = tree
            file_applied = 0
            try:
                for op in groups[vf]:
                    new_tree, applied = _apply_op(new_tree, op)
                    if applied:
                        file_applied += 1
            except _OperationError as exc:
                # Atomicity: nothing has been written yet (we are
                # still in pass 1). Return the rejection directly.
                return exc.result

            new_source = new_tree.code

            # Final sanity: the transformed source must still parse.
            try:
                cst.parse_module(new_source)
            except cst.ParserSyntaxError as exc:
                return _rejected(
                    PATCH_INVALID,
                    f"transformed source is not valid Python: {vf}: {exc}",
                )

            file_diff = _unified_diff(source, new_source, vf)

            # Idempotent no-op → empty diff → no contribution.
            if not file_diff:
                continue

            files_changed_in_memory.append(vf)
            all_diffs.append(file_diff)
            operations_applied += file_applied
            pending_writes.append((full_path, new_source, file_diff))

        resulting_diff = "".join(all_diffs) if all_diffs else None

        # ── Pass 2: persist the in-memory result (write phase only) ──
        if write and pending_writes:
            for full_path, new_source, _diff in pending_writes:
                vf = full_path.relative_to(repo_path).as_posix()
                if state and vf in state.pre_existing_changed_files:
                    # No write has happened yet on this request, so we
                    # can still honour §32 by refusing the WHOLE patch.
                    return _rejected(
                        PATCH_CONFLICT,
                        f"file {vf} was dirty before the patch and would "
                        f"be overwritten; refusing to silently clobber "
                        f"pre-existing work (spec §32)",
                    )
                try:
                    full_path.write_text(new_source, encoding="utf-8")
                except OSError as exc:
                    # We have already written earlier files. The §17
                    # fail-all guarantee is preserved against
                    # operation-handler failures (caught in pass 1),
                    # but a filesystem failure mid-write is a genuine
                    # IO error and we report it. The reviewer will see
                    # which files did and did not land.
                    return _rejected(
                        PATCH_APPLY_FAILED,
                        f"cannot write target file {vf}: {exc}",
                    )
                # Defensive: confirm the file actually changed in the
                # working tree.
                post_diff = _capture_diff_for_file(repo_path, vf)
                if not post_diff:
                    post_porcelain = _capture_porcelain(repo_path)
                    if vf not in _porcelain_paths(post_porcelain):
                        return _rejected(
                            PATCH_APPLY_FAILED,
                            f"file {vf} did not appear in post-write diff "
                            f"or porcelain; aborting",
                        )

        if write:
            status = "applied" if operations_applied > 0 else "no_change"
            applied_flag = operations_applied > 0
        else:
            # check() always reports check_passed on a structurally
            # sound request, even when the result is a no-change
            # idempotent outcome. `applied` is False because check()
            # never mutates the tree (spec §15, mirrors B1
            # GitDiffEngine.check()).
            status = "check_passed"
            applied_flag = False

        return _ok(
            files_changed=files_changed_in_memory,
            operations_requested=operations_requested,
            operations_applied=operations_applied,
            resulting_diff=resulting_diff,
            status=status,
            applied=applied_flag,
        )


# ── Audit attachment helper ────────────────────────────────────────────


def _with_audit(
    result: PatchResult,
    inputs: AuditInputs,
    *,
    files_changed: Optional[List[str]] = None,
    operations_requested: Optional[int] = None,
    operations_applied: Optional[int] = None,
    resulting_diff: Optional[str] = None,
    verification_status: str = "not_run",
) -> PatchResult:
    """Attach a fully-populated audit block to `result`.

    Mirrors `git_diff_engine._with_audit`. Each engine wraps its own
    return points to keep audit logic local; the audit module is
    engine-agnostic so the builder is shared.

    `operations_requested` defaults to the value the PatchResult
    carries when not overridden — that is the canonical source for
    the count (the engine sets it on every PatchResult it builds).
    """
    audit_inputs = dataclasses.replace(
        inputs,
        files_changed=(
            tuple(files_changed) if files_changed is not None else inputs.files_changed
        ),
        operations_requested=(
            operations_requested
            if operations_requested is not None
            else result.operations_requested
        ),
        operations_applied=(
            operations_applied
            if operations_applied is not None
            else inputs.operations_applied
        ),
        resulting_diff=(
            resulting_diff
            if resulting_diff is not None
            else inputs.resulting_diff
        ),
        verification_status=verification_status,
        final_status=result.status,
        final_error_code=result.error_code,
    )
    audit_block = build_audit_block(audit_inputs)
    return dataclasses.replace(result, audit=audit_block)
