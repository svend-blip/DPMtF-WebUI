# Restart / Runbook

## How to Start the Application
```bash
cd /path/to/project
python3 app.py
# or with uvicorn directly:
uvicorn app:app --host 0.0.0.0 --port 9130
```

## How to Verify It Is Running
- Open `http://localhost:9130` in a browser.
- Check `/api/health` returns `{"status": "healthy"}`.

## Common Failure Modes
| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Database not found | Missing `databases/dpmtf.db` | Verify path, restore from backup. |
| Port already in use | Previous instance still running | Kill old process or change port. |
| Static files 404 | Wrong working directory | Run from project root. |

## Recovery Steps
1. Check that `databases/dpmtf.db` exists and is readable.
2. Verify Python dependencies: `pip install fastapi uvicorn`.
3. Restart the server and check `/api/health`.
