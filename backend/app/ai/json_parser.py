"""Phase 8: Robust Structured JSON Parsing & Extraction.

Extracts, cleans, repairs, and parses JSON output from LLM responses
with support for markdown code blocks, raw substrings, and minor syntax recovery.
"""

import json
import re
from typing import Dict, Any, Optional, Union
from app.ai.exceptions import AIStructuredOutputError


def extract_and_parse_json(text: str, provider: Optional[str] = None) -> Union[Dict[str, Any], list]:
    """
    Safely extract and parse JSON from an LLM text response.
    Handles:
    - Markdown code fences (```json ... ```)
    - Preamble and postamble conversational text
    - Trailing commas before closing braces
    - Single quote normalization for dictionary keys
    """
    if not text or not text.strip():
        raise AIStructuredOutputError("LLM returned empty response for structured JSON.", raw_response=text, provider=provider)

    cleaned = text.strip()

    # 1. Strip Markdown code blocks
    if "```json" in cleaned:
        parts = cleaned.split("```json", 1)[1]
        if "```" in parts:
            cleaned = parts.split("```", 1)[0].strip()
        else:
            cleaned = parts.strip()
    elif "```" in cleaned:
        parts = cleaned.split("```", 1)[1]
        if "```" in parts:
            cleaned = parts.split("```", 1)[0].strip()
        else:
            cleaned = parts.strip()

    # 2. Try direct json.loads
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Substring search for outermost { ... } or [ ... ]
    first_brace = cleaned.find('{')
    last_brace = cleaned.rfind('}')
    first_bracket = cleaned.find('[')
    last_bracket = cleaned.rfind(']')

    # Determine whether object or array appears first
    candidate = None
    if first_brace != -1 and last_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        candidate = cleaned[first_brace:last_brace + 1]
    elif first_bracket != -1 and last_bracket != -1:
        candidate = cleaned[first_bracket:last_bracket + 1]

    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            cleaned = candidate

    # 4. Safe heuristic repairs
    repaired = cleaned
    # Remove trailing commas before } or ]
    repaired = re.sub(r',\s*([\}\]])', r'\1', repaired)
    # Normalize unescaped newlines within string values where possible
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Try single-to-double quote repair on keys: 'key': -> "key":
    repaired_quotes = re.sub(r"(?<=\{|\,)\s*'([A-Za-z0-9_\-]+)'\s*:", r'"\1":', repaired)
    try:
        return json.loads(repaired_quotes)
    except json.JSONDecodeError as exc:
        raise AIStructuredOutputError(
            f"Failed to parse valid JSON from LLM response: {exc}",
            raw_response=text,
            provider=provider
        ) from exc
