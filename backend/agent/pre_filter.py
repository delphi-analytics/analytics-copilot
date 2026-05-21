"""
Minimal Pre-Filter for Intent Classification
ONLY catches the most obvious patterns BEFORE LLM call.
The LLM handles all actual classification - this just saves tokens for obvious cases.
"""
from __future__ import annotations
import re


def pre_classify(question: str) -> dict:
    """
    Minimal pre-classification using simple rules.
    Returns intent type for routing - the general_llm node handles all conversational responses.

    Returns: {"type": str, "confidence": float, "skip_llm": bool}
    """
    if not question:
        return {"type": "empty", "confidence": 1.0, "skip_llm": True}

    q = question.lower().strip()

    # Detect obvious greetings - route to general_llm for natural responses
    if re.match(r"^(hi|hello|hey|gm|gn)\b[!.]*$", q):
        return {
            "type": "greeting",
            "confidence": 1.0,
            "skip_llm": False,  # Let general_llm handle the response
        }

    # Let LLM handle everything else
    return {
        "type": "llm_classify",
        "confidence": 0.5,
        "skip_llm": False,
    }
