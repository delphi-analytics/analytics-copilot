"""
Shared utilities for agent nodes.
"""
from __future__ import annotations
import json
import re
import structlog

log = structlog.get_logger(__name__)


def resilient_json_loads(text: str):
    """
    Highly resilient JSON extractor and parser.

    Handles LLM outputs that contain:
    - Markdown code blocks (```json ... ```)
    - Conversational text before/after the JSON
    - Trailing commas in objects/arrays
    - Single-line (// ...) and multi-line (/* ... */) JS-style comments
    """
    if not text:
        raise ValueError("Empty text input")

    cleaned = text.strip()

    # 1. Fast path — try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code blocks
    codeblock_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", cleaned, re.IGNORECASE)
    if codeblock_match:
        candidate = codeblock_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            cleaned = candidate  # continue cleaning this candidate

    # 3. Find outermost JSON structure { ... } or [ ... ]
    first_brace = cleaned.find("{")
    first_bracket = cleaned.find("[")

    start_pos = -1
    end_pos = -1

    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        start_pos = first_brace
        end_pos = cleaned.rfind("}")
    elif first_bracket != -1:
        start_pos = first_bracket
        end_pos = cleaned.rfind("]")

    if start_pos != -1 and end_pos != -1 and end_pos > start_pos:
        json_candidate = cleaned[start_pos : end_pos + 1]

        # 4. Remove single-line JS comments
        json_candidate = re.sub(r"//.*$", "", json_candidate, flags=re.MULTILINE)

        # 5. Remove multi-line JS comments
        json_candidate = re.sub(r"/\*[\s\S]*?\*/", "", json_candidate)

        # 6. Remove trailing commas before } or ]
        json_candidate = re.sub(r",\s*\}", "}", json_candidate)
        json_candidate = re.sub(r",\s*\]", "]", json_candidate)

        try:
            return json.loads(json_candidate.strip())
        except json.JSONDecodeError as exc:
            log.debug(
                "resilient_json.parse_failed",
                error=str(exc),
                sample=json_candidate[:200],
            )

    # Final attempt — let it raise naturally for the caller to catch
    return json.loads(cleaned)
