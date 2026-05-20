"""
Node: Insight Follow-up Handler
Handles conversational follow-ups like "why is this happening?", "tell me more", etc.
These don't require SQL generation — they analyze existing results.
"""
from __future__ import annotations
import json
import structlog
from backend.agent.state import AnalyticsState
from backend.agent.llm import call_llm

log = structlog.get_logger(__name__)


# Patterns that indicate an insight follow-up (not a new data query)
INSIGHT_FOLLOWUP_PATTERNS = [
    "why is", "why did", "why does", "why are",
    "tell me more", "explain", "elaborate",
    "what about", "how come", "reason for",
    "insight", "analysis", "breakdown",
    "driving", "caused", "factors",
]


def _is_insight_followup(question: str, history: list) -> bool:
    """Check if this is an insight follow-up question."""
    q_lower = question.lower().strip()

    # Check for insight patterns
    for pattern in INSIGHT_FOLLOWUP_PATTERNS:
        if pattern in q_lower:
            return True

    # Check if it references previous result
    if history and len(history) >= 2:
        prev = history[-2]  # Last assistant message
        if prev.get("role") == "assistant":
            # If user asks about "this", "it", etc., it's a follow-up
            if any(word in q_lower for word in ["this", "it", "that", "these", "those"]):
                return True

    return False


async def handle_insight_followup(state: AnalyticsState) -> AnalyticsState:
    """
    Handle follow-up questions about insights without running SQL.
    Analyzes previous query results and provides deeper explanation.
    """
    question = state["user_question"]
    conversation_id = state.get("conversation_id")
    history = state.get("conversation_history", [])

    # Try to get previous assistant message with results
    prev_insights = []
    prev_sql = ""
    prev_question = ""
    prev_rows_count = 0

    # Extract from history
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            # Look for insights in the message
            if "insight" in content.lower() or "₹" in content or "revenue" in content.lower():
                # Found a response with data
                prev_insights = [content]
                break
        elif msg.get("role") == "user":
            prev_question = msg.get("content", "")
            if prev_question and prev_question != question:
                break

    # If we don't have context, provide helpful response
    if not prev_insights:
        return {
            **state,
            "skip_to_response": True,
            "insight_followup_response": {
                "text": (
                    "I'd be happy to explain more! To give you the best answer, could you be more specific? "
                    "For example:\n\n"
                    "• 'Why did Nykaa revenue drop in March?'\n"
                    "• 'What factors drove the increase in skincare sales?'\n"
                    "• 'Which products are contributing most to the trend?'\n\n"
                    "Or you can re-ask your original question and I'll provide a detailed explanation."
                ),
                "chart": None,
                "insights": [],
                "follow_up_questions": [
                    "Show me revenue by platform for last month",
                    "What are the top selling products?",
                    "Compare this month vs last month"
                ],
                "viz_type": None,
                "row_count": 0,
            }
        }

    # Generate contextual explanation
    context = f"""
Previous question: {prev_question}
Previous insights: {prev_insights[0][:500] if prev_insights else 'Not available'}

Current follow-up question: {question}
"""

    prompt = f"""You are a helpful data analyst having a conversation with a user.

{context}

The user is asking a follow-up question. Provide a conversational, helpful response that:
1. Directly addresses their follow-up
2. References the context from our previous discussion
3. Is concise (2-3 sentences max)
4. Suggests one specific next step if relevant

Be friendly and helpful. Use simple language."""

    try:
        resp = await call_llm(
            messages=[{"role": "user", "content": prompt}],
            task="analysis",
            max_tokens=300,
            temperature=0.5,
        )

        return {
            **state,
            "skip_to_response": True,
            "insight_followup_response": {
                "text": resp.content,
                "chart": None,  # No new chart for insight follow-ups
                "insights": [],
                "follow_up_questions": [
                    "Show me the detailed data",
                    "Compare with previous period",
                    "Break this down further"
                ],
                "viz_type": None,
                "row_count": 0,
            }
        }
    except Exception as exc:
        log.warning("insight_followup.failed", error=str(exc))
        return {
            **state,
            "skip_to_response": True,
            "insight_followup_response": {
                "text": "I'd like to help explain that further. Could you rephrase your question or be more specific about what you'd like to know?",
                "chart": None,
                "insights": [],
                "follow_up_questions": [],
                "viz_type": None,
                "row_count": 0,
            }
        }
