"""Tests for knowledge-layer config getters (GOAL-DRAFT-001).

The getters read the ``[knowledge]`` section of ``dpmtf.ini`` and fall back
safely to disabled-by-default values when the section is absent.
"""

from __future__ import annotations

import configparser
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402


def test_knowledge_disabled_by_default():
    assert config.get_knowledge_enabled() is False


def test_provider_defaults_to_none():
    assert config.get_knowledge_provider() == "none"


def test_retrieval_limits_have_defaults():
    assert config.get_knowledge_top_k() == 8
    assert config.get_knowledge_max_context_tokens() == 12000


def test_knowledge_max_document_chars_default():
    assert config.get_knowledge_max_document_chars() == 20000


def test_index_dir_is_absolute_and_inside_project():
    path = config.get_knowledge_index_dir()
    assert os.path.isabs(path)
    assert Path(path).parent == PROJECT_ROOT


def test_getters_fall_back_safely_when_section_absent(monkeypatch):
    parser = configparser.ConfigParser()
    parser.read_dict({})
    monkeypatch.setattr(config, "_config", parser)

    assert config.get_knowledge_enabled() is False
    assert config.get_knowledge_provider() == "none"
    assert config.get_knowledge_top_k() == 8
    assert config.get_knowledge_max_context_tokens() == 12000
    assert config.get_knowledge_max_document_chars() == 20000
    assert os.path.isabs(config.get_knowledge_index_dir())
