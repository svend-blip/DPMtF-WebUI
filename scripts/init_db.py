import sqlite3
import os
import json

# Database path
DB_PATH = "databases/dpmtf.db"

# Create database directory if it doesn't exist
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Connect to database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Create tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS reference_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Create or modify frontend_panels table to include all required columns
cursor.execute("""
CREATE TABLE IF NOT EXISTS frontend_panels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    panel_key TEXT NOT NULL,
    panel_title TEXT,
    html_id TEXT,
    sort_order INTEGER,
    raw_opening_tag TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Add updated_at column if it doesn't exist (for backward compatibility)
try:
    cursor.execute("ALTER TABLE frontend_panels ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
except sqlite3.OperationalError:
    # Column already exists
    pass

cursor.execute("""
CREATE TABLE IF NOT EXISTS panel_classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    panel_id INTEGER,
    classification TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (panel_id) REFERENCES frontend_panels (id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS app_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS app_profile_panels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER,
    panel_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES app_profiles (id),
    FOREIGN KEY (panel_id) REFERENCES frontend_panels (id)
)
""")

# Create prompt_sequences table with all required columns
cursor.execute("""
CREATE TABLE IF NOT EXISTS prompt_sequences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    goal TEXT,
    status TEXT DEFAULT 'planned',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Add missing columns if they don't exist (for backward compatibility)
try:
    cursor.execute("ALTER TABLE prompt_sequences ADD COLUMN goal TEXT")
except sqlite3.OperationalError:
    # Column already exists
    pass

try:
    cursor.execute("ALTER TABLE prompt_sequences ADD COLUMN status TEXT DEFAULT 'planned'")
except sqlite3.OperationalError:
    # Column already exists
    pass

try:
    cursor.execute("ALTER TABLE prompt_sequences ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
except sqlite3.OperationalError:
    # Column already exists
    pass

cursor.execute("""
CREATE TABLE IF NOT EXISTS prompt_sequence_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_id INTEGER,
    step_number INTEGER,
    step_title TEXT,
    target_layer TEXT,
    status TEXT DEFAULT 'planned',
    prompt_text TEXT,
    result_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sequence_id) REFERENCES prompt_sequences (id)
)
""")

# Add missing columns for prompt_sequence_steps if they don't exist
try:
    cursor.execute("ALTER TABLE prompt_sequence_steps ADD COLUMN step_title TEXT")
except sqlite3.OperationalError:
    # Column already exists
    pass

try:
    cursor.execute("ALTER TABLE prompt_sequence_steps ADD COLUMN target_layer TEXT")
except sqlite3.OperationalError:
    # Column already exists
    pass

try:
    cursor.execute("ALTER TABLE prompt_sequence_steps ADD COLUMN status TEXT DEFAULT 'planned'")
except sqlite3.OperationalError:
    # Column already exists
    pass

try:
    cursor.execute("ALTER TABLE prompt_sequence_steps ADD COLUMN result_note TEXT")
except sqlite3.OperationalError:
    # Column already exists
    pass

try:
    cursor.execute("ALTER TABLE prompt_sequence_steps ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
except sqlite3.OperationalError:
    # Column already exists
    pass

cursor.execute("""
CREATE TABLE IF NOT EXISTS generated_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_step_id INTEGER,
    prompt_text TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sequence_step_id) REFERENCES prompt_sequence_steps (id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS phase_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_key TEXT UNIQUE NOT NULL,
    phase_title TEXT NOT NULL,
    phase_description TEXT,
    phase_state TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Create layout_slots table
cursor.execute("""
CREATE TABLE IF NOT EXISTS layout_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id TEXT UNIQUE NOT NULL,
    parent_slot_id TEXT,
    slot_name TEXT NOT NULL,
    slot_description TEXT,
    display_order INTEGER NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Create layout_panels table
cursor.execute("""
CREATE TABLE IF NOT EXISTS layout_panels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    panel_id TEXT UNIQUE NOT NULL,
    slot_id TEXT NOT NULL,
    panel_key TEXT NOT NULL,
    panel_title TEXT NOT NULL,
    panel_description TEXT,
    panel_type TEXT NOT NULL,
    display_order INTEGER NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Seed layout_slots data
layout_slots_data = [
    ("SLOT-2000001", None, "Main Dashboard", "Main dashboard area", 1, 1),
    ("SLOT-2000002", None, "Top Action Area", "Top action area", 2, 1),
    ("SLOT-2000003", None, "Imported Panels Area", "Area for imported panels", 3, 1),
    ("SLOT-2000004", None, "Phase Status Area", "Area for phase status display", 4, 1),
    ("SLOT-2000005", None, "Project Planning Area", "Area for project planning", 5, 1),
    ("SLOT-2000006", None, "System Setup Drawer", "System setup drawer area", 6, 1),
]

# Safely insert or update layout_slots data (no DELETE)
for slot in layout_slots_data:
    cursor.execute("""
        INSERT OR REPLACE INTO layout_slots
        (slot_id, parent_slot_id, slot_name, slot_description, display_order, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, slot)

# Seed layout_panels data
layout_panels_data = [
    ("PNL-3000001", "SLOT-2000001", "database_status", "Database Status Panel", "Database status panel", "status", 1, 1),
    ("PNL-3000002", "SLOT-2000003", "imported_panels", "Imported Panels Panel", "Imported panels panel", "imported_panels", 1, 1),
    ("PNL-3000003", "SLOT-2000001", "app_profiles", "App Profiles Panel", "App profiles panel", "app_profiles", 2, 1),
    ("PNL-3000004", "SLOT-2000001", "prompt_sequence_planner", "Prompt Sequence Planner Panel", "Prompt sequence planner panel", "prompt_sequence_planner", 3, 1),
    ("PNL-3000005", "SLOT-2000004", "phase_status", "Phase Status Panel", "Phase status panel", "phase_status", 1, 1),
    ("PNL-3000006", "SLOT-2000005", "project_planning", "New Project Planning Panel", "Project planning panel", "project_planning", 1, 1),
    ("PNL-3000007", "SLOT-2000006", "system_setup_drawer", "System Setup Drawer Shell", "System setup drawer shell", "system_setup_drawer", 1, 1),
]

# Safely insert or update layout_panels data (no DELETE)
for panel in layout_panels_data:
    cursor.execute("""
        INSERT OR REPLACE INTO layout_panels
        (panel_id, slot_id, panel_key, panel_title, panel_description, panel_type, display_order, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, panel)

# Seed phase status data
# Blok 1 (1A-1X): Core infrastructure — all completed
# Blok 2 (2A-2D): AI PC Resource WebUI migration prep — all completed
# Blok 3 (2E): Governance-template opgradering — completed 2026-06-12
# Blok 4 (2F-2I): Prompt-infrastruktur (hitrate, patterns, templates, compiler)
# Blok 5 (2J-2L): Automatisering (validation, git-sync, platform-adapter)
# Blok 6 (2M-2O): Lokal model integration (session manager, auto-loop, parallel-test)
phase_data = [
    # ── Blok 1: Core infrastructure (1A-1X) — completed ──
    ("1A", "Skeleton", "Initial project structure", "completed", 0),
    ("1B", "Panel import", "Import reference panels", "completed", 1),
    ("1C", "Read-only panel table", "Display panels in read-only table", "completed", 2),
    ("1D", "Classification UI", "Add classification dropdowns", "completed", 3),
    ("1E", "App Profiles", "Create and manage app profiles", "completed", 4),
    ("1F", "Prompt Sequence Planner", "Plan prompt sequences", "completed", 5),
    ("1G", "Generate Next Prompt Preview", "Preview next prompt", "completed", 6),
    ("1H", "Step Status / Mark Step Done", "Mark steps as done", "completed", 7),
    ("1I", "Prompt History / Generated Archive", "Archive generated prompts", "completed", 8),
    ("1J", "App Profile to Prompt Sequence Draft", "Create draft prompt sequence", "completed", 9),
    ("1K", "New Project Folder Planning", "Plan new project folder", "completed", 10),
    ("1L", "Slim Frontend File Structure", "Move JS to static files", "completed", 11),
    ("1M", "Extract Frontend CSS and Theme Foundation", "Move CSS to static files", "completed", 12),
    ("1N", "System Setup Drawer Shell", "Add system setup drawer", "completed", 13),
    ("1O", "Database-driven Frontend Layout Schema", "Create database-driven layout schema", "completed", 14),
    ("1P", "Database-driven Frontend Layout Renderer", "Render database-driven layout", "completed", 15),
    ("1Q", "Localization / i18n Label Registry Schema", "Create i18n label registry schema", "completed", 16),
    ("1R", "Localization / i18n Label Helper Scripts", "Create i18n helper scripts", "completed", 17),
    ("1S", "Localization / i18n Renderer", "Render i18n labels", "completed", 18),
    ("1T", "Endpoint Registry Schema", "Create endpoint registry schema", "completed", 19),
    ("1U", "Endpoint Registry UI", "Add endpoint registry UI", "completed", 20),
    ("1V", "Endpoint Runtime Status Checks", "Check endpoint status", "completed", 21),
    ("1W", "WebUI Bootstrap Dataset / Seed Scripts", "Create bootstrap dataset", "completed", 22),
    ("1X", "Architecture Decision Record in Frontend Roadmap", "Document architecture decisions", "completed", 23),
    # ── Blok 2: AI PC Resource WebUI migration prep (2A-2D) — completed ──
    ("2A", "New AI PC Resource WebUI Migration Target", "Create new AI PC WebUI target", "completed", 24),
    ("2B", "Select 4–5 Reusable AI PC Panels", "Select reusable panels", "completed", 25),
    ("2C", "Create New AI PC WebUI Project Skeleton on New Port", "Create project skeleton", "completed", 26),
    ("2D", "Specify AI PC WebUI v2 Panel Requirements", "Specify v2 panel requirements", "completed", 27),
    # ── Blok 3: Governance-template opgradering (2E) ──
    ("2E", "Governance-template opgradering", "Upgrade master templates from v3 learnings: 17_PERMISSION_MODE_POLICY, NEXT_CONTEXT, IMPLEMENTATION_REPORT, GIT_POLICY, CODING_STANDARD, VALIDATION, PROJECT, SCOPE, ARCHITECTURE, RESTART, DATABASE_RUNTIME_STATE", "completed", 28),
    # ── Blok 4: Prompt-infrastruktur (2F-2I) ──
    ("2F", "Hitrate Scoring", "Database tables for prompt success/failure tracking: prompt_runs, prompt_hitrates. API endpoints for hitrate queries.", "next", 29),
    ("2G", "Implementation Pattern Manager", "Capture successful implementation patterns from completed phases. Table: implementation_patterns. Pattern extraction from phase reports.", "planned", 30),
    ("2H", "Prompt Template Manager", "Migrate static Markdown templates to database-driven parametrisable templates. Table: prompt_templates with variable fields.", "planned", 31),
    ("2I", "Local Prompt Compiler", "Generate prompts from templates + hitrate data + governance context. Assembles project-specific prompts without cloud dependency.", "planned", 32),
    # ── Blok 5: Automatisering (2J-2L) ──
    ("2J", "Validation Automation", "Database-driven validation: validation_rules, validation_runs, validation_results tables. /api/validate endpoint runs all relevant rules.", "planned", 33),
    ("2K", "Git Sync Management", "Database-driven git tracking: git_sync_status, git_operations tables. /api/git/status and /api/git/push endpoints.", "planned", 34),
    ("2L", "Platform Adapter Framework", "PlatformAdapter base class for Linux/Windows abstraction. Linux implementation. Windows stub. Service actions get platform field.", "planned", 35),
    # ── Blok 6: Lokal model integration (2M-2O) ──
    ("2M", "Local Claude Code Session Manager", "Start/stop/monitor local Claude Code session via Ollama. Session status tracking in database.", "planned", 36),
    ("2N", "Prompt→Implementer→Validator loop", "DPMtF generates prompt → local Claude Code session implements → auto-validation runs → hitrate updated. Full closed loop.", "planned", 37),
    ("2O", "Parallel-kørsel test", "Same prompt executed in cloud (Claude Code) and local model. Results compared for hitrate ground-truth calibration.", "planned", 38),
]

# Safely insert or update phase status data (no DELETE)
for phase in phase_data:
    cursor.execute("""
        INSERT OR REPLACE INTO phase_status
        (phase_key, phase_title, phase_description, phase_state, sort_order)
        VALUES (?, ?, ?, ?, ?)
    """, phase)

cursor.execute("""
CREATE TABLE IF NOT EXISTS project_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    target_folder TEXT NOT NULL,
    app_port INTEGER,
    app_profile_id INTEGER,
    prompt_sequence_id INTEGER,
    notes TEXT,
    status TEXT DEFAULT 'planned',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_profile_id) REFERENCES app_profiles (id),
    FOREIGN KEY (prompt_sequence_id) REFERENCES prompt_sequences (id)
)
""")

# Create ui_labels table for i18n label registry
cursor.execute("""
CREATE TABLE IF NOT EXISTS ui_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label_id TEXT UNIQUE NOT NULL,
    label_key TEXT UNIQUE NOT NULL,
    label_domain TEXT NOT NULL,
    default_text TEXT NOT NULL,
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Create ui_label_translations table for locale-specific translations
cursor.execute("""
CREATE TABLE IF NOT EXISTS ui_label_translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label_id TEXT NOT NULL,
    locale TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(label_id, locale)
)
""")

# Seed baseline ui_labels data
ui_labels_data = [
    ("LBL-1000001", "system_setup.title", "system_setup", "System Setup", "Title for the system setup section"),
    ("LBL-1000002", "system_setup.layout_slots.title", "system_setup", "Layout Slots", "Title for the layout slots section"),
    ("LBL-1000003", "system_setup.database_layout_preview.title", "system_setup", "Database Layout Preview", "Title for the database layout preview section"),
    ("LBL-1000004", "system_setup.database_layout_preview.description", "system_setup", "Read-only preview from /api/frontend-layout", "Description for the database layout preview section"),
    ("LBL-1000005", "system_setup.database_layout_preview.refresh", "system_setup", "Refresh", "Label for the refresh button in database layout preview"),
    ("LBL-1000006", "phase_status.show_completed", "phase_status", "Show completed phases", "Toggle label to show/hide completed phases"),
]

# Safely insert or update ui_labels data (no DELETE)
for label in ui_labels_data:
    cursor.execute("""
        INSERT OR REPLACE INTO ui_labels
        (label_id, label_key, label_domain, default_text, description)
        VALUES (?, ?, ?, ?, ?)
    """, label)

# Seed en-US translations for all baseline labels
ui_label_translations_data = [
    ("LBL-1000001", "en-US", "System Setup"),
    ("LBL-1000002", "en-US", "Layout Slots"),
    ("LBL-1000003", "en-US", "Database Layout Preview"),
    ("LBL-1000004", "en-US", "Read-only preview from /api/frontend-layout"),
    ("LBL-1000005", "en-US", "Refresh"),
    ("LBL-1000006", "en-US", "Show completed phases"),
]

# Safely insert or update ui_label_translations data (no DELETE)
for translation in ui_label_translations_data:
    cursor.execute("""
        INSERT OR REPLACE INTO ui_label_translations
        (label_id, locale, translated_text)
        VALUES (?, ?, ?)
    """, translation)

# Create endpoint_registry table
cursor.execute("""
CREATE TABLE IF NOT EXISTS endpoint_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint_id TEXT UNIQUE NOT NULL,
    endpoint_key TEXT UNIQUE NOT NULL,
    route_path TEXT NOT NULL,
    http_method TEXT NOT NULL,
    endpoint_purpose TEXT NOT NULL,
    response_shape TEXT,
    frontend_consumer TEXT,
    is_read_only INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Seed baseline endpoint_registry data
endpoint_registry_data = [
    ("ENDP-4000001", "health", "/api/health", "GET", "Health check endpoint", "status JSON", "system"),
    ("ENDP-4000002", "frontend_layout", "/api/frontend-layout", "GET", "Database-driven frontend layout registry", "layout_slots and layout_panels JSON", "system_setup_drawer"),
    ("ENDP-4000003", "ui_label_registry", "/api/ui-label-registry", "GET", "UI label registry", "ui_labels and ui_label_translations JSON", "system_setup_drawer"),
    ("ENDP-4000004", "ui_labels_domain", "/api/ui-labels/{label_domain}", "GET", "Resolved localized labels for a label domain", "labels JSON", "system_setup_drawer"),
    ("ENDP-4000005", "phase_status", "/api/phase-status", "GET", "Roadmap phase status", "phase status JSON", "main_dashboard"),
    ("ENDP-4000006", "endpoint_runtime_status", "/api/endpoint-runtime-status", "GET", "Runtime route registration status for endpoint registry records", "endpoint runtime status JSON", "system_setup_drawer"),
    ("ENDP-4000007", "bootstrap_dataset_status", "/api/bootstrap-dataset-status", "GET", "Bootstrap dataset registry status", "bootstrap dataset status JSON", "system_setup_drawer"),
    ("ENDP-4000008", "architecture_decision_records", "/api/architecture-decision-records", "GET", "Architecture Decision Record registry", "architecture decision records JSON", "system_setup_drawer"),
    ("ENDP-4000009", "webui_migration_targets", "/api/webui-migration-targets", "GET", "WebUI migration target registry", "webui migration targets JSON", "system_setup_drawer"),
    ("ENDP-4000010", "reusable_panel_selections", "/api/reusable-panel-selections", "GET", "Reusable AI PC panel selection registry", "reusable panel selections JSON", "system_setup_drawer"),
    ("ENDP-4000011", "webui_project_skeletons", "/api/webui-project-skeletons", "GET", "WebUI project skeleton registry", "webui project skeletons JSON", "system_setup_drawer"),
    ("ENDP-4000012", "v2_panel_requirements", "/api/v2-panel-requirements", "GET", "AI PC Resource WebUI v2 panel requirements registry", "v2 panel requirements JSON", "system_setup_drawer"),
]

# Safely insert or update endpoint_registry data (no DELETE)
for endpoint in endpoint_registry_data:
    cursor.execute("""
        INSERT OR REPLACE INTO endpoint_registry
        (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, endpoint)

# Create bootstrap_dataset_registry table
cursor.execute("""
CREATE TABLE IF NOT EXISTS bootstrap_dataset_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT UNIQUE NOT NULL,
    dataset_key TEXT UNIQUE NOT NULL,
    table_name TEXT NOT NULL,
    dataset_purpose TEXT NOT NULL,
    source_script TEXT NOT NULL,
    min_expected_count INTEGER DEFAULT 1,
    is_required INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Seed baseline bootstrap_dataset_registry data
bootstrap_dataset_data = [
    ("BDS-5000001", "phase_status", "phase_status", "Roadmap phase seed data", "scripts/init_db.py", 1, 1, 1),
    ("BDS-5000002", "layout_slots", "layout_slots", "Database-driven layout slot seed data", "scripts/init_db.py", 6, 1, 1),
    ("BDS-5000003", "layout_panels", "layout_panels", "Database-driven layout panel seed data", "scripts/init_db.py", 7, 1, 1),
    ("BDS-5000004", "ui_labels", "ui_labels", "UI label registry seed data", "scripts/init_db.py", 6, 1, 1),
    ("BDS-5000005", "ui_label_translations", "ui_label_translations", "UI label translation seed data", "scripts/init_db.py", 6, 1, 1),
    ("BDS-5000006", "endpoint_registry", "endpoint_registry", "Endpoint registry seed data", "scripts/init_db.py", 6, 1, 1),
    ("BDS-5000007", "architecture_decision_records", "architecture_decision_records", "Architecture Decision Record seed data", "scripts/init_db.py", 4, 1, 1),
    ("BDS-5000008", "webui_migration_targets", "webui_migration_targets", "WebUI migration target seed data", "scripts/init_db.py", 1, 1, 1),
    ("BDS-5000009", "reusable_panel_selections", "reusable_panel_selections", "Reusable AI PC panel selection seed data", "scripts/init_db.py", 5, 1, 1),
    ("BDS-5000010", "webui_project_skeletons", "webui_project_skeletons", "WebUI project skeleton seed/status data", "scripts/init_db.py", 1, 1, 1),
    ("BDS-5000011", "v2_panel_requirements", "v2_panel_requirements", "AI PC Resource WebUI v2 panel requirements seed data", "scripts/init_db.py", 11, 1, 1),
]

# Safely insert or update bootstrap_dataset_registry data (no DELETE)
for dataset in bootstrap_dataset_data:
    cursor.execute("""
        INSERT OR REPLACE INTO bootstrap_dataset_registry
        (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, dataset)

# Create architecture_decision_records table
# Create webui_migration_targets table
cursor.execute("""
CREATE TABLE IF NOT EXISTS webui_migration_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id TEXT UNIQUE NOT NULL,
    target_project_key TEXT UNIQUE NOT NULL,
    target_project_name TEXT NOT NULL,
    target_project_path TEXT NOT NULL,
    target_port INTEGER NOT NULL,
    target_status TEXT NOT NULL,
    source_project_path TEXT NOT NULL,
    migration_strategy TEXT NOT NULL,
    related_adr_id TEXT,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Seed webui_migration_targets data (no DELETE — upsert style)
webui_migration_targets_data = [
    (
        "WMT-7000001",
        "ai_pc_resource_webui_v2",
        "AI PC Resource WebUI v2",
        "/home/svend/ai-pc-resource-webui-v2",
        9121,
        "planned",
        "/home/svend/ai-pc-resource-webui",
        "new_clean_project_reuse_selected_panels",
        "ADR-6000001",
        "New clean AI PC Resource WebUI version on a different port. No project files created in this phase.",
        1,
    ),
]

for target in webui_migration_targets_data:
    cursor.execute("""
        INSERT OR REPLACE INTO webui_migration_targets
        (target_id, target_project_key, target_project_name, target_project_path,
         target_port, target_status, source_project_path, migration_strategy,
         related_adr_id, notes, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, target)

# Create reusable_panel_selections table
cursor.execute("""
CREATE TABLE IF NOT EXISTS reusable_panel_selections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reusable_panel_id TEXT UNIQUE NOT NULL,
    target_project_key TEXT NOT NULL,
    source_project_path TEXT NOT NULL,
    panel_key TEXT NOT NULL,
    panel_title TEXT NOT NULL,
    source_html_id TEXT,
    source_panel_kind TEXT NOT NULL,
    selection_status TEXT NOT NULL,
    selection_reason TEXT NOT NULL,
    migration_priority INTEGER NOT NULL,
    is_required INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Seed reusable_panel_selections data (no DELETE — upsert style)
reusable_panel_selections_data = [
    (
        "RPN-8000001",
        "ai_pc_resource_webui_v2",
        "/home/svend/ai-pc-resource-webui",
        "resources",
        "System Resources",
        "resources",
        "status_panel",
        "selected",
        "Core system resource visibility is required for AI PC operations.",
        1,
        1,
        1,
    ),
    (
        "RPN-8000002",
        "ai_pc_resource_webui_v2",
        "/home/svend/ai-pc-resource-webui",
        "pipeline-status-panel",
        "Pipeline Status Panel",
        "pipeline-status-panel",
        "status_panel",
        "selected",
        "Pipeline health/status is the main overview for operational readiness.",
        2,
        1,
        1,
    ),
    (
        "RPN-8000003",
        "ai_pc_resource_webui_v2",
        "/home/svend/ai-pc-resource-webui",
        "pipeline-action-mapping-panel",
        "Pipeline Action Mapping Panel",
        "pipeline-action-mapping-panel",
        "action_mapping_panel",
        "selected",
        "Pipeline actions must be mapped to safe backend controls later.",
        3,
        1,
        1,
    ),
    (
        "RPN-8000004",
        "ai_pc_resource_webui_v2",
        "/home/svend/ai-pc-resource-webui",
        "manual-runbooks",
        "Manual Runbooks",
        "manual-runbooks",
        "runbook_panel",
        "selected_pending_source_validation",
        "Manual operational recovery steps should remain available in the clean WebUI.",
        4,
        1,
        1,
    ),
    (
        "RPN-8000005",
        "ai_pc_resource_webui_v2",
        "/home/svend/ai-pc-resource-webui",
        "wrapper-confirmation-gates",
        "Wrapper Confirmation Gates",
        "wrapper-confirmation-gates",
        "safety_panel",
        "selected_pending_source_validation",
        "Safety gates are required before exposing operational controls.",
        5,
        1,
        1,
    ),
]

for panel in reusable_panel_selections_data:
    cursor.execute("""
        INSERT OR REPLACE INTO reusable_panel_selections
        (reusable_panel_id, target_project_key, source_project_path,
         panel_key, panel_title, source_html_id, source_panel_kind,
         selection_status, selection_reason, migration_priority,
         is_required, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, panel)

# Create webui_project_skeletons table
cursor.execute("""
CREATE TABLE IF NOT EXISTS webui_project_skeletons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skeleton_id TEXT UNIQUE NOT NULL,
    target_project_key TEXT NOT NULL,
    target_project_path TEXT NOT NULL,
    target_port INTEGER NOT NULL,
    skeleton_status TEXT NOT NULL,
    created_files_json TEXT NOT NULL,
    server_start_command TEXT,
    health_endpoint TEXT NOT NULL,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Seed webui_project_skeletons data (no DELETE — upsert style)
webui_project_skeletons_data = [
    (
        "WSK-9000001",
        "ai_pc_resource_webui_v2",
        "/home/svend/ai-pc-resource-webui-v2",
        9121,
        "created",
        '["app.py","requirements.txt","README.md","templates/index.html","static/css/app.css","static/js/app.js","databases/.gitkeep"]',
        "cd /home/svend/ai-pc-resource-webui-v2 && source venv/bin/activate && uvicorn app:app --host 0.0.0.0 --port 9121",
        "/api/health",
        "Skeleton only. No server started and no panels implemented in Phase 2C. Selected panel requirements must be clarified with the user before panel code is generated.",
        1,
    ),
]

for skeleton in webui_project_skeletons_data:
    cursor.execute("""
        INSERT OR REPLACE INTO webui_project_skeletons
        (skeleton_id, target_project_key, target_project_path,
         target_port, skeleton_status, created_files_json,
         server_start_command, health_endpoint, notes, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, skeleton)

cursor.execute("""
CREATE TABLE IF NOT EXISTS architecture_decision_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adr_id TEXT UNIQUE NOT NULL,
    adr_key TEXT UNIQUE NOT NULL,
    adr_title TEXT NOT NULL,
    decision_status TEXT NOT NULL,
    decision_context TEXT NOT NULL,
    decision_text TEXT NOT NULL,
    consequences TEXT,
    related_phase_key TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Seed baseline architecture_decision_records data
adr_data = [
    (
        "ADR-6000001",
        "new_webui_version_not_full_refactor",
        "Build a new clean AI PC Resource WebUI version instead of fully refactoring the existing one",
        "accepted",
        "Existing AI PC Resource WebUI is useful as a source/reference but has grown large and hard to restructure safely.",
        "Build a new WebUI version on a different port and carve out only the few needed panels/elements from the existing project.",
        "Keeps the current system stable while allowing a cleaner database-driven architecture.",
        "1X",
    ),
    (
        "ADR-6000002",
        "database_driven_frontend_layout",
        "Use database-driven frontend layout definitions",
        "accepted",
        "Hardcoded frontend layout becomes difficult for Claude Code to modify safely as the project grows.",
        "Store layout slots, panels, labels, endpoint references, and bootstrap datasets in SQLite-backed registries.",
        "Makes generated WebUIs more predictable, inspectable, and easier to seed from scripts.",
        "1O",
    ),
    (
        "ADR-6000003",
        "linux_first_platform_adapter_design",
        "Use Linux-first implementation with future platform adapters",
        "accepted",
        "The current target machine is Linux, but the architecture should not hardcode platform behavior into frontend or data structures.",
        "Implement Linux-first backend checks now, but keep platform-specific behavior behind backend adapters or action bindings.",
        "Avoids premature heavy cross-platform abstractions while reducing future Linux lock-in.",
        "1X",
    ),
    (
        "ADR-6000004",
        "repeatable_seed_scripts_source_of_truth",
        "Use repeatable seed scripts as the source of truth for bootstrap data",
        "accepted",
        "A database-driven generated WebUI requires seed data before it can run.",
        "Keep scripts/init_db.py as the source of truth for required bootstrap datasets, with the SQLite database as a generated/runtime artifact.",
        "New WebUI instances can be initialized reproducibly.",
        "1W",
    ),
]

# Safely insert or update architecture_decision_records data (no DELETE)
for adr in adr_data:
    cursor.execute("""
        INSERT OR REPLACE INTO architecture_decision_records
        (adr_id, adr_key, adr_title, decision_status, decision_context, decision_text, consequences, related_phase_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, adr)

# Create v2_panel_requirements table
cursor.execute("""
CREATE TABLE IF NOT EXISTS v2_panel_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requirement_id TEXT UNIQUE NOT NULL,
    target_project_key TEXT NOT NULL,
    panel_key TEXT NOT NULL,
    panel_title TEXT NOT NULL,
    card_key TEXT NOT NULL,
    card_title TEXT NOT NULL,
    card_type TEXT NOT NULL,
    display_order INTEGER NOT NULL,
    source_reference TEXT,
    required_data_json TEXT NOT NULL,
    visual_requirements_json TEXT NOT NULL,
    behavior_requirements_json TEXT NOT NULL,
    implementation_status TEXT NOT NULL,
    is_required INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Seed v2_panel_requirements data (no DELETE — upsert style)
v2_panel_requirements_data = [
    # VPR-1000001: CUDA0 - RTX5090 (gpu_gauge)
    (
        "VPR-1000001",
        "ai_pc_resource_webui_v2",
        "system_resources",
        "System Resources",
        "cuda0_rtx5090",
        "CUDA0 - RTX5090",
        "gpu_gauge",
        1,
        "/home/svend/ai-pc-resource-webui System Resources CUDA0 card",
        json.dumps({
            "data_source": "/api/status",
            "json_collection": "gpus",
            "match_field": "index",
            "match_values": ["0"],
            "fields": ["index", "name", "memory_used_mb", "memory_total_mb", "memory_free_mb", "utilization_percent"],
            "display_fields": ["memory_used_mb", "memory_total_mb"],
            "label": "VRAM used",
        }),
        json.dumps({
            "dark_dashboard_style": True,
            "system_resources_section_heading": True,
            "card_grid_layout": True,
            "dark_rounded_cards": True,
            "subtle_border": True,
            "white_card_titles": True,
            "gpu_cards_use_gauge_speedometer_style": True,
            "preserve_current_visual_appearance": True,
        }),
        json.dumps({
            "read_only": True,
            "no_wrappers": True,
            "no_confirmation_gate_required": True,
            "no_post_actions": True,
            "refresh_interval_seconds": 30,
            "exact_display_order": True,
            "omitted_cards": ["RAM", "/", "/home/svend/HermesOutput", "/home/svend/ComfyUI", "/home/svend/ComfyUI-LTX23"],
        }),
        "specified",
        1,
        1,
    ),
    # VPR-1000002: CUDA1 - RTX3060 (gpu_gauge)
    (
        "VPR-1000002",
        "ai_pc_resource_webui_v2",
        "system_resources",
        "System Resources",
        "cuda1_rtx3060",
        "CUDA1 - RTX3060",
        "gpu_gauge",
        2,
        "/home/svend/ai-pc-resource-webui System Resources CUDA1 card",
        json.dumps({
            "data_source": "/api/status",
            "json_collection": "gpus",
            "match_field": "index",
            "match_values": ["1"],
            "fields": ["index", "name", "memory_used_mb", "memory_total_mb", "memory_free_mb", "utilization_percent"],
            "display_fields": ["memory_used_mb", "memory_total_mb"],
            "label": "VRAM used",
        }),
        json.dumps({
            "dark_dashboard_style": True,
            "system_resources_section_heading": True,
            "card_grid_layout": True,
            "dark_rounded_cards": True,
            "subtle_border": True,
            "white_card_titles": True,
            "gpu_cards_use_gauge_speedometer_style": True,
            "preserve_current_visual_appearance": True,
        }),
        json.dumps({
            "read_only": True,
            "no_wrappers": True,
            "no_confirmation_gate_required": True,
            "no_post_actions": True,
            "refresh_interval_seconds": 30,
            "exact_display_order": True,
            "omitted_cards": ["RAM", "/", "/home/svend/HermesOutput", "/home/svend/ComfyUI", "/home/svend/ComfyUI-LTX23"],
        }),
        "specified",
        1,
        1,
    ),
    # VPR-1000003: /home/svend (disk_usage)
    (
        "VPR-1000003",
        "ai_pc_resource_webui_v2",
        "system_resources",
        "System Resources",
        "home_svend_disk",
        "/home/svend",
        "disk_usage",
        3,
        "/home/svend/ai-pc-resource-webui System Resources /home/svend disk card",
        json.dumps({
            "data_source": "/api/status",
            "json_collection": "storage",
            "match_field": "path",
            "match_values": ["/home/svend"],
            "fields": ["path", "size", "used", "available", "use_percent"],
            "display_rows": ["Size", "Used", "Free", "Use"],
        }),
        json.dumps({
            "dark_dashboard_style": True,
            "system_resources_section_heading": True,
            "card_grid_layout": True,
            "dark_rounded_cards": True,
            "subtle_border": True,
            "white_card_titles": True,
            "disk_cards_use_text_rows": True,
            "preserve_current_visual_appearance": True,
        }),
        json.dumps({
            "read_only": True,
            "no_wrappers": True,
            "no_confirmation_gate_required": True,
            "no_post_actions": True,
            "refresh_interval_seconds": 30,
            "exact_display_order": True,
            "omitted_cards": ["RAM", "/", "/home/svend/HermesOutput", "/home/svend/ComfyUI", "/home/svend/ComfyUI-LTX23"],
        }),
        "specified",
        1,
        1,
    ),
    # VPR-1000004: /home/svend/ai-data (disk_usage)
    (
        "VPR-1000004",
        "ai_pc_resource_webui_v2",
        "system_resources",
        "System Resources",
        "ai_data_disk",
        "/home/svend/ai-data",
        "disk_usage",
        4,
        "/home/svend/ai-pc-resource-webui System Resources /home/svend/ai-data disk card",
        json.dumps({
            "data_source": "/api/status",
            "json_collection": "storage",
            "match_field": "path",
            "match_values": ["/home/svend/ai-data"],
            "fields": ["path", "size", "used", "available", "use_percent"],
            "display_rows": ["Size", "Used", "Free", "Use"],
        }),
        json.dumps({
            "dark_dashboard_style": True,
            "system_resources_section_heading": True,
            "card_grid_layout": True,
            "dark_rounded_cards": True,
            "subtle_border": True,
            "white_card_titles": True,
            "disk_cards_use_text_rows": True,
            "preserve_current_visual_appearance": True,
        }),
        json.dumps({
            "read_only": True,
            "no_wrappers": True,
            "no_confirmation_gate_required": True,
            "no_post_actions": True,
            "refresh_interval_seconds": 30,
            "exact_display_order": True,
            "omitted_cards": ["RAM", "/", "/home/svend/HermesOutput", "/home/svend/ComfyUI", "/home/svend/ComfyUI-LTX23"],
        }),
        "specified",
        1,
        1,
    ),
    # VPR-1000005: Tailscale (tailscale_status)
    (
        "VPR-1000005",
        "ai_pc_resource_webui_v2",
        "system_resources",
        "System Resources",
        "tailscale",
        "Tailscale",
        "tailscale_status",
        5,
        "/home/svend/ai-pc-resource-webui System Resources Tailscale card",
        json.dumps({
            "data_source": "/api/status",
            "json_object": "tailscale",
            "fields": ["installed", "ip"],
            "display_rows": ["Installed", "IP"],
        }),
        json.dumps({
            "dark_dashboard_style": True,
            "system_resources_section_heading": True,
            "card_grid_layout": True,
            "dark_rounded_cards": True,
            "subtle_border": True,
            "white_card_titles": True,
            "tailscale_card_uses_text_rows": True,
            "preserve_current_visual_appearance": True,
        }),
        json.dumps({
            "read_only": True,
            "no_wrappers": True,
            "no_confirmation_gate_required": True,
            "no_post_actions": True,
            "refresh_interval_seconds": 30,
            "exact_display_order": True,
            "omitted_cards": ["RAM", "/", "/home/svend/HermesOutput", "/home/svend/ComfyUI", "/home/svend/ComfyUI-LTX23"],
        }),
        "specified",
        1,
        1,
    ),
    # VPR-1000011: Instagram Kanban Pipeline (pipeline_status)
    (
        "VPR-1000011",
        "ai_pc_resource_webui_v2",
        "pipeline_status",
        "Pipeline Status",
        "instagram_kanban_pipeline",
        "Instagram Kanban Pipeline",
        "pipeline_status",
        1,
        "v1 pipeline_inventory pipeline instagram_kanban_pipeline",
        json.dumps({
            "data_source": "/api/status or later v2 pipeline status endpoint",
            "source_collection": "pipeline_inventory",
            "display_sections": ["required_services", "warnings"],
            "omitted_sections": ["status_badge", "missing"],
            "remove_status_badge": True,
            "required_services_rule": {
                "show_expected_service_types": True,
                "show_actual_running_state": True,
                "show_check_or_cross_markers": True,
                "order_must_be_explicit": True,
                "consider_restore_order": True,
                "consider_stop_order": True,
            },
            "warnings_rule": {
                "show_only_heavy_process_warnings": True,
                "include_cuda_device": True,
                "cuda_device_values": ["CUDA0", "CUDA1"],
                "source_should_be_gpu_process_analysis": True,
                "sort_order": "ascending",
            },
            "card_frame_status": {
                "green_when_all_required_services_running": True,
                "normal_or_warning_frame_when_not_ready": True,
            },
        }),
        json.dumps({
            "dark_dashboard_style": True,
            "section_heading": "Pipeline Status",
            "card_grid_layout": True,
            "dark_rounded_cards": True,
            "subtle_border": True,
            "white_card_titles": True,
            "remove_red_yellow_green_badge_text": True,
            "green_frame_when_all_required_services_running": True,
            "display_only_required_services_and_warnings": True,
            "preserve_useful_existing_visual_style_as_much_as_practical": True,
        }),
        json.dumps({
            "read_only": True,
            "no_post_actions": True,
            "action_controls_belong_to_pipeline_action_mapping": True,
            "do_not_use_frontend_object_key_order": True,
            "sort_cards_by_display_order": True,
            "claude_code_pipeline_must_be_backend_driven_later": True,
            "rename_claude_code_project_agent_to_claude_code_pipeline": True,
            "ollama_model_display_must_be_generic": True,
            "do_not_hardcode_qwen_3_coder_128k_as_only_valid_model_text": True,
            "display_ollama_model_loaded_state": [
                "ollama model not loaded",
                "ollama model loaded: qwen model",
                "ollama model loaded: other ollama model",
            ],
            "telegram_gate_or_monitored_session_relevant_for_claude_code": True,
            "future_pipeline_action_mapping_same_card_order": True,
            "future_pipeline_action_mapping_same_number_of_cards": True,
        }),
        "specified",
        1,
        1,
    ),
    # VPR-1000012: Hermes Research Pipeline (pipeline_status)
    (
        "VPR-1000012",
        "ai_pc_resource_webui_v2",
        "pipeline_status",
        "Pipeline Status",
        "hermes_research_pipeline",
        "Hermes Research Pipeline",
        "pipeline_status",
        2,
        "v1 pipeline_inventory pipeline hermes_research_pipeline",
        json.dumps({
            "data_source": "/api/status or later v2 pipeline status endpoint",
            "source_collection": "pipeline_inventory",
            "display_sections": ["required_services", "warnings"],
            "omitted_sections": ["status_badge", "missing"],
            "remove_status_badge": True,
            "required_services_rule": {
                "show_expected_service_types": True,
                "show_actual_running_state": True,
                "show_check_or_cross_markers": True,
                "order_must_be_explicit": True,
                "consider_restore_order": True,
                "consider_stop_order": True,
            },
            "warnings_rule": {
                "show_only_heavy_process_warnings": True,
                "include_cuda_device": True,
                "cuda_device_values": ["CUDA0", "CUDA1"],
                "source_should_be_gpu_process_analysis": True,
                "sort_order": "ascending",
            },
            "card_frame_status": {
                "green_when_all_required_services_running": True,
                "normal_or_warning_frame_when_not_ready": True,
            },
        }),
        json.dumps({
            "dark_dashboard_style": True,
            "section_heading": "Pipeline Status",
            "card_grid_layout": True,
            "dark_rounded_cards": True,
            "subtle_border": True,
            "white_card_titles": True,
            "remove_red_yellow_green_badge_text": True,
            "green_frame_when_all_required_services_running": True,
            "display_only_required_services_and_warnings": True,
            "preserve_useful_existing_visual_style_as_much_as_practical": True,
        }),
        json.dumps({
            "read_only": True,
            "no_post_actions": True,
            "action_controls_belong_to_pipeline_action_mapping": True,
            "do_not_use_frontend_object_key_order": True,
            "sort_cards_by_display_order": True,
            "claude_code_pipeline_must_be_backend_driven_later": True,
            "rename_claude_code_project_agent_to_claude_code_pipeline": True,
            "ollama_model_display_must_be_generic": True,
            "do_not_hardcode_qwen_3_coder_128k_as_only_valid_model_text": True,
            "display_ollama_model_loaded_state": [
                "ollama model not loaded",
                "ollama model loaded: qwen model",
                "ollama model loaded: other ollama model",
            ],
            "telegram_gate_or_monitored_session_relevant_for_claude_code": True,
            "future_pipeline_action_mapping_same_card_order": True,
            "future_pipeline_action_mapping_same_number_of_cards": True,
        }),
        "specified",
        1,
        1,
    ),
    # VPR-1000013: Claude Code Pipeline (pipeline_status)
    (
        "VPR-1000013",
        "ai_pc_resource_webui_v2",
        "pipeline_status",
        "Pipeline Status",
        "claude_code_pipeline",
        "Claude Code Pipeline",
        "pipeline_status",
        3,
        "v1 hardcoded Claude Code Project Agent card; rename to Claude Code Pipeline and make backend-driven later",
        json.dumps({
            "data_source": "/api/status or later v2 pipeline status endpoint",
            "source_collection": "pipeline_inventory",
            "display_sections": ["required_services", "warnings"],
            "omitted_sections": ["status_badge", "missing"],
            "remove_status_badge": True,
            "required_services_rule": {
                "show_expected_service_types": True,
                "show_actual_running_state": True,
                "show_check_or_cross_markers": True,
                "order_must_be_explicit": True,
                "consider_restore_order": True,
                "consider_stop_order": True,
            },
            "warnings_rule": {
                "show_only_heavy_process_warnings": True,
                "include_cuda_device": True,
                "cuda_device_values": ["CUDA0", "CUDA1"],
                "source_should_be_gpu_process_analysis": True,
                "sort_order": "ascending",
            },
            "card_frame_status": {
                "green_when_all_required_services_running": True,
                "normal_or_warning_frame_when_not_ready": True,
            },
        }),
        json.dumps({
            "dark_dashboard_style": True,
            "section_heading": "Pipeline Status",
            "card_grid_layout": True,
            "dark_rounded_cards": True,
            "subtle_border": True,
            "white_card_titles": True,
            "remove_red_yellow_green_badge_text": True,
            "green_frame_when_all_required_services_running": True,
            "display_only_required_services_and_warnings": True,
            "preserve_useful_existing_visual_style_as_much_as_practical": True,
        }),
        json.dumps({
            "read_only": True,
            "no_post_actions": True,
            "action_controls_belong_to_pipeline_action_mapping": True,
            "do_not_use_frontend_object_key_order": True,
            "sort_cards_by_display_order": True,
            "claude_code_pipeline_must_be_backend_driven_later": True,
            "rename_claude_code_project_agent_to_claude_code_pipeline": True,
            "ollama_model_display_must_be_generic": True,
            "do_not_hardcode_qwen_3_coder_128k_as_only_valid_model_text": True,
            "display_ollama_model_loaded_state": [
                "ollama model not loaded",
                "ollama model loaded: qwen model",
                "ollama model loaded: other ollama model",
            ],
            "telegram_gate_or_monitored_session_relevant_for_claude_code": True,
            "future_pipeline_action_mapping_same_card_order": True,
            "future_pipeline_action_mapping_same_number_of_cards": True,
        }),
        "specified",
        1,
        1,
    ),
    # VPR-1000014: AI Toolkit Training Pipeline (pipeline_status)
    (
        "VPR-1000014",
        "ai_pc_resource_webui_v2",
        "pipeline_status",
        "Pipeline Status",
        "ai_toolkit_training_pipeline",
        "AI Toolkit Training Pipeline",
        "pipeline_status",
        4,
        "v1 pipeline_inventory pipeline ai_toolkit_training_pipeline",
        json.dumps({
            "data_source": "/api/status or later v2 pipeline status endpoint",
            "source_collection": "pipeline_inventory",
            "display_sections": ["required_services", "warnings"],
            "omitted_sections": ["status_badge", "missing"],
            "remove_status_badge": True,
            "required_services_rule": {
                "show_expected_service_types": True,
                "show_actual_running_state": True,
                "show_check_or_cross_markers": True,
                "order_must_be_explicit": True,
                "consider_restore_order": True,
                "consider_stop_order": True,
            },
            "warnings_rule": {
                "show_only_heavy_process_warnings": True,
                "include_cuda_device": True,
                "cuda_device_values": ["CUDA0", "CUDA1"],
                "source_should_be_gpu_process_analysis": True,
                "sort_order": "ascending",
            },
            "card_frame_status": {
                "green_when_all_required_services_running": True,
                "normal_or_warning_frame_when_not_ready": True,
            },
        }),
        json.dumps({
            "dark_dashboard_style": True,
            "section_heading": "Pipeline Status",
            "card_grid_layout": True,
            "dark_rounded_cards": True,
            "subtle_border": True,
            "white_card_titles": True,
            "remove_red_yellow_green_badge_text": True,
            "green_frame_when_all_required_services_running": True,
            "display_only_required_services_and_warnings": True,
            "preserve_useful_existing_visual_style_as_much_as_practical": True,
        }),
        json.dumps({
            "read_only": True,
            "no_post_actions": True,
            "action_controls_belong_to_pipeline_action_mapping": True,
            "do_not_use_frontend_object_key_order": True,
            "sort_cards_by_display_order": True,
            "claude_code_pipeline_must_be_backend_driven_later": True,
            "rename_claude_code_project_agent_to_claude_code_pipeline": True,
            "ollama_model_display_must_be_generic": True,
            "do_not_hardcode_qwen_3_coder_128k_as_only_valid_model_text": True,
            "display_ollama_model_loaded_state": [
                "ollama model not loaded",
                "ollama model loaded: qwen model",
                "ollama model loaded: other ollama model",
            ],
            "telegram_gate_or_monitored_session_relevant_for_claude_code": True,
            "future_pipeline_action_mapping_same_card_order": True,
            "future_pipeline_action_mapping_same_number_of_cards": True,
        }),
        "specified",
        1,
        1,
    ),
    # VPR-1000015: ComfyUI CUDA0 Pipeline (pipeline_status)
    (
        "VPR-1000015",
        "ai_pc_resource_webui_v2",
        "pipeline_status",
        "Pipeline Status",
        "comfyui_cuda0_pipeline",
        "ComfyUI CUDA0 Pipeline",
        "pipeline_status",
        5,
        "v1 pipeline_inventory pipeline main_comfyui_cuda0_pipeline",
        json.dumps({
            "data_source": "/api/status or later v2 pipeline status endpoint",
            "source_collection": "pipeline_inventory",
            "display_sections": ["required_services", "warnings"],
            "omitted_sections": ["status_badge", "missing"],
            "remove_status_badge": True,
            "required_services_rule": {
                "show_expected_service_types": True,
                "show_actual_running_state": True,
                "show_check_or_cross_markers": True,
                "order_must_be_explicit": True,
                "consider_restore_order": True,
                "consider_stop_order": True,
            },
            "warnings_rule": {
                "show_only_heavy_process_warnings": True,
                "include_cuda_device": True,
                "cuda_device_values": ["CUDA0", "CUDA1"],
                "source_should_be_gpu_process_analysis": True,
                "sort_order": "ascending",
            },
            "card_frame_status": {
                "green_when_all_required_services_running": True,
                "normal_or_warning_frame_when_not_ready": True,
            },
        }),
        json.dumps({
            "dark_dashboard_style": True,
            "section_heading": "Pipeline Status",
            "card_grid_layout": True,
            "dark_rounded_cards": True,
            "subtle_border": True,
            "white_card_titles": True,
            "remove_red_yellow_green_badge_text": True,
            "green_frame_when_all_required_services_running": True,
            "display_only_required_services_and_warnings": True,
            "preserve_useful_existing_visual_style_as_much_as_practical": True,
        }),
        json.dumps({
            "read_only": True,
            "no_post_actions": True,
            "action_controls_belong_to_pipeline_action_mapping": True,
            "do_not_use_frontend_object_key_order": True,
            "sort_cards_by_display_order": True,
            "claude_code_pipeline_must_be_backend_driven_later": True,
            "rename_claude_code_project_agent_to_claude_code_pipeline": True,
            "ollama_model_display_must_be_generic": True,
            "do_not_hardcode_qwen_3_coder_128k_as_only_valid_model_text": True,
            "display_ollama_model_loaded_state": [
                "ollama model not loaded",
                "ollama model loaded: qwen model",
                "ollama model loaded: other ollama model",
            ],
            "telegram_gate_or_monitored_session_relevant_for_claude_code": True,
            "future_pipeline_action_mapping_same_card_order": True,
            "future_pipeline_action_mapping_same_number_of_cards": True,
        }),
        "specified",
        1,
        1,
    ),
    # VPR-1000016: ComfyUI-LTX23 CUDA0 Pipeline (pipeline_status)
    (
        "VPR-1000016",
        "ai_pc_resource_webui_v2",
        "pipeline_status",
        "Pipeline Status",
        "comfyui_ltx23_cuda0_pipeline",
        "ComfyUI-LTX23 CUDA0 Pipeline",
        "pipeline_status",
        6,
        "v1 pipeline_inventory pipeline ltx23_cuda0_pipeline",
        json.dumps({
            "data_source": "/api/status or later v2 pipeline status endpoint",
            "source_collection": "pipeline_inventory",
            "display_sections": ["required_services", "warnings"],
            "omitted_sections": ["status_badge", "missing"],
            "remove_status_badge": True,
            "required_services_rule": {
                "show_expected_service_types": True,
                "show_actual_running_state": True,
                "show_check_or_cross_markers": True,
                "order_must_be_explicit": True,
                "consider_restore_order": True,
                "consider_stop_order": True,
            },
            "warnings_rule": {
                "show_only_heavy_process_warnings": True,
                "include_cuda_device": True,
                "cuda_device_values": ["CUDA0", "CUDA1"],
                "source_should_be_gpu_process_analysis": True,
                "sort_order": "ascending",
            },
            "card_frame_status": {
                "green_when_all_required_services_running": True,
                "normal_or_warning_frame_when_not_ready": True,
            },
        }),
        json.dumps({
            "dark_dashboard_style": True,
            "section_heading": "Pipeline Status",
            "card_grid_layout": True,
            "dark_rounded_cards": True,
            "subtle_border": True,
            "white_card_titles": True,
            "remove_red_yellow_green_badge_text": True,
            "green_frame_when_all_required_services_running": True,
            "display_only_required_services_and_warnings": True,
            "preserve_useful_existing_visual_style_as_much_as_practical": True,
        }),
        json.dumps({
            "read_only": True,
            "no_post_actions": True,
            "action_controls_belong_to_pipeline_action_mapping": True,
            "do_not_use_frontend_object_key_order": True,
            "sort_cards_by_display_order": True,
            "claude_code_pipeline_must_be_backend_driven_later": True,
            "rename_claude_code_project_agent_to_claude_code_pipeline": True,
            "ollama_model_display_must_be_generic": True,
            "do_not_hardcode_qwen_3_coder_128k_as_only_valid_model_text": True,
            "display_ollama_model_loaded_state": [
                "ollama model not loaded",
                "ollama model loaded: qwen model",
                "ollama model loaded: other ollama model",
            ],
            "telegram_gate_or_monitored_session_relevant_for_claude_code": True,
            "future_pipeline_action_mapping_same_card_order": True,
            "future_pipeline_action_mapping_same_number_of_cards": True,
        }),
        "specified",
        1,
        1,
    ),
]

for req in v2_panel_requirements_data:
    cursor.execute("""
        INSERT OR REPLACE INTO v2_panel_requirements
        (requirement_id, target_project_key, panel_key, panel_title,
         card_key, card_title, card_type, display_order, source_reference,
         required_data_json, visual_requirements_json, behavior_requirements_json,
         implementation_status, is_required, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, req)

# Commit changes and close connection
conn.commit()
conn.close()

print("Database initialized successfully!")