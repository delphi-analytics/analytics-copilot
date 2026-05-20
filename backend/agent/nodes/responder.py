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

    # Check if pre-filter already handled this (greeting, off-topic)
    if state.get("pre_filter_response"):
        log.info("responder.pre_filter")
        return {
            **state,
            "response_text": state["pre_filter_response"]["text"],
            "follow_up_questions": state["pre_filter_response"].get("follow_up_questions", []),
            "final_response": state["pre_filter_response"],
        }

    # Check if this is an insight follow-up response
    if state.get("insight_followup_response"):
        log.info("responder.insight_followup")
        return {
            **state,
            "response_text": state["insight_followup_response"]["text"],
            "follow_up_questions": state["insight_followup_response"].get("follow_up_questions", []),
            "final_response": state["insight_followup_response"],
        }

    # Check if this is an analytical question - generate narrative response
    intent_type = state.get("intent", {}).get("type", "")
    if intent_type == "analytical_question" and query_results.get("row_count", 0) > 0:
        return await _compose_analytical_response(state)

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

    # Build beautiful executive conversational narrative summary
    response_text = ""
    if not error and row_count > 0:
        summary_prompt = f"""You are Limese's Senior Analytics Copilot. Write a highly professional, conversational executive summary answering the user's question based on the actual metrics and findings.

User Question: "{question}"
Key Metrics: {key_metrics}
Raw Bullet Point Insights: {insights}
Total Rows Returned: {row_count}

RULES:
1. Write a direct, polished narrative summary in 1-2 paragraphs max (3-5 sentences total).
2. DO NOT write lists, bullet points, or raw tables — the UI displays bullet points separately under "Key Insights".
3. Bold key metrics (e.g. **₹16.21 Cr** or **1.4L units**).
4. Use ₹ (Rupee) for Indian currency format. Never use USD or $ unless specifically asked.
5. Keep the tone conversational, helpful, and highly strategic for a business owner."""

        try:
            resp = await call_llm(
                messages=[{"role": "user", "content": summary_prompt}],
                task="general",
                max_tokens=350,
                temperature=0.3,
            )
            response_text = resp.content.strip()
        except Exception as exc:
            log.warning("responder.summary_llm_failed", error=str(exc))

    # Fallback to narrative paragraph if LLM fails or returned empty
    if not response_text and not error:
        if row_count == 0:
            response_text = "No data found for your query. Try adjusting the filters or time range."
        else:
            metrics_part = ""
            if key_metrics:
                metrics_part = " showing " + ", ".join(f"**{k}** of {v}" for k, v in list(key_metrics.items())[:3])
            
            response_text = f"I've analyzed the data for **{question}** and retrieved **{row_count}** matching records{metrics_part}. "
            if insights:
                # Remove leading bullet points/dashes if present
                clean_ins0 = insights[0].lstrip("*-• ").strip()
                response_text += f"A key takeaway from the analysis is: {clean_ins0}. "
                if len(insights) > 1:
                    clean_ins1 = insights[1].lstrip("*-• ").strip()
                    # Lowercase first character if appropriate
                    if clean_ins1 and clean_ins1[0].isupper() and not clean_ins1.startswith("₹"):
                        clean_ins1 = clean_ins1[0].lower() + clean_ins1[1:]
                    response_text += f"Additionally, {clean_ins1}."

    # Generate follow-up questions
    sql = state.get("sql_query", "")
    columns = query_results.get("columns", [])
    try:
        follow_ups = await _generate_follow_ups(question, insights, viz_type, sql, columns)
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


async def _generate_follow_ups(question: str, insights: list, viz_type: str, sql: str = "", columns: list = []) -> list[str]:
    """
    Generate follow-up questions that are GUARANTEED to be answerable by the system.
    Grounds suggestions in the actual database schema, known columns, and domain context.
    """
    import re

    # ── Extract time scope from SQL so follow-ups stay in the same period ──────
    year_hints = re.findall(r"'(20\d\d)(?:-\d\d)?(?:-\d\d)?'", sql)
    year_scope = ", ".join(sorted(set(year_hints))) if year_hints else "the same period as the query"

    # ── Extract which table(s) were queried ────────────────────────────────────
    tables_used = []
    for tname in ["combined_sales_final", "product_master", "inventory_sales_overview_new",
                   "shopify_orders", "unicomm_sales_final", "zoho_sales_final"]:
        if tname in sql.lower():
            tables_used.append(tname)
    tables_str = ", ".join(tables_used) if tables_used else "combined_sales_final"

    # ── Domain knowledge: always-available dimensions ─────────────────────────
    KNOWN_DIMENSIONS = """
AVAILABLE DIMENSIONS (always queryable via combined_sales_final + product_master JOIN):
- sales_platform: 'Nykaa Beauty', 'Myntra_PPMP', 'Shopify', 'Unicomm', 'Zoho'
- category_l1: 'Skincare', 'Makeup', 'Haircare'
- category_l2: sub-category (Face Wash, Serum, Foundation, etc.)
- item_name: individual product name (from product_master)
- internal_sku: unique product code
- date_created: order date (for monthly/daily grouping)
- final_status: order status (already filtered out cancelled/returned)

AVAILABLE METRICS:
- row_subtotal → revenue/sales (SUM)
- quantity_ordered → units sold (SUM)
- COUNT(*) → number of orders
"""

    cols_str = ", ".join(columns) if columns else "revenue, platform"

    prompt = f"""You are generating follow-up questions for an analytics dashboard about Limese beauty brand sales.

User's original question: "{question}"
SQL query used tables: {tables_str}
Columns in the result: {cols_str}
Time period filtered: {year_scope}
Chart shown: {viz_type}
Key insight: {insights[0] if insights else 'N/A'}

{KNOWN_DIMENSIONS}

Generate exactly 3 follow-up questions. Each question MUST:
1. Be directly answerable using the dimensions and metrics listed above via a single SQL query
2. Stay within the same time period ({year_scope}) unless asking for a comparison
3. Be a natural drill-down or comparison from the original question
4. Be specific — use real platform names, category names, or metric names from above (not vague phrases like "break this down further")
5. Be under 12 words

GOOD examples (specific, answerable):
- "Show revenue by category_l1 on Nykaa Beauty in {year_scope}"
- "Which product had highest units sold in {year_scope}?"
- "Compare Skincare vs Makeup revenue in {year_scope}"
- "Show monthly revenue trend for Nykaa Beauty in {year_scope}"

BAD examples (vague, unanswerable):
- "Break this down further" ← too vague
- "Show me more details" ← not specific
- "Compare with other regions" ← no region column exists

Return ONLY a JSON array of exactly 3 strings: ["question 1", "question 2", "question 3"]"""

    try:
        resp = await call_llm(
            messages=[{"role": "user", "content": prompt}],
            task="routing",
            max_tokens=200,
            temperature=0.2,
        )
        raw = resp.content.strip()
        if not raw:
            raise ValueError("Empty LLM response")
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        result = json.loads(raw)
        if isinstance(result, list) and len(result) >= 1:
            return [q for q in result if isinstance(q, str)][:3]
        raise ValueError("Invalid format")
    except Exception:
        return _default_follow_ups(question, year_scope)


