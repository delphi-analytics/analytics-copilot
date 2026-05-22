"""
Enhanced Agent Graph with Real-time Progress Tracking
Streams actual node execution progress instead of fake updates.
"""
from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator, Callable
from langgraph.graph import StateGraph
from langgraph.pregel import Pregel

from backend.agent.state import AnalyticsState
from backend.agent.nodes import (
    intent, schema, sql_gen, executor,
    analyst, viz_config, responder, general_llm, disambiguate
)
from backend.agent.nodes.insight_followup import handle_insight_followup, _is_insight_followup
import structlog

log = structlog.get_logger(__name__)


class StreamingGraphRunner:
    """Wraps the LangGraph execution with real progress streaming."""

    # Step definitions with descriptions and progress percentages
    STEPS = {
        "understand_intent": {
            "progress": 10,
            "message": "Understanding your question...",
            "description": "Analyzing what you're asking for"
        },
        "disambiguate": {
            "progress": 15,
            "message": "Clarifying ambiguous terms...",
            "description": "Checking if any terms need clarification"
        },
        "general_llm": {
            "progress": 50,
            "message": "Generating response...",
            "description": "Formulating a conversational answer"
        },
        "discover_schema": {
            "progress": 25,
            "message": "Exploring database structure...",
            "description": "Finding relevant tables and columns"
        },
        "generate_sql": {
            "progress": 45,
            "message": "Writing SQL query...",
            "description": "Generating the database query"
        },
        "execute_sql": {
            "progress": 60,
            "message": "Running query on database...",
            "description": "Fetching your data"
        },
        "analyze_insights": {
            "progress": 75,
            "message": "Analyzing results...",
            "description": "Finding patterns and insights"
        },
        "generate_viz_config": {
            "progress": 85,
            "message": "Creating visualization...",
            "description": "Building your chart"
        },
        "compose_response": {
            "progress": 95,
            "message": "Preparing response...",
            "description": "Finalizing the answer"
        },
    }

    def __init__(self):
        self.graph = self._build_streaming_graph()
        self.progress_callback: Callable[[str, int, dict], Any] | None = None

    def set_progress_callback(self, callback: Callable[[str, int, dict], Any]):
        """Set callback for progress updates."""
        self.progress_callback = callback

    def _emit_progress(self, step: str, data: dict | None = None):
        """Emit progress update if callback is set."""
        if self.progress_callback:
            step_info = self.STEPS.get(step, {
                "progress": 50,
                "message": f"Processing {step}...",
                "description": ""
            })
            self.progress_callback(
                step,
                step_info["progress"],
                {**step_info, "data": data or {}}
            )

    def _wrap_node(self, original_func, node_name: str):
        """Wrap a node function to emit progress before/after execution."""
        async def wrapped(state: AnalyticsState) -> AnalyticsState:
            # Emit start
            self._emit_progress(node_name, {"status": "starting"})

            try:
                # Run original node
                result = await original_func(state)

                # Emit completion with partial results
                partial_data = {"status": "complete"}

                # Add node-specific data for streaming
                if node_name == "understand_intent":
                    intent = result.get("intent", {})
                    partial_data["intent"] = intent.get("type")
                    partial_data["rephrased_question"] = intent.get("rephrased_question")

                elif node_name == "discover_schema":
                    # Emit tables being used
                    relevant_tables = result.get("relevant_tables", [])
                    partial_data["tables"] = relevant_tables

                elif node_name == "generate_sql":
                    partial_data["sql"] = result.get("sql_query", "")

                elif node_name == "execute_sql":
                    qr = result.get("query_results", {})
                    partial_data["row_count"] = qr.get("row_count", 0)
                    partial_data["columns"] = qr.get("columns", [])[:10]

                elif node_name == "analyze_insights":
                    partial_data["insights"] = result.get("insights", [])[:3]
                    partial_data["key_metrics"] = result.get("key_metrics", {})

                elif node_name == "generate_viz_config":
                    partial_data["viz_type"] = result.get("viz_type")

                self._emit_progress(node_name, partial_data)
                return result

            except Exception as e:
                self._emit_progress(node_name, {
                    "status": "error",
                    "error": str(e)
                })
                raise

        return wrapped

    def _build_streaming_graph(self) -> StateGraph:
        """Build the graph with progress-wrapped nodes."""
        graph = StateGraph(AnalyticsState)

        # Wrap nodes with progress tracking
        graph.add_node(
            "understand_intent",
            self._wrap_node(intent.understand_intent, "understand_intent")
        )
        graph.add_node(
            "disambiguate",
            self._wrap_node(disambiguate.disambiguate, "disambiguate")
        )
        graph.add_node(
            "general_llm",
            self._wrap_node(general_llm.handle_general_query, "general_llm")
        )
        graph.add_node(
            "discover_schema",
            self._wrap_node(schema.discover_schema, "discover_schema")
        )
        graph.add_node(
            "generate_sql",
            self._wrap_node(sql_gen.generate_sql, "generate_sql")
        )
        graph.add_node(
            "execute_sql",
            self._wrap_node(executor.execute_sql, "execute_sql")
        )
        graph.add_node(
            "analyze_insights",
            self._wrap_node(analyst.analyze_insights, "analyze_insights")
        )
        graph.add_node(
            "generate_viz_config",
            self._wrap_node(viz_config.generate_viz_config, "generate_viz_config")
        )
        graph.add_node(
            "compose_response",
            self._wrap_node(responder.compose_response, "compose_response")
        )
        graph.add_node(
            "insight_followup",
            self._wrap_node(handle_insight_followup, "insight_followup")
        )

        # Same routing logic as original graph
        graph.set_entry_point("understand_intent")

        def _should_skip_sql(state: AnalyticsState) -> str:
            if state.get("skip_pipeline"):
                return "skip_to_respond"

            intent_type = state.get("intent", {}).get("type", "")
            question = state.get("user_question", "")
            history = state.get("conversation_history", [])

            if _is_insight_followup(question, history):
                return "insight_followup"

            if intent_type == "analytical_question":
                return "generate_sql"

            if intent_type in ("greeting", "conversational", "off_topic"):
                return "general_llm"

            if intent_type == "export_request":
                return "skip_to_respond"

            return "generate_sql"

        def _after_disambiguate(state: AnalyticsState) -> str:
            if state.get("skip_pipeline"):
                return "skip_to_respond"
            return "discover_schema"

        graph.add_conditional_edges(
            "understand_intent",
            _should_skip_sql,
            {
                "generate_sql": "disambiguate",
                "skip_to_respond": "compose_response",
                "insight_followup": "insight_followup",
                "general_llm": "general_llm",
            }
        )
        graph.add_conditional_edges(
            "disambiguate",
            _after_disambiguate,
            {
                "discover_schema": "discover_schema",
                "skip_to_respond": "compose_response",
            }
        )
        graph.add_edge("discover_schema", "generate_sql")
        graph.add_edge("generate_sql", "execute_sql")
        graph.add_edge("execute_sql", "analyze_insights")
        graph.add_edge("analyze_insights", "generate_viz_config")
        graph.add_edge("generate_viz_config", "compose_response")
        graph.add_edge("insight_followup", "compose_response")
        graph.add_edge("general_llm", "compose_response")
        graph.add_edge("compose_response", "__end__")

        return graph.compile()

    async def astream(
        self,
        initial_state: AnalyticsState,
    ) -> AsyncIterator[dict]:
        """
        Execute graph and yield progress updates.

        Yields dicts with:
        - type: "progress" | "complete" | "error"
        - step: current node name
        - progress: 0-100
        - message: user-friendly description
        - data: partial results from each node
        """
        t0 = time.perf_counter()

        # Generator to collect progress updates
        progress_queue = []

        def progress_callback(step: str, progress: int, info: dict):
            progress_queue.append({
                "type": "progress",
                "step": step,
                "progress": progress,
                "message": info["message"],
                "data": info.get("data", {}),
                "timestamp": time.time()
            })

        self.set_progress_callback(progress_callback)

        try:
            # Run the graph using astream so we can yield updates in real-time
            final_state = initial_state
            async for output in self.graph.astream(initial_state):
                # Drain and yield any progress events generated during this node's execution
                while progress_queue:
                    yield progress_queue.pop(0)
                
                # Keep track of the latest state
                for node_name, state in output.items():
                    final_state = state

            # Emit any remaining queued progress updates
            while progress_queue:
                yield progress_queue.pop(0)

            # Final result
            total_ms = int((time.perf_counter() - t0) * 1000)
            result = final_state.get("final_response", {})
            result["total_latency_ms"] = total_ms
            result["model_used"] = final_state.get("model_used", "")

            yield {
                "type": "complete",
                "result": result,
                "total_latency_ms": total_ms
            }

        except Exception as exc:
            # Emit queued progress before error
            for update in progress_queue:
                yield update

            yield {
                "type": "error",
                "error": str(exc),
                "step": progress_queue[-1]["step"] if progress_queue else "unknown"
            }


# Singleton
_streaming_graph = None


def get_streaming_graph() -> StreamingGraphRunner:
    global _streaming_graph
    if _streaming_graph is None:
        _streaming_graph = StreamingGraphRunner()
    return _streaming_graph
