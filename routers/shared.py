"""Shared helpers for the routers/ package.

The routers/* modules cannot import app at module top-level — that
would create a circular import (app.py imports the routers via
`from routers.bridge import router as bridge_router` + `app.include_router`,
and the routers want to use `app.DB_PATH` and similar module globals).

The `get_db_path()` helper resolves this with a late import: it imports
`app` inside the function body so the module-level import is not
triggered when routers/* are first loaded. By call time, app is fully
loaded and `app.DB_PATH` reflects whatever value it currently holds
(production default OR the temp DB path set by tests/conftest.py).

This pattern preserves the same external behavior the inline endpoints
in app.py had: they read `DB_PATH` (a module-level constant set at
import time), and the test fixture patches that constant. With the
late-import helper, the routers read the SAME constant, just at
function-call time instead of module-load time.
"""


def get_db_path() -> str:
    """Return the current value of app.DB_PATH.

    Late-imports `app` to avoid circular import at module top-level.
    The test fixture (tests/conftest.py) monkey-patches `app.DB_PATH`
    to point at a temp DB; this helper picks up that patched value at
    call time.
    """
    import app  # late import — app is fully loaded by endpoint call time
    return app.DB_PATH