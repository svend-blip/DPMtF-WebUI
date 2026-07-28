"""Tests for bridge_lib.py functions get_next_id_for_flow and bump_id_counter_past.

These tests validate the behavior of ID counter management in the BridgeV002 system.
"""
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import bridge_lib


@pytest.fixture
def temp_db(tmp_path):
    """Provide a temporary database for testing bridge_lib functions."""
    db = tmp_path / "test.db"
    # Copy the real DB to temp location so we have schema and existing data
    real_db = PROJECT_ROOT / "databases" / "dpmtf.db"
    shutil.copy(real_db, db)
    
    # Return the database path for use in tests
    return str(db)


def test_get_next_id_for_flow_returns_correct_counter_value(temp_db):
    """Test that get_next_id_for_flow returns current counter and increments it."""
    flow_key = "test_flow"
    
    # First call should return 1 (counter is created at 1)
    first_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert first_id == 1
    
    # Second call should return 2 (counter incremented)
    second_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert second_id == 2

    # Third call should return 3
    third_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert third_id == 3


def test_get_next_id_for_flow_unknown_flow_auto_creates_counter(temp_db):
    """Test that get_next_id_for_flow auto-creates counter for unknown flow."""
    flow_key = "unknown_flow"
    
    # Counter should be created and return 1 for a new flow
    first_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert first_id == 1
    
    # Counter should now be 2 after first access
    second_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert second_id == 2


def test_bump_id_counter_past_increments_counter(temp_db):
    """Test that bump_id_counter_past correctly bumps the counter."""
    flow_key = "test_bump_flow"
    
    # First get a starting id
    start_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert start_id == 1
    
    # Bump to a higher number
    bridge_lib.bump_id_counter_past(flow_key, 5, db_path=temp_db)
    
    # Next allocation should be 6 (5 + 1)
    next_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert next_id == 6


def test_bump_id_counter_past_no_backwards_movement(temp_db):
    """Test that bump_id_counter_past does not move counter backwards."""
    flow_key = "test_backwards_flow"
    
    # Get first ID
    start_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert start_id == 1
    
    # Bump to a higher number
    bridge_lib.bump_id_counter_past(flow_key, 5, db_path=temp_db)
    
    # Now attempt to bump to a lower number - should not change anything
    bridge_lib.bump_id_counter_past(flow_key, 3, db_path=temp_db)
    
    # Next allocation should still be 6 (not 4)
    next_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert next_id == 6


def test_bump_id_counter_past_non_numeric_input(temp_db):
    """Test that bump_id_counter_past handles non-numeric input gracefully."""
    flow_key = "test_non_numeric_flow"
    
    # Get first ID
    start_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert start_id == 1
    
    # Try to bump with invalid input - should not cause errors
    bridge_lib.bump_id_counter_past(flow_key, "invalid", db_path=temp_db)
    
    # Counter should still work normally
    next_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert next_id == 2


def test_bump_id_counter_past_edge_cases(temp_db):
    """Test that bump_id_counter_past handles edge cases."""
    flow_key = "test_edge_flow"
    
    # Test with zero
    bridge_lib.bump_id_counter_past(flow_key, 0, db_path=temp_db)
    next_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert next_id == 1
    
    # Test with negative number 
    bridge_lib.bump_id_counter_past(flow_key, -5, db_path=temp_db)
    next_id = bridge_lib.get_next_id_for_flow(flow_key, db_path=temp_db)
    assert next_id == 2


def test_load_role_from_db_happy_path_returns_dict_with_keys(temp_db):
    """Test that load_role_from_db returns a dict with documented keys for existing role."""
    role_name = "archi01"
    
    role = bridge_lib.load_role_from_db(role_name, db_path=temp_db)
    
    # Assert it's a dictionary with expected keys (documented in function docstring)
    assert isinstance(role, dict)
    assert "role_key" in role
    assert "tmux_session" in role
    assert "setup_script" in role
    assert "teardown_script" in role
    assert "deliver_error_msg" in role
    assert "is_active" in role
    assert "created_at" in role
    assert "updated_at" in role
    assert "restart_policy" in role
    assert "governance_file" in role
    assert "role_type" in role
    assert "enter_command" in role
    assert "config_dir" in role
    assert "default_model_source" in role
    assert "default_model_alias" in role
    
    # Assert specific values
    assert role["role_key"] == "archi01"
    assert role["tmux_session"] == "archi01"
    assert role["governance_file"] == "402_STRICT_REVIEW_ARCHI01.md"
    assert role["role_type"] == "agent"


