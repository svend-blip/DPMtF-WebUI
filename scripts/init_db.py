import sqlite3
import os
import json
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

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
    ("2F", "Hitrate Scoring", "Database tables for prompt success/failure tracking: prompt_runs, prompt_hitrates. API endpoints for hitrate queries.", "completed", 29),
    ("2F-bis", "Frontend i18n + Dark Theme Refactoring", "Skeleton HTML (46 lines), 0 dynamic innerHTML, dark dashboard theme, 54 lbl() i18n calls, four-layer i18n architecture.", "completed", 30),
    ("2G", "Implementation Pattern Manager", "Capture successful implementation patterns from completed phases. Table: implementation_patterns. Pattern extraction from phase reports.", "next", 31),
    ("2H", "Prompt Template Manager", "Migrate static Markdown templates to database-driven parametrisable templates. Table: prompt_templates with variable fields.", "planned", 32),
    ("2I", "Local Prompt Compiler", "Generate prompts from templates + hitrate data + governance context. Assembles project-specific prompts without cloud dependency.", "planned", 33),
    # ── Blok 5: Automatisering (2J-2L) ──
    ("2J", "Validation Automation", "Database-driven validation: validation_rules, validation_runs, validation_results tables. /api/validate endpoint runs all relevant rules.", "planned", 34),
    ("2K", "Git Sync Management", "Database-driven git tracking: git_sync_status, git_operations tables. /api/git/status and /api/git/push endpoints.", "planned", 35),
    ("2L", "Platform Adapter Framework", "PlatformAdapter base class for Linux/Windows abstraction. Linux implementation. Windows stub. Service actions get platform field.", "planned", 36),
    # ── Blok 6: Lokal model integration (2M-2O) ──
    ("2M", "Local Claude Code Session Manager", "Start/stop/monitor local Claude Code session via Ollama. Session status tracking in database.", "planned", 37),
    ("2N", "Prompt→Implementer→Validator loop", "DPMtF generates prompt → local Claude Code session implements → auto-validation runs → hitrate updated. Full closed loop.", "next", 38),
    ("2O", "Parallel-kørsel test", "Same prompt executed in cloud (Claude Code) and local model. Results compared for hitrate ground-truth calibration.", "planned", 39),
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

