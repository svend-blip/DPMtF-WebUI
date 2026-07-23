"""Prompt parser — extract JSON actions from model output.

Handles:
- Think-tags / thinking blocks stripped
- Code fences stripped
- Actual newlines inside JSON string values escaped
- Multiple JSON objects per message — takes first only
- Alternate field name normalization (operation→action, filepath→path, etc.)
"""
from __future__ import annotations

import json
import re


def _fix_json_newlines(text: str) -> str:
    """Fix actual newlines inside JSON string values by escaping them."""
    result = []
    in_string = False
    escape = False
    for c in text:
        if escape:
            result.append(c)
            escape = False
            continue
        if c == '\\':
            result.append(c)
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            result.append(c)
            continue
        if c == '\n' and in_string:
            result.append('\\n')
            continue
        if c == '\r' and in_string:
            result.append('\\r')
            continue
        result.append(c)
    return ''.join(result)


def extract_json(text: str) -> dict | None:
    """Extract the first JSON object from model output. Returns None if no valid JSON."""
    if not text or not text.strip():
        return None

    # Strip think-tags
    cleaned = re.sub(r"\xd0\x9c.*?\xd0\x94", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()

    # Strip code fences
    fence = chr(96) * 3
    if cleaned.startswith(fence):
        lines = cleaned.split("\n")
        if lines[0].startswith(fence):
            lines = lines[1:]
        if lines and lines[-1].startswith(fence):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Find the first complete JSON object by tracking brace depth
    start = cleaned.find("{")
    if start < 0:
        return None

    depth = 0
    in_str = False
    esc = False
    end = -1
    for i, c in enumerate(cleaned[start:]):
        if esc:
            esc = False
            continue
        if c == '\\':
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = start + i
                break

    if end < 0 or end <= start:
        return None

    json_str = _fix_json_newlines(cleaned[start:end + 1])

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    # Normalize alternate field names
    if "operation" in data and "action" not in data:
        data["action"] = data.pop("operation")
    if "type" in data and "action" not in data:
        data["action"] = data.pop("type")
    if "filepath" in data and "path" not in data:
        data["path"] = data.pop("filepath")
    if "file" in data and "path" not in data:
        data["path"] = data.pop("file")
    if "patch" in data and "content" not in data:
        data["content"] = data.pop("patch")
    if "code" in data and "content" not in data:
        data["content"] = data.pop("code")

    return data
