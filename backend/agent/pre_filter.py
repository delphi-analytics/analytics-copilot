"""
Minimal Pre-Filter for Intent Classification
ONLY catches the most obvious patterns BEFORE LLM call.
The LLM handles all actual classification - this just saves tokens for obvious cases.
"""
from __future__ import annotations
import re
import random


def _get_greeting_response(question: str) -> dict:
    """Generate a varied greeting response based on the specific greeting."""
    q = question.lower().strip()

    # Different responses for different greetings
    greetings = {
        "hi": [
            "# 👋 Hi there! I'm your Data Analytics Copilot\n\nI'm here to help you explore your Limese data. What would you like to analyze today?",
            "# Hey! 👋 Great to see you!\n\nReady to dive into some data? I can help you with sales, products, inventory, and more.",
        ],
        "hello": [
            "# Hello! 👋 Welcome to Analytics Copilot\n\nI'm your AI assistant for exploring Limese's data. What questions can I help answer?",
            "# Hi! Hello! 👋\n\nI'm here to make data analysis easy. Just ask me anything about your business data.",
        ],
        "hey": [
            "# Hey! 👋 What's on your mind?\n\nI'm ready to help you explore your data. What would you like to know?",
            "# Hey there! 👋\n\nWhat can I help you discover in your data today?",
        ],
        "gm": [
            "# Good morning! ☀️\n\nHope you have a great day ahead! Ready to explore some insights from your data?",
            "# GM! ☀️ Good morning!\n\nLet's start the day with some data insights. What would you like to explore?",
        ],
        "good morning": [
            "# Good morning! ☀️\n\nWishing you a productive day! I'm here to help with any data analysis you need.",
            "# Good morning! ☀️\n\nWhat data would you like to explore today? I'm here to help!",
        ],
        "gn": [
            "# Good evening! 🌙\n\nHope you've had a great day! What can I help you with?",
            "# GN! 🌙 Good evening!\n\nWrapping up? I'm here if you need to check any data.",
        ],
        "good evening": [
            "# Good evening! 🌙\n\nHope your day went well! What would you like to explore?",
            "# Good evening! 🌙\n\nI'm here to help with any data questions you have.",
        ],
        "good afternoon": [
            "# Good afternoon! 👋\n\nHow can I help you with your data today?",
            "# Good afternoon! ☀️\n\nWhat insights are you looking for?",
        ],
        "how are you": [
            "# I'm doing great, thank you! 🤖\n\nI'm fully operational and ready to crunch some numbers. How can I help you analyze your data today?",
            "# I'm doing well! ✨\n\nAlways happy to help you discover insights in your business data. What would you like to explore?",
            "# Fantastic, thanks for asking! 📊\n\nI've got all my circuits fired up and ready to analyze your sales and performance metrics. What's on your mind?",
        ],
    }

    # Find the matching greeting type
    for key, responses in greetings.items():
        if q.startswith(key):
            return {
                "type": "greeting",
                "confidence": 1.0,
                "skip_llm": True,
                "response": {
                    "text": random.choice(responses) + "\n\n**Try asking:**\n• Show revenue by platform\n• Top 10 products by sales\n• What's the trend for Nykaa this month?",
                    "chart": None,
                    "insights": [],
                    "key_metrics": {},
                    "follow_up_questions": [
                        "Show me revenue by platform",
                        "What are the top selling products?",
                        "How does Nykaa compare to Myntra?"
                    ],
                    "viz_type": None,
                    "row_count": 0,
                }
            }

    # Default greeting response
    return {
        "type": "greeting",
        "confidence": 1.0,
        "skip_llm": True,
        "response": {
            "text": "# 👋 Hello! I'm your Data Analytics Copilot\n\nI can help you explore and analyze your data with natural language questions.\n\n**Try asking:**\n• Show revenue by platform\n• Top 10 products by sales\n• What's the trend for Nykaa this month?",
            "chart": None,
            "insights": [],
            "key_metrics": {},
            "follow_up_questions": [
                "Show me revenue by platform",
                "What are the top selling products?",
                "How does Nykaa compare to Myntra?"
            ],
            "viz_type": None,
            "row_count": 0,
        }
    }


def _detect_off_topic(question: str) -> dict:
    """Detect off-topic questions that are not related to business analytics.
    We now let the LLM handle these dynamically to give real answers instead of hard-blocks.
    """
    return None


def pre_classify(question: str) -> dict:
    """
    Minimal pre-classification using simple rules.
    Returns intent type for routing - the general_llm node handles all conversational responses.

    Returns: {"type": str, "confidence": float, "skip_llm": bool, "response": dict (optional)}
    """
    if not question:
        return {
            "type": "empty",
            "confidence": 1.0,
            "skip_llm": True,
            "response": {
                "text": "I didn't receive a question. Could you please ask me something about your data?",
                "chart": None,
                "insights": [],
                "key_metrics": {},
                "follow_up_questions": ["Show me revenue by platform"],
                "viz_type": None,
                "row_count": 0,
            }
        }

    q = question.lower().strip()

    # Check for off-topic questions first
    off_topic_result = _detect_off_topic(question)
    if off_topic_result:
        return off_topic_result

    # Detect obvious greetings
    # We strip any trailing punctuation like ? ! .
    q_clean = re.sub(r'[?!.]+$', '', q).strip()
    greeting_match = re.match(r"^(hi|hello|hey|gm|gn|good morning|good evening|good afternoon|how are you)$", q_clean)
    if greeting_match:
        return _get_greeting_response(question)

    # Let LLM handle everything else
    return {
        "type": "llm_classify",
        "confidence": 0.5,
        "skip_llm": False,
    }