# ── Phase 2F-bis: i18n four-layer architecture ─────────────────────
# Layer 1: ui_text_slots — stable frontend text placement IDs
cursor.execute("""
CREATE TABLE IF NOT EXISTS ui_text_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Layer 2: ui_text_slot_labels — binds slots to labels
cursor.execute("""
CREATE TABLE IF NOT EXISTS ui_text_slot_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key TEXT NOT NULL,
    label_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(slot_key, label_key)
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

# Seed baseline ui_labels data (existing + 45 new for 2F-bis)
ui_labels_data = [
    # Existing system_setup labels
    ("LBL-1000001", "system_setup.title", "system_setup", "System Setup", "Title for the system setup section"),
    ("LBL-1000002", "system_setup.layout_slots.title", "system_setup", "Layout Slots", "Title for the layout slots section"),
    ("LBL-1000003", "system_setup.database_layout_preview.title", "system_setup", "Database Layout Preview", "Title for the database layout preview section"),
    ("LBL-1000004", "system_setup.database_layout_preview.description", "system_setup", "Read-only preview from /api/frontend-layout", "Description for the database layout preview section"),
    ("LBL-1000005", "system_setup.database_layout_preview.refresh", "system_setup", "Refresh", "Label for the refresh button in database layout preview"),
    ("LBL-1000006", "phase_status.show_completed", "main", "Show completed phases", "Toggle label to show/hide completed phases"),
    # ── 2F-bis: Main layout labels ──
    ("LBL-1000007", "lbl_page_title", "main", "DPMtF WebUI", "Page title"),
    ("LBL-1000008", "lbl_heading_main", "main", "Deterministic Prompt – MockUp to Finalised", "Main heading"),
    ("LBL-1000009", "lbl_panel_db_status", "main", "Database Status", "Database Status panel heading"),
    ("LBL-1000010", "lbl_panel_phase_status", "main", "Phase Status", "Phase Status panel heading"),
    ("LBL-1000011", "lbl_panel_hitrates", "main", "Prompt Hitrates", "Prompt Hitrates panel heading"),
    ("LBL-1000012", "lbl_panel_prompt_sequences", "main", "Prompt Sequence Planner", "Prompt Sequence Planner panel heading"),
    ("LBL-1000013", "lbl_panel_project_planning", "main", "New Project Planning", "New Project Planning panel heading"),
    ("LBL-1000014", "lbl_btn_system_setup", "main", "System Setup", "System Setup button"),
    ("LBL-1000015", "lbl_btn_refresh", "main", "Refresh", "Refresh button"),
    ("LBL-1000016", "lbl_btn_create", "main", "Create", "Create button"),
    ("LBL-1000017", "lbl_btn_add_step", "main", "Add Step", "Add Step button"),
    ("LBL-1000018", "lbl_btn_generate_prompt", "main", "Generate Next Prompt Preview", "Generate Next Prompt Preview button"),
    ("LBL-1000019", "lbl_btn_copy_prompt", "main", "Copy Prompt", "Copy Prompt button"),
    ("LBL-1000020", "lbl_btn_save_prompt", "main", "Save Generated Prompt", "Save Generated Prompt button"),
    ("LBL-1000021", "lbl_btn_create_project_plan", "main", "Create Project Plan", "Create Project Plan button"),
    ("LBL-1000022", "lbl_btn_close_drawer", "main", "Close", "Close drawer button"),
    # ── 2F-bis: Status labels ──
    ("LBL-1000023", "lbl_status_loading", "main", "Loading...", "Loading indicator"),
    ("LBL-1000024", "lbl_status_no_data", "main", "No data available.", "No data message"),
    ("LBL-1000025", "lbl_status_error_prefix", "main", "Error: ", "Error message prefix"),
    ("LBL-1000026", "lbl_status_success", "main", "Success", "Success status"),
    ("LBL-1000027", "lbl_status_failed", "main", "Failed", "Failed status"),
    ("LBL-1000028", "lbl_status_planned", "main", "Planned", "Planned phase status"),
    ("LBL-1000029", "lbl_status_completed", "main", "Completed", "Completed phase status"),
    ("LBL-1000030", "lbl_status_next", "main", "Next", "Next phase status"),
    # ── 2F-bis: Prompt Sequence labels ──
    ("LBL-1000031", "lbl_sequence_count", "main", "Sequences", "Sequence count label"),
    ("LBL-1000032", "lbl_step_count", "main", "Steps", "Step count label"),
    ("LBL-1000033", "lbl_sequences", "main", "Sequences", "Sequences label"),
    ("LBL-1000034", "lbl_steps", "main", "Steps", "Steps label"),
    ("LBL-1000035", "lbl_select_sequence", "main", "Select a sequence...", "Select sequence prompt"),
    ("LBL-1000036", "lbl_empty_sequences", "main", "No prompt sequences yet. Create the first sequence to begin planning small Claude Code prompts.", "Empty sequences message"),
    ("LBL-1000037", "lbl_empty_steps", "main", "No steps yet. Add steps to the sequence to generate prompts.", "Empty steps message"),
    ("LBL-1000038", "lbl_prompt_preview", "main", "Generate Next Prompt Preview", "Prompt preview heading"),
    ("LBL-1000039", "lbl_prompt_history", "main", "Prompt History / Generated Archive", "Prompt history heading"),
    ("LBL-1000040", "lbl_no_prompts_yet", "main", "No generated prompts yet. Generate and save prompts to see them appear here.", "No prompts message"),
    # ── 2F-bis: Project Planning labels ──
    ("LBL-1000041", "lbl_project_name", "main", "Project Name", "Project name field"),
    ("LBL-1000042", "lbl_target_folder", "main", "Target Folder", "Target folder field"),
    ("LBL-1000043", "lbl_app_port", "main", "App Port", "App port field"),
    ("LBL-1000044", "lbl_app_profile", "main", "App Profile", "App profile field"),
    ("LBL-1000045", "lbl_prompt_sequence_select", "main", "Prompt Sequence", "Prompt sequence selector"),
    ("LBL-1000046", "lbl_notes", "main", "Notes", "Notes field"),
    # ── 2F-bis: Drawer section labels ──
    ("LBL-1000047", "lbl_drawer_layout_slots", "main", "Layout Slots", "Layout Slots drawer section"),
    ("LBL-1000048", "lbl_drawer_db_layout", "main", "Database Layout Preview", "Database Layout Preview drawer section"),
    ("LBL-1000049", "lbl_drawer_i18n", "main", "UI Labels / i18n", "UI Labels / i18n drawer section"),
    ("LBL-1000050", "lbl_drawer_endpoint_registry", "main", "Endpoint Registry", "Endpoint Registry drawer section"),
    ("LBL-1000051", "lbl_drawer_bootstrap", "main", "Bootstrap Dataset", "Bootstrap Dataset drawer section"),
    ("LBL-1000052", "lbl_drawer_security", "main", "Security / Permissions", "Security / Permissions drawer section"),
    # ── 2H: Template Manager i18n ──
    ("LBL-1000053", "lbl_tpl_templates", "main", "Templates", "Template Manager section heading"),
    ("LBL-1000054", "lbl_tpl_key", "main", "Key", "Template key column header"),
    ("LBL-1000055", "lbl_tpl_name", "main", "Name", "Template name column header"),
    ("LBL-1000056", "lbl_tpl_tier", "main", "Tier", "Complexity tier column header"),
    ("LBL-1000057", "lbl_tpl_suitable_for", "main", "Suitable For", "Suitable for column header"),
    ("LBL-1000058", "lbl_tpl_capture", "main", "Capture", "Capture source column header"),
    ("LBL-1000059", "lbl_tpl_local_sr", "main", "Local SR", "Local success rate column header"),
    ("LBL-1000060", "lbl_tpl_cloud_sr", "main", "Cloud SR", "Cloud success rate column header"),
    ("LBL-1000061", "lbl_tpl_tokens", "main", "Tokens (in/out)", "Token estimates column header"),
    ("LBL-1000062", "lbl_tpl_preview", "main", "Preview", "Preview column header"),
    ("LBL-1000063", "lbl_tpl_click_to_view", "main", "Click to view", "Click to view placeholder"),
    ("LBL-1000064", "lbl_tpl_model_hitrates", "main", "Model Hitrates", "Model hitrates section heading"),
    ("LBL-1000065", "lbl_tpl_compile_prompt", "main", "Compile Prompt", "Compile prompt button/section"),
    ("LBL-1000066", "lbl_tpl_project_path", "main", "Project Path:", "Project path input label"),
    ("LBL-1000067", "lbl_tpl_phase_id", "main", "Phase ID:", "Phase ID input label"),
    ("LBL-1000068", "lbl_tpl_goal", "main", "Goal:", "Goal input label"),
    ("LBL-1000069", "lbl_tpl_constraints", "main", "Constraints (one per line):", "Constraints textarea label"),
    ("LBL-1000070", "lbl_tpl_allowed_files", "main", "Allowed files (one per line):", "Allowed files textarea label"),
    ("LBL-1000071", "lbl_tpl_validation_cmds", "main", "Validation commands (one per line):", "Validation commands textarea label"),
    ("LBL-1000072", "lbl_tpl_estimated_tokens", "main", "Estimated tokens:", "Estimated tokens label"),
    ("LBL-1000073", "lbl_tpl_local_sr_label", "main", "Local SR:", "Local success rate label"),
    ("LBL-1000074", "lbl_tpl_cloud_sr_label", "main", "Cloud SR:", "Cloud success rate label"),
    ("LBL-1000075", "lbl_tpl_runs_count", "main", "runs", "Runs count suffix"),
    # ── 2I-v2: Compiler Fields — section labels ────────────────────
    ("LBL-1000200", "lbl_section_human_resp", "main", "Human Responsibility", "Compiler form section header"),
    ("LBL-1000201", "lbl_section_project", "main", "Project", "Compiler form project section header"),
    ("LBL-1000202", "lbl_section_scope", "main", "Scope", "Compiler form scope section header"),
    ("LBL-1000203", "lbl_section_migration", "main", "Migration", "Compiler form migration section header"),
    ("LBL-1000204", "lbl_section_validation", "main", "Validation", "Compiler form validation section header"),
    ("LBL-1000205", "lbl_compile_validation_errors", "main", "Validation Errors", "Compiler validation errors heading"),
    ("LBL-1000206", "lbl_status_compiling", "main", "Compiling...", "Compile button loading state"),
    ("LBL-1000207", "lbl_tpl_compiled_prompt", "main", "Compiled Prompt", "Compiler output heading"),
    # ── 2H: Model Hitrates table ──
    ("LBL-1000076", "lbl_col_model", "main", "Model", "Model column header"),
    ("LBL-1000077", "lbl_col_runs", "main", "Runs", "Runs column header"),
    ("LBL-1000078", "lbl_col_success_rate", "main", "Success Rate", "Success rate column header"),
    ("LBL-1000079", "lbl_col_avg_duration", "main", "Avg Duration", "Average duration column header"),
    # ── 2H: Prompt Runs extended columns ──
    ("LBL-1000080", "lbl_col_status", "main", "Status", "Execution status column header"),
    ("LBL-1000081", "lbl_col_first_try", "main", "1st-Try", "First-try success column header"),
    ("LBL-1000082", "lbl_col_corrections", "main", "Corr", "Manual corrections column header"),
    # ── 2H: Hitrate table headers (pre-existing, now i18n) ──
    ("LBL-1000083", "lbl_col_phase", "main", "Phase", "Phase column header"),
    ("LBL-1000084", "lbl_col_successful_total", "main", "Successful / Total", "Successful/Total column header"),
    ("LBL-1000085", "lbl_col_last_run", "main", "Last Run", "Last run column header"),
    ("LBL-1000086", "lbl_pat_heading", "main", "Implementation Patterns", "Implementation Patterns section heading"),
    ("LBL-1000087", "lbl_runs_heading", "main", "Recent Prompt Runs", "Recent Prompt Runs section heading"),
    # ── 2H: Runs table pre-existing columns (now i18n) ──
    ("LBL-1000088", "lbl_col_run_id", "main", "Run ID", "Run ID column header"),
    ("LBL-1000089", "lbl_col_project", "main", "Project", "Project column header"),
    ("LBL-1000090", "lbl_col_duration", "main", "Duration", "Duration column header"),
    ("LBL-1000091", "lbl_col_cost", "main", "Cost", "Cost column header"),
    ("LBL-1000092", "lbl_col_timestamp", "main", "Timestamp", "Timestamp column header"),
    # ── 2H: Pattern table columns ──
    ("LBL-1000093", "lbl_col_pattern_id", "main", "Pattern ID", "Pattern ID column header"),
    ("LBL-1000094", "lbl_col_files", "main", "Files", "Files column header"),
    ("LBL-1000095", "lbl_col_constraints", "main", "Constraints", "Constraints column header"),
    ("LBL-1000096", "lbl_col_best_model", "main", "Best Model", "Best model column header"),
    ("LBL-1000097", "lbl_col_avg_dur", "main", "Avg Dur", "Average duration column header"),
    # ── 2H: Validation results table ──
    ("LBL-1000098", "lbl_col_rule", "main", "Rule", "Rule column header"),
    ("LBL-1000099", "lbl_col_result", "main", "Result", "Result column header"),
    ("LBL-1000100", "lbl_col_notes", "main", "Notes", "Notes column header"),
    ("LBL-1000101", "lbl_val_running", "main", "Running validation...", "Validation running status"),
    ("LBL-1000102", "lbl_val_no_rules", "main", "No validation rules.", "No validation rules message"),
    # ── Panel group headings ──
    ("LBL-1000103", "pg_daily", "main", "📆 Daily", "Daily panel group heading"),
    ("LBL-1000104", "pg_journals", "main", "📓 Journals", "Journals panel group heading"),
    ("LBL-1000105", "pg_reports", "main", "📊 Reports", "Reports panel group heading"),
    ("LBL-1000106", "pg_periodic", "main", "🔄 Periodic", "Periodic panel group heading"),
    ("LBL-1000107", "pg_setup", "main", "⚙️ Setup", "Setup panel group heading"),
    ("LBL-1000108", "lbl_panel_templates", "main", "Prompt Templates", "Prompt Templates panel heading"),
    # ── 2O-b: Comparison Runs (7 labels) ──
    ("LBL-1000109", "lbl_drawer_comparisons", "main", "Comparison Runs", "Comparison Runs drawer panel heading"),
    ("LBL-1000110", "lbl_cmp_id", "main", "ID", "Comparison ID column header"),
    ("LBL-1000111", "lbl_cmp_task", "main", "Task", "Comparison task type column header"),
    ("LBL-1000112", "lbl_cmp_tier", "main", "Tier", "Comparison complexity tier column header"),
    ("LBL-1000113", "lbl_cmp_cloud", "main", "Cloud", "Comparison cloud model column header"),
    ("LBL-1000114", "lbl_cmp_local", "main", "Local", "Comparison local model column header"),
    ("LBL-1000115", "lbl_cmp_winner", "main", "Winner", "Comparison winner column header"),
    # ── 2P: Prompt Compiler v2 — target_session labels (handoff 021) ──
    ("LBL-1000208", "lbl_target_session", "template_manager", "Target tmux Session", "Prompt compiler target session field label"),
    ("LBL-1000209", "lbl_target_session_implementor", "template_manager", "Implementor — code execution (claude_implementer)", "target_session option: claude_implementer"),
    ("LBL-1000210", "lbl_target_session_architect", "template_manager", "Architect — design & analysis (claude_architect)", "target_session option: claude_architect"),
    ("LBL-1000211", "lbl_target_session_review", "template_manager", "Review — validation & coordination (claude_review)", "target_session option: claude_review"),
    # ── Prompt Compiler Hardening: handoff ID assignment (handoff 017) ──
    ("LBL-1000212", "lbl_btn_assign_handoff_id", "template_manager", "Assign Handoff ID", "Button to assign a real handoff ID to a compiled prompt"),
    ("LBL-1000213", "lbl_status_assigning_id", "template_manager", "Assigning handoff ID...", "Loading state for handoff ID assignment"),
    ("LBL-1000214", "lbl_handoff_ready", "template_manager", "Handoff {ID} ready", "Success message when handoff file is written"),
    ("LBL-1000215", "lbl_handoff_file_written", "template_manager", "File written:", "Label preceding the handoff file path"),
    ("LBL-1000216", "lbl_dispatch_command", "template_manager", "Dispatch command:", "Label preceding the dispatch shell command"),
    ("LBL-1000217", "lbl_btn_copy_command", "template_manager", "Copy Command", "Button to copy dispatch command to clipboard"),
    # ── Accelerated WebUI Factory labels (2026-06-18) ──
    ("LBL-1000218", "lbl_compiler_new_webui_name", "template_manager", "New webui", "Accelerated: new webui name field"),
    ("LBL-1000219", "lbl_compiler_new_webui_port", "template_manager", "Port", "Accelerated: port number field"),
    ("LBL-1000220", "lbl_compiler_new_webui_title", "template_manager", "Title", "Accelerated: project title field"),
    ("LBL-1000221", "lbl_compiler_create_webui_btn", "template_manager", "Create New WebUI", "Accelerated: create button"),
    ("LBL-1000222", "lbl_compiler_start_server_btn", "template_manager", "Start WebUI Server", "Accelerated: start server button"),
    ("LBL-1000223", "lbl_compiler_webui_created", "template_manager", "WebUI project created successfully", "Accelerated: success message"),
    ("LBL-1000224", "lbl_compiler_governance_reminder", "template_manager", "Governance files to create in docs/dpmtf/:", "Accelerated: governance reminder"),
    ("LBL-1000225", "lbl_compiler_open_webui", "template_manager", "Open WebUI", "Accelerated: open webui link text"),
    ("LBL-1000226", "lbl_compiler_script_error", "template_manager", "Script error", "Accelerated: script error heading"),
    ("LBL-1000227", "lbl_compiler_field_required", "template_manager", "This field is required", "Accelerated: field required message"),
    # ── BridgeV002 Compiler Integration (B4, 2026-06-22) ──
    ("LBL-1000228", "lbl_compiler_flow_key", "template_manager", "Flow Key", "BridgeV002: select flow for dispatch"),
    ("LBL-1000229", "lbl_compiler_step_key", "template_manager", "Step Key", "BridgeV002: select step for dispatch"),
]

# Safely insert or update ui_labels data (no DELETE)
for label in ui_labels_data:
    cursor.execute("""
        INSERT OR REPLACE INTO ui_labels
        (label_id, label_key, label_domain, default_text, description)
        VALUES (?, ?, ?, ?, ?)
    """, label)

# Seed translations (en-US + da-DK) for all labels
ui_label_translations_data = [
    # Existing en-US
    ("LBL-1000001", "en-US", "System Setup"),
    ("LBL-1000002", "en-US", "Layout Slots"),
    ("LBL-1000003", "en-US", "Database Layout Preview"),
    ("LBL-1000004", "en-US", "Read-only preview from /api/frontend-layout"),
    ("LBL-1000005", "en-US", "Refresh"),
    ("LBL-1000006", "en-US", "Show completed phases"),
    # Existing da-DK
    ("LBL-1000001", "da-DK", "System Opsætning"),
    ("LBL-1000002", "da-DK", "Layout Slots"),
    ("LBL-1000003", "da-DK", "Database Layout Preview"),
    ("LBL-1000004", "da-DK", "Read-only preview fra /api/frontend-layout"),
    ("LBL-1000005", "da-DK", "Opdatér"),
    ("LBL-1000006", "da-DK", "Vis fuldførte faser"),
    # ── 2F-bis: Main layout (en-US + da-DK) ──
    ("LBL-1000007", "en-US", "DPMtF WebUI"),
    ("LBL-1000007", "da-DK", "DPMtF WebUI"),
    ("LBL-1000008", "en-US", "Deterministic Prompt – MockUp to Finalised"),
    ("LBL-1000008", "da-DK", "Deterministisk Prompt — MockUp til Finaliseret"),
    ("LBL-1000009", "en-US", "Database Status"),
    ("LBL-1000009", "da-DK", "Database Status"),
    ("LBL-1000010", "en-US", "Phase Status"),
    ("LBL-1000010", "da-DK", "Fase Status"),
    ("LBL-1000011", "en-US", "Prompt Hitrates"),
    ("LBL-1000011", "da-DK", "Prompt Hitrates"),
    ("LBL-1000012", "en-US", "Prompt Sequence Planner"),
    ("LBL-1000012", "da-DK", "Prompt Sekvens Planlægger"),
    ("LBL-1000013", "en-US", "New Project Planning"),
    ("LBL-1000013", "da-DK", "Nyt Projekt Planlægning"),
    ("LBL-1000014", "en-US", "System Setup"),
    ("LBL-1000014", "da-DK", "System Opsætning"),
    ("LBL-1000015", "en-US", "Refresh"),
    ("LBL-1000015", "da-DK", "Opdatér"),
    ("LBL-1000016", "en-US", "Create"),
    ("LBL-1000016", "da-DK", "Opret"),
    ("LBL-1000017", "en-US", "Add Step"),
    ("LBL-1000017", "da-DK", "Tilføj Trin"),
    ("LBL-1000018", "en-US", "Generate Next Prompt Preview"),
    ("LBL-1000018", "da-DK", "Generér Næste Prompt Preview"),
    ("LBL-1000019", "en-US", "Copy Prompt"),
    ("LBL-1000019", "da-DK", "Kopiér Prompt"),
    ("LBL-1000020", "en-US", "Save Generated Prompt"),
    ("LBL-1000020", "da-DK", "Gem Genereret Prompt"),
    ("LBL-1000021", "en-US", "Create Project Plan"),
    ("LBL-1000021", "da-DK", "Opret Projekt Plan"),
    ("LBL-1000022", "en-US", "Close"),
    ("LBL-1000022", "da-DK", "Luk"),
    # ── 2F-bis: Status (en-US + da-DK) ──
    ("LBL-1000023", "en-US", "Loading..."),
    ("LBL-1000023", "da-DK", "Indlæser..."),
    ("LBL-1000024", "en-US", "No data available."),
    ("LBL-1000024", "da-DK", "Ingen data tilgængelig."),
    ("LBL-1000025", "en-US", "Error: "),
    ("LBL-1000025", "da-DK", "Fejl: "),
    ("LBL-1000026", "en-US", "Success"),
    ("LBL-1000026", "da-DK", "Gennemført"),
    ("LBL-1000027", "en-US", "Failed"),
    ("LBL-1000027", "da-DK", "Fejlet"),
    ("LBL-1000028", "en-US", "Planned"),
    ("LBL-1000028", "da-DK", "Planlagt"),
    ("LBL-1000029", "en-US", "Completed"),
    ("LBL-1000029", "da-DK", "Færdig"),
    ("LBL-1000030", "en-US", "Next"),
    ("LBL-1000030", "da-DK", "Næste"),
    # ── 2F-bis: Prompt Sequences (en-US + da-DK) ──
    ("LBL-1000031", "en-US", "Sequences"),
    ("LBL-1000031", "da-DK", "Sekvenser"),
    ("LBL-1000032", "en-US", "Steps"),
    ("LBL-1000032", "da-DK", "Trin"),
    ("LBL-1000033", "en-US", "Sequences"),
    ("LBL-1000033", "da-DK", "Sekvenser"),
    ("LBL-1000034", "en-US", "Steps"),
    ("LBL-1000034", "da-DK", "Trin"),
    ("LBL-1000035", "en-US", "Select a sequence..."),
    ("LBL-1000035", "da-DK", "Vælg en sekvens..."),
    ("LBL-1000036", "en-US", "No prompt sequences yet. Create the first sequence to begin planning small Claude Code prompts."),
    ("LBL-1000036", "da-DK", "Ingen prompt sekvenser endnu. Opret den første sekvens for at begynde at planlægge små Claude Code prompts."),
    ("LBL-1000037", "en-US", "No steps yet. Add steps to the sequence to generate prompts."),
    ("LBL-1000037", "da-DK", "Ingen trin endnu. Tilføj trin til sekvensen for at generere prompts."),
    ("LBL-1000038", "en-US", "Generate Next Prompt Preview"),
    ("LBL-1000038", "da-DK", "Generér Næste Prompt Preview"),
    ("LBL-1000039", "en-US", "Prompt History / Generated Archive"),
    ("LBL-1000039", "da-DK", "Prompt Historik / Genereret Arkiv"),
    ("LBL-1000040", "en-US", "No generated prompts yet. Generate and save prompts to see them appear here."),
    ("LBL-1000040", "da-DK", "Ingen genererede prompts endnu. Generér og gem prompts for at se dem her."),
    # ── 2F-bis: Project Planning (en-US + da-DK) ──
    ("LBL-1000041", "en-US", "Project Name"),
    ("LBL-1000041", "da-DK", "Projekt Navn"),
    ("LBL-1000042", "en-US", "Target Folder"),
    ("LBL-1000042", "da-DK", "Mål Mappe"),
    ("LBL-1000043", "en-US", "App Port"),
    ("LBL-1000043", "da-DK", "App Port"),
    ("LBL-1000044", "en-US", "App Profile"),
    ("LBL-1000044", "da-DK", "App Profil"),
    ("LBL-1000045", "en-US", "Prompt Sequence"),
    ("LBL-1000045", "da-DK", "Prompt Sekvens"),
    ("LBL-1000046", "en-US", "Notes"),
    ("LBL-1000046", "da-DK", "Noter"),
    # ── 2F-bis: Drawer (en-US + da-DK) ──
    ("LBL-1000047", "en-US", "Layout Slots"),
    ("LBL-1000047", "da-DK", "Layout Slots"),
    ("LBL-1000048", "en-US", "Database Layout Preview"),
    ("LBL-1000048", "da-DK", "Database Layout Preview"),
    ("LBL-1000049", "en-US", "UI Labels / i18n"),
    ("LBL-1000049", "da-DK", "UI Labels / i18n"),
    ("LBL-1000050", "en-US", "Endpoint Registry"),
    ("LBL-1000050", "da-DK", "Endpoint Registry"),
    ("LBL-1000051", "en-US", "Bootstrap Dataset"),
    ("LBL-1000051", "da-DK", "Bootstrap Dataset"),
    ("LBL-1000052", "en-US", "Security / Permissions"),
    ("LBL-1000052", "da-DK", "Sikkerhed / Rettigheder"),
    # ── 2H: Template Manager i18n ──
    ("LBL-1000053", "en-US", "Templates"),
    ("LBL-1000053", "da-DK", "Skabeloner"),
    ("LBL-1000054", "en-US", "Key"),
    ("LBL-1000054", "da-DK", "Nøgle"),
    ("LBL-1000055", "en-US", "Name"),
    ("LBL-1000055", "da-DK", "Navn"),
    ("LBL-1000056", "en-US", "Tier"),
    ("LBL-1000056", "da-DK", "Niveau"),
    ("LBL-1000057", "en-US", "Suitable For"),
    ("LBL-1000057", "da-DK", "Egnet til"),
    ("LBL-1000058", "en-US", "Capture"),
    ("LBL-1000058", "da-DK", "Kilde"),
    ("LBL-1000059", "en-US", "Local SR"),
    ("LBL-1000059", "da-DK", "Lokal SR"),
    ("LBL-1000060", "en-US", "Cloud SR"),
    ("LBL-1000060", "da-DK", "Cloud SR"),
    ("LBL-1000061", "en-US", "Tokens (in/out)"),
    ("LBL-1000061", "da-DK", "Tokens (ind/ud)"),
    ("LBL-1000062", "en-US", "Preview"),
    ("LBL-1000062", "da-DK", "Forhåndsvisning"),
    ("LBL-1000063", "en-US", "Click to view"),
    ("LBL-1000063", "da-DK", "Klik for at se"),
    ("LBL-1000064", "en-US", "Model Hitrates"),
    ("LBL-1000064", "da-DK", "Model Hitrates"),
    ("LBL-1000065", "en-US", "Compile Prompt"),
    ("LBL-1000065", "da-DK", "Kompilér Prompt"),
    ("LBL-1000066", "en-US", "Project Path:"),
    ("LBL-1000066", "da-DK", "Projekt Sti:"),
    ("LBL-1000067", "en-US", "Phase ID:"),
    ("LBL-1000067", "da-DK", "Fase ID:"),
    ("LBL-1000068", "en-US", "Goal:"),
    ("LBL-1000068", "da-DK", "Mål:"),
    ("LBL-1000069", "en-US", "Constraints (one per line):"),
    ("LBL-1000069", "da-DK", "Begrænsninger (én per linje):"),
    ("LBL-1000070", "en-US", "Allowed files (one per line):"),
    ("LBL-1000070", "da-DK", "Tilladte filer (én per linje):"),
    ("LBL-1000071", "en-US", "Validation commands (one per line):"),
    ("LBL-1000071", "da-DK", "Valideringskommandoer (én per linje):"),
    ("LBL-1000072", "en-US", "Estimated tokens:"),
    ("LBL-1000072", "da-DK", "Estimerede tokens:"),
    ("LBL-1000073", "en-US", "Local SR:"),
    ("LBL-1000073", "da-DK", "Lokal SR:"),
    ("LBL-1000074", "en-US", "Cloud SR:"),
    ("LBL-1000074", "da-DK", "Cloud SR:"),
    ("LBL-1000075", "en-US", "runs"),
    ("LBL-1000075", "da-DK", "kørsler"),
    # ── 2H: Model Hitrates table ──
    ("LBL-1000076", "en-US", "Model"),
    ("LBL-1000076", "da-DK", "Model"),
    ("LBL-1000077", "en-US", "Runs"),
    ("LBL-1000077", "da-DK", "Kørsler"),
    ("LBL-1000078", "en-US", "Success Rate"),
    ("LBL-1000078", "da-DK", "Successrate"),
    ("LBL-1000079", "en-US", "Avg Duration"),
    ("LBL-1000079", "da-DK", "Gns. Varighed"),
    # ── 2H: Prompt Runs extended columns ──
    ("LBL-1000080", "en-US", "Status"),
    ("LBL-1000080", "da-DK", "Status"),
    ("LBL-1000081", "en-US", "1st-Try"),
    ("LBL-1000081", "da-DK", "1. Forsøg"),
    ("LBL-1000082", "en-US", "Corr"),
    ("LBL-1000082", "da-DK", "Korr"),
    # ── 2H: Hitrate table headers ──
    ("LBL-1000083", "en-US", "Phase"),
    ("LBL-1000083", "da-DK", "Fase"),
    ("LBL-1000084", "en-US", "Successful / Total"),
    ("LBL-1000084", "da-DK", "Succes / Total"),
    ("LBL-1000085", "en-US", "Last Run"),
    ("LBL-1000085", "da-DK", "Seneste Kørsel"),
    ("LBL-1000086", "en-US", "Implementation Patterns"),
    ("LBL-1000086", "da-DK", "Implementeringsmønstre"),
    ("LBL-1000087", "en-US", "Recent Prompt Runs"),
    ("LBL-1000087", "da-DK", "Seneste Prompt Kørsler"),
    # ── 2H: Runs table columns ──
    ("LBL-1000088", "en-US", "Run ID"),
    ("LBL-1000088", "da-DK", "Kørsel ID"),
    ("LBL-1000089", "en-US", "Project"),
    ("LBL-1000089", "da-DK", "Projekt"),
    ("LBL-1000090", "en-US", "Duration"),
    ("LBL-1000090", "da-DK", "Varighed"),
    ("LBL-1000091", "en-US", "Cost"),
    ("LBL-1000091", "da-DK", "Omkostning"),
    ("LBL-1000092", "en-US", "Timestamp"),
    ("LBL-1000092", "da-DK", "Tidsstempel"),
    # ── 2H: Pattern table columns ──
    ("LBL-1000093", "en-US", "Pattern ID"),
    ("LBL-1000093", "da-DK", "Mønster ID"),
    ("LBL-1000094", "en-US", "Files"),
    ("LBL-1000094", "da-DK", "Filer"),
    ("LBL-1000095", "en-US", "Constraints"),
    ("LBL-1000095", "da-DK", "Begrænsninger"),
    ("LBL-1000096", "en-US", "Best Model"),
    ("LBL-1000096", "da-DK", "Bedste Model"),
    ("LBL-1000097", "en-US", "Avg Dur"),
    ("LBL-1000097", "da-DK", "Gns. Varighed"),
    # ── 2H: Validation results table ──
    ("LBL-1000098", "en-US", "Rule"),
    ("LBL-1000098", "da-DK", "Regel"),
    ("LBL-1000099", "en-US", "Result"),
    ("LBL-1000099", "da-DK", "Resultat"),
    ("LBL-1000100", "en-US", "Notes"),
    ("LBL-1000100", "da-DK", "Noter"),
    ("LBL-1000101", "en-US", "Running validation..."),
    ("LBL-1000101", "da-DK", "Kører validering..."),
    ("LBL-1000102", "en-US", "No validation rules."),
    ("LBL-1000102", "da-DK", "Ingen valideringsregler."),
    # ── Panel group headings ──
    ("LBL-1000103", "en-US", "📆 Daily"),
    ("LBL-1000103", "da-DK", "📆 Daglig"),
    ("LBL-1000104", "en-US", "📓 Journals"),
    ("LBL-1000104", "da-DK", "📓 Journaler"),
    ("LBL-1000105", "en-US", "📊 Reports"),
    ("LBL-1000105", "da-DK", "📊 Rapporter"),
    ("LBL-1000106", "en-US", "🔄 Periodic"),
    ("LBL-1000106", "da-DK", "🔄 Periodisk"),
    ("LBL-1000107", "en-US", "⚙️ Setup"),
    ("LBL-1000107", "da-DK", "⚙️ Opsætning"),
    ("LBL-1000108", "en-US", "Prompt Templates"),
    ("LBL-1000108", "da-DK", "Prompt Skabeloner"),
    # ── 2O-b: Comparison Runs (en-US + da-DK) ──
    ("LBL-1000109", "en-US", "Comparison Runs"),
    ("LBL-1000109", "da-DK", "Sammenligninger"),
    ("LBL-1000110", "en-US", "ID"),
    ("LBL-1000110", "da-DK", "ID"),
    ("LBL-1000111", "en-US", "Task"),
    ("LBL-1000111", "da-DK", "Opgave"),
    ("LBL-1000112", "en-US", "Tier"),
    ("LBL-1000112", "da-DK", "Niveau"),
    ("LBL-1000113", "en-US", "Cloud"),
    ("LBL-1000113", "da-DK", "Cloud"),
    ("LBL-1000114", "en-US", "Local"),
    ("LBL-1000114", "da-DK", "Lokal"),
    ("LBL-1000115", "en-US", "Winner"),
    ("LBL-1000115", "da-DK", "Vinder"),
    # ── de-DE: Tyske oversættelser ──
    ("LBL-1000001", "de-DE", "Systemeinstellung"),
    ("LBL-1000002", "de-DE", "Layout-Slots"),
    ("LBL-1000003", "de-DE", "Datenbank-Layout-Vorschau"),
    ("LBL-1000004", "de-DE", "Schreibgeschützte Vorschau von /api/frontend-layout"),
    ("LBL-1000005", "de-DE", "Aktualisieren"),
    ("LBL-1000006", "de-DE", "Abgeschlossene Phasen anzeigen"),
    ("LBL-1000007", "de-DE", "DPMtF WebUI"),
    ("LBL-1000008", "de-DE", "Deterministischer Prompt — Von Mockup bis Finalisiert"),
    ("LBL-1000009", "de-DE", "Datenbankstatus"),
    ("LBL-1000010", "de-DE", "Phasenstatus"),
    ("LBL-1000011", "de-DE", "Prompt-Trefferquoten"),
    ("LBL-1000012", "de-DE", "Prompt-Sequenzplaner"),
    ("LBL-1000013", "de-DE", "Neue Projektplanung"),
    ("LBL-1000014", "de-DE", "Systemeinstellung"),
    ("LBL-1000015", "de-DE", "Aktualisieren"),
    ("LBL-1000016", "de-DE", "Erstellen"),
    ("LBL-1000017", "de-DE", "Schritt hinzufügen"),
    ("LBL-1000018", "de-DE", "Nächsten Prompt-Vorschau generieren"),
    ("LBL-1000019", "de-DE", "Prompt kopieren"),
    ("LBL-1000020", "de-DE", "Generierten Prompt speichern"),
    ("LBL-1000021", "de-DE", "Projektplan erstellen"),
    ("LBL-1000022", "de-DE", "Schließen"),
    ("LBL-1000023", "de-DE", "Laden..."),
    ("LBL-1000024", "de-DE", "Keine Daten verfügbar."),
    ("LBL-1000025", "de-DE", "Fehler: "),
    ("LBL-1000026", "de-DE", "Erfolgreich"),
    ("LBL-1000027", "de-DE", "Fehlgeschlagen"),
    ("LBL-1000028", "de-DE", "Geplant"),
    ("LBL-1000029", "de-DE", "Abgeschlossen"),
    ("LBL-1000030", "de-DE", "Nächste"),
    ("LBL-1000031", "de-DE", "Sequenzen"),
    ("LBL-1000032", "de-DE", "Schritte"),
    ("LBL-1000033", "de-DE", "Sequenzen"),
    ("LBL-1000034", "de-DE", "Schritte"),
    ("LBL-1000035", "de-DE", "Sequenz auswählen..."),
    ("LBL-1000036", "de-DE", "Noch keine Prompt-Sequenzen. Erstellen Sie die erste Sequenz, um mit der Planung kleiner Claude Code-Prompts zu beginnen."),
    ("LBL-1000037", "de-DE", "Noch keine Schritte. Fügen Sie der Sequenz Schritte hinzu, um Prompts zu generieren."),
    ("LBL-1000038", "de-DE", "Nächsten Prompt-Vorschau generieren"),
    ("LBL-1000039", "de-DE", "Prompt-Verlauf / Generiertes Archiv"),
    ("LBL-1000040", "de-DE", "Noch keine generierten Prompts. Generieren und speichern Sie Prompts, um sie hier zu sehen."),
    ("LBL-1000041", "de-DE", "Projektname"),
    ("LBL-1000042", "de-DE", "Zielordner"),
    ("LBL-1000043", "de-DE", "App-Port"),
    ("LBL-1000044", "de-DE", "App-Profil"),
    ("LBL-1000045", "de-DE", "Prompt-Sequenz"),
    ("LBL-1000046", "de-DE", "Notizen"),
    ("LBL-1000047", "de-DE", "Layout-Slots"),
    ("LBL-1000048", "de-DE", "Datenbank-Layout-Vorschau"),
    ("LBL-1000049", "de-DE", "UI-Labels / i18n"),
    ("LBL-1000050", "de-DE", "Endpunkt-Register"),
    ("LBL-1000051", "de-DE", "Bootstrap-Datensatz"),
    ("LBL-1000052", "de-DE", "Sicherheit / Berechtigungen"),
    ("LBL-1000053", "de-DE", "Vorlagen"),
    ("LBL-1000054", "de-DE", "Schlüssel"),
    ("LBL-1000055", "de-DE", "Name"),
    ("LBL-1000056", "de-DE", "Stufe"),
    ("LBL-1000057", "de-DE", "Geeignet für"),
    ("LBL-1000058", "de-DE", "Quelle"),
    ("LBL-1000059", "de-DE", "Lokale ER"),
    ("LBL-1000060", "de-DE", "Cloud-ER"),
    ("LBL-1000061", "de-DE", "Tokens (ein/aus)"),
    ("LBL-1000062", "de-DE", "Vorschau"),
    ("LBL-1000063", "de-DE", "Klicken zum Anzeigen"),
    ("LBL-1000064", "de-DE", "Modell-Trefferquoten"),
    ("LBL-1000065", "de-DE", "Prompt kompilieren"),
    ("LBL-1000066", "de-DE", "Projekt-Pfad:"),
    ("LBL-1000067", "de-DE", "Phasen-ID:"),
    ("LBL-1000068", "de-DE", "Ziel:"),
    ("LBL-1000069", "de-DE", "Einschränkungen (je eine pro Zeile):"),
    ("LBL-1000070", "de-DE", "Erlaubte Dateien (je eine pro Zeile):"),
    ("LBL-1000071", "de-DE", "Validierungsbefehle (je einer pro Zeile):"),
    ("LBL-1000072", "de-DE", "Geschätzte Tokens:"),
    ("LBL-1000073", "de-DE", "Lokale ER:"),
    ("LBL-1000074", "de-DE", "Cloud-ER:"),
    ("LBL-1000075", "de-DE", "Ausführungen"),
    ("LBL-1000076", "de-DE", "Modell"),
    ("LBL-1000077", "de-DE", "Ausführungen"),
    ("LBL-1000078", "de-DE", "Erfolgsrate"),
    ("LBL-1000079", "de-DE", "Durchschn. Dauer"),
    ("LBL-1000080", "de-DE", "Status"),
    ("LBL-1000081", "de-DE", "1. Versuch"),
    ("LBL-1000082", "de-DE", "Korr."),
    ("LBL-1000083", "de-DE", "Phase"),
    ("LBL-1000084", "de-DE", "Erfolge / Gesamt"),
    ("LBL-1000085", "de-DE", "Letzte Ausführung"),
    ("LBL-1000086", "de-DE", "Implementierungsmuster"),
    ("LBL-1000087", "de-DE", "Aktuelle Prompt-Ausführungen"),
    ("LBL-1000088", "de-DE", "Ausführungs-ID"),
    ("LBL-1000089", "de-DE", "Projekt"),
    ("LBL-1000090", "de-DE", "Dauer"),
    ("LBL-1000091", "de-DE", "Kosten"),
    ("LBL-1000092", "de-DE", "Zeitstempel"),
    ("LBL-1000093", "de-DE", "Muster-ID"),
    ("LBL-1000094", "de-DE", "Dateien"),
    ("LBL-1000095", "de-DE", "Einschränkungen"),
    ("LBL-1000096", "de-DE", "Bestes Modell"),
    ("LBL-1000097", "de-DE", "Durchschn. Dau."),
    ("LBL-1000098", "de-DE", "Regel"),
    ("LBL-1000099", "de-DE", "Ergebnis"),
    ("LBL-1000100", "de-DE", "Notizen"),
    ("LBL-1000101", "de-DE", "Validierung läuft..."),
    ("LBL-1000102", "de-DE", "Keine Validierungsregeln."),
    ("LBL-1000103", "de-DE", "📆 Täglich"),
    ("LBL-1000104", "de-DE", "📆 Journale"),
    ("LBL-1000105", "de-DE", "📊 Berichte"),
    ("LBL-1000106", "de-DE", "🔄 Periodisch"),
    ("LBL-1000107", "de-DE", "⚙️ Einrichtung"),
    ("LBL-1000108", "de-DE", "Prompt-Vorlagen"),
    ("LBL-1000109", "de-DE", "Vergleichsläufe"),
    ("LBL-1000110", "de-DE", "ID"),
    ("LBL-1000111", "de-DE", "Aufgabe"),
    ("LBL-1000112", "de-DE", "Stufe"),
    ("LBL-1000113", "de-DE", "Cloud"),
    ("LBL-1000114", "de-DE", "Lokal"),
    ("LBL-1000115", "de-DE", "Gewinner"),
    ("LBL-1000116", "de-DE", "Phase"),
    ("LBL-1000117", "de-DE", "Planung"),
    ("LBL-1000118", "de-DE", "Bestehende Projekte"),
    # ── sv-SE: Svenske oversættelser ──
    ("LBL-1000001", "sv-SE", "Systeminställning"),
    ("LBL-1000002", "sv-SE", "Layoutplatser"),
    ("LBL-1000003", "sv-SE", "Databaslajutförhandsgranskning"),
    ("LBL-1000004", "sv-SE", "Skritskyddad förhandsvisning från /api/frontend-layout"),
    ("LBL-1000005", "sv-SE", "Uppdatera"),
    ("LBL-1000006", "sv-SE", "Visa avslutade faser"),
    ("LBL-1000007", "sv-SE", "DPMtF WebUI"),
    ("LBL-1000008", "sv-SE", "Deterministisk Prompt — Från Mockup till Finaliserad"),
    ("LBL-1000009", "sv-SE", "Databasstatus"),
    ("LBL-1000010", "sv-SE", "Fasstatus"),
    ("LBL-1000011", "sv-SE", "Promptträffkvoter"),
    ("LBL-1000012", "sv-SE", "Promptsekvensplanerare"),
    ("LBL-1000013", "sv-SE", "Ny projektplanering"),
    ("LBL-1000014", "sv-SE", "Systeminställning"),
    ("LBL-1000015", "sv-SE", "Uppdatera"),
    ("LBL-1000016", "sv-SE", "Skapa"),
    ("LBL-1000017", "sv-SE", "Lägg till steg"),
    ("LBL-1000018", "sv-SE", "Generera nästa promptförhandsvisning"),
    ("LBL-1000019", "sv-SE", "Kopiera prompt"),
    ("LBL-1000020", "sv-SE", "Spara genererad prompt"),
    ("LBL-1000021", "sv-SE", "Skapa projektplan"),
    ("LBL-1000022", "sv-SE", "Stäng"),
    ("LBL-1000023", "sv-SE", "Laddar..."),
    ("LBL-1000024", "sv-SE", "Ingen data tillgänglig."),
    ("LBL-1000025", "sv-SE", "Fel: "),
    ("LBL-1000026", "sv-SE", "Lyckades"),
    ("LBL-1000027", "sv-SE", "Misslyckades"),
    ("LBL-1000028", "sv-SE", "Planerad"),
    ("LBL-1000029", "sv-SE", "Avslutad"),
    ("LBL-1000030", "sv-SE", "Nästa"),
    ("LBL-1000031", "sv-SE", "Sekvenser"),
    ("LBL-1000032", "sv-SE", "Steg"),
    ("LBL-1000033", "sv-SE", "Sekvenser"),
    ("LBL-1000034", "sv-SE", "Steg"),
    ("LBL-1000035", "sv-SE", "Välj en sekvens..."),
    ("LBL-1000036", "sv-SE", "Inga promptsekvenser ännu. Skapa den första sekvensen för att börja planera små Claude Code-prompts."),
    ("LBL-1000037", "sv-SE", "Inga steg ännu. Lägg till steg i sekvensen för att generera prompts."),
    ("LBL-1000038", "sv-SE", "Generera nästa promptförhandsvisning"),
    ("LBL-1000039", "sv-SE", "Prompthistorik / Genererat arkiv"),
    ("LBL-1000040", "sv-SE", "Inga genererade prompts ännu. Generera och spara prompts för att se dem här."),
    ("LBL-1000041", "sv-SE", "Projektnamn"),
    ("LBL-1000042", "sv-SE", "Målmapp"),
    ("LBL-1000043", "sv-SE", "App-port"),
    ("LBL-1000044", "sv-SE", "App-profil"),
    ("LBL-1000045", "sv-SE", "Promptsekvens"),
    ("LBL-1000046", "sv-SE", "Anteckningar"),
    ("LBL-1000047", "sv-SE", "Layoutplatser"),
    ("LBL-1000048", "sv-SE", "Databaslajutförhandsgranskning"),
    ("LBL-1000049", "sv-SE", "UI-etiketter / i18n"),
    ("LBL-1000050", "sv-SE", "Slutpunktsregister"),
    ("LBL-1000051", "sv-SE", "Bootstrapdataset"),
    ("LBL-1000052", "sv-SE", "Säkerhet / Behörigheter"),
    ("LBL-1000053", "sv-SE", "Mallar"),
    ("LBL-1000054", "sv-SE", "Nyckel"),
    ("LBL-1000055", "sv-SE", "Namn"),
    ("LBL-1000056", "sv-SE", "Nivå"),
    ("LBL-1000057", "sv-SE", "Lämplig för"),
    ("LBL-1000058", "sv-SE", "Källa"),
    ("LBL-1000059", "sv-SE", "Lokal FK"),
    ("LBL-1000060", "sv-SE", "Cloud-FK"),
    ("LBL-1000061", "sv-SE", "Tokens (in/ut)"),
    ("LBL-1000062", "sv-SE", "Förhandsvisning"),
    ("LBL-1000063", "sv-SE", "Klicka för att visa"),
    ("LBL-1000064", "sv-SE", "Modellträffkvoter"),
    ("LBL-1000065", "sv-SE", "Kompilera prompt"),
    ("LBL-1000066", "sv-SE", "Projektsökväg:"),
    ("LBL-1000067", "sv-SE", "Fas-ID:"),
    ("LBL-1000068", "sv-SE", "Mål:"),
    ("LBL-1000069", "sv-SE", "Begränsningar (en per rad):"),
    ("LBL-1000070", "sv-SE", "Tillåtna filer (en per rad):"),
    ("LBL-1000071", "sv-SE", "Valideringskommandon (ett per rad):"),
    ("LBL-1000072", "sv-SE", "Uppskattade tokens:"),
    ("LBL-1000073", "sv-SE", "Lokal FK:"),
    ("LBL-1000074", "sv-SE", "Cloud-FK:"),
    ("LBL-1000075", "sv-SE", "körningar"),
    ("LBL-1000076", "sv-SE", "Modell"),
    ("LBL-1000077", "sv-SE", "Körningar"),
    ("LBL-1000078", "sv-SE", "Lyckokvot"),
    ("LBL-1000079", "sv-SE", "Medeltid"),
    ("LBL-1000080", "sv-SE", "Status"),
    ("LBL-1000081", "sv-SE", "Försök 1"),
    ("LBL-1000082", "sv-SE", "Korr."),
    ("LBL-1000083", "sv-SE", "Fas"),
    ("LBL-1000084", "sv-SE", "Lyckade / Totalt"),
    ("LBL-1000085", "sv-SE", "Senaste körning"),
    ("LBL-1000086", "sv-SE", "Implementeringsmönster"),
    ("LBL-1000087", "sv-SE", "Senaste promptkörningar"),
    ("LBL-1000088", "sv-SE", "Körnings-ID"),
    ("LBL-1000089", "sv-SE", "Projekt"),
    ("LBL-1000090", "sv-SE", "Varaktighet"),
    ("LBL-1000091", "sv-SE", "Kostnad"),
    ("LBL-1000092", "sv-SE", "Tidstämpel"),
    ("LBL-1000093", "sv-SE", "Mönster-ID"),
    ("LBL-1000094", "sv-SE", "Filer"),
    ("LBL-1000095", "sv-SE", "Begränsningar"),
    ("LBL-1000096", "sv-SE", "Bästa modell"),
    ("LBL-1000097", "sv-SE", "Medeltid"),
    ("LBL-1000098", "sv-SE", "Regel"),
    ("LBL-1000099", "sv-SE", "Resultat"),
    ("LBL-1000100", "sv-SE", "Anteckningar"),
    ("LBL-1000101", "sv-SE", "Kör validering..."),
    ("LBL-1000102", "sv-SE", "Inga valideringsregler."),
    ("LBL-1000103", "sv-SE", "📆 Daglig"),
    ("LBL-1000104", "sv-SE", "📓 Journaler"),
    ("LBL-1000105", "sv-SE", "📊 Rapporter"),
    ("LBL-1000106", "sv-SE", "🔄 Periodisk"),
    ("LBL-1000107", "sv-SE", "⚙️ Inställning"),
    ("LBL-1000108", "sv-SE", "Promptmallar"),
    ("LBL-1000109", "sv-SE", "Jämförelsekörningar"),
    ("LBL-1000110", "sv-SE", "ID"),
    ("LBL-1000111", "sv-SE", "Uppgift"),
    ("LBL-1000112", "sv-SE", "Nivå"),
    ("LBL-1000113", "sv-SE", "Cloud"),
    ("LBL-1000114", "sv-SE", "Lokal"),
    ("LBL-1000115", "sv-SE", "Vinnare"),
    ("LBL-1000116", "sv-SE", "Fas"),
    ("LBL-1000117", "sv-SE", "Planering"),
    ("LBL-1000118", "sv-SE", "Befintliga projekt"),
    # ── 2I-v2: Compiler Fields — section labels ────────────────────
    ("LBL-1000200", "en-US", "Human Responsibility"),
    ("LBL-1000200", "da-DK", "Human Ansvar"),
    ("LBL-1000200", "de-DE", "Human-Verantwortung"),
    ("LBL-1000200", "sv-SE", "Human Ansvar"),
    ("LBL-1000201", "en-US", "Project"),
    ("LBL-1000201", "da-DK", "Projekt"),
    ("LBL-1000201", "de-DE", "Projekt"),
    ("LBL-1000201", "sv-SE", "Projekt"),
    ("LBL-1000202", "en-US", "Scope"),
    ("LBL-1000202", "da-DK", "Scope"),
    ("LBL-1000202", "de-DE", "Umfang"),
    ("LBL-1000202", "sv-SE", "Omfattning"),
    ("LBL-1000203", "en-US", "Migration"),
    ("LBL-1000203", "da-DK", "Migration"),
    ("LBL-1000203", "de-DE", "Migration"),
    ("LBL-1000203", "sv-SE", "Migration"),
    ("LBL-1000204", "en-US", "Validation"),
    ("LBL-1000204", "da-DK", "Validering"),
    ("LBL-1000204", "de-DE", "Validierung"),
    ("LBL-1000204", "sv-SE", "Validering"),
    ("LBL-1000205", "en-US", "Validation Errors"),
    ("LBL-1000205", "da-DK", "Valideringsfejl"),
    ("LBL-1000205", "de-DE", "Validierungsfehler"),
    ("LBL-1000205", "sv-SE", "Valideringsfel"),
    ("LBL-1000206", "en-US", "Compiling..."),
    ("LBL-1000206", "da-DK", "Compiler..."),
    ("LBL-1000206", "de-DE", "Kompilierung..."),
    ("LBL-1000206", "sv-SE", "Compilerar..."),
    ("LBL-1000207", "en-US", "Compiled Prompt"),
    ("LBL-1000207", "da-DK", "Kompileret Prompt"),
    ("LBL-1000207", "de-DE", "Kompilierte Eingabeaufforderung"),
    ("LBL-1000207", "sv-SE", "Compilerad prompt"),
    # ── 2P: target_role labels (handoff 015) ──
    ("LBL-1000208", "en-US", "Target tmux Session"),
    ("LBL-1000208", "da-DK", "tmux-session"),
    ("LBL-1000208", "de-DE", "Ziel-tmux-Session"),
    ("LBL-1000208", "sv-SE", "tmux-session"),
    ("LBL-1000209", "en-US", "Implementor — code execution (claude_implementer)"),
    ("LBL-1000209", "da-DK", "Implementor — kodeudførelse (claude_implementer)"),
    ("LBL-1000209", "de-DE", "Implementierer — Code-Ausführung (claude_implementer)"),
    ("LBL-1000209", "sv-SE", "Implementör — kodexekvering (claude_implementer)"),
    ("LBL-1000210", "en-US", "Architect — design & analysis (claude_architect)"),
    ("LBL-1000210", "da-DK", "Arkitekt — design & analyse (claude_architect)"),
    ("LBL-1000210", "de-DE", "Architekt — Design & Analyse (claude_architect)"),
    ("LBL-1000210", "sv-SE", "Arkitekt — design & analys (claude_architect)"),
    ("LBL-1000211", "en-US", "Review — validation & coordination (claude_review)"),
    ("LBL-1000211", "da-DK", "Review — validering & koordinering (claude_review)"),
    ("LBL-1000211", "de-DE", "Prüfung — Validierung & Koordination (claude_review)"),
    ("LBL-1000211", "sv-SE", "Granskning — validering & koordinering (claude_review)"),
    # ── handoff 017: Assign Handoff ID labels ──
    ("LBL-1000212", "en-US", "Assign Handoff ID"),
    ("LBL-1000212", "da-DK", "Tildel Handoff ID"),
    ("LBL-1000212", "de-DE", "Handoff-ID zuweisen"),
    ("LBL-1000212", "sv-SE", "Tilldela Handoff-ID"),
    ("LBL-1000213", "en-US", "Assigning handoff ID..."),
    ("LBL-1000213", "da-DK", "Tildeler handoff ID..."),
    ("LBL-1000213", "de-DE", "Weise Handoff-ID zu..."),
    ("LBL-1000213", "sv-SE", "Tilldelar handoff-ID..."),
    ("LBL-1000214", "en-US", "Handoff {ID} ready"),
    ("LBL-1000214", "da-DK", "Handoff {ID} klar"),
    ("LBL-1000214", "de-DE", "Handoff {ID} bereit"),
    ("LBL-1000214", "sv-SE", "Handoff {ID} redo"),
    ("LBL-1000215", "en-US", "File written:"),
    ("LBL-1000215", "da-DK", "Fil skrevet:"),
    ("LBL-1000215", "de-DE", "Datei geschrieben:"),
    ("LBL-1000215", "sv-SE", "Fil skriven:"),
    ("LBL-1000216", "en-US", "Dispatch command:"),
    ("LBL-1000216", "da-DK", "Dispatcherkommando:"),
    ("LBL-1000216", "de-DE", "Sendebefehl:"),
    ("LBL-1000216", "sv-SE", "Skicka-kommando:"),
    ("LBL-1000217", "en-US", "Copy Command"),
    ("LBL-1000217", "da-DK", "Kopier Kommando"),
    ("LBL-1000217", "de-DE", "Befehl kopieren"),
    ("LBL-1000217", "sv-SE", "Kopiera kommando"),
    # ── Accelerated WebUI Factory (en-US) ──
    ("LBL-1000218", "en-US", "New webui"),
    ("LBL-1000219", "en-US", "Port"),
    ("LBL-1000220", "en-US", "Title"),
    ("LBL-1000221", "en-US", "Create New WebUI"),
    ("LBL-1000222", "en-US", "Start WebUI Server"),
    ("LBL-1000223", "en-US", "WebUI project created successfully"),
    ("LBL-1000224", "en-US", "Governance files to create in docs/dpmtf/:"),
    ("LBL-1000225", "en-US", "Open WebUI"),
    ("LBL-1000226", "en-US", "Script error"),
    ("LBL-1000227", "en-US", "This field is required"),
    # ── BridgeV002 Compiler Integration (en-US) ──
    ("LBL-1000228", "en-US", "Flow Key"),
    ("LBL-1000229", "en-US", "Step Key"),
    # ── Accelerated WebUI Factory (da-DK) ──
    ("LBL-1000218", "da-DK", "Nyt webui"),
    ("LBL-1000219", "da-DK", "Port"),
    ("LBL-1000220", "da-DK", "Titel"),
    ("LBL-1000221", "da-DK", "Opret nyt WebUI"),
    ("LBL-1000222", "da-DK", "Start WebUI Server"),
    ("LBL-1000223", "da-DK", "WebUI projekt oprettet"),
    ("LBL-1000224", "da-DK", "Governance-filer der skal oprettes i docs/dpmtf/:"),
    ("LBL-1000225", "da-DK", "Åbn WebUI"),
    ("LBL-1000226", "da-DK", "Script fejl"),
    ("LBL-1000227", "da-DK", "Dette felt er påkrævet"),
    # ── BridgeV002 Compiler Integration (en-US) ──
    ("LBL-1000228", "da-DK", "Flow-nøgle"),
    ("LBL-1000229", "da-DK", "Trin-nøgle"),
]

# Safely insert or update ui_label_translations data (no DELETE)
for translation in ui_label_translations_data:
    cursor.execute("""
        INSERT OR REPLACE INTO ui_label_translations
        (label_id, locale, translated_text)
        VALUES (?, ?, ?)
    """, translation)

# ── 2F-bis: Seed ui_text_slots ──
ui_text_slots_data = [
    ("lbl_page_title", "Page title"),
    ("lbl_heading_main", "Main heading"),
    ("lbl_panel_db_status", "Database Status panel heading"),
    ("lbl_panel_phase_status", "Phase Status panel heading"),
    ("lbl_panel_hitrates", "Prompt Hitrates panel heading"),
    ("lbl_panel_prompt_sequences", "Prompt Sequence Planner panel heading"),
    ("lbl_panel_project_planning", "New Project Planning panel heading"),
    ("lbl_btn_system_setup", "System Setup button"),
    ("lbl_btn_refresh", "Refresh button"),
    ("lbl_btn_create", "Create button"),
    ("lbl_btn_add_step", "Add Step button"),
    ("lbl_btn_generate_prompt", "Generate Next Prompt Preview button"),
    ("lbl_btn_copy_prompt", "Copy Prompt button"),
    ("lbl_btn_save_prompt", "Save Generated Prompt button"),
    ("lbl_btn_create_project_plan", "Create Project Plan button"),
    ("lbl_btn_close_drawer", "Close drawer button"),
    ("lbl_status_loading", "Loading indicator"),
    ("lbl_status_no_data", "No data message"),
    ("lbl_status_error_prefix", "Error message prefix"),
    ("lbl_status_success", "Success status"),
    ("lbl_status_failed", "Failed status"),
    ("lbl_status_planned", "Planned phase status"),
    ("lbl_status_completed", "Completed phase status"),
    ("lbl_status_next", "Next phase status"),
    ("lbl_sequence_count", "Sequence count label"),
    ("lbl_step_count", "Step count label"),
    ("lbl_sequences", "Sequences label"),
    ("lbl_steps", "Steps label"),
    ("lbl_select_sequence", "Select sequence prompt"),
    ("lbl_empty_sequences", "Empty sequences message"),
    ("lbl_empty_steps", "Empty steps message"),
    ("lbl_prompt_preview", "Prompt preview heading"),
    ("lbl_prompt_history", "Prompt history heading"),
    ("lbl_no_prompts_yet", "No prompts message"),
    ("lbl_project_name", "Project name field"),
    ("lbl_target_folder", "Target folder field"),
    ("lbl_app_port", "App port field"),
    ("lbl_app_profile", "App profile field"),
    ("lbl_prompt_sequence_select", "Prompt sequence selector"),
    ("lbl_notes", "Notes field"),
    ("lbl_drawer_layout_slots", "Layout Slots drawer section"),
    ("lbl_drawer_db_layout", "Database Layout Preview drawer section"),
    ("lbl_drawer_i18n", "UI Labels / i18n drawer section"),
    ("lbl_drawer_endpoint_registry", "Endpoint Registry drawer section"),
    ("lbl_drawer_bootstrap", "Bootstrap Dataset drawer section"),
    ("lbl_drawer_security", "Security / Permissions drawer section"),
    # ── Panel group headings ──
    ("pg_daily", "Daily panel group heading"),
    ("pg_journals", "Journals panel group heading"),
    ("pg_reports", "Reports panel group heading"),
    ("pg_periodic", "Periodic panel group heading"),
    ("pg_setup", "Setup panel group heading"),
    # ── 2H: Template Manager slots ──
    ("lbl_tpl_templates", "Template Manager section heading"),
    ("lbl_tpl_key", "Template key column header"),
    ("lbl_tpl_name", "Template name column header"),
    ("lbl_tpl_tier", "Complexity tier column header"),
    ("lbl_tpl_suitable_for", "Suitable for column header"),
    ("lbl_tpl_capture", "Capture source column header"),
    ("lbl_tpl_local_sr", "Local success rate column header"),
    ("lbl_tpl_cloud_sr", "Cloud success rate column header"),
    ("lbl_tpl_tokens", "Token estimates column header"),
    ("lbl_tpl_preview", "Preview column header"),
    ("lbl_tpl_click_to_view", "Click to view placeholder"),
    ("lbl_tpl_model_hitrates", "Model hitrates section heading"),
    ("lbl_tpl_compile_prompt", "Compile prompt button/section"),
    ("lbl_tpl_project_path", "Project path input label"),
    ("lbl_tpl_phase_id", "Phase ID input label"),
    ("lbl_tpl_goal", "Goal input label"),
    ("lbl_tpl_constraints", "Constraints textarea label"),
    ("lbl_tpl_allowed_files", "Allowed files textarea label"),
    ("lbl_tpl_validation_cmds", "Validation commands textarea label"),
    ("lbl_tpl_estimated_tokens", "Estimated tokens label"),
    ("lbl_tpl_local_sr_label", "Local success rate label"),
    ("lbl_tpl_cloud_sr_label", "Cloud success rate label"),
    ("lbl_tpl_runs_count", "Runs count suffix"),
    # ── 2H: Model Hitrates table slots ──
    ("lbl_col_model", "Model column header"),
    ("lbl_col_runs", "Runs column header"),
    ("lbl_col_success_rate", "Success rate column header"),
    ("lbl_col_avg_duration", "Average duration column header"),
    # ── 2H: Prompt Runs extended column slots ──
    ("lbl_col_status", "Execution status column header"),
    ("lbl_col_first_try", "First-try success column header"),
    ("lbl_col_corrections", "Manual corrections column header"),
    # ── 2H: Hitrate table slots ──
    ("lbl_col_phase", "Phase column header"),
    ("lbl_col_successful_total", "Successful/Total column header"),
    ("lbl_col_last_run", "Last run column header"),
    ("lbl_pat_heading", "Implementation Patterns section heading"),
    ("lbl_runs_heading", "Recent Prompt Runs section heading"),
    # ── 2H: Runs table column slots ──
    ("lbl_col_run_id", "Run ID column header"),
    ("lbl_col_project", "Project column header"),
    ("lbl_col_duration", "Duration column header"),
    ("lbl_col_cost", "Cost column header"),
    ("lbl_col_timestamp", "Timestamp column header"),
    # ── 2H: Pattern table column slots ──
    ("lbl_col_pattern_id", "Pattern ID column header"),
    ("lbl_col_files", "Files column header"),
    ("lbl_col_constraints", "Constraints column header"),
    ("lbl_col_best_model", "Best model column header"),
    ("lbl_col_avg_dur", "Average duration column header"),
    # ── 2H: Validation result slots ──
    ("lbl_col_rule", "Rule column header"),
    ("lbl_col_result", "Result column header"),
    ("lbl_col_notes", "Notes column header"),
    ("lbl_val_running", "Validation running status"),
    ("lbl_val_no_rules", "No validation rules message"),
    # ── System setup slots (pre-existing labels, now mapped) ──
    ("system_setup.title", "System Setup drawer title"),
    ("system_setup.layout_slots.title", "Layout Slots section title"),
    ("system_setup.database_layout_preview.title", "Database Layout Preview section title"),
    ("system_setup.database_layout_preview.description", "Database Layout Preview description"),
    ("system_setup.database_layout_preview.refresh", "Database Layout Preview refresh button"),
    ("phase_status.show_completed", "Show completed phases toggle"),
    ("lbl_panel_templates", "Prompt Templates panel heading"),
    # ── 2I (handoff 017): Assign Handoff ID slots ──
    ("lbl_btn_assign_handoff_id", "Assign Handoff ID button"),
    ("lbl_status_assigning_id", "Assigning handoff ID loading state"),
    ("lbl_handoff_ready", "Handoff ready success message"),
    ("lbl_handoff_file_written", "File written info label"),
    ("lbl_dispatch_command", "Dispatch command label"),
    ("lbl_btn_copy_command", "Copy dispatch command button"),
    # ── Accelerated WebUI Factory slots ──
    ("lbl_compiler_new_webui_name", "Accelerated: new webui name field"),
    ("lbl_compiler_new_webui_port", "Accelerated: port number field"),
    ("lbl_compiler_new_webui_title", "Accelerated: project title field"),
    ("lbl_compiler_create_webui_btn", "Accelerated: create button"),
    ("lbl_compiler_start_server_btn", "Accelerated: start server button"),
    ("lbl_compiler_webui_created", "Accelerated: success message"),
    ("lbl_compiler_governance_reminder", "Accelerated: governance reminder"),
    ("lbl_compiler_open_webui", "Accelerated: open webui link text"),
    ("lbl_compiler_script_error", "Accelerated: script error heading"),
    ("lbl_compiler_field_required", "Accelerated: field required message"),
]
for slot_key, description in ui_text_slots_data:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_text_slots (slot_key, description)
        VALUES (?, ?)
    """, (slot_key, description))

# ── 2F-bis: Seed ui_text_slot_labels (bind each slot to its label) ──
ui_text_slot_labels_data = [
    ("lbl_page_title", "lbl_page_title"),
    ("lbl_heading_main", "lbl_heading_main"),
    ("lbl_panel_db_status", "lbl_panel_db_status"),
    ("lbl_panel_phase_status", "lbl_panel_phase_status"),
    ("lbl_panel_hitrates", "lbl_panel_hitrates"),
    ("lbl_panel_prompt_sequences", "lbl_panel_prompt_sequences"),
    ("lbl_panel_project_planning", "lbl_panel_project_planning"),
    ("lbl_btn_system_setup", "lbl_btn_system_setup"),
    ("lbl_btn_refresh", "lbl_btn_refresh"),
    ("lbl_btn_create", "lbl_btn_create"),
    ("lbl_btn_add_step", "lbl_btn_add_step"),
    ("lbl_btn_generate_prompt", "lbl_btn_generate_prompt"),
    ("lbl_btn_copy_prompt", "lbl_btn_copy_prompt"),
    ("lbl_btn_save_prompt", "lbl_btn_save_prompt"),
    ("lbl_btn_create_project_plan", "lbl_btn_create_project_plan"),
    ("lbl_btn_close_drawer", "lbl_btn_close_drawer"),
    ("lbl_status_loading", "lbl_status_loading"),
    ("lbl_status_no_data", "lbl_status_no_data"),
    ("lbl_status_error_prefix", "lbl_status_error_prefix"),
    ("lbl_status_success", "lbl_status_success"),
    ("lbl_status_failed", "lbl_status_failed"),
    ("lbl_status_planned", "lbl_status_planned"),
    ("lbl_status_completed", "lbl_status_completed"),
    ("lbl_status_next", "lbl_status_next"),
    ("lbl_sequence_count", "lbl_sequence_count"),
    ("lbl_step_count", "lbl_step_count"),
    ("lbl_sequences", "lbl_sequences"),
    ("lbl_steps", "lbl_steps"),
    ("lbl_select_sequence", "lbl_select_sequence"),
    ("lbl_empty_sequences", "lbl_empty_sequences"),
    ("lbl_empty_steps", "lbl_empty_steps"),
    ("lbl_prompt_preview", "lbl_prompt_preview"),
    ("lbl_prompt_history", "lbl_prompt_history"),
    ("lbl_no_prompts_yet", "lbl_no_prompts_yet"),
    ("lbl_project_name", "lbl_project_name"),
    ("lbl_target_folder", "lbl_target_folder"),
    ("lbl_app_port", "lbl_app_port"),
    ("lbl_app_profile", "lbl_app_profile"),
    ("lbl_prompt_sequence_select", "lbl_prompt_sequence_select"),
    ("lbl_notes", "lbl_notes"),
    ("lbl_drawer_layout_slots", "lbl_drawer_layout_slots"),
    ("lbl_drawer_db_layout", "lbl_drawer_db_layout"),
    ("lbl_drawer_i18n", "lbl_drawer_i18n"),
    ("lbl_drawer_endpoint_registry", "lbl_drawer_endpoint_registry"),
    ("lbl_drawer_bootstrap", "lbl_drawer_bootstrap"),
    ("lbl_drawer_security", "lbl_drawer_security"),
    # ── Panel group headings ──
    ("pg_daily", "pg_daily"),
    ("pg_journals", "pg_journals"),
    ("pg_reports", "pg_reports"),
    ("pg_periodic", "pg_periodic"),
    ("pg_setup", "pg_setup"),
    # ── 2H: Template Manager ──
    ("lbl_tpl_templates", "lbl_tpl_templates"),
    ("lbl_tpl_key", "lbl_tpl_key"),
    ("lbl_tpl_name", "lbl_tpl_name"),
    ("lbl_tpl_tier", "lbl_tpl_tier"),
    ("lbl_tpl_suitable_for", "lbl_tpl_suitable_for"),
    ("lbl_tpl_capture", "lbl_tpl_capture"),
    ("lbl_tpl_local_sr", "lbl_tpl_local_sr"),
    ("lbl_tpl_cloud_sr", "lbl_tpl_cloud_sr"),
    ("lbl_tpl_tokens", "lbl_tpl_tokens"),
    ("lbl_tpl_preview", "lbl_tpl_preview"),
    ("lbl_tpl_click_to_view", "lbl_tpl_click_to_view"),
    ("lbl_tpl_model_hitrates", "lbl_tpl_model_hitrates"),
    ("lbl_tpl_compile_prompt", "lbl_tpl_compile_prompt"),
    ("lbl_tpl_project_path", "lbl_tpl_project_path"),
    ("lbl_tpl_phase_id", "lbl_tpl_phase_id"),
    ("lbl_tpl_goal", "lbl_tpl_goal"),
    ("lbl_tpl_constraints", "lbl_tpl_constraints"),
    ("lbl_tpl_allowed_files", "lbl_tpl_allowed_files"),
    ("lbl_tpl_validation_cmds", "lbl_tpl_validation_cmds"),
    ("lbl_tpl_estimated_tokens", "lbl_tpl_estimated_tokens"),
    ("lbl_tpl_local_sr_label", "lbl_tpl_local_sr_label"),
    ("lbl_tpl_cloud_sr_label", "lbl_tpl_cloud_sr_label"),
    ("lbl_tpl_runs_count", "lbl_tpl_runs_count"),
    # ── 2H: Model Hitrates table ──
    ("lbl_col_model", "lbl_col_model"),
    ("lbl_col_runs", "lbl_col_runs"),
    ("lbl_col_success_rate", "lbl_col_success_rate"),
    ("lbl_col_avg_duration", "lbl_col_avg_duration"),
    # ── 2H: Prompt Runs extended columns ──
    ("lbl_col_status", "lbl_col_status"),
    ("lbl_col_first_try", "lbl_col_first_try"),
    ("lbl_col_corrections", "lbl_col_corrections"),
    # ── 2H: Hitrate table ──
    ("lbl_col_phase", "lbl_col_phase"),
    ("lbl_col_successful_total", "lbl_col_successful_total"),
    ("lbl_col_last_run", "lbl_col_last_run"),
    ("lbl_pat_heading", "lbl_pat_heading"),
    ("lbl_runs_heading", "lbl_runs_heading"),
    # ── 2H: Runs table columns ──
    ("lbl_col_run_id", "lbl_col_run_id"),
    ("lbl_col_project", "lbl_col_project"),
    ("lbl_col_duration", "lbl_col_duration"),
    ("lbl_col_cost", "lbl_col_cost"),
    ("lbl_col_timestamp", "lbl_col_timestamp"),
    # ── 2H: Pattern table columns ──
    ("lbl_col_pattern_id", "lbl_col_pattern_id"),
    ("lbl_col_files", "lbl_col_files"),
    ("lbl_col_constraints", "lbl_col_constraints"),
    ("lbl_col_best_model", "lbl_col_best_model"),
    ("lbl_col_avg_dur", "lbl_col_avg_dur"),
    # ── 2H: Validation results ──
    ("lbl_col_rule", "lbl_col_rule"),
    ("lbl_col_result", "lbl_col_result"),
    ("lbl_col_notes", "lbl_col_notes"),
    ("lbl_val_running", "lbl_val_running"),
    ("lbl_val_no_rules", "lbl_val_no_rules"),
    # ── System setup (pre-existing labels, now mapped) ──
    ("system_setup.title", "system_setup.title"),
    ("system_setup.layout_slots.title", "system_setup.layout_slots.title"),
    ("system_setup.database_layout_preview.title", "system_setup.database_layout_preview.title"),
    ("system_setup.database_layout_preview.description", "system_setup.database_layout_preview.description"),
    ("system_setup.database_layout_preview.refresh", "system_setup.database_layout_preview.refresh"),
    ("phase_status.show_completed", "phase_status.show_completed"),
    ("lbl_panel_templates", "lbl_panel_templates"),
    # ── 2I (handoff 017): Assign Handoff ID slot-label bindings ──
    ("lbl_btn_assign_handoff_id", "lbl_btn_assign_handoff_id"),
    ("lbl_status_assigning_id", "lbl_status_assigning_id"),
    ("lbl_handoff_ready", "lbl_handoff_ready"),
    ("lbl_handoff_file_written", "lbl_handoff_file_written"),
    ("lbl_dispatch_command", "lbl_dispatch_command"),
    ("lbl_btn_copy_command", "lbl_btn_copy_command"),
    # ── Accelerated WebUI Factory bindings ──
    ("lbl_compiler_new_webui_name", "lbl_compiler_new_webui_name"),
    ("lbl_compiler_new_webui_port", "lbl_compiler_new_webui_port"),
    ("lbl_compiler_new_webui_title", "lbl_compiler_new_webui_title"),
    ("lbl_compiler_create_webui_btn", "lbl_compiler_create_webui_btn"),
    ("lbl_compiler_start_server_btn", "lbl_compiler_start_server_btn"),
    ("lbl_compiler_webui_created", "lbl_compiler_webui_created"),
    ("lbl_compiler_governance_reminder", "lbl_compiler_governance_reminder"),
    ("lbl_compiler_open_webui", "lbl_compiler_open_webui"),
    ("lbl_compiler_script_error", "lbl_compiler_script_error"),
    ("lbl_compiler_field_required", "lbl_compiler_field_required"),
]
for slot_key, label_key in ui_text_slot_labels_data:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key)
        VALUES (?, ?)
    """, (slot_key, label_key))

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
    ("BDS-5000004", "ui_labels", "ui_labels", "UI label registry seed data", "scripts/init_db.py", 107, 1, 1),
    ("BDS-5000005", "ui_label_translations", "ui_label_translations", "UI label translation seed data", "scripts/init_db.py", 214, 1, 1),
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

