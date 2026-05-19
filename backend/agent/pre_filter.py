"""
Rule-based Pre-Filter for Intent Classification
Catches greetings, off-topic, and analytical questions BEFORE LLM call.
Saves tokens and provides instant responses for common patterns.
"""
from __future__ import annotations
import re

# Greeting patterns - instant response, no SQL needed
GREETING_PATTERNS = [
    r"^(hi|hello|hey|hi there|hello there)\b",
    r"^(good morning|good afternoon|good evening)",
    r"^how are you( doing)?\?",
    r"^(what's up|sup)\b",
    r"^(who are you|what are you)\b",
    r"^what can you do\?",
    r"^help\b",
]

# Analytical/conversational patterns - need data + narrative response
ANALYTICAL_KEYWORDS = [
    "why is", "why did", "why does", "why are",
    "what caused", "what's the reason", "reason for",
    "explain", "explain to me", "elaborate on",
    "how is", "how did", "how does",
    "tell me more about", "what about",
    "insight", "analysis", "breakdown",
    "driving", "factors", "contributing to",
    "trending", "performance",
]

# Off-topic topics the system shouldn't touch
OFF_TOPICS = [
    "weather", "politics", "sports", "news", "joke",
    "recipe", "cooking", "movie", "song",
]


def pre_classify(question: str) -> dict:
    """
    Classify question using rules before LLM call.
    Returns: {"type": str, "confidence": float, "skip_llm": bool}
    """
    if not question:
        return {"type": "empty", "confidence": 1.0, "skip_llm": True}

    q = question.lower().strip()

    # Check greetings
    for pattern in GREETING_PATTERNS:
        if re.match(pattern, q, re.IGNORECASE):
            return {
                "type": "greeting",
                "confidence": 1.0,
                "skip_llm": True,
                "response": _get_greeting_response()
            }

    # Check off-topic
    for topic in OFF_TOPICS:
        if topic in q:
            return {
                "type": "off_topic",
                "confidence": 0.9,
                "skip_llm": True,
                "response": f"I'm an analytics assistant focused on your data. I can't help with {topic}, but I'd love to help you explore your sales, inventory, or customer data!"
            }

    # Check analytical/why questions
    for keyword in ANALYTICAL_KEYWORDS:
        if keyword in q:
            # Also check if they're asking about "this" or "it" (follow-up)
            is_followup = any(word in q for word in ["this", "it", "that", "these", "those"])
            return {
                "type": "analytical_question",
                "confidence": 0.8,
                "skip_llm": False,  # Still need LLM for narrative
                "is_followup": is_followup,
                "needs_data": True,  # Should fetch data for context
            }

    # Data query - send to full pipeline
    return {
        "type": "data_query",
        "confidence": 0.5,
        "skip_llm": False,
        "needs_data": True,
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
