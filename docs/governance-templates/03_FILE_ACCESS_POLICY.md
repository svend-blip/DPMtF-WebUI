# File Access Policy

## Read-Only Files
Files that must not be modified without explicit approval:
- `DATABASE_RUNTIME_STATE.md` — database schema reference.
- `DECISIONS.md` — append-only decision log.
- `CHANGELOG.md` — append-only change history.

## Restricted Write
Files that require human approval before modification:
- `app.py` — backend entry point; changes must pass validation.
- Database migration scripts.

## Free Write
Files safe to modify within scope:
- Template files in `templates/`.
- Static assets in `static/`.
- Documentation in `docs/`.

## Dangerous Patterns
The following patterns require extra review:
- Schema changes (`ALTER TABLE`, new tables).
- Dependency additions.
- Deletion of existing functionality (prefer hiding over deleting).
