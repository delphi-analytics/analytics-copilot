"""General LLM Node — Handle conversational and general knowledge questions."""
import structlog
from backend.agent.state import AnalyticsState
from backend.agent.llm import call_llm

log = structlog.get_logger(__name__)


async def handle_general_query(state: AnalyticsState) -> AnalyticsState:
    """
    Handle general queries (greetings, conversational, general knowledge)
    using the LLM naturally without hardcoded responses.
    """
    question = state.get("user_question", "")
    history = state.get("conversation_history", [])
    intent = state.get("intent", {})
    intent_type = intent.get("type", "")

    # Build conversation history context (last 5 messages)
    history_context = ""
    if history:
        recent_history = history[-5:]
        history_context = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in recent_history
        ])
        history_context = f"\n\nRecent conversation:\n{history_context}"

    # Build prompt for natural response
    if intent_type == "greeting":
        # Greetings still get a helpful welcome but with natural variation
        prompt = f"""You are a friendly Data Analytics Copilot for an e-commerce company called Limese.

User just greeted you with: "{question}"{history_context}

Respond naturally and warmly (1-2 sentences max). Then suggest 3 specific analytics questions they could ask about their business data.

Keep it concise and conversational. DO NOT use markdown headers like ## or ###."""

    elif intent_type == "conversational":
        # Questions like "who are you", "what can you do"
        prompt = f"""You are a Data Analytics Copilot for an e-commerce company called Limese.

User asked: "{question}"{history_context}

Explain what you can do naturally in 2-3 sentences. Focus on:
- Answering questions about sales, revenue, products, customers
- Generating charts and visualizations
- Analyzing trends and providing insights
- Working with data from multiple platforms (Nykaa, Myntra, Amazon, etc.)

End with 3 example questions they could ask. Be conversational, NOT robotic."""

    else:
        # General knowledge or off-topic - handle gracefully
        prompt = f"""You are a helpful AI assistant for a data analytics platform called Limese Copilot.

User asked: "{question}"{history_context}

If this is a general knowledge question (math, facts, etc.), answer it directly and concisely.

If this is unrelated to business analytics, politely redirect them to ask about their data:
- Sales and revenue trends
- Product performance
- Platform comparisons
- Customer insights

Keep your response to 2-3 sentences max. Be conversational and helpful."""

    try:
        resp = await call_llm(
            messages=[{"role": "user", "content": prompt}],
            task="general",
            max_tokens=300,
            temperature=0.8,  # Higher temperature for more varied responses
        )

        response_text = resp.content.strip()

        # Generate contextual follow-ups
        follow_ups = _generate_general_followups(question, intent_type)

        return {
            **state,
            "skip_pipeline": True,
            "pre_filter_response": {
                "text": response_text,
                "chart": None,
                "insights": [],
                "key_metrics": {},
                "follow_up_questions": follow_ups,
                "sql": "",
                "sql_explanation": "",
                "row_count": 0,
                "viz_type": None,
                "columns": [],
                "rows": [],
                "total_latency_ms": 200,
                "model_used": "general_llm",
            }
        }

    except Exception as e:
        log.warning("general_llm.failed", error=str(e))
        # Fallback to simple response
        return {
            **state,
            "skip_pipeline": True,
            "pre_filter_response": {
                "text": (
                    f"I'm your Data Analytics Copilot. I can help you explore sales, revenue, "
                    "products, and trends for your business. Try asking about revenue by platform, "
                    "top selling products, or monthly trends!"
                ),
                "chart": None,
                "insights": [],
                "key_metrics": {},
                "follow_up_questions": [
                    "Show me revenue by platform",
                    "What are the top selling products?",
                    "How does Nykaa compare to Myntra?"
                ],
                "sql": "",
                "row_count": 0,
                "viz_type": None,
                "columns": [],
                "rows": [],
            }
        }


def _generate_general_followups(question: str, intent_type: str) -> list[str]:
    """Generate contextual follow-up questions for general queries."""
    q_lower = question.lower()

    # If they asked about the copilot itself
    if any(w in q_lower for w in ["who are you", "what are you", "help", "capabilities"]):
        return [
            "Show me revenue by platform",
            "What are the top selling products?",
            "Show monthly sales trend"
        ]

    # If they asked about the company/data
    if any(w in q_lower for w in ["sales", "revenue", "performance"]):
        return [
            "Show revenue by platform",
            "Compare this month to last month",
            "Which products are selling best?"
        ]

    # Default follow-ups
    return [
        "Show me revenue by platform",
        "What are the top selling products?",
        "How is business doing this month?"
    ]
