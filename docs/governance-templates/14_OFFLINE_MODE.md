# Offline Mode

## Overview
This project is designed to run fully offline. All models, data, and tools are local.

## Requirements for Offline Operation
- Local Python runtime with FastAPI and Uvicorn installed.
- SQLite database file present at `databases/dpmtf.db`.
- Local LLM (e.g., Ollama) for agent-driven prompt execution.
- Local git repository for version control.

## What Does NOT Require Internet
- Application startup and API endpoints.
- Database reads and writes.
- Prompt generation and execution with local models.
- Git commit operations.

## What MAY Require Internet
- Initial dependency installation (`pip install`).
- Model downloads (one-time setup).
- Upstream package updates.

## Offline Verification
1. Disconnect network.
2. Start the application: `python3 app.py`.
3. Verify `/api/health` responds.
4. Verify all UI panels load.
