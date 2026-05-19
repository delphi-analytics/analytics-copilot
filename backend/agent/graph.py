"""
LangGraph Agent Pipeline — Data Visualization Copilot
Orchestrates the 7-step pipeline:
  Intent → Schema → SQL → Execute → Analyze → Visualize → Respond

Each step is a pure async function that reads/writes to AnalyticsState.
LangGraph handles the DAG execution, state passing, and error propagation.
"""
from __future__ import annotations

import time
import structlog
from langgraph.graph import StateGraph, END

from backend.agent.state import AnalyticsState
from backend.agent.nodes.intent import understand_intent
from backend.agent.nodes.schema import discover_schema
from backend.agent.nodes.sql_gen import generate_sql
from backend.agent.nodes.executor import execute_sql
from backend.agent.nodes.analyst import analyze_insights
from backend.agent.nodes.viz_config import generate_viz_config
from backend.agent.nodes.responder import compose_response
from backend.agent.nodes.insight_followup import handle_insight_followup, _is_insight_followup

log = structlog.get_logger(__name__)


def _should_skip_sql(state: AnalyticsState) -> str:
    """Route: skip SQL generation for greetings, analytical questions, or export requests."""
    # Check if pre-filter already handled this
    if state.get("skip_pipeline"):
        return "skip_to_respond"

    intent_type = state.get("intent", {}).get("type", "")
    question = state.get("user_question", "")
    history = state.get("conversation_history", [])

    # Check for insight follow-up (e.g., "why is this happening?")
    if _is_insight_followup(question, history):
        return "insight_followup"

    # Analytical questions need data but different treatment
    if intent_type == "analytical_question":
        return "generate_sql"  # Still get data, but respond differently

    # Skip for greetings or export requests
    if intent_type in ("greeting", "export_request"):
        return "skip_to_respond"

    return "generate_sql"


def _should_retry_sql(state: AnalyticsState) -> str:
    """Route: retry SQL if execution failed due to schema mismatch."""
    error = state.get("error", "")
    row_count = state.get("query_results", {}).get("row_count", 0)
    if error and "syntax error" in error.lower():
        return "retry"   # Could retry with different SQL
    return "analyze"


def build_graph() -> StateGraph:
    """Build and compile the LangGraph pipeline."""
    graph = StateGraph(AnalyticsState)

    # Register all 7 nodes + insight follow-up
    graph.add_node("understand_intent", understand_intent)
    graph.add_node("discover_schema", discover_schema)
    graph.add_node("generate_sql", generate_sql)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("analyze_insights", analyze_insights)
    graph.add_node("generate_viz_config", generate_viz_config)
    graph.add_node("compose_response", compose_response)
    graph.add_node("insight_followup", handle_insight_followup)

    # Entry point
    graph.set_entry_point("understand_intent")

    # Linear pipeline with conditional routing
    graph.add_conditional_edges(
        "understand_intent",
        _should_skip_sql,
        {
            "generate_sql": "discover_schema",
            "skip_to_respond": "compose_response",
            "insight_followup": "insight_followup",
        }
    )
    graph.add_edge("discover_schema", "generate_sql")
    graph.add_edge("generate_sql", "execute_sql")
    graph.add_edge("execute_sql", "analyze_insights")
    graph.add_edge("analyze_insights", "generate_viz_config")
    graph.add_edge("generate_viz_config", "compose_response")
    graph.add_edge("insight_followup", "compose_response")
    graph.add_edge("compose_response", END)

    return graph.compile()


# Singleton compiled graph
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def run_analytics_agent(
    question: str,
    datasource_id: str,
    session_id: str,
    conversation_id: str,
    conversation_history: list[dict],
    user_id: str = "anonymous",
) -> dict:
    """
    Main entry point for the analytics agent.
    Returns the final_response dict ready to send to the frontend.
    """
    t0 = time.perf_counter()

    initial_state: AnalyticsState = {
        "session_id": session_id,
        "conversation_id": conversation_id,
        "user_question": question,
        "datasource_id": datasource_id,
        "conversation_history": conversation_history,
        "user_id": user_id,
        "step_errors": [],
    }

    try:
        graph = get_graph()
        final_state = await graph.ainvoke(initial_state)

        total_ms = int((time.perf_counter() - t0) * 1000)
        log.info(
            "agent.complete",
            session_id=session_id,
            total_ms=total_ms,
            viz_type=final_state.get("viz_type"),
            row_count=final_state.get("query_results", {}).get("row_count", 0),
        )

        result = final_state.get("final_response", {})
        result["total_latency_ms"] = total_ms
        result["model_used"] = final_state.get("model_used", "")
        return result

    except Exception as exc:
        total_ms = int((time.perf_counter() - t0) * 1000)
        log.error("agent.failed", error=str(exc), total_ms=total_ms)
        return {
            "text": f"I ran into an unexpected error. Please try again. ({str(exc)[:100]})",
            "chart": None,
            "insights": [],
            "key_metrics": {},
            "follow_up_questions": ["Try a simpler question", "Check your data source connection"],
            "sql": "",
            "row_count": 0,
            "viz_type": None,
            "total_latency_ms": total_ms,
            "error": str(exc),
        }
