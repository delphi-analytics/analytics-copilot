"""
Node 2: Data & Schema Discovery
Finds the relevant tables and columns for the question.
Uses cached schema + LLM to select most relevant tables.

Role boundary: ONLY selects which tables are relevant.
Does NOT generate SQL. Does NOT execute queries.
"""
from __future__ import annotations
import json
import structlog
from backend.agent.state import AnalyticsState
from backend.agent.llm import call_llm
from backend.data.connector import get_schema

log = structlog.get_logger(__name__)

# Keyword → table mapping for instant fallback when LLM JSON fails
_TABLE_KEYWORDS: dict[str, list[str]] = {
    "combined_sales_final":          ["revenue", "sales", "order", "platform", "channel", "subtotal", "amount", "income"],
    "product_master":                ["product", "item", "sku", "category", "brand", "name", "skincare", "makeup", "haircare"],
    "product_catlog":                ["catalog", "catlog", "catalogue", "listing"],
    "inventory_sales_overview_new":  ["inventory", "stock", "warehouse", "restock", "supply", "on hand", "low stock"],
    "platform_sku_mapping":          ["mapping", "external sku", "platform sku"],
    "shopify_orders":                ["shopify", "online store", "website"],
    "unicomm_sales_final":           ["unicomm", "unicommerce"],
    "zoho_sales_final":              ["zoho"],
    "lead_time":                     ["lead time", "replenishment", "delivery days"],
}


def _keyword_select_tables(question: str, all_table_names: list[str]) -> list[str]:
    """Fallback: pick tables by keyword matching the question."""
    q = question.lower()
    selected = []
    for tname in all_table_names:
        kws = _TABLE_KEYWORDS.get(tname, [tname.lower().replace("_", " ")])
        if any(kw in q for kw in kws):
            selected.append(tname)
    # Always include the primary sales table for revenue/order queries
    if not selected or ("revenue" in q or "sale" in q or "order" in q):
        if "combined_sales_final" not in selected:
            selected.insert(0, "combined_sales_final")
    # Add product_master when products, categories are mentioned
    if any(k in q for k in ["product", "item", "sku", "category", "skincare", "makeup"]):
        if "product_master" not in selected:
            selected.append("product_master")
    return selected[:4]


async def discover_schema(state: AnalyticsState) -> AnalyticsState:
    # Skip if SQL was already populated by semantic cache
    if state.get("sql_query"):
        return state

    intent = state.get("intent", {})
    datasource_id = state.get("datasource_id")
    question = intent.get("rephrased_question") or state.get("user_question", "")

    # Fetch schema (from 1-hour in-memory cache or live)
    try:
        full_schema = await get_schema(datasource_id)
    except Exception as exc:
        log.error("schema.fetch_failed", error=str(exc))
        full_schema = {"tables": [], "error": str(exc)}

    tables = full_schema.get("tables", [])
    all_table_names = [t["name"] for t in tables]

    if not tables:
        return {**state, "schema_context": {"relevant_tables": [], "error": "No tables found"}}

    # Build a COMPACT schema summary — only table name + column names (no types, no row counts)
    # This keeps the prompt under 400 tokens so the 8B model returns valid JSON reliably.
    schema_summary = "\n".join(
        f"{t['name']}: {', '.join(c['name'] for c in t.get('columns', [])[:25])}"
        for t in tables[:20]
    )

    prompt = f"""Select the most relevant database tables for this question.

Question: "{question}"

Available tables and their columns:
{schema_summary}

Return JSON only — no explanation:
{{
  "relevant_tables": ["table1", "table2"],
  "suggested_joins": ["table_a.col = table_b.col"]
}}

Rules:
- Return at most 4 table names (strings only, not objects)
- Always include combined_sales_final for revenue/sales/order questions
- Include product_master when products/categories/SKUs are mentioned
- Include inventory_sales_overview_new for stock/inventory questions"""

    selected_names: list[str] = []
    suggested_joins: list[str] = []

    try:
        resp = await call_llm(
            messages=[{"role": "user", "content": prompt}],
            task="routing",
            max_tokens=200,
            temperature=0.0,
        )
        raw = resp.content.strip()
        # Strip markdown fences if present
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        parsed = json.loads(raw)
        raw_tables = parsed.get("relevant_tables", [])
        # Accept both string list and object list formats
        for t in raw_tables:
            if isinstance(t, str):
                selected_names.append(t)
            elif isinstance(t, dict) and "name" in t:
                selected_names.append(t["name"])
        suggested_joins = parsed.get("suggested_joins", [])
    except Exception as exc:
        log.warning("schema.llm_selection_failed", error=str(exc))
        # Smart keyword fallback instead of blind tables[:3]
        selected_names = _keyword_select_tables(question, all_table_names)

    # Validate — only keep table names that actually exist
    valid_names = [n for n in selected_names if n in all_table_names]
    if not valid_names:
        valid_names = _keyword_select_tables(question, all_table_names)

    # Enrich with full column metadata from the real schema
    table_map = {t["name"]: t for t in tables}
    relevant_tables = []
    for name in valid_names[:4]:
        full_table = table_map.get(name, {"name": name, "columns": []})
        relevant_tables.append({
            "name": name,
            "columns": full_table.get("columns", []),
            "sample_data": full_table.get("sample_data"),
        })

    schema_context = {
        "relevant_tables": relevant_tables,
        "suggested_joins": suggested_joins,
    }

    log.info("schema.discovered", tables=[t["name"] for t in relevant_tables])
    return {**state, "schema_context": schema_context}
