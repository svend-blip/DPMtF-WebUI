CREATE TABLE IF NOT EXISTS app_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_profile_panels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER,
    panel_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES app_profiles (id),
    FOREIGN KEY (panel_id) REFERENCES frontend_panels (id)
);

CREATE TABLE IF NOT EXISTS phase_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_key TEXT UNIQUE NOT NULL,
    phase_title TEXT NOT NULL,
    phase_description TEXT,
    phase_state TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
);

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
);

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
);

CREATE TABLE IF NOT EXISTS ui_label_translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label_id TEXT NOT NULL,
    locale TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(label_id, locale)
);

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
);

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
);

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
);

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
);

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
);

CREATE TABLE IF NOT EXISTS ui_text_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ui_text_slot_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key TEXT NOT NULL,
    label_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(slot_key, label_key)
);

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
);

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
);

CREATE TABLE IF NOT EXISTS validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    rule_key TEXT NOT NULL,
    passed INTEGER NOT NULL DEFAULT 0,
    actual_output TEXT,
    notes TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
);

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
);

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
);

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
);

CREATE TABLE IF NOT EXISTS user_language (
        user_id    TEXT    NOT NULL PRIMARY KEY,
        locale     TEXT    NOT NULL DEFAULT 'en-US',
        updated_at TEXT    DEFAULT (datetime('now'))
    );

CREATE TABLE IF NOT EXISTS user_panel_groups (
    user_id    TEXT NOT NULL,
    group_name TEXT NOT NULL,
    state      TEXT NOT NULL DEFAULT 'expanded',
    updated_at TEXT DEFAULT (datetime('now')), is_visible INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, group_name)
);

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
);

CREATE TABLE IF NOT EXISTS panel_subgroups (
    subgroup_key  TEXT PRIMARY KEY NOT NULL,
    group_name    TEXT NOT NULL,
    title_da      TEXT NOT NULL,
    title_en      TEXT NOT NULL,
    sort_order    INTEGER DEFAULT 0,
    is_visible    INTEGER DEFAULT 1,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS panel_subgroup_mappings (
    slot_key      TEXT NOT NULL,
    subgroup_key  TEXT NOT NULL,
    PRIMARY KEY (slot_key, subgroup_key)
);

CREATE TABLE IF NOT EXISTS bridge_roles (
    role_key TEXT PRIMARY KEY,
    tmux_session TEXT NOT NULL,
    model_type TEXT DEFAULT 'ollama',
    cloud_model TEXT,
    ollama_model TEXT,
    setup_script TEXT,
    teardown_script TEXT,
    deliver_error_msg TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
, restart_policy TEXT DEFAULT 'none', governance_file TEXT DEFAULT NULL, role_type TEXT DEFAULT 'agent', enter_command TEXT DEFAULT 'default', default_runtime TEXT DEFAULT NULL, default_provider TEXT DEFAULT NULL, default_model TEXT DEFAULT NULL, config_dir TEXT DEFAULT NULL, primary_output_type TEXT DEFAULT NULL);

CREATE TABLE IF NOT EXISTS bridge_flows (
    flow_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    step_order TEXT,
    is_default INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
, auto_complete_enabled INTEGER DEFAULT 0, use_machine_profile INTEGER DEFAULT 0);

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
    is_active INTEGER DEFAULT 1, rule_key TEXT REFERENCES bridge_convention_rules(rule_key), auto_chain_to_next INTEGER DEFAULT 0, validation_required INTEGER DEFAULT 0, runtime_override TEXT DEFAULT NULL, provider_override TEXT DEFAULT NULL, model_override TEXT DEFAULT NULL,
    FOREIGN KEY (flow_key) REFERENCES bridge_flows(flow_key),
    UNIQUE(flow_key, step_key)
);

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
);

CREATE TABLE IF NOT EXISTS bridge_convention_rules (
    rule_key TEXT PRIMARY KEY,
    step_type TEXT NOT NULL,
    dir_template TEXT NOT NULL,
    pattern_template TEXT NOT NULL,
    error_template TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
, prompt_template TEXT DEFAULT '', content_template TEXT, validation_schema TEXT, rule_type TEXT DEFAULT 'generic');

CREATE TABLE IF NOT EXISTS bridge_id_counters (
    flow_key TEXT PRIMARY KEY,
    next_id  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_preferences (
        user_id TEXT NOT NULL,
        pref_key TEXT NOT NULL,
        pref_value TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, pref_key)
    );

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
);

CREATE TABLE IF NOT EXISTS panel_classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    panel_id INTEGER,
    classification TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (panel_id) REFERENCES frontend_panels (id)
);

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
);

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
);
