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
    ("1L", "Slim Frontend File Structure", "Prepare frontend structure for slimming", "next", 11),
    ("1M", "Extract Frontend JavaScript", "Move JS to static files", "planned", 12),
    ("1N", "Extract Frontend CSS and Theme Foundation", "Move CSS to static files", "planned", 13),
    ("1O", "System Setup Drawer Shell", "Add system setup drawer", "planned", 14),
    ("1P", "Endpoint Registry Schema", "Create endpoint registry schema", "planned", 15),
    ("1Q", "Endpoint Registry UI", "Add endpoint registry UI", "planned", 16),
    ("1R", "Endpoint Runtime Status Checks", "Check endpoint status", "planned", 17),
    ("1S", "Localization / i18n Language Schema", "Create language schema", "planned", 18),
    ("1T", "Localization / i18n Label Registry", "Create label registry", "planned", 19),
    ("1U", "Migrate Frontend Labels to en-US", "Migrate labels to en-US", "planned", 20),
    ("1V", "Language Selection / URL Language Tag", "Add language selection", "planned", 21),
    ("1W", "Configuration-driven Wrappers and Scripts Review", "Review wrappers/scripts", "planned", 22),
    ("1X", "Project Skeleton Prompt after Architecture Foundation", "Generate skeleton prompt", "planned", 23),
    ("2A", "Controlled Project Folder Creation", "Create project folders safely", "planned", 24),
    ("2B", "Selected Panels Static Mockup", "Generate static mockup", "planned", 25),
    ("2C", "CLAUDE.md / SKILL.md Baseline Manager", "Manage baselines", "planned", 26),
    ("2D", "Prompt Run Review", "Manual review form", "planned", 27),
    ("2E", "Hitrate Scoring", "Score prompt effectiveness", "planned", 28),
    ("2F", "Implementation Patterns", "Store implementation patterns", "planned", 29),
    ("2G", "Prompt Template Manager", "Manage prompt templates", "planned", 30),
    ("2H", "Local Prompt Compiler", "Use local models for prompts", "planned", 31),
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

# Commit changes and close connection
conn.commit()
conn.close()

print("Database initialized successfully!")