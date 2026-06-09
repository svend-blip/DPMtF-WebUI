import sqlite3
import os

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
phase_data = [
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
    ("1X", "Architecture Decision Record in Frontend Roadmap", "Document architecture decisions", "next", 23),
    ("2A", "New AI PC Resource WebUI Migration Target", "Create new AI PC WebUI target", "planned", 24),
    ("2B", "Select 4–5 Reusable AI PC Panels", "Select reusable panels", "planned", 25),
    ("2C", "Create New AI PC WebUI Project Skeleton on New Port", "Create project skeleton", "planned", 26),
    ("2D", "Migrate Selected Panels into Database-driven Layout", "Migrate panels to DB layout", "planned", 27),
    ("2E", "Wire Selected Endpoints and Status Checks", "Connect endpoints", "planned", 28),
    ("2F", "Validate New AI PC WebUI as Replacement Candidate", "Validate replacement", "planned", 29),
    ("2G", "Prompt Run Review", "Manual review form", "planned", 30),
    ("2H", "Hitrate Scoring", "Score prompt effectiveness", "planned", 31),
    ("2I", "Implementation Pattern Manager", "Manage implementation patterns", "planned", 32),
    ("2J", "Prompt Template Manager", "Manage prompt templates", "planned", 33),
    ("2K", "Local Prompt Compiler", "Compile prompts locally", "planned", 34),
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
]

# Safely insert or update bootstrap_dataset_registry data (no DELETE)
for dataset in bootstrap_dataset_data:
    cursor.execute("""
        INSERT OR REPLACE INTO bootstrap_dataset_registry
        (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, dataset)

# Create architecture_decision_records table
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

# Commit changes and close connection
conn.commit()
conn.close()

print("Database initialized successfully!")