"""General LLM Node — Handle conversational and general knowledge questions."""
import json
import structlog
from backend.agent.state import AnalyticsState
from backend.agent.llm import call_llm
from backend.data.connector import get_schema

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
    datasource_id = state.get("datasource_id", "default")

    # Load active database schema context dynamically
    tables = []
    db_summary = ""
    try:
        schema = await get_schema(datasource_id)
        tables = schema.get("tables", [])
        if tables:
            summary_parts = []
            for t in tables[:5]:  # Limit to first 5 tables for prompt length
                t_name = t.get("name", "")
                t_desc = t.get("description", "")
                cols = [c.get("name", "") for c in t.get("columns", [])]
                col_list = ", ".join(cols[:8])
                if len(cols) > 8:
                    col_list += ", ..."
                desc_str = f" ({t_desc})" if t_desc else ""
                summary_parts.append(f"- Table: `{t_name}`{desc_str}. Columns: {col_list}")
            db_summary = "\n".join(summary_parts)
    except Exception as e:
        log.warning("general_llm.load_schema_failed", error=str(e))

    # Build conversation history context (last 5 messages)
    history_context = ""
    if history:
        recent_history = history[-5:]
        history_context = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in recent_history
        ])
        history_context = f"\n\nRecent conversation:\n{history_context}"

    # Build prompt for natural response based on the active schema
    if intent_type == "greeting":
        prompt = f"""You are a friendly Data Analytics Copilot.
User just greeted you with: "{question}"{history_context}

Active Database Schema Details:
{db_summary or "No active database schema available."}

Respond to the greeting naturally and warmly (1-2 sentences max). Then suggest 3 specific analytics questions the user could ask about their active database tables and columns.
Do not assume this is an e-commerce or Limese database unless the schema details above explicitly contain e-commerce tables. Customize the response and the suggestions to fit the active database schema provided.

Return your response ONLY as a JSON object matching this schema:
{{
  "text": "Warm greeting reply",
  "follow_up_questions": [
    "Context-specific question 1",
    "Context-specific question 2",
    "Context-specific question 3"
  ]
}}"""

    elif intent_type == "conversational":
        prompt = f"""You are a helpful Data Analytics Copilot.
User asked: "{question}"{history_context}

Active Database Schema Details:
{db_summary or "No active database schema available."}

Explain what you can do naturally in 2-3 sentences based on the active database schemas/tables. Focus on how you can help them analyze their specific database tables and columns, generate charts, and find trends.
Do not assume this is an e-commerce or Limese database unless the schema details above explicitly contain e-commerce tables. Customize the description and suggestions to fit the active database schema.

Return your response ONLY as a JSON object matching this schema:
{{
  "text": "Your explanation of capabilities",
  "follow_up_questions": [
    "Context-specific question 1",
    "Context-specific question 2",
    "Context-specific question 3"
  ]
}}"""

    else:
        # General knowledge or off-topic - handle gracefully
        prompt = f"""You are a helpful AI assistant for a data analytics platform.
User asked: "{question}"{history_context}

Active Database Schema Details:
{db_summary or "No active database schema available."}

If this is a general knowledge question (math, facts, weather, etc.), answer it directly and concisely.
If this is unrelated to business analytics, politely redirect them to ask about their actual database data:
Mention some of the actual tables/columns they have (e.g., they can ask about {', '.join([t.get('name','') for t in tables[:3]]) if tables else 'their database data'}).
Do not assume this is an e-commerce or Limese database unless the schema details above explicitly contain e-commerce tables. Customize your response to fit their active database.

Return your response ONLY as a JSON object matching this schema:
{{
  "text": "Direct answer or polite redirection",
  "follow_up_questions": [
    "Context-specific question 1",
    "Context-specific question 2",
    "Context-specific question 3"
  ]
}}"""

    try:
        resp = await call_llm(
            messages=[{"role": "user", "content": prompt}],
            task="general",
            max_tokens=300,
            temperature=0.8,  # Higher temperature for more varied responses
        )

        raw = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()

        try:
            parsed = json.loads(raw)
            response_text = parsed.get("text", "").strip()
            follow_ups = parsed.get("follow_up_questions", [])
        except Exception:
            response_text = raw
            follow_ups = _generate_general_followups(question, intent_type, tables)

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
        fallback_follow_ups = _generate_general_followups(question, intent_type, tables)
        return {
            **state,
            "skip_pipeline": True,
            "pre_filter_response": {
                "text": (
                    f"I'm your Data Analytics Copilot. I can help you explore and analyze your database tables. "
                    f"Try asking questions about " + (f"the {tables[0]['name']} table." if tables else "your data!")
                ),
                "chart": None,
                "insights": [],
                "key_metrics": {},
                "follow_up_questions": fallback_follow_ups,
                "sql": "",
                "row_count": 0,
                "viz_type": None,
                "columns": [],
                "rows": [],
            }
        }


def _generate_general_followups(question: str, intent_type: str, tables: list[dict]) -> list[str]:
    """Generate contextual fallback follow-up questions for general queries based on active tables."""
    if not tables:
        return [
            "Show me a list of tables",
            "What columns are in this database?",
            "Can you help me analyze this data?"
        ]

    table_names = [t.get("name", "") for t in tables[:3]]
    follow_ups = []

    for t_name in table_names:
        follow_ups.append(f"Show details about the {t_name} table")

    if len(follow_ups) < 3:
        follow_ups.append("Show the list of all tables")

    return follow_ups[:3]
