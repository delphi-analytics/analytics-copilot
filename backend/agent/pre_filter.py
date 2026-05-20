"""
Minimal Pre-Filter for Intent Classification
ONLY catches the most obvious patterns BEFORE LLM call.
The LLM handles all actual classification - this just saves tokens for obvious cases.
"""
from __future__ import annotations
import re

# ONLY the most obvious greeting patterns - let LLM handle everything else
# These are strictly for common greetings that shouldn't require any LLM processing
OBVIOUS_GREETINGS = [
    r"^(hi|hello|hey)\b[!.]*$",
    r"^gm[!.]*$",
    r"^gn[!.]*$",
]


def pre_classify(question: str) -> dict:
    """
    Minimal pre-classification using simple rules.
    ONLY catches obvious greetings - everything else goes to LLM.

    Returns: {"type": str, "confidence": float, "skip_llm": bool}
    """
    if not question:
        return {"type": "empty", "confidence": 1.0, "skip_llm": True}

    q = question.lower().strip()

    # Check for obvious greetings ONLY (very strict matching)
    for pattern in OBVIOUS_GREETINGS:
        if re.match(pattern, q, re.IGNORECASE):
            return {
                "type": "greeting",
                "confidence": 1.0,
                "skip_llm": True,
                "response": _get_greeting_response()
            }

    # Let LLM handle everything else - including:
    # - Conversational questions ("what can you do", "who are you")
    # - Analytical questions ("why is", "explain")
    # - Data queries
    # - Off-topic questions
    return {
        "type": "llm_classify",
        "confidence": 0.5,
        "skip_llm": False,
    }


def _get_greeting_response() -> dict:
    """Get conversational greeting response with suggested actions."""
    return {
        "text": (
            "# 👋 Hello! I'm your Data Analytics Copilot\n\n"
            "I can help you explore and analyze your data with natural language questions.\n\n"
            "**Try asking:**\n"
            "• Show revenue by platform\n"
            "• Top 10 products by sales\n"
            "• What's the trend for Nykaa this month?\n"
            "• Compare inventory across platforms\n\n"
            "**Or ask analytical questions:**\n"
            "• Why is Nykaa performing better?\n"
            "• What caused the drop in returns?\n"
            "• How are we doing this quarter?"
        ),
        "chart": None,
        "insights": [],
        "follow_up_questions": [
            "Show me revenue by platform",
            "What are the top selling products?",
            "How does Nykaa compare to Myntra?"
        ],
        "viz_type": None,
        "row_count": 0,
    }
