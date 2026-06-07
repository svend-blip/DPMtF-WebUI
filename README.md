# DPMtF WebUI

## Project Purpose

DPMtF WebUI is a web-based interface for managing deterministic prompt workflows. It provides a structured approach to creating, organizing, and executing prompt sequences for AI applications.

## Installation

To install the required dependencies, run:

```bash
pip install -r requirements.txt
```

## Starting the Application

To start the WebUI on port 9130:

```bash
python app.py
```

Or using uvicorn directly:

```bash
uvicorn app:app --host 0.0.0.0 --port 9130
```

## Health Check

To check if the application is running properly:

```bash
curl http://localhost:9130/api/health
```

## Importing Reference Panels

To import panels from ai-pc-resource-webui:

```bash
python scripts/import_reference_panels.py
```

## Checking Imported Panels

To view imported panels through the API:

```bash
curl http://localhost:9130/api/panels
```

## Phase 1F: Prompt Sequence Planner

This phase implements the skeleton for the Prompt Sequence Planner feature. The planner allows users to:

1. See existing prompt sequences
2. Create new prompt sequences manually
3. Select a prompt sequence
4. See steps for the selected sequence
5. Add simple manual steps to the selected sequence

### Features Implemented

- **Database Schema**: Updated `prompt_sequences` and `prompt_sequence_steps` tables with required columns
- **API Endpoints**: 
  - GET /api/prompt-sequences
  - POST /api/prompt-sequences  
  - GET /api/prompt-sequences/{sequence_id}/steps
  - POST /api/prompt-sequences/{sequence_id}/steps
- **Frontend UI**: 
  - Form to create new sequences
  - Dropdown to select existing sequences
  - Read-only list of steps for selected sequence
  - Form to add new steps
  - Status indicators and error handling

### Usage

The Prompt Sequence Planner is now accessible through the WebUI under the "Prompt Sequence Planner" section.

## Project Structure

- `app.py` - Main FastAPI application
- `databases/` - Database files
- `templates/` - HTML templates
- `static/` - CSS and other static assets
- `scripts/` - Utility scripts
- `exports/` - Exported data
- `docs/` - Documentation
- `config/` - Configuration files

## Database Initialization

To initialize the database, run:

```bash
python scripts/init_db.py
```

This creates the necessary tables for the application's data model.