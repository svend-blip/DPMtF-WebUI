# Coding Standard

## General Rules
- No new dependencies unless explicitly authorized.
- Hide over delete — prefer CSS `display: none` or conditional rendering.
- Match existing code style (indentation, naming, comment density).
- One logical change per commit.
- Stop after verification — do not expand scope mid-task.

## Python
- Use `py_compile` to verify syntax before committing.
- Follow PEP 8 for formatting where practical.
- Document functions with docstrings matching existing conventions.
- Database queries must use parameterized statements (no string interpolation).

## JavaScript
- Use `node --check` to verify syntax before committing.
- Match existing variable naming (`camelCase`).
- No global state mutation without explicit comment explaining why.
- DOM manipulation should be localized; avoid side effects on unrelated elements.

## CSS
- Use class-based selectors; avoid inline styles unless dynamically generated.
- Group related rules together.
- Comment sections that hide panels (reversible hiding).

## Markdown / Governance Files
- Use ATX headings (`#`, `##`, `###`).
- Keep tables consistent with header separators.
- Append only to `CHANGELOG.md` and `DECISIONS.md`.
