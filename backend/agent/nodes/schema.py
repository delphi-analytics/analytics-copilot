"""
Node 2: Data & Schema Discovery
Finds the relevant tables and columns for the question.
Uses cached schema + LLM to select most relevant tables.
"""
from __future__ import annotations
import json
import structlog
from backend.agent.state import AnalyticsState
from backend.agent.llm import call_llm
from backend.data.connector import get_schema

log = structlog.get_logger(__name__)


async def discover_schema(state: AnalyticsState) -> AnalyticsState:
    intent = state.get("intent", {})
    datasource_id = state.get("datasource_id")
    question = intent.get("rephrased_question", state["user_question"])

    # Fetch schema (from cache or live)
    try:
        full_schema = await get_schema(datasource_id)
    except Exception as exc:
        log.error("schema.fetch_failed", error=str(exc))
        full_schema = {"tables": [], "error": str(exc)}

    tables = full_schema.get("tables", [])

    if not tables:
        return {**state, "schema_context": {"relevant_tables": [], "error": "No tables found"}}

    # Limit schema text to avoid token overflow
    schema_summary = "\n".join(
        f"Table: {t['name']}\n  Columns: {', '.join(c['name'] + '(' + c['type'] + ')' for c in t.get('columns', [])[:20])}"
        for t in tables[:30]
    )

    prompt = f"""You are a data engineer selecting relevant database tables for a query.

Question: "{question}"
Entities mentioned: {intent.get("entities", [])}

Available tables:
{schema_summary}

Return JSON with the most relevant tables (max 5):
{{
  "relevant_tables": [
    {{
      "name": "<table_name>",
      "reason": "<why this table is relevant>",
      "key_columns": ["<col1>", "<col2>"],
      "estimated_relevance": <0.0-1.0>
    }}
  ],
  "suggested_joins": [
    "<table_a.col JOIN table_b.col>"
  ],
  "date_column_hint": "<most likely date/timestamp column for time filters or null>"
}}"""

    try:
        resp = await call_llm(
            messages=[{"role": "user", "content": prompt}],
            task="routing",
            max_tokens=500,
            temperature=0.0,
        )
        raw = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        schema_selection = json.loads(raw)

        # Enrich selected tables with full column info from schema
        table_map = {t["name"]: t for t in tables}
        relevant_tables = []
        for sel in schema_selection.get("relevant_tables", []):
            full_table = table_map.get(sel["name"], sel)
            relevant_tables.append({
                **sel,
                "columns": full_table.get("columns", []),
                "sample_data": full_table.get("sample_data"),
            })

        schema_context = {
            "relevant_tables": relevant_tables,
            "suggested_joins": schema_selection.get("suggested_joins", []),
            "date_column_hint": schema_selection.get("date_column_hint"),
        }
    except Exception as exc:
        log.warning("schema.selection_failed", error=str(exc))
        # Fall back to first 3 tables
        schema_context = {"relevant_tables": tables[:3], "suggested_joins": []}

    log.info("schema.discovered", tables=[t.get("name") for t in schema_context["relevant_tables"]])
    return {**state, "schema_context": schema_context}
