import json
import subprocess

import routers.bridge as bridge


def _completed(stdout="", stderr="", rc=0):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


def test_get_config_returns_sections(client, monkeypatch):
    payload = {"aliases": {"a1": {}}, "roles": {}, "profiles": {"p1": {}}}
    monkeypatch.setattr(bridge.subprocess, "run",
                        lambda *a, **k: _completed(stdout=json.dumps(payload)))
    resp = client.get("/api/bridge-v2/allocator/config")
    assert resp.status_code == 200
    assert resp.json()["aliases"] == {"a1": {}}


def test_post_alias_ok(client, monkeypatch):
    captured = {}

    def fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        return _completed(stdout=json.dumps({"ok": True, "name": "a2"}))

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    resp = client.post("/api/bridge-v2/allocator/config/alias",
                       json={"name": "a2", "definition": {"runtime_profile": "p1"}})
    assert resp.status_code == 200
    assert "set-alias" in captured["cmd"]
    assert "--name" in captured["cmd"] and "a2" in captured["cmd"]


def test_post_alias_validation_error_is_400(client, monkeypatch):
    monkeypatch.setattr(bridge.subprocess, "run",
                        lambda *a, **k: _completed(stderr=json.dumps({"error": "unknown runtime_profile: ghost"}), rc=1))
    resp = client.post("/api/bridge-v2/allocator/config/alias",
                       json={"name": "bad", "definition": {"runtime_profile": "ghost"}})
    assert resp.status_code == 400
    assert "ghost" in resp.json()["detail"]


def test_delete_role_ok(client, monkeypatch):
    captured = {}

    def fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        return _completed(stdout=json.dumps({"ok": True, "name": "r1"}))

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    resp = client.delete("/api/bridge-v2/allocator/config/role/r1")
    assert resp.status_code == 200
    assert "delete-role" in captured["cmd"]


def test_post_alias_non_dict_error_json_is_400(client, monkeypatch):
    monkeypatch.setattr(bridge.subprocess, "run",
                        lambda *a, **k: _completed(stderr=json.dumps("just a string"), rc=1))
    resp = client.post("/api/bridge-v2/allocator/config/alias",
                       json={"name": "bad", "definition": {"runtime_profile": "ghost"}})
    assert resp.status_code == 400


def test_post_alias_non_string_name_is_400(client, monkeypatch):
    monkeypatch.setattr(bridge.subprocess, "run",
                        lambda *a, **k: _completed(stdout=json.dumps({"ok": True})))
    resp = client.post("/api/bridge-v2/allocator/config/alias",
                       json={"name": 123, "definition": {"runtime_profile": "p1"}})
    assert resp.status_code == 400
