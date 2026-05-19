"""
Node 7: Response & Follow-ups
Composes the final response: text + chart + insights + suggested next questions.
"""
from __future__ import annotations
import json
import structlog
from backend.agent.state import AnalyticsState
from backend.agent.memory import vector_memory
from backend.agent.llm import call_llm

log = structlog.get_logger(__name__)


async def compose_response(state: AnalyticsState) -> AnalyticsState:
    question = state["user_question"]
    insights = state.get("insights", [])
    key_metrics = state.get("key_metrics", {})
    anomalies = state.get("anomalies", [])
    viz_type = state.get("viz_type", "table")
    query_results = state.get("query_results", {})
    sql_explanation = state.get("sql_explanation", "")
    error = state.get("error")

    row_count = query_results.get("row_count", 0)

    # Handle error case
    if error and not row_count:
        return {
            **state,
            "response_text": f"I encountered an issue: {error}\n\nPlease try rephrasing your question or check the data source connection.",
            "follow_up_questions": [
                "Show me what tables are available",
                "Can you simplify the query?",
                "Show me a sample of the data",
            ],
            "final_response": {
                "text": f"I encountered an issue: {error}",
                "chart": None,
                "insights": [],
                "key_metrics": {},
                "follow_up_questions": [],
                "sql": state.get("sql_query", ""),
                "row_count": 0,
                "viz_type": None,
            },
        }

    # Build text response — replace $ with ₹ in all values
    def _inr(v: str) -> str:
        import re
        return re.sub(r'\$\s?([\d,]+(?:\.\d+)?)', lambda m: f'₹{m.group(1)}', str(v))

    insights_text = "\n".join(f"* {_inr(i)}" for i in insights[:3]) if insights else ""
    metrics_text = " | ".join(f"**{k}**: {_inr(v)}" for k, v in list(key_metrics.items())[:4]) if key_metrics else ""
    anomaly_text = f"\n⚠️ Notable: {anomalies[0]}" if anomalies else ""

    response_parts = []
    if metrics_text:
        response_parts.append(metrics_text)
    if insights_text:
        response_parts.append(insights_text)
    if anomaly_text:
        response_parts.append(anomaly_text)

    response_text = "\n\n".join(response_parts) if response_parts else f"Here are the results ({row_count} rows found)."

    if row_count == 0:
        response_text = "No data found for your query. Try adjusting the filters or time range."

    # Generate follow-up questions
    try:
        follow_ups = await _generate_follow_ups(question, insights, viz_type)
    except Exception:
        follow_ups = _default_follow_ups(question)

    log.info("responder.complete", response_length=len(response_text))

    final_response = {
        "text": response_text,
        "chart": state.get("viz_config") if row_count > 0 else None,
        "insights": insights[:3],
        "key_metrics": key_metrics,
        "anomalies": anomalies,
        "follow_up_questions": follow_ups,
        "sql": state.get("sql_query", ""),
        "sql_explanation": sql_explanation,
        "row_count": row_count,
        "viz_type": viz_type,
        "columns": query_results.get("columns", []),
        "rows": query_results.get("rows", [])[:200],
        "truncated": query_results.get("truncated", False),
    }

    # Store in Vector Memory (Qdrant) for long-term semantic learning
    sql = state.get("sql_query")
    if sql and not state.get("error"):
        try:
            vector_memory.store_query(
                user_id=state.get("user_id", "anonymous"),
                question=state["user_question"],
                sql=sql,
                payload={
                    "datasource_id": state.get("datasource_id"),
                    "viz_type": viz_type,
                    "row_count": row_count
                }
            )
            log.debug("responder.stored_in_vector_memory", question=state["user_question"][:60])
        except Exception as e:
            log.warning("responder.vector_store_failed", error=str(e))

    return {**state, "response_text": response_text, "follow_up_questions": follow_ups, "final_response": final_response}


async def _generate_follow_ups(question: str, insights: list, viz_type: str) -> list[str]:
    prompt = f"""A user asked: "{question}"
Key insights found: {insights[:2]}
Chart type shown: {viz_type}

Suggest 3 natural follow-up questions they would likely ask next.
Return as JSON array: ["question 1", "question 2", "question 3"]
Keep them short (under 10 words each) and directly related."""

    resp = await call_llm(
        messages=[{"role": "user", "content": prompt}],
        task="routing",
        max_tokens=150,
        temperature=0.4,
    )
    raw = resp.content.strip()
    if "```" in raw:
        raw = raw.split("```")[1].replace("json", "").strip()
    return json.loads(raw)[:3]


def _default_follow_ups(question: str) -> list[str]:
    return [
        "Show this as a different chart type",
        "Break this down by category",
        "Compare with the previous period",
    ]