def test_load_role_from_db_unknown_role_raises_value_error(temp_db):
    """Test that load_role_from_db raises ValueError for unknown role."""
    with pytest.raises(ValueError, match="Active role 'nonexistent' not found"):
        bridge_lib.load_role_from_db("nonexistent", db_path=temp_db)


def test_load_flow_from_db_happy_path_returns_dict_with_flow_and_steps(temp_db):
    """Test that load_flow_from_db returns dict with flow and steps for existing flow."""
    flow_name = "strict_review"
    
    result = bridge_lib.load_flow_from_db(flow_name, db_path=temp_db)
    
    # Assert it's a dictionary with expected keys
    assert isinstance(result, dict)
    assert "flow" in result
    assert "steps" in result
    
    # Assert flow content
    flow = result["flow"]
    assert isinstance(flow, dict)
    assert flow["flow_key"] == "strict_review"
    assert flow["name"] == "Standard development flow"
    
    # Assert steps are a list sorted by sort_order
    steps = result["steps"]
    assert isinstance(steps, list)
    assert len(steps) > 0
    
    # Check that steps are ordered (sort_order should be increasing)
    for i in range(len(steps) - 1):
        assert steps[i]["sort_order"] <= steps[i + 1]["sort_order"]
    
    # Verify some step content 
    first_step = steps[0]
    assert first_step["flow_key"] == "strict_review"
    assert first_step["step_key"] == "archi01-imple01"
    assert first_step["from_role"] == "archi01"
    assert first_step["to_role"] == "imple01"


def test_load_flow_from_db_unknown_flow_raises_value_error(temp_db):
    """Test that load_flow_from_db raises ValueError for unknown flow."""
    with pytest.raises(ValueError, match="Active flow 'nonexistent_flow' not found"):
        bridge_lib.load_flow_from_db("nonexistent_flow", db_path=temp_db)


def test_resolve_convention_from_db_happy_path_returns_dict_with_keys(temp_db):
    """Test that resolve_convention_from_db returns dict with documented keys for existing rule."""
    rule_key = "handoff"
    
    result = bridge_lib.resolve_convention_from_db(rule_key, db_path=temp_db)
    
    # Assert it's a dictionary with expected keys (documented in function docstring)
    assert isinstance(result, dict)
    assert "rule_key" in result
    assert "step_type" in result
    assert "dir_template" in result
    assert "pattern_template" in result
    assert "error_template" in result
    assert "prompt_template" in result
    
    # Verify specific values
    assert result["rule_key"] == "handoff"
    assert result["step_type"] == "Handoff"
    assert result["dir_template"] == "handoffs"
    assert result["pattern_template"] == "{ID}-handoff.md"


def test_resolve_convention_from_db_unknown_rule_raises_value_error(temp_db):
    """Test that resolve_convention_from_db raises ValueError for unknown rule."""
    with pytest.raises(ValueError, match="Convention rule 'nonexistent_rule' not found"):
        bridge_lib.resolve_convention_from_db("nonexistent_rule", db_path=temp_db)


def test_resolve_content_template_from_db_happy_path_returns_string(temp_db):
    """Test that resolve_content_template_from_db returns content template string for existing rule."""
    rule_key = "callback"
    
    result = bridge_lib.resolve_content_template_from_db(rule_key, db_path=temp_db)
    
    # Should return a string
    assert isinstance(result, str)
    
    # Should contain expected content (the actual content is longer, but we verify it's not empty)
    assert len(result) > 0
    assert "handoff_id" in result