# ── Phase 2F: Hitrate Scoring ──────────────────────────────────────────
# prompt_runs: individual prompt execution records
cursor.execute("""
CREATE TABLE IF NOT EXISTS prompt_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    phase_key TEXT NOT NULL,
    target_project TEXT NOT NULL,
    prompt_summary TEXT,
    success INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER,
    error_summary TEXT,
    model_used TEXT,
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
)
""")

# prompt_hitrates: aggregated success rates grouped by phase_key
cursor.execute("""
CREATE TABLE IF NOT EXISTS prompt_hitrates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_key TEXT UNIQUE NOT NULL,
    total_runs INTEGER NOT NULL DEFAULT 0,
    successful_runs INTEGER NOT NULL DEFAULT 0,
    rolling_success_rate REAL NOT NULL DEFAULT 0.0,
    last_run_timestamp TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Seed empty hitrate records for known phases so the frontend has
# something to display immediately (INSERT OR IGNORE — idempotent).
hitrate_seeds = [
    ("2E", 1, 1, 1.0),   # Governance-template opgradering — 1 run, success
]
for phase_key, total, success, rate in hitrate_seeds:
    cursor.execute("""
        INSERT OR IGNORE INTO prompt_hitrates
        (phase_key, total_runs, successful_runs, rolling_success_rate)
        VALUES (?, ?, ?, ?)
    """, (phase_key, total, success, rate))

# Seed the 2E run that was just completed so the table is not empty
cursor.execute("""
    INSERT OR IGNORE INTO prompt_runs
    (run_id, phase_key, target_project, prompt_summary, success,
     duration_seconds, model_used, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "PRUN-2E-0001",
    "2E",
    "DPMtF-WebUI",
    "Upgrade 10 governance templates from v3 learnings, restructure phase roadmap to 6-block plan (2E-2O), write cross-project analysis report",
    1,
    240,
    "claude-fable-5",
    "Completed in one session. All 10 templates upgraded, init_db.py restructured, project-report.md written. Committed as bd671f5.",
))

