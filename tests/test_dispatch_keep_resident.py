"""The sender's local model stays resident when the receiver binds no GPU.

Human decision 2026-09-03: with one local model in a flow (Flash-Next as
implementer, cloud everywhere else) stopping it at every transition to a
cloud role cost a ~2 min reload per return and cut the sender's
post-signal stream. The receiver's GPU need is the discriminator.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import dispatch  # noqa: E402


def _gpu_map(mapping):
    return lambda alias: mapping.get(alias, False)


def test_local_to_cloud_keeps_the_local_model(monkeypatch):
    monkeypatch.setattr(dispatch, "_alias_holds_no_gpu", _gpu_map({"cloud_deepseek_v4pro": True}))
    assert dispatch._from_model_disposition("freetoken-qwen38-flash-next", "cloud_deepseek_v4pro") == "keep"


def test_local_to_local_still_stops(monkeypatch):
    monkeypatch.setattr(dispatch, "_alias_holds_no_gpu", _gpu_map({}))
    assert dispatch._from_model_disposition("freetoken-qwen38-flash-next", "imple01-local") == "stop"


def test_unreadable_allocator_fails_closed_to_stop(monkeypatch):
    # _alias_holds_no_gpu returns False when it cannot tell -> previous behaviour.
    monkeypatch.setattr(dispatch, "_alias_holds_no_gpu", lambda alias: False)
    assert dispatch._from_model_disposition("local-a", "cloud-b") == "stop"


def test_same_alias_or_no_sender_is_none(monkeypatch):
    monkeypatch.setattr(dispatch, "_alias_holds_no_gpu", lambda alias: True)
    assert dispatch._from_model_disposition("x", "x") == "none"
    assert dispatch._from_model_disposition("", "x") == "none"
    assert dispatch._from_model_disposition("x", "y", from_source="db") == "none"


def test_human_receiver_keeps_the_model(monkeypatch):
    monkeypatch.setattr(dispatch, "_alias_holds_no_gpu", lambda alias: False)
    assert dispatch._from_model_disposition("local-a", "", to_source="model_allocator") == "keep"
    assert dispatch._from_model_disposition("local-a", "human-x", to_source="db") == "keep"
