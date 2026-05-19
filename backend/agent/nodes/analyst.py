"""
Node 5: Insight & Analysis
Analyzes query results to find key metrics, trends, anomalies.
Generates human-readable insights from raw data.
"""
from __future__ import annotations
import json
import structlog
from backend.agent.state import AnalyticsState
from backend.agent.llm import call_llm

log = structlog.get_logger(__name__)


def _compute_basic_stats(rows: list, columns: list) -> dict:
    """Compute basic stats client-side to reduce LLM tokens."""
    if not rows or not columns:
        return {}

    stats: dict = {}
    # Find numeric columns
    for col in columns:
        values = []
        for row in rows:
            val = row.get(col) if isinstance(row, dict) else None
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    pass

        if values:
            stats[col] = {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "total": sum(values),
                "count": len(values),
            }

    return stats


async def analyze_insights(state: AnalyticsState) -> AnalyticsState:
    query_results = state.get("query_results", {})
    intent = state.get("intent", {})
    question = state["user_question"]

    rows = query_results.get("rows", [])
    columns = query_results.get("columns", [])

    if not rows:
        return {**state,
                "insights": ["No data found for this query."],
                "key_metrics": {},
                "anomalies": []}

    # Compute stats locally
    basic_stats = _compute_basic_stats(rows, columns)

    # Prepare data sample for LLM (max 50 rows to save tokens)
    sample_rows = rows[:50]
    data_preview = json.dumps({"columns": columns, "rows": sample_rows[:10]}, default=str)

    stats_summary = json.dumps(basic_stats, indent=2, default=str) if basic_stats else "No numeric columns"

    prompt = f"""You are a data analyst. Analyze this query result and generate business insights.

Original question: "{question}"
Intent: {intent.get("type")} | Time range: {intent.get("time_range")}

Data stats:
{stats_summary}

Sample data (first 10 rows):
{data_preview}

Total rows: {query_results.get("row_count", 0)}

Return JSON:
{{
  "insights": [
    "<insight 1 — most important finding>",
    "<insight 2>",
    "<insight 3 — optional>"
  ],
  "key_metrics": {{
    "<metric name>": "<value with unit>"
  }},
  "anomalies": [
    "<anomaly or outlier if found>"
  ],
  "trend": "<increasing|decreasing|stable|volatile|null>",
  "top_performer": "<highest value entity if applicable>",
  "bottom_performer": "<lowest value entity if applicable>",
  "summary_sentence": "<one sentence that directly answers the user's question>"
}}

Keep insights actionable and business-focused. Use specific numbers from the data.

CRITICAL REASONING & CONTENT RULES:
1. If the user asks for "reasons", "causes", "factors", or "drivers" of a trend (decline/growth/change):
   - Every single bullet point in the "insights" list MUST represent a specific, concrete reason, factor, or driver (e.g., specific platform drop, category decline, volume decrease, seasonal effect) based on the data.
   - Do NOT just summarize the chart or repeat overall statistics. Answer the "why" or "what causes this" directly using the data points.

IMPORTANT: Use ₹ (Rupee) symbol ONLY for monetary values (Revenue, Sales, Spend, Profit).
Do NOT use ₹ for counts (Orders, Units, Users, Tickets).
Format large numbers in Indian style: e.g. ₹23.8 Cr (monetary), 2.8 L units (count)."""

    try:
        resp = await call_llm(
            messages=[{"role": "user", "content": prompt}],
            task="analysis",
            max_tokens=600,
            temperature=0.2,
        )
        raw = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        analysis = json.loads(raw)
    except Exception as exc:
        log.warning("analyst.parse_failed", error=str(exc))
        analysis = {
            "insights": [f"Query returned {len(rows)} rows."],
            "key_metrics": {k: str(v.get("total", "")) for k, v in basic_stats.items()},
            "anomalies": [],
            "summary_sentence": f"Found {len(rows)} records matching your query.",
        }

    log.info("analyst.complete", insight_count=len(analysis.get("insights", [])))
    return {
        **state,
        "insights": analysis.get("insights", []),
        "key_metrics": analysis.get("key_metrics", {}),
        "anomalies": analysis.get("anomalies", []),
    }
