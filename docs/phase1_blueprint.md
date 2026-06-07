# DPMtF WebUI - Phase 1 Blueprint

## Phase 1A Scope

This phase implements the initial project skeleton for the DPMtF WebUI application. The focus is on establishing the basic structure and core functionality needed for the application to run.

### Implemented Features:
- Basic FastAPI application structure
- HTML template rendering for the main page
- Health check endpoint at `/api/health`
- Database initialization script
- CSS styling for the user interface
- Project documentation

### Database Schema:
The database includes the following tables:
- `projects`
- `reference_projects`
- `frontend_panels`
- `panel_classifications`
- `app_profiles`
- `app_profile_panels`
- `prompt_sequences`
- `prompt_sequence_steps`
- `generated_prompts`

## Phase 1B Scope

This phase implements the import functionality for reference panels from the ai-pc-resource-webui project.

### Implemented Features:
- Import script (`scripts/import_reference_panels.py`) that reads HTML panels from ai-pc-resource-webui/templates/index.html
- Database insertion of panel data with proper schema mapping
- Classification system for panels (default "unknown" classification)
- New API endpoint `/api/panels` to retrieve imported panels

### Import Process:
- Reads HTML from `/home/svend/ai-pc-resource-webui/templates/index.html`
- Detects panel sections using HTML attributes and class names
- Extracts panel information including:
  - source_file
  - panel_key
  - panel_title
  - html_id if present
  - sort_order
  - raw_opening_tag
- Inserts or updates records in `frontend_panels` table
- Creates matching `panel_classifications` records with default "unknown" classification

## What is Intentionally Not Implemented Yet

The following features are planned for future phases but are not included in Phase 1B:

1. **AI Prompt Generation**: Implementation of AI prompt generation capabilities
2. **Service Control**: Service control, wrappers, and execution buttons
3. **Advanced Features**: Additional UI components and functionality

## Next Phase: AI Prompt Generation

Phase 1C will focus on implementing AI prompt generation capabilities based on the imported panels.