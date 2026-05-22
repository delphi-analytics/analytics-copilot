"""
Minimal Pre-Filter for Intent Classification
ONLY catches the most obvious patterns BEFORE LLM call.
The LLM handles all actual classification - this just saves tokens for obvious cases.

This module is deliberately minimal and contains NO hardcoded domain-specific
responses (no brand names, no product categories, no platform names). All
non-trivial classification is delegated to the LLM via the `general_llm` node,
which dynamically inspects the active datasource schema.
"""
from __future__ import annotations


def pre_classify(question: str) -> dict:
    """
    Minimal pre-classification using simple rules.
    Returns intent type for routing — the general_llm node handles all
    conversational/greeting/off-topic responses dynamically.

    Only the truly trivial case (empty input) is handled here.
    Everything else goes to the LLM for context-aware classification.

    Returns: {"type": str, "confidence": float, "skip_llm": bool, "response": dict (optional)}
    """
    if not question or not question.strip():
        return {
            "type": "empty",
            "confidence": 1.0,
            "skip_llm": True,
            "response": {
                "text": "I didn't receive a question. Could you please ask me something about your data?",
                "chart": None,
                "insights": [],
                "key_metrics": {},
                "follow_up_questions": [
                    "Show me a summary of all tables",
                    "What columns are in this database?",
                ],
                "viz_type": None,
                "row_count": 0,
            }
        }

    # Let LLM classify all inputs so responses are completely dynamic and custom.
    return {
        "type": "llm_classify",
        "confidence": 0.5,
        "skip_llm": False,
    }