# Register the new endpoints in endpoint_registry
endpoint_registry_2f = [
    ("ENDP-4000013", "prompt_runs", "/api/prompt-runs", "GET", "List prompt runs with optional phase/project filters", "prompt_runs JSON array", "hitrate_panel"),
    ("ENDP-4000014", "prompt_runs_create", "/api/prompt-runs", "POST", "Record a new prompt run result and update hitrate aggregate", "created run JSON", "hitrate_panel"),
    ("ENDP-4000015", "prompt_hitrates", "/api/prompt-hirates", "GET", "Aggregated hitrate statistics grouped by phase", "prompt_hitrates JSON array", "hitrate_panel"),
]
for endpoint in endpoint_registry_2f:
    cursor.execute("""
        INSERT OR REPLACE INTO endpoint_registry
        (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, endpoint)

# Register bootstrap datasets for the new tables
bootstrap_2f = [
    ("BDS-5000012", "prompt_runs", "prompt_runs", "Prompt execution records for hitrate tracking", "scripts/init_db.py", 1, 1, 1),
    ("BDS-5000013", "prompt_hitrates", "prompt_hitrates", "Aggregated hitrate statistics by phase", "scripts/init_db.py", 1, 1, 1),
]
for ds in bootstrap_2f:
    cursor.execute("""
        INSERT OR REPLACE INTO bootstrap_dataset_registry
        (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ds)

# ── Phase 2G: Implementation Pattern Manager ─────────────────────────
# Extend prompt_runs with model metadata + pattern linking
alter_runs = [
    ("model_type", "TEXT"),
    ("idle_seconds", "INTEGER"),
    ("token_count_input", "INTEGER"),
    ("token_count_output", "INTEGER"),
    ("token_cost_eur", "REAL"),
    ("token_cost_dkk", "REAL"),
    ("pattern_id", "TEXT"),
]
for col_name, col_type in alter_runs:
    try:
        cursor.execute(
            f"ALTER TABLE prompt_runs ADD COLUMN {col_name} {col_type}"
        )
    except sqlite3.OperationalError:
        pass  # Column already exists — idempotent

# ── Phase 2H Redesign: Extend prompt_runs ────────────────────────────
# 5 new columns for mandatory outcome tracking + template linking
alter_runs_2h = [
    ("template_key", "TEXT"),
    ("execution_status", "TEXT NOT NULL DEFAULT 'unknown'"),
    ("first_try_success", "INTEGER"),
    ("manual_corrections", "INTEGER DEFAULT 0"),
    ("validation_passed", "INTEGER"),
]
for col_name, col_type in alter_runs_2h:
    try:
        cursor.execute(
            f"ALTER TABLE prompt_runs ADD COLUMN {col_name} {col_type}"
        )
    except sqlite3.OperationalError:
        pass  # Column already exists — idempotent

# implementation_patterns: aggregated by file_signature + constraint_set
cursor.execute("""
CREATE TABLE IF NOT EXISTS implementation_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_id TEXT UNIQUE NOT NULL,
    file_signature TEXT NOT NULL,
    constraint_set TEXT NOT NULL,
    phase_key TEXT,
    total_runs INTEGER NOT NULL DEFAULT 0,
    successful_runs INTEGER NOT NULL DEFAULT 0,
    rolling_success_rate REAL NOT NULL DEFAULT 0.0,
    best_model TEXT,
    avg_duration_seconds INTEGER,
    avg_idle_seconds INTEGER,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_signature, constraint_set)
)
""")

# Backfill PRUN-2E-0001 with model type, pattern link, and 2H outcome fields
cursor.execute("""
    UPDATE prompt_runs SET
        model_type = 'cloud',
        pattern_id = 'PAT-0001',
        template_key = 'tpl_implementation_medium',
        execution_status = 'completed',
        first_try_success = 1,
        manual_corrections = 0,
        validation_passed = 1
    WHERE run_id = 'PRUN-2E-0001'
""")

# Seed PAT-0001
cursor.execute("""
    INSERT OR IGNORE INTO implementation_patterns
    (pattern_id, file_signature, constraint_set, phase_key,
     total_runs, successful_runs, rolling_success_rate,
     best_model, avg_duration_seconds, last_used_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
""", (
    "PAT-0001",
    "docs/governance-templates/*,scripts/init_db.py,docs/project-report.md",
    "read-only,no-schema,no-POST/PUT/DELETE,no-service-control",
    "2E",
    1, 1, 1.0,
    "claude-fable-5",
    240,
))

# Register new endpoints
endpoint_registry_2g = [
    ("ENDP-4000016", "implementation_patterns", "/api/implementation-patterns", "GET", "List implementation patterns grouped by file_signature + constraint_set with hitrate stats", "patterns JSON array", "hitrate_panel"),
    ("ENDP-4000017", "pattern_runs", "/api/implementation-patterns/{pattern_id}/runs", "GET", "List prompt runs for a specific implementation pattern", "runs JSON array", "hitrate_panel"),
]
for endpoint in endpoint_registry_2g:
    cursor.execute("""
        INSERT OR REPLACE INTO endpoint_registry
        (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, endpoint)

# Register bootstrap dataset
cursor.execute("""
    INSERT OR REPLACE INTO bootstrap_dataset_registry
    (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("BDS-5000014", "implementation_patterns", "implementation_patterns", "Implementation pattern registry with hitrate aggregates", "scripts/init_db.py", 1, 1, 1))

# ── Phase 2H: Prompt Template Manager ──────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_key TEXT UNIQUE NOT NULL,
    template_name TEXT NOT NULL,
    description TEXT,
    structure_json TEXT NOT NULL,
    constraints_json TEXT,
    suitable_for TEXT NOT NULL DEFAULT 'both',
    avg_token_count_input INTEGER,
    avg_token_count_output INTEGER,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ── Phase 2H Redesign: Extend prompt_templates ───────────────────────
# 6 new columns based on Excel data analysis (2026-06-13)
alter_templates = [
    ("complexity_tier", "INTEGER DEFAULT 2"),
    ("capture_source", "TEXT DEFAULT 'designed'"),
    ("local_success_rate", "REAL DEFAULT 0.0"),
    ("cloud_success_rate", "REAL DEFAULT 0.0"),
    ("total_local_runs", "INTEGER DEFAULT 0"),
    ("total_cloud_runs", "INTEGER DEFAULT 0"),
]
for col_name, col_type in alter_templates:
    try:
        cursor.execute(
            f"ALTER TABLE prompt_templates ADD COLUMN {col_name} {col_type}"
        )
    except sqlite3.OperationalError:
        pass  # Column already exists — idempotent

# Seed baseline templates from existing prompt-run template patterns
template_seeds = [
    ("tpl_implementation_small", "Small Implementation Prompt",
     "For 10-15 minute phases: single-file or few-file changes, read-only, no schema migration.",
     json.dumps({
         "sections": [
             {"name": "context", "label": "You are working in:", "type": "fixed", "value": "{project_path}"},
             {"name": "phase", "label": "Start phase", "type": "param", "param_key": "phase_id"},
             {"name": "goal", "label": "Goal:", "type": "param", "param_key": "goal"},
             {"name": "rules", "label": "Rules:", "type": "list", "param_key": "constraints"},
             {"name": "implementation", "label": "Implementation target:", "type": "param", "param_key": "implementation"},
             {"name": "allowed_files", "label": "Allowed files:", "type": "list", "param_key": "allowed_files"},
             {"name": "validate", "label": "Validate:", "type": "list", "param_key": "validation_commands"},
             {"name": "stop", "label": "Do not commit.", "type": "fixed", "value": ""}
         ]
     }),
     json.dumps({
         "default_constraints": ["read-only", "no-schema-migration", "no-innerHTML", "no-POST/PUT/DELETE", "no-service-control"]
     }),
     "both", 1, "designed", 800, 1200, 0.0, 0.0, 0, 0, 1),

    ("tpl_implementation_medium", "Medium Implementation Prompt",
     "For larger phases: multiple files, backend + frontend changes, new endpoints allowed.",
     json.dumps({
         "sections": [
             {"name": "context", "label": "You are working in:", "type": "fixed", "value": "{project_path}"},
             {"name": "phase", "label": "Start phase", "type": "param", "param_key": "phase_id"},
             {"name": "goal", "label": "Goal:", "type": "param", "param_key": "goal"},
             {"name": "rules", "label": "Rules:", "type": "list", "param_key": "constraints"},
             {"name": "implementation", "label": "Implementation target:", "type": "param", "param_key": "implementation"},
             {"name": "allowed_files", "label": "Allowed files:", "type": "list", "param_key": "allowed_files"},
             {"name": "validate", "label": "Validate:", "type": "list", "param_key": "validation_commands"},
             {"name": "docs", "label": "Update docs/dpmtf/10_CHANGELOG.md, 11_NEXT_CONTEXT.md, 12_IMPLEMENTATION_REPORT.md", "type": "fixed", "value": ""},
             {"name": "stop", "label": "Stop before commit and report.", "type": "fixed", "value": ""}
         ]
     }),
     json.dumps({
         "default_constraints": ["no-innerHTML", "no-service-control"]
     }),
     "both", 2, "designed", 1200, 2000, 0.0, 0.0, 0, 0, 1),

    ("tpl_validation", "Validation Prompt",
     "Read-only validation of changes. No edits, no commits.",
     json.dumps({
         "sections": [
             {"name": "context", "label": "You are validating changes in:", "type": "fixed", "value": "{project_path}"},
             {"name": "task", "label": "Task:", "type": "param", "param_key": "task"},
             {"name": "baseline", "label": "Expected baseline:", "type": "param", "param_key": "baseline"},
             {"name": "goal", "label": "Expected goal:", "type": "param", "param_key": "goal"},
             {"name": "checks", "label": "Check:", "type": "list", "param_key": "checks"},
             {"name": "report", "label": "Report:", "type": "fixed", "value": "1. PASS or FAIL\n2. Specific issues found\n3. Whether it is safe for Svend to commit\n4. If FAIL, provide a short correction prompt"},
             {"name": "stop", "label": "Do not fix anything yourself.", "type": "fixed", "value": ""}
         ]
     }),
     json.dumps({
         "default_constraints": ["read-only", "no-edits", "no-commits"]
     }),
     "local", 1, "designed", 600, 800, 0.0, 0.0, 0, 0, 1),

    ("tpl_brainstorm", "Brainstorm / Design Prompt",
     "High-level design and brainstorming. No code changes.",
     json.dumps({
         "sections": [
             {"name": "context", "label": "This is a brainstorm session.", "type": "fixed", "value": ""},
             {"name": "scope", "label": "Scope:", "type": "param", "param_key": "scope"},
             {"name": "constraints", "label": "Constraints:", "type": "list", "param_key": "constraints"},
             {"name": "deliverable", "label": "Deliverable:", "type": "param", "param_key": "deliverable"},
             {"name": "stop", "label": "This is an investigation and report task only.", "type": "fixed", "value": ""}
         ]
     }),
     json.dumps({
         "default_constraints": ["read-only", "no-code-changes", "no-commits"]
     }),
     "cloud", 3, "designed", 500, 1500, 0.0, 0.0, 0, 0, 1),

    # ── Phase 2H Redesign: New templates from Excel data patterns ──────
    ("tpl_create_add_local", "Create/Add — Local Model",
     "For create/add operations with local Ollama model. 1-3 files, no schema changes. Based on 6 prompt runs averaging 83% success rate.",
     json.dumps({
         "sections": [
             {"name": "context", "label": "You are working in:", "type": "fixed", "value": "{project_path}", "required": True},
             {"name": "phase", "label": "Start phase", "type": "param", "param_key": "phase_id", "required": True},
             {"name": "goal", "label": "Goal:", "type": "param", "param_key": "goal", "required": True, "min_length": 20, "max_length": 300},
             {"name": "rules", "label": "Rules:", "type": "list", "param_key": "constraints", "required": True},
             {"name": "implementation", "label": "Implementation target:", "type": "param", "param_key": "implementation", "required": True, "max_length": 200},
             {"name": "allowed_files", "label": "Allowed files:", "type": "list", "param_key": "allowed_files", "required": True},
             {"name": "validate", "label": "Validate:", "type": "list", "param_key": "validation_commands", "required": True},
             {"name": "notes", "label": "Additional notes:", "type": "param", "param_key": "notes", "required": False, "max_length": 300},
             {"name": "stop", "label": "Do not commit.", "type": "fixed", "value": "", "required": True}
         ]
     }),
     json.dumps({
         "default_constraints": ["no-schema-migration", "no-innerHTML", "no-service-control", "no-new-dependencies"]
     }),
     "local", 1, "verbatim", 300, 600, 0.0, 0.0, 0, 0, 1),

    ("tpl_update_edit_local", "Update/Edit — Local Model",
     "For update/edit operations with local Ollama model. Read-only context, targeted edits. Based on 2 prompt runs (v3 phases 3C-6, 3C-14).",
     json.dumps({
         "sections": [
             {"name": "context", "label": "You are working in:", "type": "fixed", "value": "{project_path}", "required": True},
             {"name": "phase", "label": "Start phase", "type": "param", "param_key": "phase_id", "required": True},
             {"name": "baseline", "label": "First run phase-start git baseline checks:", "type": "list", "param_key": "baseline_commands", "required": True},
             {"name": "goal", "label": "Goal:", "type": "param", "param_key": "goal", "required": True, "min_length": 30, "max_length": 500},
             {"name": "rules", "label": "Rules:", "type": "list", "param_key": "constraints", "required": True},
             {"name": "implementation", "label": "Implementation target:", "type": "param", "param_key": "implementation", "required": True, "max_length": 300},
             {"name": "allowed_files", "label": "Allowed files:", "type": "list", "param_key": "allowed_files", "required": True},
             {"name": "validate", "label": "Validate:", "type": "list", "param_key": "validation_commands", "required": True},
             {"name": "docs", "label": "Update docs/dpmtf/10_CHANGELOG.md, 11_NEXT_CONTEXT.md, 12_IMPLEMENTATION_REPORT.md", "type": "fixed", "value": "", "required": False},
             {"name": "stop", "label": "Stop before commit and report.", "type": "fixed", "value": "", "required": True}
         ]
     }),
     json.dumps({
         "default_constraints": ["read-only", "no-schema-migration", "no-innerHTML", "no-POST/PUT/DELETE", "no-service-control"]
     }),
     "local", 2, "verbatim", 500, 1000, 0.0, 0.0, 0, 0, 1),
]

for tpl in template_seeds:
    cursor.execute("""
        INSERT OR IGNORE INTO prompt_templates
        (template_key, template_name, description, structure_json,
         constraints_json, suitable_for, complexity_tier, capture_source,
         avg_token_count_input, avg_token_count_output,
         local_success_rate, cloud_success_rate,
         total_local_runs, total_cloud_runs, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, tpl)

# ── Phase 2H Redesign: template_model_hitrates ───────────────────────
# Tracks per-model success rates for each template.
# Enables data-driven model selection — not just suitable_for flag.
cursor.execute("""
CREATE TABLE IF NOT EXISTS template_model_hitrates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_key TEXT NOT NULL,
    model_used TEXT NOT NULL,
    total_runs INTEGER NOT NULL DEFAULT 0,
    successful_runs INTEGER NOT NULL DEFAULT 0,
    rolling_success_rate REAL NOT NULL DEFAULT 0.0,
    avg_duration_seconds INTEGER,
    last_run_timestamp TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(template_key, model_used)
)
""")

# Seed template_model_hitrates for PRUN-2E-0001
cursor.execute("""
    INSERT OR IGNORE INTO template_model_hitrates
    (template_key, model_used, total_runs, successful_runs,
     rolling_success_rate, avg_duration_seconds)
    VALUES (?, ?, ?, ?, ?, ?)
""", ("tpl_implementation_medium", "claude-fable-5", 1, 1, 1.0, 240))

# ── Phase 2I-v2: Prompt Compiler Fields (database-driven) ────────────
# Dynamic form fields for the Prompt Compiler — governance-v2 compliant.
# Enables conditional gating based on trigger conditions.
cursor.execute("""
CREATE TABLE IF NOT EXISTS prompt_compiler_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_key TEXT UNIQUE NOT NULL,
    field_label TEXT NOT NULL,
    field_type TEXT NOT NULL,
    is_required INTEGER DEFAULT 1,
    required_condition TEXT,
    section TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    placeholder TEXT,
    help_text TEXT,
    default_value TEXT,
    is_active INTEGER DEFAULT 1
)
""")

# Seed prompt_compiler_fields — 20 fields across 5 sections
compiler_fields_seed = [
    # ── Section: human_responsibility (sort_order 1-9) ──────────────
    ("scope_approved", "Scope approved per 11_SCOPE", "checkbox", 1, None,
     "human_responsibility", 1, None,
     "Human has approved the phase scope definition", None),
    ("phase_key", "Phase Key", "text", 1, None,
     "human_responsibility", 2, "e.g. 3B",
     "Which phase does this task belong to", None),
    ("target_project", "Target Project", "select", 1, None,
     "human_responsibility", 3, None,
     "Which project will be modified", config.get_project_root()),
    ("goal", "Goal", "textarea", 1, None,
     "human_responsibility", 4, "Describe what this task should achieve",
     "Clear, specific description of the desired outcome", None),
    ("gate_scope_answered", "GATE-SCOPE answered", "checkbox", 1,
     '{"trigger":"scope_changed","description":"Scope differs from existing 11_SCOPE"}',
     "human_responsibility", 5, None,
     "Has GATE-SCOPE been asked and answered per 20_GATES.md", None),
    ("gate_v3_answered", "GATE-V3 answered", "checkbox", 1,
     '{"trigger":"target_is_v3","description":"Target project is ai-pc-resource-webui-v3"}',
     "human_responsibility", 6, None,
     "Has GATE-V3 been asked and answered per 20_GATES.md", None),
    ("gate_model_answered", "GATE-MODEL answered", "checkbox", 1,
     '{"trigger":"model_differs_from_default","description":"Selected model differs from tier default"}',
     "human_responsibility", 7, None,
     "Has GATE-MODEL been asked and answered per 20_GATES.md", None),
    ("gate_feature_rollout_answered", "GATE-FEATURE-ROLLOUT answered", "checkbox", 1,
     '{"trigger":"multi_project_impact","description":"Feature may affect ENO or v3"}',
     "human_responsibility", 8, None,
     "Has GATE-FEATURE-ROLLOUT been asked and answered per 20_GATES.md", None),
    ("commit_authorized", "Commit authorized by Human", "checkbox", 1,
     '{"trigger":"phase_mode_commit_release","description":"Phase is in commit_release mode"}',
     "human_responsibility", 9, None,
     "Human has explicitly authorized commit for this task", None),
    # ── Section: project (sort_order 10-11) ────────────────────────
    ("father_project", "Father Project", "select", 0, None,
     "project", 10, None, "The Father project governing this task", "DPMtF-WebUI"),
    ("is_new_child_project", "This is a new Child project", "checkbox", 0, None,
     "project", 11, None,
     "Check if this task initializes a new project under DPMtF governance", None),
    # ── Section: scope (sort_order 12-14) ──────────────────────────
    ("allowed_files", "Allowed files (one per line)", "textarea", 1, None,
     "scope", 12, f"{config.get_project_root()}/scripts/init_db.py",
     "Full paths to files the Implementor MAY modify", None),
    ("forbidden_files", "Forbidden files (one per line)", "textarea", 1, None,
     "scope", 13, f"/home/svend/{config.get_child_projects()[0]}/\n/home/svend/{config.get_reference_projects()[0]}/",
     "Full paths to files the Implementor MUST NOT touch", None),
    ("constraints", "Constraints (one per line)", "textarea", 1, None,
     "scope", 14, "no-innerHTML\nno-schema-migration\nno-new-dependencies",
     "Specific constraints extracted from governance", None),
    # ── Section: migration (sort_order 15-17) ──────────────────────
    ("is_migration", "This is a migration task", "checkbox", 0, None,
     "migration", 15, None,
     "Check if this task involves migrating from existing WebUI projects", None),
    ("migration_folders", "Migration folders — READ-ONLY (one per line)", "textarea", 1,
     '{"trigger":"is_migration_true","description":"is_migration checkbox is checked"}',
     "migration", 16, "/home/svend/old-webui-v2/",
     "Full paths to existing WebUI folders for reference inspection only", None),
    ("migration_source_description", "Migration source description", "text", 1,
     '{"trigger":"is_migration_true","description":"is_migration checkbox is checked"}',
     "migration", 17, "Describe what is being migrated from",
     "Brief description of the source project and what to migrate", None),
    # ── Section: validation (sort_order 18-21) ────────────────────
    ("validation_commands", "Validation commands (one per line)", "textarea", 1, None,
     "validation", 18, "python3 -m py_compile app.py\nnode --check static/js/dpmtf-app.js\ngrep -RIn innerHTML static templates",
     "Shell commands the Implementor must run before signaling completion", None),
    ("model_selection", "Model for execution", "select", 0, None,
     "validation", 19, None,
     "Which model should execute this task per 22_MODEL_SELECTION.md", "qwen36-27b-q4km"),
    ("target_session", "Target tmux Session", "select", 1, None,
     "validation", 20, None,
     "Which tmux session receives the dispatch — determines prompt format and bridge target", "claude_implementer"),
    ("screenshot_required", "Screenshot required (Visual Approval)", "checkbox", 1,
     '{"trigger":"has_visual_changes","description":"Task involves frontend visual changes"}',
     "validation", 21, None,
     "Human must review screenshot before commit per 01_HUMAN.md", None),
    # ── Section: deployment (sort_order 22) ──────────────────────────
    ("deployment_strategy", "Deployment Strategy", "select", 0, None,
     "deployment", 22, None,
     "How the task should be deployed — standard step-by-step or accelerated skeleton-based", "standard"),
]
for field in compiler_fields_seed:
    cursor.execute("""
        INSERT OR IGNORE INTO prompt_compiler_fields
        (field_key, field_label, field_type, is_required, required_condition,
         section, sort_order, placeholder, help_text, default_value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, field)

# Deactivate model_selection — replaced by target_session (handoff 021)
cursor.execute("""
    UPDATE prompt_compiler_fields
    SET is_active = 0
    WHERE field_key = 'model_selection'
""")

# ── Handoff 021: Migrate target_role → target_session ──
# Idempotent UPDATE for existing databases that have the old target_role data.
# Only run if seed-data INSERT didn't already create target_session.
_target_session_exists = cursor.execute(
    "SELECT COUNT(*) FROM prompt_compiler_fields WHERE field_key = 'target_session'"
).fetchone()[0]
if not _target_session_exists:
    cursor.execute("""
        UPDATE prompt_compiler_fields
        SET field_key = 'target_session',
            field_label = 'Target tmux Session',
            help_text = 'Which tmux session receives the dispatch — determines prompt format and bridge target',
            default_value = 'claude_implementer'
        WHERE field_key = 'target_role'
    """)

    cursor.execute("""
        UPDATE prompt_compiler_field_options
        SET field_key = 'target_session'
        WHERE field_key = 'target_role'
    """)

# Update option values and labels for the migrated rows
cursor.execute("""
    UPDATE prompt_compiler_field_options
    SET option_value = 'claude_implementer',
        option_label = 'Implementor — code execution (claude_implementer)'
    WHERE field_key = 'target_session' AND option_value = 'Implementor'
""")

cursor.execute("""
    UPDATE prompt_compiler_field_options
    SET option_value = 'claude_architect',
        option_label = 'Architect — design & analysis (claude_architect)'
    WHERE field_key = 'target_session' AND option_value = 'Architect'
""")

cursor.execute("""
    UPDATE prompt_compiler_field_options
    SET option_value = 'claude_review',
        option_label = 'Review — validation & coordination (claude_review)'
    WHERE field_key = 'target_session' AND option_value = 'Review'
""")

# ── Handoff 015: Database-driven field options ──────────────────────

# Create table for select-field options (database-driven dropdowns)
cursor.execute("""
CREATE TABLE IF NOT EXISTS prompt_compiler_field_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_key TEXT NOT NULL,
    option_value TEXT NOT NULL,
    option_label TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    is_default INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    UNIQUE(field_key, option_value)
)
""")

# Clean up old duplicate data (handoff 015 reviewer fix — table originally
# lacked UNIQUE(field_key, option_value) constraint causing duplicates on re-run)
cursor.execute("DELETE FROM prompt_compiler_field_options")

# Seed field options for select fields
compiler_field_options_seed = [
    # ── target_session options ──
    ("target_session", "claude_implementer", "Implementor — code execution (claude_implementer)", 1, 1),
    ("target_session", "claude_architect", "Architect — design & analysis (claude_architect)", 2, 0),
    ("target_session", "claude_review", "Review — validation & coordination (claude_review)", 3, 0),
    # ── target_project options ──
    ("target_project", config.get_project_root(), "DPMtF-WebUI (Father, port 9130)", 1, 1),
    ("target_project", f"/home/svend/{config.get_child_projects()[0]}", "ENO (Child, port 9131)", 2, 0),
    ("target_project", f"/home/svend/{config.get_reference_projects()[0]}", "ai-pc-resource-webui-v3 (Reference, port 9123)", 3, 0),
    # ── father_project options ──
    ("father_project", "DPMtF-WebUI", "DPMtF-WebUI", 1, 1),
    # ── deployment_strategy options ──
    ("deployment_strategy", "standard", "Standard — step-by-step implementation via prompts", 1, 1),
    ("deployment_strategy", "accelerated", "Accelerated — skeleton-based fast deployment, then prompts for content", 2, 0),
]
for opt in compiler_field_options_seed:
    cursor.execute("""
        INSERT OR IGNORE INTO prompt_compiler_field_options
        (field_key, option_value, option_label, sort_order, is_default)
        VALUES (?, ?, ?, ?, ?)
    """, opt)

# Register compiler fields endpoints
endpoint_registry_2i_v2 = [
    ("ENDP-4000038", "prompt_compiler_fields_list", "/api/prompt-compiler-fields", "GET",
     "List all active prompt compiler fields grouped by section", "fields JSON with sections", "template_manager"),
    ("ENDP-4000039", "prompt_compiler_fields_create", "/api/prompt-compiler-fields", "POST",
     "Create a new prompt compiler field", "created field JSON", "template_manager"),
    ("ENDP-4000040", "prompt_compiler_field_options_list", "/api/prompt-compiler-fields", "GET",
     "List all active field options for select fields (attached to fields response)",
     "options JSON array per field", "template_manager"),
    ("ENDP-4000041", "prompt_compiler_field_options_create", "/api/prompt-compiler-field-options", "POST",
     "Create a new option for a compiler select field", "created option JSON", "template_manager"),
    ("ENDP-4000042", "prompt_compiler_assign_handoff_id", "/api/prompt-compiler/assign-handoff-id", "POST",
     "Assign a real handoff ID to a compiled prompt via bridge.py next-id, replace ??? placeholders, and write the handoff file to reviewtoimplementor/",
     "handoff assignment JSON with dispatch command", "template_manager"),
]
for endpoint in endpoint_registry_2i_v2:
    cursor.execute("""
        INSERT OR REPLACE INTO endpoint_registry
        (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, endpoint)

# Register bootstrap dataset for prompt_compiler_fields
cursor.execute("""
    INSERT OR REPLACE INTO bootstrap_dataset_registry
    (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("BDS-5000023", "prompt_compiler_fields", "prompt_compiler_fields",
    "Dynamic form fields for Prompt Compiler with conditional gating — governance-v2 compliant",
    "scripts/init_db.py", 20, 1, 1))

# Register bootstrap dataset for prompt_compiler_field_options (handoff 015)
cursor.execute("""
    INSERT OR REPLACE INTO bootstrap_dataset_registry
    (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("BDS-5000040", "prompt_compiler_field_options", "prompt_compiler_field_options",
    "Database-driven dropdown options for select fields in Prompt Compiler",
    "scripts/init_db.py", 7, 1, 1))

# ── Register new endpoints
endpoint_registry_2h = [
    ("ENDP-4000018", "prompt_templates_list", "/api/prompt-templates", "GET", "List all prompt templates", "templates JSON array", "template_manager"),
    ("ENDP-4000019", "prompt_templates_create", "/api/prompt-templates", "POST", "Create a new prompt template", "created template JSON", "template_manager"),
    ("ENDP-4000020", "prompt_templates_detail", "/api/prompt-templates/{template_key}", "GET", "Get a single template with rendered preview", "template JSON", "template_manager"),
    ("ENDP-4000021", "prompt_templates_update", "/api/prompt-templates/{template_key}", "PUT", "Update an existing template", "updated template JSON", "template_manager"),
    ("ENDP-4000022", "template_model_hitrates", "/api/prompt-templates/{template_key}/hitrate", "GET", "Per-model hitrate statistics for a template", "model_hitrates JSON array", "template_manager"),
]
for endpoint in endpoint_registry_2h:
    cursor.execute("""
        INSERT OR REPLACE INTO endpoint_registry
        (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, endpoint)

# Register bootstrap dataset
cursor.execute("""
    INSERT OR REPLACE INTO bootstrap_dataset_registry
    (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("BDS-5000015", "prompt_templates", "prompt_templates", "Prompt template registry for parametrisable prompt generation", "scripts/init_db.py", 6, 1, 1))

# Register bootstrap dataset for template_model_hitrates
cursor.execute("""
    INSERT OR REPLACE INTO bootstrap_dataset_registry
    (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("BDS-5000016", "template_model_hitrates", "template_model_hitrates", "Per-model hitrate statistics for prompt templates", "scripts/init_db.py", 1, 1, 1))

# Update phase tracking: 2G→completed, 2H→completed (redesign implemented)
cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2G", "Implementation Pattern Manager", "Capture successful implementation patterns from completed phases.", "completed", 31))

cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2H", "Prompt Template Manager", "Database-driven parametrisable templates with complexity tiers, capture sources, and per-model hitrate tracking. Redesigned based on Excel data analysis of 8 prompt runs.", "completed", 32))

# ── Phase 2J: Validation Automation ────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS validation_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key TEXT UNIQUE NOT NULL,
    rule_name TEXT NOT NULL,
    command TEXT NOT NULL,
    expected_output TEXT,
    severity TEXT NOT NULL DEFAULT 'error',
    applies_to TEXT NOT NULL DEFAULT 'all',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS validation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    phase_key TEXT,
    target_project TEXT,
    overall_verdict TEXT,
    rules_total INTEGER DEFAULT 0,
    rules_passed INTEGER DEFAULT 0,
    rules_failed INTEGER DEFAULT 0,
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    rule_key TEXT NOT NULL,
    passed INTEGER NOT NULL DEFAULT 0,
    actual_output TEXT,
    notes TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Seed the 7 baseline validation rules from 06_VALIDATION.md
validation_rules_seed = [
    ("val_backend_syntax", "Backend syntax check",
     "python3 -m py_compile app.py", "Exit code 0, no errors", "error", "python"),
    ("val_frontend_syntax", "Frontend syntax check",
     "node --check static/js/*.js", "Exit code 0 for each modified file", "error", "javascript"),
    ("val_shell_syntax", "Shell script syntax check",
     "find . -name '*.sh' -print0 | xargs -0 -r bash -n 2>&1 || echo 'no_shell_scripts_or_ok'", "Exit code 0", "error", "shell"),
    ("val_diff_scope", "Diff scope review",
     "git diff --stat", "Changes are within phase scope. No broad refactor.", "error", "all"),
    ("val_dependency_check", "Dependency check",
     "git diff requirements.txt || echo 'no_dependency_changes'", "No new dependencies added unless explicitly approved.", "error", "dependencies"),
    ("val_schema_change", "Schema change check",
     "git diff --name-only | grep -i 'sql\\|migration' || echo 'no_schema_changes'", "No schema changes unless phase explicitly allows them.", "error", "schema"),
    ("val_innerHTML", "Frontend innerHTML check",
     "grep -RIn 'innerHTML' static templates --exclude-dir=__pycache__ || echo 'no_innerHTML'",
     "Result must be no_innerHTML or an approved exception.", "error", "javascript"),
]
for rule in validation_rules_seed:
    cursor.execute("""
        INSERT OR IGNORE INTO validation_rules
        (rule_key, rule_name, command, expected_output, severity, applies_to)
        VALUES (?, ?, ?, ?, ?, ?)
    """, rule)

# Register new endpoint
cursor.execute("""
    INSERT OR REPLACE INTO endpoint_registry
    (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", ("ENDP-4000022", "validate", "/api/validate", "POST", "Run validation rules against a project and return structured report", "validation report JSON", "validation_panel"))

# Register bootstrap datasets
for ds in [
    ("BDS-5000016", "validation_rules", "validation_rules", "Validation rule definitions", "scripts/init_db.py", 7, 1, 1),
    ("BDS-5000017", "validation_runs", "validation_runs", "Validation run history", "scripts/init_db.py", 0, 0, 1),
    ("BDS-5000018", "validation_results", "validation_results", "Per-rule validation results", "scripts/init_db.py", 0, 0, 1),
]:
    cursor.execute("""
        INSERT OR REPLACE INTO bootstrap_dataset_registry
        (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ds)

# Update phase tracking: 2H→completed, 2I→completed, 2J→next
cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2H", "Prompt Template Manager", "Migrate static Markdown templates to database-driven parametrisable templates.", "completed", 32))

cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2I", "Local Prompt Compiler", "Generate prompts from templates + hitrate data + governance context.", "completed", 33))

cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2J", "Validation Automation", "Database-driven validation: validation_rules, validation_runs, validation_results tables.", "next", 34))

# ── Phase 2K: Git Sync Management ────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS git_sync_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_key TEXT UNIQUE NOT NULL,
    project_path TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'master',
    unpushed_commits INTEGER DEFAULT 0,
    last_push_timestamp TIMESTAMP,
    last_push_success INTEGER,
    last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS git_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id TEXT UNIQUE NOT NULL,
    project_key TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    details TEXT,
    success INTEGER NOT NULL DEFAULT 1,
    error_log TEXT,
    operator TEXT,
    operation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Seed DPMtF-WebUI's own git status
cursor.execute("""
    INSERT OR IGNORE INTO git_sync_status
    (project_key, project_path, branch, unpushed_commits)
    VALUES (?, ?, ?, ?)
""", ("DPMtF-WebUI", config.get_project_root(), "master", 0))

# Register new endpoints
endpoint_registry_2k = [
    ("ENDP-4000023", "git_status", "/api/git/status", "GET", "Read-only git sync status for tracked projects", "git status JSON", "git_panel"),
    ("ENDP-4000024", "git_operations", "/api/git/operations", "POST", "Record a git operation (commit/push) that happened externally", "operation JSON", "git_panel"),
    ("ENDP-4000025", "git_operations_list", "/api/git/operations", "GET", "List recent git operations", "operations JSON array", "git_panel"),
]
for endpoint in endpoint_registry_2k:
    cursor.execute("""
        INSERT OR REPLACE INTO endpoint_registry
        (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, endpoint)

# Register bootstrap datasets
for ds in [
    ("BDS-5000019", "git_sync_status", "git_sync_status", "Git sync status for tracked projects", "scripts/init_db.py", 1, 1, 1),
    ("BDS-5000020", "git_operations", "git_operations", "Git operation history log", "scripts/init_db.py", 0, 0, 1),
]:
    cursor.execute("""
        INSERT OR REPLACE INTO bootstrap_dataset_registry
        (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ds)

# Update phase tracking: 2J→completed, 2K→next
cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2J", "Validation Automation", "Database-driven validation: validation_rules, validation_runs, validation_results tables.", "completed", 34))

cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2K", "Git Sync Management", "Database-driven git tracking: git_sync_status, git_operations tables.", "next", 35))

# Update phase tracking: 2K→completed, 2L→next
cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2K", "Git Sync Management", "Database-driven git tracking: git_sync_status, git_operations tables.", "completed", 35))

cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2L", "Platform Adapter Framework", "PlatformAdapter base class for Linux/Windows abstraction. Linux implementation. Windows stub.", "next", 36))

# ── Phase 2M: Local Claude Code Session Manager ──────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS claude_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    model_used TEXT,
    project_context TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Register new endpoints
endpoint_registry_2m = [
    ("ENDP-4000026", "sessions_list", "/api/sessions", "GET", "List recent Claude Code sessions", "sessions JSON array", "session_panel"),
    ("ENDP-4000027", "sessions_create", "/api/sessions", "POST", "Record a new Claude Code session (started manually)", "session JSON", "session_panel"),
    ("ENDP-4000028", "sessions_current", "/api/sessions/current", "GET", "Check if a Claude Code session is currently active", "session JSON or null", "session_panel"),
    ("ENDP-4000029", "sessions_update", "/api/sessions/{session_id}", "PUT", "Update session status (stop, update activity)", "updated session JSON", "session_panel"),
]
for endpoint in endpoint_registry_2m:
    cursor.execute("""
        INSERT OR REPLACE INTO endpoint_registry
        (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, endpoint)

# Register bootstrap dataset
cursor.execute("""
    INSERT OR REPLACE INTO bootstrap_dataset_registry
    (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("BDS-5000021", "claude_sessions", "claude_sessions", "Claude Code session tracking for local model usage monitoring", "scripts/init_db.py", 0, 0, 1))

# Update phase tracking: 2L→completed, 2M→next
cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2L", "Platform Adapter Framework", "PlatformAdapter base class for Linux/Windows abstraction. Linux implementation. Windows stub.", "completed", 36))

cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2M", "Local Claude Code Session Manager", "Start/stop/monitor local Claude Code session via Ollama. Session status tracking in database.", "completed", 37))

# ── Phase 2N: Prompt→Implementer→Validator loop ─────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS workflow_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    phase_key TEXT NOT NULL,
    target_project TEXT NOT NULL,
    template_key TEXT,
    prompt_text TEXT,
    session_id TEXT,
    status TEXT NOT NULL DEFAULT 'prompt_compiled',
    validation_run_id TEXT,
    hitrate_run_id TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ── Phase 3C: User language preference ─────────────────
cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_language (
        user_id    TEXT    NOT NULL PRIMARY KEY,
        locale     TEXT    NOT NULL DEFAULT 'en-US',
        updated_at TEXT    DEFAULT (datetime('now'))
    )
""")

# Register new endpoints
endpoint_registry_2n = [
    ("ENDP-4000030", "workflow_start", "/api/workflow/start", "POST", "Compile prompt and start a workflow run through the P→I→V loop", "workflow run JSON", "workflow_panel"),
    ("ENDP-4000031", "workflow_status", "/api/workflow/{run_id}/status", "PUT", "Update workflow run status as it progresses through the loop", "updated run JSON", "workflow_panel"),
    ("ENDP-4000032", "workflow_runs", "/api/workflow/runs", "GET", "List recent workflow runs with status", "runs JSON array", "workflow_panel"),
]
for endpoint in endpoint_registry_2n:
    cursor.execute("""
        INSERT OR REPLACE INTO endpoint_registry
        (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, endpoint)

# Register bootstrap dataset
cursor.execute("""
    INSERT OR REPLACE INTO bootstrap_dataset_registry
    (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("BDS-5000022", "workflow_runs", "workflow_runs", "Workflow runs tracking the Prompt→Implementer→Validator loop", "scripts/init_db.py", 0, 0, 1))

# Update phase tracking: 2M→completed, 2N→next
cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2M", "Local Claude Code Session Manager", "Start/stop/monitor local Claude Code session via Ollama.", "completed", 37))

cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2N", "Prompt→Implementer→Validator loop", "DPMtF generates prompt → local Claude Code session implements → auto-validation runs → hitrate updated.", "next", 38))

# Seed default user language
cursor.execute("""
    INSERT OR IGNORE INTO user_language (user_id, locale, updated_at)
    VALUES ('default', 'en-US', datetime('now'))
""")

# Panel group collapse/expand user preferences
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_panel_groups (
    user_id    TEXT NOT NULL,
    group_name TEXT NOT NULL,
    state      TEXT NOT NULL DEFAULT 'expanded',
    is_visible INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, group_name)
)
""")

# Tilføj is_visible kolonne hvis den ikke findes (for eksisterende DB'er)
cursor.execute("PRAGMA table_info(user_panel_groups)")
_columns = [col[1] for col in cursor.fetchall()]
if "is_visible" not in _columns:
    cursor.execute("ALTER TABLE user_panel_groups ADD COLUMN is_visible INTEGER DEFAULT 1")

# ── Fase 3A: Panel Subgroups — Design subpatterns ──────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS panel_subgroups (
    subgroup_key  TEXT PRIMARY KEY NOT NULL,
    group_name    TEXT NOT NULL,
    title_da      TEXT NOT NULL,
    title_en      TEXT NOT NULL,
    sort_order    INTEGER DEFAULT 0,
    is_visible    INTEGER DEFAULT 1,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS panel_subgroup_mappings (
    slot_key      TEXT NOT NULL,
    subgroup_key  TEXT NOT NULL,
    PRIMARY KEY (slot_key, subgroup_key)
)
""")

# Seed data — DPMtF subgroups
panel_subgroups_seed = [
    ("sg_periodic_phase", "periodic", "Fase", "Phase", 1, 1),
    ("sg_periodic_planning", "periodic", "Planlægning", "Planning", 2, 1),
    ("sg_periodic_existing", "periodic", "Eksisterende Projekter", "Existing Projects", 3, 1),
]
for sg in panel_subgroups_seed:
    cursor.execute("""
        INSERT OR REPLACE INTO panel_subgroups
        (subgroup_key, group_name, title_da, title_en, sort_order, is_visible)
        VALUES (?, ?, ?, ?, ?, ?)
    """, sg)

# Seed data — DPMtF mappings
panel_subgroup_mappings_seed = [
    ("lbl_panel_phase_status", "sg_periodic_phase"),
    ("lbl_panel_project_planning", "sg_periodic_planning"),
]
for slot, sg in panel_subgroup_mappings_seed:
    cursor.execute("""
        INSERT OR REPLACE INTO panel_subgroup_mappings (slot_key, subgroup_key)
        VALUES (?, ?)
    """, (slot, sg))

# Sæt Journals is_visible = 0 (skjul Journals panel-group)
cursor.execute("""
    INSERT OR REPLACE INTO user_panel_groups (user_id, group_name, state, is_visible, updated_at)
    VALUES ('default', 'journals', 'expanded', 0, datetime('now'))
""")

# ── i18n labels — subgroup titles (tilføjes til de eksisterende lists) ──
# LBL-ID'er 1000116-118 for subgroup titles
ui_labels_subgroups = [
    ("LBL-1000116", "sg_periodic_phase_title", "main", "Fase", "Subgroup: Phase"),
    ("LBL-1000117", "sg_periodic_planning_title", "main", "Planlægning", "Subgroup: Planning"),
    ("LBL-1000118", "sg_periodic_existing_title", "main", "Eksisterende Projekter", "Subgroup: Existing Projects"),
]
for label in ui_labels_subgroups:
    cursor.execute("""
        INSERT OR REPLACE INTO ui_labels
        (label_id, label_key, label_domain, default_text, description)
        VALUES (?, ?, ?, ?, ?)
    """, label)

# Tilføj til translations
ui_label_translations_subgroups = [
    ("LBL-1000116", "da-DK", "Fase"),
    ("LBL-1000116", "en-US", "Phase"),
    ("LBL-1000117", "da-DK", "Planlægning"),
    ("LBL-1000117", "en-US", "Planning"),
    ("LBL-1000118", "da-DK", "Eksisterende Projekter"),
    ("LBL-1000118", "en-US", "Existing Projects"),
]
for translation in ui_label_translations_subgroups:
    cursor.execute("""
        INSERT OR REPLACE INTO ui_label_translations
        (label_id, locale, translated_text)
        VALUES (?, ?, ?)
    """, translation)

# Tilføj text slots for subgroup titles
ui_text_slots_subgroups = [
    ("sg_periodic_phase_title", "Subgroup: Phase title"),
    ("sg_periodic_planning_title", "Subgroup: Planning title"),
    ("sg_periodic_existing_title", "Subgroup: Existing Projects title"),
]
for slot_key, description in ui_text_slots_subgroups:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_text_slots (slot_key, description)
        VALUES (?, ?)
    """, (slot_key, description))

# Bind slots til labels
ui_text_slot_labels_subgroups = [
    ("sg_periodic_phase_title", "sg_periodic_phase_title"),
    ("sg_periodic_planning_title", "sg_periodic_planning_title"),
    ("sg_periodic_existing_title", "sg_periodic_existing_title"),
]
for slot_key, label_key in ui_text_slot_labels_subgroups:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key)
        VALUES (?, ?)
    """, (slot_key, label_key))

# Register new endpoints — panel structure + subgroup state
endpoint_registry_subgroups = [
    ("ENDP-4000036", "panel_structure", "/api/panel-structure", "GET", "Get full panel hierarchy with subgroups, visibility, and collapse states", "panel structure JSON", "panel_groups"),
    ("ENDP-4000037", "subgroup_state", "/api/panel-structure/subgroup-state", "POST", "Save collapse state for a panel subgroup", "state JSON", "panel_groups"),
]
for ep in endpoint_registry_subgroups:
    cursor.execute("""
        INSERT OR REPLACE INTO endpoint_registry
        (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ep)

# Register bootstrap datasets for subgroups
cursor.execute("""
    INSERT OR REPLACE INTO bootstrap_dataset_registry
    (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("BDS-5000024", "panel_subgroups", "panel_subgroups", "Panel subgroup definitions for nested expand/collapse", "scripts/init_db.py", 3, 0, 1))

cursor.execute("""
    INSERT OR REPLACE INTO bootstrap_dataset_registry
    (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("BDS-5000025", "panel_subgroup_mappings", "panel_subgroup_mappings", "Slot-to-subgroup mappings", "scripts/init_db.py", 2, 0, 1))

# ── Phase tracking: 2O-b → completed, 3A → next (Panel Subgroups) ────────

# ── Phase 2O-b: Comparison Runs ────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS comparison_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id TEXT UNIQUE NOT NULL,
    prompt_template_key TEXT,
    task_type TEXT NOT NULL,
    complexity_tier INTEGER NOT NULL,
    cloud_run_id TEXT,
    local_run_id TEXT,
    cloud_model TEXT NOT NULL,
    local_model TEXT NOT NULL,
    cloud_verdict TEXT,
    local_verdict TEXT,
    cloud_output_quality INTEGER,
    local_output_quality INTEGER,
    cloud_gov_compliance INTEGER,
    local_gov_compliance INTEGER,
    cloud_duration_seconds INTEGER,
    local_duration_seconds INTEGER,
    cloud_cost_eur REAL,
    local_cost_eur REAL,
    winner TEXT,
    conclusion TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Seed comparison data (from 2O comparisons)
comparison_runs_seed = [
    (
        "CMP-0001",
        "governance_audit_v3",
        "README.md v3-specifik",
        3,
        None, None,
        "deepseek-v4-pro:cloud", "qwen36-27b-q4km:latest",
        "completed", "completed",
        5, 5,
        100, 100,
        45, 15,
        0.01, 0.0,
        "cloud",
        "Cloud fandt 2 forbedringer den lokale model oversatte (broken link + stale DB description). Lokal korrekt no-op recognition."
    ),
    (
        "CMP-0002",
        "footer_build_info",
        "Footer med build-info",
        3,
        None, None,
        "deepseek-v4-pro:cloud", "qwen36-27b-q4km:latest",
        "completed", "completed",
        5, 5,
        100, 100,
        90, 20,
        0.02, 0.0,
        "tie",
        "Cloud byggede featuren (HTML+JS+CSS+seed). Lokal fandt og fikser cloud duplikat-bug. Hybrid-resultat."
    ),
    (
        "CMP-0003",
        "changelog_update",
        "CHANGELOG opdatering",
        2,
        None, None,
        "deepseek-v4-pro:cloud", "qwen36-27b-q4km:latest",
        "completed", "completed",
        5, 5,
        100, 100,
        120, 90,
        0.03, 0.0,
        "cloud",
        "Metodisk fix fra CMP-0002 virkede — fair sammenligning. Cloud byggede 8 entries. Lokal validerede no-op med thinking-overhead."
    ),
]
for cmp in comparison_runs_seed:
    cursor.execute("""
        INSERT OR REPLACE INTO comparison_runs
        (comparison_id, prompt_template_key, task_type, complexity_tier,
         cloud_run_id, local_run_id,
         cloud_model, local_model,
         cloud_verdict, local_verdict,
         cloud_output_quality, local_output_quality,
         cloud_gov_compliance, local_gov_compliance,
         cloud_duration_seconds, local_duration_seconds,
         cloud_cost_eur, local_cost_eur,
         winner, conclusion)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, cmp)

# Register new endpoints
endpoint_registry_2ob = [
    ("ENDP-4000033", "comparison_runs_list", "/api/comparison-runs", "GET", "List comparison runs with optional filters", "comparisons JSON array", "comparison_panel"),
    ("ENDP-4000034", "comparison_detail", "/api/comparison-runs/{comparison_id}", "GET", "Get single comparison run detail", "comparison run JSON", "comparison_panel"),
    ("ENDP-4000035", "comparison_create", "/api/comparison-runs", "POST", "Create new comparison run entry", "created run JSON", "comparison_panel"),
]
for endpoint in endpoint_registry_2ob:
    cursor.execute("""
        INSERT OR REPLACE INTO endpoint_registry
        (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, endpoint)

# Register bootstrap dataset
cursor.execute("""
    INSERT OR REPLACE INTO bootstrap_dataset_registry
    (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("BDS-5000023", "comparison_runs", "comparison_runs", "Comparison runs tracking cloud vs local model execution", "scripts/init_db.py", 0, 0, 1))

# Update phase tracking: 2O→completed, 2O-b→completed, 3A→next
cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2O", "Cloud vs Local Comparison", "Three parallel comparisons: README audit, footer build-info, CHANGELOG update. Cloud marginally better for thoroughness; local sufficient for no-op recognition.", "completed", 38))

cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2O-b", "Comparison Panel", "Comparison Runs panel in System Setup drawer with table view of cloud vs local results.", "completed", 39))

cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("3A", "Panel Subgroups", "Design subpatterns: nested expand/collapse subgroups within panel groups. Database-driven visibility and collapse states.", "next", 40))

# ── Register GET /api/available-languages endpoint (handoff 019, Phase 3B) ──
cursor.execute("""
    INSERT OR REPLACE INTO endpoint_registry
    (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", ("ENDP-4000043", "available_languages", "/api/available-languages", "GET",
    "List distinct locales with display names from ui_label_translations for dynamic language dropdown",
    "languages JSON array with locale and display_name", "language_selector"))

# ── Spor G: Deactivate obsolete Prompt Compiler fields ──
# Only 8 simplified fields remain active.
cursor.execute("""
    UPDATE prompt_compiler_fields
    SET is_active = 0
    WHERE field_key NOT IN (
        'target_session',
        'target_project',
        'phase_key',
        'goal',
        'deployment_strategy',
        'allowed_files',
        'forbidden_files'
    )
""")

# ── Spor G: Ensure the simplified fields exist ──
cursor.execute("""
    INSERT OR IGNORE INTO prompt_compiler_fields
    (field_key, field_label, field_type, section, is_required, sort_order, is_active)
    VALUES
    ('scope_gate_confirmed', 'Scope and Gate confirmed', 'checkbox', 'human_responsibility', 1, 5, 1)
""")

# ── Spor G: Keep only one active template ──
cursor.execute("""
    UPDATE prompt_templates
    SET is_active = 0
    WHERE template_key != 'tpl_implementation_small'
""")

# Spor G: Deactivate Periodic panel subgroups (Phase, Planning, Existing Projects)
cursor.execute("""
    UPDATE panel_subgroups
    SET is_visible = 0
    WHERE group_name = 'periodic'
""")

# Spor G: Hide empty panel groups (only Daily and Setup remain visible)
cursor.execute("""
    UPDATE user_panel_groups
    SET is_visible = 0
    WHERE group_name IN ('journals', 'reports', 'periodic')
""")

# ── Spor I: BridgeV002 Database Integration ────────────────

cursor.execute("""
CREATE TABLE IF NOT EXISTS bridge_roles (
    role_key TEXT PRIMARY KEY,
    tmux_session TEXT NOT NULL,
    start_cmd TEXT,
    model_type TEXT DEFAULT 'ollama',
    cloud_model TEXT,
    ollama_model TEXT,
    setup_script TEXT,
    teardown_script TEXT,
    deliver_error_msg TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bridge_flows (
    flow_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    step_order TEXT,
    is_default INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bridge_flow_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_key TEXT NOT NULL,
    step_key TEXT NOT NULL,
    from_role TEXT NOT NULL,
    to_role TEXT NOT NULL,
    deliverable_dir TEXT,
    deliverable_pattern TEXT,
    pre_dispatch_script TEXT,
    post_dispatch_script TEXT,
    error_msg TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (flow_key) REFERENCES bridge_flows(flow_key),
    UNIQUE(flow_key, step_key)
)
""")

cursor.executemany(
    """INSERT OR IGNORE INTO bridge_roles
       (role_key, tmux_session, start_cmd, model_type, cloud_model, ollama_model,
        setup_script, teardown_script, deliver_error_msg) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    [
        ("architect", "claude_architect",
         "cd {PROJECT_ROOT} && claude",
         "cloud", "deepseek-v4-pro:cloud", None,
         "scripts/bridgeV002/role_setup.py", "scripts/bridgeV002/role_teardown.py",
         "Architect session stopped unexpectedly. Check tmux status with 'tmux ls'."),
        ("implementer", "claude_implementer",
         "OPENCODE_CONFIG_DIR={PROJECT_ROOT}/.config/opencode-roles/implementer OPENCODE_CONFIG={PROJECT_ROOT}/.config/opencode-roles/implementer/opencode.json opencode",
         "ollama", None, "qwen3.6:27b-q4_K_M",
         "scripts/bridgeV002/role_setup.py", "scripts/bridgeV002/role_teardown.py",
         "Implementer session stopped unexpectedly. Start manually in tmux."),
        ("review_heavy1", "claude_review",
         "cd {PROJECT_ROOT} && claude",
         "cloud", "deepseek-v4-flash:cloud", None,
         "scripts/bridgeV002/role_setup.py", "scripts/bridgeV002/role_teardown.py",
         "Review session stopped unexpectedly. Check tmux status with 'tmux ls'."),
        ("review_heavy2", "claude_review_2",
         "cd {PROJECT_ROOT} && claude",
         "cloud", "deepseek-v4-flash:cloud", None,
         "scripts/bridgeV002/role_setup.py", "scripts/bridgeV002/role_teardown.py",
         "Review2 session stopped unexpectedly. Start manually."),
        ("reviewer_lite", "claude_review_lite",
         "OPENCODE_CONFIG_DIR={PROJECT_ROOT}/.config/opencode-roles/review OPENCODE_CONFIG={PROJECT_ROOT}/.config/opencode-roles/review/opencode.json opencode",
         "ollama", None, "qwen3.6:27b-q4_K_M",
         "scripts/bridgeV002/role_setup.py", "scripts/bridgeV002/role_teardown.py",
         "Lite review session stopped unexpectedly. Start manually in tmux."),
    ],
)

cursor.executemany(
    """INSERT OR IGNORE INTO bridge_flows
       (flow_key, name, description, step_order, is_default) VALUES (?, ?, ?, ?, ?)""",
    [
        ("heavy", "Heavy",
         "Full chain: Architect -> Implementer -> Review1 -> Review2 -> Human",
         "architect_to_implementer,implementer_to_review_heavy1,review_heavy1_to_heavy2,review_heavy2_to_human",
         1),
        ("simplified", "Simplified",
         "Direct: Implementer -> Review (no architect)",
         "architect_to_implementer,implementer_to_reviewer_lite,reviewer_lite_to_human",
         0),
        ("escalation", "Escalation",
         "Review escalates to Architect for architectural questions",
         "review_to_architect,architect_to_review_response",
         0),
    ],
)

cursor.executemany(
    """INSERT OR IGNORE INTO bridge_flow_steps
       (flow_key, step_key, from_role, to_role, deliverable_dir, deliverable_pattern,
        pre_dispatch_script, post_dispatch_script, error_msg, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    [
        ("heavy", "architect_to_implementer", "architect", "implementer",
         "reviewtoimplementor", "{ID}-handoff.md", None, None,
         "Failed to deliver handoff to implementer.", 1),
        ("heavy", "implementer_to_review_heavy1", "implementer", "review_heavy1",
         "implementertoreview", "{ID}-callback.md", None, None,
         "Failed to deliver completion signal to review.", 2),
        ("heavy", "review_heavy1_to_heavy2", "review_heavy1", "review_heavy2",
         "architecttoreview", "{ID}-callback.md", None, None,
         "Failed to deliver response to review2.", 3),
        ("heavy", "review_heavy2_to_human", "review_heavy2", "human",
         "implementertoreview", "{ID}-review-verdict.md", None, None,
         "Failed to deliver verdict. Present to Human manually.", 4),
        ("heavy", "review_to_architect_escalation", "review_heavy1", "architect",
         "reviewtoarchitect", "{ID}-handoff.md", None, None,
         "Escalation failed. Present question to Architect manually.", 5),
        ("simplified", "architect_to_implementer", "architect", "implementer",
         "reviewtoimplementor", "{ID}-handoff.md", None, None,
         "Failed to deliver handoff to implementer.", 1),
        ("simplified", "implementer_to_reviewer_lite", "implementer", "reviewer_lite",
         "implementertoreview", "{ID}-callback.md", None, None,
         "Failed to deliver completion signal to lite review.", 2),
        ("simplified", "reviewer_lite_to_human", "reviewer_lite", "human",
         "implementertoreview", "{ID}-review-verdict.md", None, None,
         "Failed to deliver verdict. Present to Human manually.", 3),
        ("escalation", "review_to_architect", "review_heavy1", "architect",
         "reviewtoarchitect", "{ID}-handoff.md", None, None,
         "Escalation failed. Present question to Architect manually.", 1),
        ("escalation", "architect_to_review_response", "architect", "review_heavy1",
          "architecttoreview", "{ID}-callback.md", None, None,
          "Failed to deliver architect answer back to review.", 2),
    ],
)

# ── Fase 2: Bridge Script Registry ────────────────────────

cursor.execute("""
CREATE TABLE IF NOT EXISTS bridge_scripts (
    script_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    path TEXT NOT NULL,
    stage TEXT CHECK(stage IN ('pre', 'post', 'both')),
    params_required TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.executemany(
    """INSERT OR IGNORE INTO bridge_scripts
       (script_key, name, description, path, stage, params_required) VALUES (?, ?, ?, ?, ?, ?)""",
    [
        ("role_setup", "Role Setup",
         "Start role session with fresh context, load correct model/tool",
         "scripts/bridgeV002/role_setup.py",
         "pre",
         "--role"),
        ("role_teardown", "Role Teardown",
         "Stop role session, unload Ollama model, free VRAM",
         "scripts/bridgeV002/role_teardown.py",
         "post",
         "--role,--force"),
        ("dispatch", "Dispatcher",
          "Universal role-to-role transition dispatcher",
          "scripts/bridgeV002/dispatch.py",
          "both",
          "--from-role,--to-role,--id,--flow,--step,--deliverable"),
        # ── No-Kill Phase 4: Generic Post-Dispatch Script ──
        ("post-dispatch-common", "Generic Post-Dispatch",
          "Validate deliverable + stop from_role Ollama model (convention-agnostic)",
          "scripts/bridgeV002/post-dispatch-common.py",
          "post",
          "--handoff-id,--step-key,--deliverable-dir,--deliverable-pattern,--from-role,--error-msg"),
    ],
)

# ── No-Kill Phase 4: Cleanup old script key ──
cursor.execute(
    "DELETE FROM bridge_scripts WHERE script_key = ?",
    ("archi01-imple01",)
)

# ── Fase 3: Bridge Convention Rules ────────────────────

cursor.execute("""
CREATE TABLE IF NOT EXISTS bridge_convention_rules (
    rule_key TEXT PRIMARY KEY,
    step_type TEXT NOT NULL,
    dir_template TEXT NOT NULL,
    pattern_template TEXT NOT NULL,
    error_template TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.executemany(
    """INSERT OR IGNORE INTO bridge_convention_rules
       (rule_key, step_type, dir_template, pattern_template, error_template)
       VALUES (?, ?, ?, ?, ?)""",
    [
        ("handoff", "Handoff",
         "reviewtoimplementor", "{ID}-handoff.md",
         "Failed to deliver handoff to {to_role}."),
        ("callback", "Callback",
         "implementertoreview", "{ID}-callback.md",
         "Failed to deliver callback to {to_role}."),
        ("escalation", "Escalation",
         "escalations", "{ID}-{from_role}-question.md",
         "Failed to escalate question to architect."),
        ("verdict", "Verdict",
         "implementertoreview", "{ID}-review-verdict.md",
         "Failed to deliver verdict. Present to Human manually."),
    ],
)

# Add rule_key FK column to bridge_flow_steps (idempotent — ignore if exists)
try:
    cursor.execute("""
    ALTER TABLE bridge_flow_steps ADD COLUMN rule_key TEXT REFERENCES bridge_convention_rules(rule_key)
    """)
except sqlite3.OperationalError:
    pass  # Column already exists

# Map existing steps to convention rules
cursor.executemany(
    """UPDATE bridge_flow_steps SET rule_key = ? WHERE step_key = ? AND flow_key = ?""",
    [
        # Heavy flow
        ("handoff", "architect_to_implementer", "heavy"),
        ("callback", "implementer_to_review_heavy1", "heavy"),
        ("callback", "review_heavy1_to_heavy2", "heavy"),
        ("verdict", "review_heavy2_to_human", "heavy"),
        ("callback", "review_to_architect_escalation", "heavy"),
        # Simplified flow
        ("handoff", "architect_to_implementer", "simplified"),
        ("callback", "implementer_to_reviewer_lite", "simplified"),
        ("verdict", "reviewer_lite_to_human", "simplified"),
        # Escalation flow
        ("handoff", "review_to_architect", "escalation"),
        ("callback", "architect_to_review_response", "escalation"),
    ],
)

# Update all heavy flow steps with generic post-dispatch script (Phase 4)
cursor.execute(
    "UPDATE bridge_flow_steps SET post_dispatch_script = ? WHERE step_key = ? AND flow_key = ?",
    ("post-dispatch-common", "architect_to_implementer", "heavy")
)
cursor.execute(
    "UPDATE bridge_flow_steps SET post_dispatch_script = ? WHERE step_key = ? AND flow_key = ?",
    ("post-dispatch-common", "implementer_to_review_heavy1", "heavy")
)
cursor.execute(
    "UPDATE bridge_flow_steps SET post_dispatch_script = ? WHERE step_key = ? AND flow_key = ?",
    ("post-dispatch-common", "review_heavy1_to_heavy2", "heavy")
)
cursor.execute(
    "UPDATE bridge_flow_steps SET post_dispatch_script = ? WHERE step_key = ? AND flow_key = ?",
    ("post-dispatch-common", "review_heavy2_to_human", "heavy")
)

# Add prompt_template column to bridge_convention_rules (idempotent)
try:
    cursor.execute("""
    ALTER TABLE bridge_convention_rules ADD COLUMN prompt_template TEXT DEFAULT ''
    """)
except sqlite3.OperationalError:
    pass  # Column already exists

# Seed verdict_feedback convention with enriched prompt_template
cursor.execute(
    """INSERT OR IGNORE INTO bridge_convention_rules
       (rule_key, step_type, dir_template, pattern_template, error_template, prompt_template)
       VALUES (?, ?, ?, ?, ?, ?)""",
    (
        "verdict_feedback",
        "VerdictFeedback",
        "implementertoreview",
        "{ID}-review-verdict.md",
        "Failed to deliver verdict feedback. Present to Architect manually.",
        "Read docs/StartUpNextSession.md first to restore design context. Then read {bridge_dir}/implementertoreview/{handoff_id}-review-verdict.md and evaluate whether the implementation matches the original design intent.",
    ),
)

# ── Handoff 131: DB-driven Callback, Escalation & Convention Content ───

# 2.1 bridge_flows — auto_complete_enabled
try:
    cursor.execute("""
        ALTER TABLE bridge_flows ADD COLUMN auto_complete_enabled INTEGER DEFAULT 0
    """)
except sqlite3.OperationalError:
    pass

# 2.2 bridge_flow_steps — auto_chain_to_next
try:
    cursor.execute("""
        ALTER TABLE bridge_flow_steps ADD COLUMN auto_chain_to_next INTEGER DEFAULT 0
    """)
except sqlite3.OperationalError:
    pass

# 2.3 bridge_flow_steps — validation_required
try:
    cursor.execute("""
        ALTER TABLE bridge_flow_steps ADD COLUMN validation_required INTEGER DEFAULT 0
    """)
except sqlite3.OperationalError:
    pass

# 2.4 removed (restart_policy dropped H132)

# 2.5 bridge_convention_rules — content_template
try:
    cursor.execute("""
        ALTER TABLE bridge_convention_rules ADD COLUMN content_template TEXT
    """)
except sqlite3.OperationalError:
    pass

# 2.6 bridge_convention_rules — validation_schema
try:
    cursor.execute("""
        ALTER TABLE bridge_convention_rules ADD COLUMN validation_schema TEXT
    """)
except sqlite3.OperationalError:
    pass

# 3.1 bridge_convention_rules — rule_type
try:
    cursor.execute("""
        ALTER TABLE bridge_convention_rules ADD COLUMN rule_type TEXT DEFAULT 'generic'
    """)
except sqlite3.OperationalError:
    pass

# 3.2 Update rule_type on existing convention rows (idempotent)
cursor.executemany(
    "UPDATE bridge_convention_rules SET rule_type = ? WHERE rule_key = ?",
    [
        ("callback_content", "callback"),
        ("handoff_content", "handoff"),
        ("verdict_content", "verdict"),
        ("verdict_feedback_content", "verdict_feedback"),
    ],
)

# 3.2 Seed content_template for existing rules (only when NULL)
cursor.execute(
    """UPDATE bridge_convention_rules
       SET content_template = ?
       WHERE rule_key = 'callback' AND content_template IS NULL""",
    (
        "<handoff>\n"
        "<role>{next_role}</role>\n"
        "<task>The previous role has completed their deliverable. Please review and proceed with the next step in the flow.\n\n"
        "## Previous Deliverable\n"
        "Handoff ID: {handoff_id}\n"
        "Source Role: {source_role}\n\n"
        "## Required Sections\n"
        "Your callback file must include these XML sections:\n"
        "- <role>: The target role for this handoff\n"
        "- <task>: What needs to be accomplished\n"
        "- <notification>: Summary of what was completed</task>\n"
        "<notification>The handoff from {source_role} (ID: {handoff_id}) has been completed.</notification>\n"
        "</handoff>",
    ),
)

cursor.execute(
    """UPDATE bridge_convention_rules
       SET content_template = ?
       WHERE rule_key = 'handoff' AND content_template IS NULL""",
    (
        "<handoff>\n"
        "<role>{next_role}</role>\n"
        "<task>The architect has prepared a handoff. Read and execute the referenced file.\n\n"
        "## Previous Deliverable\n"
        "Handoff ID: {handoff_id}\n"
        "Source Role: {source_role}\n\n"
        "## Required Sections\n"
        "Your callback file must include these XML sections:\n"
        "- <role>: The target role for this handoff\n"
        "- <task>: What needs to be accomplished\n"
        "- <constraint>: Any constraints that apply\n"
        "- <deliverable>: What you will produce</task>\n"
        "<notification>The handoff from {source_role} (ID: {handoff_id}) requires your implementation.</notification>\n"
        "</handoff>",
    ),
)

cursor.execute(
    """UPDATE bridge_convention_rules
       SET content_template = ?
       WHERE rule_key = 'verdict' AND content_template IS NULL""",
    (
        "<handoff>\n"
        "<role>{next_role}</role>\n"
        "<task>Produce a final verdict on the completed work.\n\n"
        "## Previous Deliverable\n"
        "Handoff ID: {handoff_id}\n"
        "Source Role: {source_role}\n\n"
        "## Required Sections\n"
        "Your verdict file must include these XML sections:\n"
        "- <role>: The target role for this handoff\n"
        "- <task>: What was reviewed\n"
        "- <verdict>: Pass or Fail with reasoning\n"
        "- <feedback>: Detailed feedback</task>\n"
        "<notification>The review from {source_role} (ID: {handoff_id}) requires a verdict.</notification>\n"
        "</handoff>",
    ),
)

cursor.execute(
    """UPDATE bridge_convention_rules
       SET content_template = ?
       WHERE rule_key = 'verdict_feedback' AND content_template IS NULL""",
    (
        "<handoff>\n"
        "<role>{next_role}</role>\n"
        "<task>Review verdict feedback has been generated. Evaluate whether the implementation matches design intent.\n\n"
        "## Previous Deliverable\n"
        "Handoff ID: {handoff_id}\n"
        "Source Role: {source_route}\n\n"
        "## Required Sections\n"
        "- <role>: The target role for this handoff\n"
        "- <task>: What was evaluated\n"
        "- <feedback>: Verdict feedback details</task>\n"
        "<notification>Verdict feedback from {source_role} (ID: {handoff_id}) requires evaluation.</notification>\n"
        "</handoff>",
    ),
)

# 3.3 Seed validation_schema for existing rules (only when NULL)
cursor.execute(
    """UPDATE bridge_convention_rules
       SET validation_schema = ?
       WHERE rule_key = 'callback' AND validation_schema IS NULL""",
    ('["<role>", "<task>", "<notification>"]',),
)

cursor.execute(
    """UPDATE bridge_convention_rules
       SET validation_schema = ?
       WHERE rule_key = 'handoff' AND validation_schema IS NULL""",
    ('["<role>", "<task>", "<constraint>", "<deliverable>"]',),
)

cursor.execute(
    """UPDATE bridge_convention_rules
       SET validation_schema = ?
       WHERE rule_key = 'verdict' AND validation_schema IS NULL""",
    ('["<role>", "<task>", "<verdict>", "<feedback>"]',),
)

cursor.execute(
    """UPDATE bridge_convention_rules
       SET validation_schema = ?
       WHERE rule_key = 'verdict_feedback' AND validation_schema IS NULL""",
    ('["<role>", "<task>", "<feedback>"]',),
)

# H137: Escalation convention — review → architect escalation prompts
cursor.execute(
    """UPDATE bridge_convention_rules
       SET content_template = ?
       WHERE rule_key = 'escalation' AND content_template IS NULL""",
    (
        "<handoff>\n"
        "<role>{next_role}</role>\n"
        "<task>A review role has escalated a question. Review the deliverable and provide your architect guidance.\n\n"
        "## Escalation Details\n"
        "Handoff ID: {handoff_id}\n"
        "Source Role: {source_role}\n\n"
        "## Required Sections\n"
        "- <role>: The target role for this response\n"
        "- <decision>: Your architect decision\n"
        "- <reasoning>: Why this decision\n"
        "- <action>: What the review should do next</task>\n"
        "<notification>The escalation from {source_role} (ID: {handoff_id}) requires your architect input.</notification>\n"
        "</handoff>",
    ),
)

cursor.execute(
    """UPDATE bridge_convention_rules
       SET validation_schema = ?
       WHERE rule_key = 'escalation' AND validation_schema IS NULL""",
    ('["<role>", "<decision>", "<reasoning>", "<action>"]',),
)

# H137: Set rule_type for escalation convention
cursor.execute(
    "UPDATE bridge_convention_rules SET rule_type = ? WHERE rule_key = ?",
    ("escalation_content", "escalation"),
)

# H140: governance_file column on bridge_roles — role-specific governance reference
try:
    cursor.execute("""
        ALTER TABLE bridge_roles ADD COLUMN governance_file TEXT DEFAULT NULL
    """)
except sqlite3.OperationalError:
    pass

# Seed governance_file for strict_review roles
cursor.execute(
    "UPDATE bridge_roles SET governance_file = ? WHERE role_key = ?",
    ("02_ARCHITECT.md", "archi01"),
)
cursor.execute(
    "UPDATE bridge_roles SET governance_file = ? WHERE role_key = ?",
    ("03_IMPLEMENTOR.md", "imple01"),
)
cursor.execute(
    "UPDATE bridge_roles SET governance_file = ? WHERE role_key = ?",
    ("04_REVIEW.md", "review01"),
)
cursor.execute(
    "UPDATE bridge_roles SET governance_file = ? WHERE role_key = ?",
    ("04_REVIEW.md", "review02"),
)

# ── Spor J: Bridge Setup UI i18n labels ────────────────────────────────

# Layer 3: ui_labels — semantic definitions
_bridge_setup_labels = [
    ("LBL-1000228", "lbl_bridge_panel_title", "main", "Bridge Setup", "Panel heading for Bridge Setup"),
    ("LBL-1000229", "lbl_bridge_status_available", "main", "Bridge configuration available", "Status: bridge tables exist"),
    ("LBL-1000230", "lbl_bridge_roles_title", "main", "Roles", "Roles section title"),
    ("LBL-1000231", "lbl_bridge_role_add", "main", "Add Role", "Add role button"),
    ("LBL-1000232", "lbl_bridge_role_key", "main", "Role Key", "Role key field label"),
    ("LBL-1000233", "lbl_bridge_tmux_session", "main", "Tmux Session", "Tmux session field label"),
    ("LBL-1000234", "lbl_bridge_start_cmd", "main", "Start Command", "Start command field label"),
    ("LBL-1000235", "lbl_bridge_model_type", "main", "Model Type", "Model type field label"),
    ("LBL-1000236", "lbl_bridge_cloud_model", "main", "Cloud Model", "Cloud model field label"),
    ("LBL-1000237", "lbl_bridge_ollama_model", "main", "Ollama Model", "Ollama model field label"),
    ("LBL-1000238", "lbl_bridge_setup_script", "main", "Setup Script", "Setup script field label"),
    ("LBL-1000239", "lbl_bridge_teardown_script", "main", "Teardown Script", "Teardown script field label"),
    ("LBL-1000240", "lbl_bridge_deliver_error_msg", "main", "Error Message", "Error message field label"),
    ("LBL-1000241", "lbl_bridge_flows_title", "main", "Flows", "Flows section title"),
    ("LBL-1000242", "lbl_bridge_flow_add", "main", "Add Flow", "Add flow button"),
    ("LBL-1000243", "lbl_bridge_flow_key", "main", "Flow Key", "Flow key field label"),
    ("LBL-1000244", "lbl_bridge_flow_name", "main", "Name", "Flow name field label"),
    ("LBL-1000245", "lbl_bridge_flow_description", "main", "Description", "Flow description field label"),
    ("LBL-1000246", "lbl_bridge_flow_step_order", "main", "Step Order", "Flow step order label"),
    ("LBL-1000247", "lbl_bridge_flow_is_default", "main", "Default", "Flow default flag label"),
    ("LBL-1000248", "lbl_bridge_steps_title", "main", "Steps", "Steps section title"),
    ("LBL-1000249", "lbl_bridge_step_from_role", "main", "From Role", "Step from role label"),
    ("LBL-1000250", "lbl_bridge_step_to_role", "main", "To Role", "Step to role label"),
    ("LBL-1000251", "lbl_bridge_step_key", "main", "Step Key", "Step key field label"),
    ("LBL-1000252", "lbl_bridge_deliverable_dir", "main", "Deliverable Directory", "Deliverable directory label"),
    ("LBL-1000253", "lbl_bridge_deliverable_pattern", "main", "Deliverable Pattern", "Deliverable pattern label"),
    ("LBL-1000254", "lbl_bridge_pre_dispatch_script", "main", "Pre-Dispatch Script", "Pre-dispatch script label"),
    ("LBL-1000255", "lbl_bridge_post_dispatch_script", "main", "Post-Dispatch Script", "Post-dispatch script label"),
    ("LBL-1000256", "lbl_bridge_step_sort_order", "main", "Sort Order", "Step sort order label"),
    ("LBL-1000257", "lbl_bridge_step_add", "main", "Add Step", "Add step button"),
    ("LBL-1000258", "lbl_bridge_step_remove", "main", "Remove Step", "Remove step button"),
    ("LBL-1000259", "lbl_bridge_edit", "main", "Edit", "Edit button"),
    ("LBL-1000260", "lbl_bridge_delete", "main", "Delete", "Delete button"),
    ("LBL-1000261", "lbl_bridge_save", "main", "Save", "Save button"),
    ("LBL-1000262", "lbl_bridge_cancel", "main", "Cancel", "Cancel button"),
    ("LBL-1000263", "lbl_bridge_active", "main", "Active", "Active status label"),
    ("LBL-1000264", "lbl_bridge_inactive", "main", "Inactive", "Inactive status label"),
    ("LBL-1000265", "lbl_bridge_created", "main", "Successfully created", "Success message: created"),
    ("LBL-1000266", "lbl_bridge_updated", "main", "Successfully updated", "Success message: updated"),
    ("LBL-1000267", "lbl_bridge_deleted", "main", "Successfully deleted", "Success message: deleted"),
    ("LBL-1000268", "lbl_bridge_export", "main", "Export", "Export button"),
    ("LBL-1000269", "lbl_bridge_export_all", "main", "Export All", "Export all button"),
    ("LBL-1000270", "lbl_bridge_export_roles", "main", "Export Roles", "Export roles button"),
    ("LBL-1000271", "lbl_bridge_export_flows", "main", "Export Flows", "Export flows button"),
    ("LBL-1000272", "lbl_bridge_ollama_option", "main", "Ollama", "Ollama option label"),
    ("LBL-1000273", "lbl_bridge_cloud_option", "main", "Cloud", "Cloud option label"),
    ("LBL-1000274", "lbl_bridge_no_roles", "main", "No roles configured", "Empty state: no roles"),
    ("LBL-1000275", "lbl_bridge_no_flows", "main", "No flows configured", "Empty state: no flows"),
    ("LBL-1000277", "lbl_bridge_select_flow", "main", "Select Flow", "Flow selector label"),
    ("LBL-1000278", "lbl_bridge_step_form_title", "main", "Add/Edit Step", "Step form modal title"),
    ("LBL-1000279", "lbl_bridge_rule_key", "main", "Convention Rule", "Rule key dropdown label"),
    ("LBL-1000280", "lbl_bridge_script_pre", "main", "Pre-Dispatch Script", "Pre-dispatch script dropdown"),
    ("LBL-1000281", "lbl_bridge_script_post", "main", "Post-Dispatch Script", "Post-dispatch script dropdown"),
    ("LBL-1000282", "lbl_bridge_auto_filled", "main", "(auto-filled)", "Indicator: field auto-filled from convention"),
    ("LBL-1000283", "lbl_bridge_rename", "main", "Rename", "Rename button"),
    ("LBL-1000284", "lbl_bridge_rename_invalid", "main", "No change made", "Error: renamed role key is same as original"),
    ("LBL-1000285", "lbl_bridge_renamed", "main", "Successfully renamed", "Success message: renamed"),
    ("LBL-1000286", "lbl_bridge_edit_role", "main", "Edit Role", "Full edit role form heading"),
    ("LBL-1000287", "lbl_bridge_flow_auto_complete", "main", "Auto-complete enabled", "Flow auto-complete checkbox label"),
    ("LBL-1000288", "lbl_bridge_step_auto_chain", "main", "Auto-chain to next", "Step auto-chain checkbox label"),
    ("LBL-1000289", "lbl_bridge_step_validation_required", "main", "Require validation", "Step validation required checkbox label"),
    ("LBL-1000295", "lbl_bridge_content_template", "main", "Content Template", "Convention content template textarea label"),
    ("LBL-1000296", "lbl_bridge_validation_schema", "main", "Validation Schema (JSON array)", "Convention validation schema textarea label"),
    ("LBL-1000297", "lbl_bridge_conventions_title", "main", "Conventions", "Bridge conventions admin section title"),
    ("LBL-1000298", "lbl_bridge_governance_file", "main", "Governance File", "Governance file reference field label"),
]
for label in _bridge_setup_labels:
    cursor.execute("""
        INSERT OR REPLACE INTO ui_labels
        (label_id, label_key, label_domain, default_text, description)
        VALUES (?, ?, ?, ?, ?)
    """, label)

# Layer 4: ui_label_translations — locale-specific text
_bridge_setup_translations = [
    ("LBL-1000228", "en-US", "Bridge Setup"),
    ("LBL-1000228", "da-DK", "Bridge Opsætning"),
    ("LBL-1000229", "en-US", "Bridge configuration available"),
    ("LBL-1000229", "da-DK", "Bridge-konfiguration tilgængelig"),
    ("LBL-1000230", "en-US", "Roles"),
    ("LBL-1000230", "da-DK", "Roller"),
    ("LBL-1000231", "en-US", "Add Role"),
    ("LBL-1000231", "da-DK", "Tilføj Rolle"),
    ("LBL-1000232", "en-US", "Role Key"),
    ("LBL-1000232", "da-DK", "Rollemnøgle"),
    ("LBL-1000233", "en-US", "Tmux Session"),
    ("LBL-1000233", "da-DK", "Tmux Session"),
    ("LBL-1000234", "en-US", "Start Command"),
    ("LBL-1000234", "da-DK", "Startkommando"),
    ("LBL-1000235", "en-US", "Model Type"),
    ("LBL-1000235", "da-DK", "Modeltype"),
    ("LBL-1000236", "en-US", "Cloud Model"),
    ("LBL-1000236", "da-DK", "Cloud Model"),
    ("LBL-1000237", "en-US", "Ollama Model"),
    ("LBL-1000237", "da-DK", "Ollama Model"),
    ("LBL-1000238", "en-US", "Setup Script"),
    ("LBL-1000238", "da-DK", "Opsætningscript"),
    ("LBL-1000239", "en-US", "Teardown Script"),
    ("LBL-1000239", "da-DK", "Rydningsscript"),
    ("LBL-1000240", "en-US", "Error Message"),
    ("LBL-1000240", "da-DK", "Fejlbesked"),
    ("LBL-1000241", "en-US", "Flows"),
    ("LBL-1000241", "da-DK", "Arbejdsflows"),
    ("LBL-1000242", "en-US", "Add Flow"),
    ("LBL-1000242", "da-DK", "Tilføj Flow"),
    ("LBL-1000243", "en-US", "Flow Key"),
    ("LBL-1000243", "da-DK", "Flow-nøgle"),
    ("LBL-1000244", "en-US", "Name"),
    ("LBL-1000244", "da-DK", "Navn"),
    ("LBL-1000245", "en-US", "Description"),
    ("LBL-1000245", "da-DK", "Beskrivelse"),
    ("LBL-1000246", "en-US", "Step Order"),
    ("LBL-1000246", "da-DK", "Trinrækkefølge"),
    ("LBL-1000247", "en-US", "Default"),
    ("LBL-1000247", "da-DK", "Standard"),
    ("LBL-1000248", "en-US", "Steps"),
    ("LBL-1000248", "da-DK", "Trin"),
    ("LBL-1000249", "en-US", "From Role"),
    ("LBL-1000249", "da-DK", "Fra Rolle"),
    ("LBL-1000250", "en-US", "To Role"),
    ("LBL-1000250", "da-DK", "Til Rolle"),
    ("LBL-1000251", "en-US", "Step Key"),
    ("LBL-1000251", "da-DK", "Trin-nøgle"),
    ("LBL-1000252", "en-US", "Deliverable Directory"),
    ("LBL-1000252", "da-DK", "Leveringsmappe"),
    ("LBL-1000253", "en-US", "Deliverable Pattern"),
    ("LBL-1000253", "da-DK", "Leveringsmønster"),
    ("LBL-1000254", "en-US", "Pre-Dispatch Script"),
    ("LBL-1000254", "da-DK", "Forudsendelsesscript"),
    ("LBL-1000255", "en-US", "Post-Dispatch Script"),
    ("LBL-1000255", "da-DK", "Efterafsendelsscript"),
    ("LBL-1000256", "en-US", "Sort Order"),
    ("LBL-1000256", "da-DK", "Sorteringsrækkefølge"),
    ("LBL-1000257", "en-US", "Add Step"),
    ("LBL-1000257", "da-DK", "Tilføj Trin"),
    ("LBL-1000258", "en-US", "Remove Step"),
    ("LBL-1000258", "da-DK", "Fjern Trin"),
    ("LBL-1000259", "en-US", "Edit"),
    ("LBL-1000259", "da-DK", "Rediger"),
    ("LBL-1000260", "en-US", "Delete"),
    ("LBL-1000260", "da-DK", "Slet"),
    ("LBL-1000261", "en-US", "Save"),
    ("LBL-1000261", "da-DK", "Gem"),
    ("LBL-1000262", "en-US", "Cancel"),
    ("LBL-1000262", "da-DK", "Annuller"),
    ("LBL-1000263", "en-US", "Active"),
    ("LBL-1000263", "da-DK", "Aktiv"),
    ("LBL-1000264", "en-US", "Inactive"),
    ("LBL-1000264", "da-DK", "Inaktiv"),
    ("LBL-1000265", "en-US", "Successfully created"),
    ("LBL-1000265", "da-DK", "Oprettet succesfuldt"),
    ("LBL-1000266", "en-US", "Successfully updated"),
    ("LBL-1000266", "da-DK", "Opdateret succesfuldt"),
    ("LBL-1000267", "en-US", "Successfully deleted"),
    ("LBL-1000267", "da-DK", "Slettet succesfuldt"),
    ("LBL-1000268", "en-US", "Export"),
    ("LBL-1000268", "da-DK", "Eksportér"),
    ("LBL-1000269", "en-US", "Export All"),
    ("LBL-1000269", "da-DK", "Eksportér Alt"),
    ("LBL-1000270", "en-US", "Export Roles"),
    ("LBL-1000270", "da-DK", "Eksportér Roller"),
    ("LBL-1000271", "en-US", "Export Flows"),
    ("LBL-1000271", "da-DK", "Eksportér Flows"),
    ("LBL-1000272", "en-US", "Ollama"),
    ("LBL-1000272", "da-DK", "Ollama"),
    ("LBL-1000273", "en-US", "Cloud"),
    ("LBL-1000273", "da-DK", "Cloud"),
    ("LBL-1000274", "en-US", "No roles configured"),
    ("LBL-1000274", "da-DK", "Ingen roller konfigureret"),
    ("LBL-1000275", "en-US", "No flows configured"),
    ("LBL-1000275", "da-DK", "Ingen flows konfigureret"),
    # Steps UI labels - da-DK translations
    ("LBL-1000277", "en-US", "Select Flow"),
    ("LBL-1000277", "da-DK", "Vælg Flow"),
    ("LBL-1000278", "en-US", "Add/Edit Step"),
    ("LBL-1000278", "da-DK", "Tilføj/Redigér Trin"),
    ("LBL-1000279", "en-US", "Convention Rule"),
    ("LBL-1000279", "da-DK", "Konvention Regel"),
    ("LBL-1000280", "en-US", "Pre-Dispatch Script"),
    ("LBL-1000280", "da-DK", "Forud-script"),
    ("LBL-1000281", "en-US", "Post-Dispatch Script"),
    ("LBL-1000281", "da-DK", "Efter-script"),
    ("LBL-1000282", "en-US", "(auto-filled)"),
    ("LBL-1000282", "da-DK", "(auto-udfyldt)"),
    ("LBL-1000283", "en-US", "Rename"),
    ("LBL-1000283", "da-DK", "Omdøb"),
    ("LBL-1000284", "en-US", "No change made"),
    ("LBL-1000284", "da-DK", "Ingen ændring foretaget"),
    ("LBL-1000285", "en-US", "Successfully renamed"),
    ("LBL-1000285", "da-DK", "Omdøbet succesfuldt"),
    ("LBL-1000286", "en-US", "Edit Role"),
    ("LBL-1000286", "da-DK", "Rediger rolle"),
    ("LBL-1000287", "en-US", "Auto-complete enabled"),
    ("LBL-1000287", "da-DK", "Auto-fuldfør aktiveret"),
    ("LBL-1000288", "en-US", "Auto-chain to next"),
    ("LBL-1000288", "da-DK", "Auto-kæd videre"),
    ("LBL-1000289", "en-US", "Require validation"),
    ("LBL-1000289", "da-DK", "Kræv validering"),
    ("LBL-1000295", "en-US", "Content Template"),
    ("LBL-1000295", "da-DK", "Indholdsskabelon"),
    ("LBL-1000296", "en-US", "Validation Schema (JSON array)"),
    ("LBL-1000296", "da-DK", "Valideringsschema (JSON-array)"),
    ("LBL-1000297", "en-US", "Conventions"),
    ("LBL-1000297", "da-DK", "Konventioner"),
    ("LBL-1000298", "en-US", "Governance File"),
    ("LBL-1000298", "da-DK", "Styrefil"),
]
for translation in _bridge_setup_translations:
    cursor.execute("""
        INSERT OR REPLACE INTO ui_label_translations
        (label_id, locale, translated_text)
        VALUES (?, ?, ?)
    """, translation)

# Layer 1: ui_text_slots — position IDs
_bridge_setup_slots = [
    ("lbl_bridge_panel_title", "Bridge Setup panel heading"),
    ("lbl_bridge_status_available", "Bridge status available message"),
    ("lbl_bridge_roles_title", "Roles section title"),
    ("lbl_bridge_role_add", "Add role button"),
    ("lbl_bridge_role_key", "Role key field label"),
    ("lbl_bridge_tmux_session", "Tmux session field label"),
    ("lbl_bridge_start_cmd", "Start command field label"),
    ("lbl_bridge_model_type", "Model type field label"),
    ("lbl_bridge_cloud_model", "Cloud model field label"),
    ("lbl_bridge_ollama_model", "Ollama model field label"),
    ("lbl_bridge_setup_script", "Setup script field label"),
    ("lbl_bridge_teardown_script", "Teardown script field label"),
    ("lbl_bridge_deliver_error_msg", "Error message field label"),
    ("lbl_bridge_flows_title", "Flows section title"),
    ("lbl_bridge_flow_add", "Add flow button"),
    ("lbl_bridge_flow_key", "Flow key field label"),
    ("lbl_bridge_flow_name", "Flow name field label"),
    ("lbl_bridge_flow_description", "Flow description field label"),
    ("lbl_bridge_flow_step_order", "Flow step order label"),
    ("lbl_bridge_flow_is_default", "Flow default flag label"),
    ("lbl_bridge_steps_title", "Steps section title"),
    ("lbl_bridge_step_from_role", "Step from role label"),
    ("lbl_bridge_step_to_role", "Step to role label"),
    ("lbl_bridge_step_key", "Step key field label"),
    ("lbl_bridge_deliverable_dir", "Deliverable directory label"),
    ("lbl_bridge_deliverable_pattern", "Deliverable pattern label"),
    ("lbl_bridge_pre_dispatch_script", "Pre-dispatch script label"),
    ("lbl_bridge_post_dispatch_script", "Post-dispatch script label"),
    ("lbl_bridge_step_sort_order", "Step sort order label"),
    ("lbl_bridge_step_add", "Add step button"),
    ("lbl_bridge_step_remove", "Remove step button"),
    ("lbl_bridge_edit", "Edit button"),
    ("lbl_bridge_delete", "Delete button"),
    ("lbl_bridge_save", "Save button"),
    ("lbl_bridge_cancel", "Cancel button"),
    ("lbl_bridge_active", "Active status label"),
    ("lbl_bridge_inactive", "Inactive status label"),
    ("lbl_bridge_created", "Success message: created"),
    ("lbl_bridge_updated", "Success message: updated"),
    ("lbl_bridge_deleted", "Success message: deleted"),
    ("lbl_bridge_export", "Export button"),
    ("lbl_bridge_export_all", "Export all button"),
    ("lbl_bridge_export_roles", "Export roles button"),
    ("lbl_bridge_export_flows", "Export flows button"),
    ("lbl_bridge_ollama_option", "Ollama option label"),
    ("lbl_bridge_cloud_option", "Cloud option label"),
    ("lbl_bridge_no_roles", "Empty state: no roles"),
    ("lbl_bridge_no_flows", "Empty state: no flows"),
    ("lbl_bridge_rename", "Rename button"),
    ("lbl_bridge_rename_invalid", "Error: rename invalid"),
    ("lbl_bridge_renamed", "Success message: renamed"),
    ("lbl_bridge_edit_role", "Full edit role form heading"),
    ("lbl_bridge_start_tmux", "Start tmux button for flow"),
    ("lbl_bridge_starting", "Label shown while starting tmux"),
    ("lbl_bridge_governance_file", "Governance file reference field label"),
]
for slot_key, description in _bridge_setup_slots:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_text_slots (slot_key, description)
        VALUES (?, ?)
    """, (slot_key, description))

# Layer 2: ui_text_slot_labels — slot-to-label mapping
_bridge_setup_slot_labels = [
    ("lbl_bridge_panel_title", "lbl_bridge_panel_title"),
    ("lbl_bridge_status_available", "lbl_bridge_status_available"),
    ("lbl_bridge_roles_title", "lbl_bridge_roles_title"),
    ("lbl_bridge_role_add", "lbl_bridge_role_add"),
    ("lbl_bridge_role_key", "lbl_bridge_role_key"),
    ("lbl_bridge_tmux_session", "lbl_bridge_tmux_session"),
    ("lbl_bridge_start_cmd", "lbl_bridge_start_cmd"),
    ("lbl_bridge_model_type", "lbl_bridge_model_type"),
    ("lbl_bridge_cloud_model", "lbl_bridge_cloud_model"),
    ("lbl_bridge_ollama_model", "lbl_bridge_ollama_model"),
    ("lbl_bridge_setup_script", "lbl_bridge_setup_script"),
    ("lbl_bridge_teardown_script", "lbl_bridge_teardown_script"),
    ("lbl_bridge_deliver_error_msg", "lbl_bridge_deliver_error_msg"),
    ("lbl_bridge_flows_title", "lbl_bridge_flows_title"),
    ("lbl_bridge_flow_add", "lbl_bridge_flow_add"),
    ("lbl_bridge_flow_key", "lbl_bridge_flow_key"),
    ("lbl_bridge_flow_name", "lbl_bridge_flow_name"),
    ("lbl_bridge_flow_description", "lbl_bridge_flow_description"),
    ("lbl_bridge_flow_step_order", "lbl_bridge_flow_step_order"),
    ("lbl_bridge_flow_is_default", "lbl_bridge_flow_is_default"),
    ("lbl_bridge_steps_title", "lbl_bridge_steps_title"),
    ("lbl_bridge_step_from_role", "lbl_bridge_step_from_role"),
    ("lbl_bridge_step_to_role", "lbl_bridge_step_to_role"),
    ("lbl_bridge_step_key", "lbl_bridge_step_key"),
    ("lbl_bridge_deliverable_dir", "lbl_bridge_deliverable_dir"),
    ("lbl_bridge_deliverable_pattern", "lbl_bridge_deliverable_pattern"),
    ("lbl_bridge_pre_dispatch_script", "lbl_bridge_pre_dispatch_script"),
    ("lbl_bridge_post_dispatch_script", "lbl_bridge_post_dispatch_script"),
    ("lbl_bridge_step_sort_order", "lbl_bridge_step_sort_order"),
    ("lbl_bridge_step_add", "lbl_bridge_step_add"),
    ("lbl_bridge_step_remove", "lbl_bridge_step_remove"),
    ("lbl_bridge_edit", "lbl_bridge_edit"),
    ("lbl_bridge_delete", "lbl_bridge_delete"),
    ("lbl_bridge_save", "lbl_bridge_save"),
    ("lbl_bridge_cancel", "lbl_bridge_cancel"),
    ("lbl_bridge_active", "lbl_bridge_active"),
    ("lbl_bridge_inactive", "lbl_bridge_inactive"),
    ("lbl_bridge_created", "lbl_bridge_created"),
    ("lbl_bridge_updated", "lbl_bridge_updated"),
    ("lbl_bridge_deleted", "lbl_bridge_deleted"),
    ("lbl_bridge_export", "lbl_bridge_export"),
    ("lbl_bridge_export_all", "lbl_bridge_export_all"),
    ("lbl_bridge_export_roles", "lbl_bridge_export_roles"),
    ("lbl_bridge_export_flows", "lbl_bridge_export_flows"),
    ("lbl_bridge_ollama_option", "lbl_bridge_ollama_option"),
    ("lbl_bridge_cloud_option", "lbl_bridge_cloud_option"),
    ("lbl_bridge_no_roles", "lbl_bridge_no_roles"),
    ("lbl_bridge_no_flows", "lbl_bridge_no_flows"),
    ("lbl_bridge_select_flow", "lbl_bridge_select_flow"),
    ("lbl_bridge_step_form_title", "lbl_bridge_step_form_title"),
    ("lbl_bridge_rule_key", "lbl_bridge_rule_key"),
    ("lbl_bridge_script_pre", "lbl_bridge_script_pre"),
    ("lbl_bridge_script_post", "lbl_bridge_script_post"),
    ("lbl_bridge_auto_filled", "lbl_bridge_auto_filled"),
    ("lbl_bridge_rename", "lbl_bridge_rename"),
    ("lbl_bridge_rename_invalid", "lbl_bridge_rename_invalid"),
    ("lbl_bridge_renamed", "lbl_bridge_renamed"),
    ("lbl_bridge_edit_role", "lbl_bridge_edit_role"),
    ("lbl_bridge_start_tmux", "lbl_bridge_start_tmux"),
    ("lbl_bridge_starting", "lbl_bridge_starting"),
    ("lbl_bridge_governance_file", "lbl_bridge_governance_file"),
]
for slot_key, label_key in _bridge_setup_slot_labels:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key)
        VALUES (?, ?)
    """, (slot_key, label_key))

# ── Bridge ID Counters (DB-driven, flow-isolated) ────────────────────

cursor.execute("""
CREATE TABLE IF NOT EXISTS bridge_id_counters (
    flow_key TEXT PRIMARY KEY,
    next_id  INTEGER NOT NULL DEFAULT 1
)
""")

# Seed: one counter per active flow — auto-create via INSERT OR IGNORE.
# Human updates next_id when starting a new flow cycle.
cursor.execute(
    """INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id)
       VALUES (?, ?)""",
    ("strict_review", 139),
)

# Commit changes and close connection
conn.commit()
conn.close()

print("Database initialized successfully!")