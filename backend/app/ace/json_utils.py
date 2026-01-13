"""
ACE JSON utilities.
"""

import json
from typing import Any, Dict, Optional


def _find_matching_brace(text: str, start: int) -> Optional[int]:
    depth = 0
    in_string = False
    escape = False

    for idx in range(start, len(text)):
        ch = text[idx]

        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return idx

    return None


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    cleaned = text.strip()
    if not cleaned:
        return None

    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    for start, ch in enumerate(cleaned):
        if ch != "{":
            continue
        end = _find_matching_brace(cleaned, start)
        if end is None:
            continue
        candidate = cleaned[start:end + 1]
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value

    return None