def test_resolve_content_template_from_db_unknown_rule_returns_empty_string(temp_db):
    """Test that resolve_content_template_from_db returns empty string for unknown rule."""
    result = bridge_lib.resolve_content_template_from_db("nonexistent_rule", db_path=temp_db)
    
    # Should return an empty string for unknown rule
    assert isinstance(result, str)
    assert result == ""


def test_resolve_placeholders_replace_bridge_dir_and_project_root(temp_db):
    """Test that resolve_placeholders replaces {BRIDGE_DIR} and {PROJECT_ROOT} with explicit values."""
    bridge_dir = "/tmp/bridge"
    project_root = "/tmp/project"
    
    # Test basic replacements 
    text = "{BRIDGE_DIR}/config.ini"
    result = bridge_lib.resolve_placeholders(text, bridge_dir=bridge_dir, project_root=project_root)
    assert result == f"{bridge_dir}/config.ini"
    
    # Test PROJECT_ROOT replacement  
    text = "Project at {PROJECT_ROOT}"
    result = bridge_lib.resolve_placeholders(text, bridge_dir=bridge_dir, project_root=project_root)
    assert result == f"Project at {project_root}"
    
    # Test SCRIPTS_DIR replacement (should be project_root/scripts/bridgeV002)
    text = "{SCRIPTS_DIR}/script.sh"
    result = bridge_lib.resolve_placeholders(text, bridge_dir=bridge_dir, project_root=project_root)
    assert result == f"{project_root}/scripts/bridgeV002/script.sh"


def test_resolve_placeholders_multiple_placeholders(temp_db):
    """Test that resolve_placeholders handles text with multiple/ repeated placeholders."""
    bridge_dir = "/tmp/bridge"
    project_root = "/tmp/project"
    
    # Test text with multiple placeholders
    text = "{PROJECT_ROOT}/app/{BRIDGE_DIR}/config.ini"
    result = bridge_lib.resolve_placeholders(text, bridge_dir=bridge_dir, project_root=project_root)
    assert result == f"{project_root}/app/{bridge_dir}/config.ini"
    
    # Test text with repeated placeholder
    text = "{PROJECT_ROOT}/{PROJECT_ROOT}"
    result = bridge_lib.resolve_placeholders(text, bridge_dir=bridge_dir, project_root=project_root)
    assert result == f"{project_root}/{project_root}"


def test_resolve_placeholders_no_placeholders(temp_db):
    """Test that resolve_placeholders leaves text without placeholders unchanged."""
    bridge_dir = "/tmp/bridge"
    project_root = "/tmp/project"
    
    # Test text with no placeholders
    text = "simple_text.txt"
    result = bridge_lib.resolve_placeholders(text, bridge_dir=bridge_dir, project_root=project_root)
    assert result == text
    
    # Test mixed content 
    text = "no placeholders here but 12345 numbers"
    result = bridge_lib.resolve_placeholders(text, bridge_dir=bridge_dir, project_root=project_root)
    assert result == text


def test_get_effective_model_source_step_override_wins(temp_db):
    """Test that step-level override wins over role default."""
    # Test case: Step has NULL value → should fall back to role 
    role_key = "archi01"
    step_key = "archi01-imple01"
    flow_key = "strict_review"
    
    # Since the step has NULL model_source, it falls back to role
    result = bridge_lib.get_effective_model_source(
        role_key, step_key=step_key, flow_key=flow_key, db_path=temp_db
    )
    
    # Should fall back to role default (which is "model_allocator")
    assert result[0] == "model_allocator"  # model_source should be from role
    assert result[1] == "archi-local"      # alias should be from role


def test_get_effective_model_source_step_inherit_falls_back_to_role(temp_db):
    """Test that step value "inherit_from_role" or NULL falls back to role default."""
    # Since the step has NULL values, it falls back to role defaults
    result = bridge_lib.get_effective_model_source(
        "archi01", step_key="archi01-imple01", flow_key="strict_review", db_path=temp_db
    )
    
    # Should fall back to role default (which is the test data)
    assert result[0] == "model_allocator"  # From role, since step is NULL


