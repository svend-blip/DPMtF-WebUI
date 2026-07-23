#!/usr/bin/env python3
"""Generate an authoritative inventory of active roles and their model settings.

Read-only script — queries bridge_roles + bridge_flow_steps, reports every
active role with its effective model source, direct settings, and step overrides.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import config

def main():
    db_path = config.get_db_path()
    if not os.path.isabs(db_path):
        db_path = os.path.join(str(PROJECT_ROOT), db_path)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Query all active roles
    roles = conn.execute("""
        SELECT role_key, tmux_session, model_type, cloud_model, ollama_model,
               role_type, enter_command, governance_file,
               default_runtime, default_provider, default_model,
               default_model_source, default_model_alias,
               max_output_tokens, trade_mcp_push_mode,
               config_dir, primary_output_type
        FROM bridge_roles 
        WHERE is_active = 1
        ORDER BY role_key
    """).fetchall()
    
    # Query step-level model overrides
    step_overrides = conn.execute("""
        SELECT flow_key, step_key, from_role, to_role,
               model_source, model_alias
        FROM bridge_flow_steps
        WHERE is_active = 1
          AND (model_source IS NOT NULL AND model_source != '' 
               OR model_alias IS NOT NULL AND model_alias != '')
        ORDER BY flow_key, sort_order
    """).fetchall()
    
    # Query all flows for context
    flows = conn.execute("""
        SELECT flow_key, name FROM bridge_flows WHERE is_active = 1
    """).fetchall()
    
    # Build inventory
    inventory = {
        "generated_at": "2026-07-23",
        "db_path": db_path,
        "flows": [dict(f) for f in flows],
        "roles": [],
        "step_overrides": [dict(s) for s in step_overrides],
    }
    
    for r in roles:
        role = dict(r)
        
        # Categorize
        if role["role_type"] == "human":
            role["category"] = "human"
        elif role.get("default_model_source") == "model_allocator":
            role["category"] = "allocator"
        elif role.get("default_runtime") == "freebuff" or "freebuff" in (role.get("cloud_model") or "").lower():
            role["category"] = "freebuff"
        elif role.get("default_provider") == "openrouter":
            role["category"] = "cloud_openrouter"
        elif role.get("default_runtime") == "claude":
            role["category"] = "claude_code_local"
        elif role.get("default_runtime") == "opencode":
            role["category"] = "opencode_local"
        else:
            role["category"] = "unknown"
        
        inventory["roles"].append(role)
    
    # Print human-readable report
    print("=" * 80)
    print("DPMtF Role Inventory — 2026-07-23")
    print("=" * 80)
    print()
    
    # Summary
    cats = {}
    for r in inventory["roles"]:
        cats.setdefault(r["category"], []).append(r["role_key"])
    
    print("## Summary by category")
    for cat in sorted(cats.keys()):
        print(f"  {cat} ({len(cats[cat])}): {', '.join(cats[cat])}")
    print()
    
    # Shared models
    model_to_roles = {}
    for r in inventory["roles"]:
        if r["role_type"] == "human":
            continue
        model = r.get("ollama_model") or r.get("cloud_model") or r.get("default_model") or "?"
        model_to_roles.setdefault(model, []).append(r["role_key"])
    
    print("## Roles sharing the same concrete model")
    for model, roles_list in sorted(model_to_roles.items()):
        if len(roles_list) > 1:
            print(f"  {model}: {', '.join(roles_list)}")
    print()
    
    # Detailed role listing
    print("## Detailed role listing")
    print()
    for r in inventory["roles"]:
        print(f"### {r['role_key']}")
        print(f"  role_type:       {r['role_type']}")
        print(f"  category:        {r['category']}")
        print(f"  tmux_session:    {r['tmux_session']}")
        print(f"  model_type:      {r.get('model_type', '')}")
        print(f"  ollama_model:    {r.get('ollama_model', '')}")
        print(f"  cloud_model:     {r.get('cloud_model', '')}")
        print(f"  default_runtime: {r.get('default_runtime', '')}")
        print(f"  default_provider: {r.get('default_provider', '')}")
        print(f"  default_model:   {r.get('default_model', '')}")
        print(f"  model_source:    {r.get('default_model_source', '')}")
        print(f"  model_alias:     {r.get('default_model_alias', '')}")
        print(f"  max_output_tokens: {r.get('max_output_tokens', '')}")
        print(f"  trade_mcp_push_mode: {r.get('trade_mcp_push_mode', '')}")
        print(f"  config_dir:      {r.get('config_dir', '')}")
        print(f"  governance_file: {r.get('governance_file', '')}")
        print()
    
    # Step overrides
    if inventory["step_overrides"]:
        print("## Step-level model overrides")
        for s in inventory["step_overrides"]:
            print(f"  {s['flow_key']}/{s['step_key']}: {s['from_role']}→{s['to_role']}"
                  f"  source={s['model_source']}  alias={s['model_alias']}")
        print()
    
    # JSON output for machine consumption
    print("## JSON")
    print(json.dumps(inventory, indent=2, default=str))
    
    conn.close()

if __name__ == "__main__":
    main()
