# Database Backup Strategy

## Principle

The SQLite database (`databases/dpmtf.db`) is runtime state managed by the idempotent
`scripts/init_db.py` script. It is NOT tracked in git (excluded via `.gitignore`).

Manual backups are created before running `init_db.py` to prevent accidental data loss.

## Backup Procedure

### Manual Backup (Recommended before init_db.py)

Run this before any `init_db.py` execution that might overwrite existing state:

```bash
cd databases
cp dpmtf.db "dpmtf.db.bak.$(date +%Y%m%d-%H%M%S)"
```

This creates a timestamped backup file (e.g., `dpmtf.db.bak.20260619-143022`).

All `.bak.*` files are excluded from git via `.gitignore`.

### Automatic Backup (Future Enhancement)

Add to `scripts/init_db.py` before the main initialization block:

```python
import shutil
from datetime import datetime

db_path = "databases/dpmtf.db"
if os.path.exists(db_path):
    backup_name = f"{db_path}.bak.{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(db_path, backup_name)
    print(f"Backup created: {backup_name}")
```

### Retention Policy

- Keep the **most recent 3 backups** in `databases/`.
- Delete older backups manually or via periodic cleanup.
- All backup files are gitignored and do not affect repository size.

## Recovery

To restore from a backup:

```bash
cd databases
cp dpmtf.db.bak.20260619-143022 dpmtf.db
python3 scripts/init_db.py  # Re-initialize schema/seed on restored database
```

## Notes

- The `init_db.py` script is idempotent — running it multiple times produces the same result.
- Backup is only needed when the database contains user data that should not be overwritten.
- During active development, backups are rarely needed since seed data is authoritative.