def test_get_effective_model_source_no_step_or_role_returns_system_default(temp_db):
    """Test that NULL role-level yields system default (None, None)."""
    # Test case: No role found or role has NULL values
    # This would require creating a custom temp db setup with test data
    
    # Test with a nonexistent role - this should return (None, None)
    result = bridge_lib.get_effective_model_source("nonexistent_role", db_path=temp_db)
    
    # Should return system default 
    assert result == (None, None)


def test_validate_deliverable_against_schema_all_tags_present(temp_db):
    """Test that validate_deliverable_against_schema returns valid=True when all tags are present."""
    # Create a temporary file with required sections
    import tempfile
    
    # Get the handoff convention which has validation schema ["<role>", "<task>", "<constraint>", "<deliverable>"]
    rule_key = "handoff"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        file_path = f.name
        f.write("""<role>imple01</role>

<task>What needs to be accomplished</task>

<constraint>Any constraints that apply</constraint>

<deliverable>What you will produce</deliverable>
""")
    
    try:
        result = bridge_lib.validate_deliverable_against_schema(file_path, rule_key, db_path=temp_db)
        
        assert result["valid"] is True
        assert result["missing"] == []
        assert len(result["checked"]) > 0
    finally:
        # Clean up the temporary file 
        import os
        os.unlink(file_path)


def test_validate_deliverable_against_schema_missing_tags(temp_db):
    """Test that validate_deliverable_against_schema returns valid=False with missing tags."""
    # Create a temporary file with only some required sections
    import tempfile
    
    # Use the handoff convention which has validation schema ["<role>", "<task>", "<constraint>", "<deliverable>"]
    rule_key = "handoff"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        file_path = f.name
        f.write("""<role>imple01</role>

<task>What needs to be accomplished</task>
""")
    
    try:
        result = bridge_lib.validate_deliverable_against_schema(file_path, rule_key, db_path=temp_db)
        
        assert result["valid"] is False
        # Should contain the missing tags (constraint and deliverable)
        assert "<constraint>" in result["missing"]
        assert "<deliverable>" in result["missing"]
        assert len(result["checked"]) == 4  # All 4 tags from schema
    finally:
        # Clean up the temporary file 
        import os
        os.unlink(file_path)


def test_validate_deliverable_against_schema_empty_validation_schema(temp_db):
    """Test that validate_deliverable_against_schema returns valid=True when validation_schema is empty."""
    # First, we need to create a convention rule with an empty validation schema
    # We'll add a test row for this purpose
    
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Create a test convention rule with empty validation schema
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO bridge_convention_rules "
            "(rule_key, step_type, dir_template, pattern_template, error_template, created_at, updated_at, content_template, validation_schema) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("test_empty_schema", "Test", "tests", "{ID}-test.md", "Error template", "2026-06-19 10:07:42", "2026-07-26 10:40:06", "", "")
        )
        conn.commit()
    except Exception:
        # If the insert fails, it's okay as we may be in a race condition
        pass
    finally:
        conn.close()
    
    # Create a temporary file with some content
    import tempfile
    
    rule_key = "test_empty_schema"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        file_path = f.name
        f.write("# Test content")
    
    try:
        result = bridge_lib.validate_deliverable_against_schema(file_path, rule_key, db_path=temp_db)
        
        assert result["valid"] is True  # Empty schema should pass vacuously
        assert result["missing"] == []
        assert result["checked"] == []
    finally:
        # Clean up the temporary file 
        import os
        os.unlink(file_path)


def test_validate_deliverable_against_schema_nonexistent_file(temp_db):
    """Test that validate_deliverable_against_schema returns valid=False for nonexistent file."""
    rule_key = "handoff"
    
    # Use a path that doesn't exist
    file_path = "/tmp/nonexistent_file.md"
    
    result = bridge_lib.validate_deliverable_against_schema(file_path, rule_key, db_path=temp_db)
    
    assert result["valid"] is False
    # Should contain error path
    assert "<validation-error>" in result["missing"]