def _default_follow_ups(question: str, year_scope: str = "2025") -> list[str]:
    """Deterministic fallback follow-ups — always answerable."""
    q_lower = question.lower()
    # Pick context-relevant fallbacks
    if "nykaa" in q_lower:
        return [
            f"Show Nykaa Beauty revenue by category in {year_scope}",
            f"Which product sold most on Nykaa in {year_scope}?",
            f"Compare Nykaa vs Myntra revenue in {year_scope}",
        ]
    if "myntra" in q_lower:
        return [
            f"Show Myntra revenue by category in {year_scope}",
            f"Compare Myntra vs Nykaa revenue in {year_scope}",
            f"Which SKU performed best on Myntra in {year_scope}?",
        ]
    if "skincare" in q_lower or "makeup" in q_lower or "haircare" in q_lower:
        return [
            f"Show monthly revenue trend by category in {year_scope}",
            f"Which platform drives most Skincare sales in {year_scope}?",
            f"Compare category revenue across platforms in {year_scope}",
        ]
    # Generic but always answerable defaults
    return [
        f"Show revenue by platform in {year_scope}",
        f"Which product had highest sales in {year_scope}?",
        f"Show monthly revenue trend in {year_scope}",
    ]




async def _compose_analytical_response(state: AnalyticsState) -> dict:
    """
    Compose a narrative, prose-based response for analytical questions.
    Uses the fetched data to ground the explanation in facts.
    """
    question = state["user_question"]
    query_results = state.get("query_results", {})
    insights = state.get("insights", [])
    key_metrics = state.get("key_metrics", {})
    row_count = query_results.get("row_count", 0)
    columns = query_results.get("columns", [])
    rows = query_results.get("rows", [])[:10]

    # Build data context for the LLM
    data_summary = f"""
Question: {question}

Data Retrieved ({row_count} rows):
Columns: {columns}

Sample Data:
{rows[:5]}

Key Metrics:
{key_metrics}

Insights Found:
{insights[:3]}
"""

    prompt = f"""You are a data analyst answering an analytical question.

{data_summary}

Provide a clear, conversational answer (2-3 paragraphs) that:
1. Directly addresses their "why/explain" question
2. Uses specific numbers from the data above
3. Provides context and interpretation
4. Is easy to understand (avoid technical jargon)

Format with markdown for readability. Use ₹ for currency.

After your explanation, suggest 2-3 specific follow-up questions."""

    try:
        resp = await call_llm(
            messages=[{"role": "user", "content": prompt}],
            task="analysis",
            max_tokens=600,
            temperature=0.4,
        )

        # Generate contextual follow-up questions
        follow_ups = await _generate_analytical_followups(question, key_metrics, insights)

        return {
            **state,
            "response_text": resp.content,
            "follow_up_questions": follow_ups,
            "final_response": {
                "text": resp.content,
                "chart": state.get("viz_config"),  # Still show chart if available
                "insights": insights,
                "key_metrics": key_metrics,
                "follow_up_questions": follow_ups,
                "sql": state.get("sql_query", ""),
                "row_count": row_count,
                "viz_type": state.get("viz_type"),
                "columns": columns,
                "rows": rows,
            }
        }
    except Exception as exc:
        log.warning("analytical_response.failed", error=str(exc))
        # Fallback to standard response
        return {
            **state,
            "response_text": f"Based on the data ({row_count} rows found), here are the key findings:\n\n" + "\n".join(f"* {i}" for i in insights[:3]),
            "follow_up_questions": _default_follow_ups(question),
        }


async def _generate_analytical_followups(question: str, key_metrics: dict, insights: list, sql: str = "") -> list[str]:
    """Delegate to the main schema-aware follow-up generator for consistency."""
    try:
        columns = list(key_metrics.keys())
        return await _generate_follow_ups(question, insights, "table", sql, columns)
    except Exception:
        return _default_follow_ups(question)

