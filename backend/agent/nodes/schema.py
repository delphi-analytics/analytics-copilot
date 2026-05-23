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


import re

def _keyword_select_tables(question: str, tables: list[dict]) -> list[str]:
    """
    Fallback: pick tables dynamically by matching keywords in the question
    against table names, column names, descriptions, and Limese fallbacks.
    """
    q = question.lower()
    selected = []

    # 1. Build keyword lists dynamically for all tables
    for table in tables:
        tname = table["name"]
        tname_lower = tname.lower()

        keywords = {tname_lower, tname_lower.replace("_", " "), tname_lower.replace("-", " ")}
        # Add parts of table name
        for part in re.split(r'[-_]', tname_lower):
            if len(part) > 2:
                keywords.add(part)

        # Add column names
        for col in table.get("columns", []):
            cname = col.get("name", "").lower()
            keywords.add(cname)
            for part in re.split(r'[-_]', cname):
                if len(part) > 2:
                    keywords.add(part)

        # Add table description keywords
        desc = table.get("description", "").lower()
        if desc:
            for word in re.findall(r'\b\w{3,}\b', desc):
                keywords.add(word)

        if any(kw in q for kw in keywords):
            selected.append(tname)

    # 2. Hardcoded fallback checks for Limese specifically (for backwards compatibility)
    if not selected:
        for table in tables:
            tname = table["name"]
            kws = _TABLE_KEYWORDS.get(tname, [])
            if any(kw in q for kw in kws):
                selected.append(tname)

    # 3. Always ensure a default table is selected if list is empty
    if not selected and tables:
        selected.append(tables[0]["name"])

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
        selected_names = _keyword_select_tables(question, tables)

    # Validate — only keep table names that actually exist
    valid_names = [n for n in selected_names if n in all_table_names]
    if not valid_names:
        valid_names = _keyword_select_tables(question, tables)

    # Enrich with full column metadata from the real schema
    table_map = {t["name"]: t for t in tables}
    relevant_tables = []
    for name in valid_names[:4]:
        full_table = table_map.get(name, {"name": name, "columns": []})
        relevant_tables.append({
            "name": name,
            "columns": full_table.get("columns", []),
            "sample_data": full_table.get("sample_data"),
            "row_count": full_table.get("row_count"),
            "description": full_table.get("description", ""),
        })

    schema_context = {
        "relevant_tables": relevant_tables,
        "suggested_joins": suggested_joins,
    }

    log.info("schema.discovered", tables=[t["name"] for t in relevant_tables])
    return {**state, "schema_context": schema_context}