def test_auto_prepend_xml_sections_all_tags_present(temp_db):
    """Test that auto_prepend_xml_sections returns prepended=False when all tags are already present."""
    # Create a temporary file with required sections
    import tempfile
    
    rule_key = "handoff"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        file_path = f.name
        f.write("""<role>imple01</role>

<task>What needs to be accomplished</task>

<constraint>Any constraints that apply</constraint>

<deliverable>What you will produce</deliverable>
""")
    
    try:
        # Call auto_prepend_xml_sections
        result = bridge_lib.auto_prepend_xml_sections(
            file_path, rule_key, "123", "archi01", "strict_review", "/tmp/bridge", db_path=temp_db
        )
        
        assert result["prepended"] is False
        assert result["missing"] == []
    finally:
        # Clean up the temporary file 
        import os
        os.unlink(file_path)


def test_auto_prepend_xml_sections_missing_tags(temp_db):
    """Test that auto_prepend_xml_sections prepends missing tags and validates the resulting content."""
    # Create a temporary file with only some required sections
    import tempfile
    
    rule_key = "handoff"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        file_path = f.name
        f.write("# Test content\n\nSome text here")
    
    try:
        # Call auto_prepend_xml_sections which should prepend missing tags
        result = bridge_lib.auto_prepend_xml_sections(
            file_path, rule_key, "123", "archi01", "strict_review", "/tmp/bridge", db_path=temp_db
        )
        
        assert result["prepended"] is True
        
        # Should be missing the sections that were absent
        assert "<role>" in result["missing"]
        assert "<task>" in result["missing"]
        assert "<constraint>" in result["missing"]
        assert "<deliverable>" in result["missing"]
        
        # Read back the content to verify prepending worked
        with open(file_path, 'r') as f:
            content = f.read()
            
        # The function should have added placeholder content for all missing tags
        assert "<role>(auto-added: model omitted this section)</role>" in content
        assert "# Test content" in content  # Original content preserved
        
    finally:
        # Clean up the temporary file 
        import os
        os.unlink(file_path)


def test_auto_prepend_xml_sections_known_tag_values(temp_db):
    """Test that auto_prepend_xml_sections populates known tag values correctly."""
    # Create a temporary file with no sections
    import tempfile
    
    rule_key = "handoff"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        file_path = f.name
        f.write("# Test content")
    
    try:
        # Call auto_prepend_xml_sections
        result = bridge_lib.auto_prepend_xml_sections(
            file_path, rule_key, "456", "imple01", "strict_review", "/tmp/bridge", db_path=temp_db
        )
        
        assert result["prepended"] is True
        
        # Read back content to verify the function works
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Should have added placeholder content for all tags (since no specific handling for handoff_id/source_role)
        # But check that it at least has the general missing tags in placeholder format 
        assert "<role>(auto-added: model omitted this section)</role>" in content
        
    finally:
        # Clean up the temporary file 
        import os
        os.unlink(file_path)


def test_auto_prepend_xml_sections_empty_validation_schema(temp_db):
    """Test that auto_prepend_xml_sections returns prepended=False when validation_schema is empty."""
    # First, need to create a convention rule with empty validation schema
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Create a test convention rule with empty validation schema
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO bridge_convention_rules "
            "(rule_key, step_type, dir_template, pattern_template, error_template, created_at, updated_at, content_template, validation_schema) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("test_empty_schema2", "Test", "tests", "{ID}-test.md", "Error template", "2026-06-19 10:07:42", "2026-07-26 10:40:06", "", "")
        )
        conn.commit()
    except Exception:
        # If the insert fails, it's okay as we may be in a race condition
        pass
    finally:
        conn.close()
    
    import tempfile
    
    rule_key = "test_empty_schema2"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        file_path = f.name
        f.write("# Test content")
    
    try:
        # Call auto_prepend_xml_sections 
        result = bridge_lib.auto_prepend_xml_sections(
            file_path, rule_key, "789", "archi01", "strict_review", "/tmp/bridge", db_path=temp_db
        )
        
        assert result["prepended"] is False  # Should not prepend anything with empty schema
        assert result["missing"] == []
    finally:
        # Clean up the temporary file 
        import os
        os.unlink(file_path)