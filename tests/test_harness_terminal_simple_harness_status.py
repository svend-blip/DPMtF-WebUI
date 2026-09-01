"""The Harness Terminal banner states simple-harness facts from real configuration.

Before 2026-09-01 every line but Bridge/flows read ``unknown`` or
``not configured`` for a simple-harness role, because the collector only
ever read DPMTF_* environment variables that no launch sets. The values
exist: the allocator resolves the permission mode the launch passes, and
the harness's own config files declare its MCP servers.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import harness_terminal as _ht  # noqa: E402


def _clear_env(monkeypatch):
    for var in ("DPMTF_SANDBOX_MODE", "DPMTF_SANDBOX", "DPMTF_APPROVAL_POLICY", "DPMTF_APPROVAL",
                "DPMTF_WORKSPACE_ACCESS_MODE", "DPMTF_WORKSPACE_ACCESS", "DPMTF_MCP_LIGHT",
                "MCP_LIGHT_STATE", "MCP_LIGHT", "DPMTF_PERMISSION", "DPMTF_PERMISSION_MODE"):
        monkeypatch.delenv(var, raising=False)


def _fake_standalone(permission):
    return SimpleNamespace(config=SimpleNamespace(get_simple_harness_permission=lambda: permission))


def test_simple_harness_fields_come_from_configuration(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    home = tmp_path / "home"
    (home / ".simple-harness").mkdir(parents=True)
    (home / ".simple-harness" / "config.json").write_text(json.dumps({
        "mcp_servers": [{"name": "mcp-light", "transport": "http",
                         "endpoint": "http://127.0.0.1:9135/mcp"}]}))
    monkeypatch.setattr(_ht.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(_ht.harness, "_standalone", lambda: _fake_standalone("workspace_write"))
    probed = []
    monkeypatch.setattr(_ht, "_probe_mcp_endpoint", lambda ep, timeout=2.0: probed.append(ep) or True)

    info = _ht.collect_runtime_status(harness_key="simple-harness", cwd=str(tmp_path))
    assert info["permission"] == "workspace-write"
    assert info["sandbox_mode"] == "workspace-write"
    assert info["workspace_access_mode"] == "writable"
    assert info["approval_policy"] == "never"
    assert info["mcp_light"] == "available"
    assert probed == ["http://127.0.0.1:9135/mcp"]


def test_unreachable_mcp_light_is_reported_not_hidden(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    home = tmp_path / "home"
    (home / ".simple-harness").mkdir(parents=True)
    (home / ".simple-harness" / "config.json").write_text(json.dumps({
        "mcp_servers": [{"name": "mcp-light", "transport": "http", "endpoint": "http://127.0.0.1:9/mcp"}]}))
    monkeypatch.setattr(_ht.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(_ht.harness, "_standalone", lambda: _fake_standalone("read_only"))
    monkeypatch.setattr(_ht, "_probe_mcp_endpoint", lambda ep, timeout=2.0: False)
    info = _ht.collect_runtime_status(harness_key="simple-harness", cwd=str(tmp_path))
    assert info["mcp_light"] == "unavailable"
    assert info["permission"] == "read-only"
    assert info["workspace_access_mode"] == "read-only"


def test_no_config_file_means_not_configured_and_no_probe(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr(_ht.Path, "home", staticmethod(lambda: tmp_path / "nohome"))
    monkeypatch.setattr(_ht.harness, "_standalone", lambda: _fake_standalone("workspace_write"))

    def _never(ep, timeout=2.0):
        raise AssertionError("no config -> no probe")
    monkeypatch.setattr(_ht, "_probe_mcp_endpoint", _never)
    info = _ht.collect_runtime_status(harness_key="simple-harness", cwd=str(tmp_path))
    assert info["mcp_light"] == "not configured"


def test_workspace_config_overrides_home_config(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    home = tmp_path / "home"
    (home / ".simple-harness").mkdir(parents=True)
    (home / ".simple-harness" / "config.json").write_text(json.dumps({
        "mcp_servers": [{"name": "mcp-light", "transport": "http", "endpoint": "http://home:1/mcp"}]}))
    ws = tmp_path / "ws" / "deep"
    (tmp_path / "ws" / ".simple-harness").mkdir(parents=True)
    ws.mkdir(parents=True)
    (tmp_path / "ws" / ".simple-harness" / "config.json").write_text(json.dumps({
        "mcp_servers": [{"name": "mcp-light", "transport": "http", "endpoint": "http://ws:2/mcp"}]}))
    monkeypatch.setattr(_ht.Path, "home", staticmethod(lambda: home))
    assert _ht._simple_harness_mcp_light_endpoint(str(ws)) == "http://ws:2/mcp"


def test_explicit_env_still_wins(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("DPMTF_MCP_LIGHT", "connected")
    monkeypatch.setenv("DPMTF_PERMISSION", "full-access")
    monkeypatch.setattr(_ht.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(_ht.harness, "_standalone", lambda: _fake_standalone("read_only"))
    info = _ht.collect_runtime_status(harness_key="simple-harness", cwd=str(tmp_path))
    assert info["mcp_light"] == "connected"
    assert info["permission"] == "full-access"


def test_other_harnesses_are_untouched(monkeypatch):
    _clear_env(monkeypatch)
    info = _ht.collect_runtime_status(harness_key="dsh", cwd="/tmp")
    assert info["permission"] == "unknown"
    assert info["approval_policy"] == "unknown"
