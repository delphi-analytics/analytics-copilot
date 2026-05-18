"""
Node 3: SQL Generation & Validation
Generates SQL from the question + schema context.
Uses smart model (Groq 70B / Claude) for accuracy.
Validates syntax before passing to execution.
"""
from __future__ import annotations
import json
import re
import structlog
from backend.agent.state import AnalyticsState
from backend.agent.llm import call_llm
from backend.agent.memory import vector_memory
from backend.config import settings

log = structlog.get_logger(__name__)


def _clean_sql(sql: str) -> str:
    """
    Strip trailing JSON artifacts that Groq sometimes appends to the SQL string.
    """
    for pattern in [
        r'(SELECT[\s\S]+?LIMIT\s+\d+)\s*"[\s\S]*$',
        r'(SELECT[\s\S]+?)\s*",\s*"(?:explanation|columns|is_aggregated)',
        r'(SELECT[\s\S]+?)\s*;\s*"[\s\S]*$',
    ]:
        m = re.search(pattern, sql, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return sql.strip()


def _parse_sql_from_llm(content: str) -> tuple[str, dict]:
    """
    Robust parser for LLM SQL responses.
    """
    raw = content.strip()
    result: dict = {"explanation": "", "columns_returned": []}

    # 1. Try to parse as JSON first
    try:
        json_str = raw
        if "```" in raw:
            match = re.search(r'```(?:json)?\s*(\{[\s\S]+?\})\s*```', raw)
            if match: json_str = match.group(1)
        
        parsed = json.loads(json_str)
        sql = parsed.get("sql", "").strip()
        result["explanation"] = parsed.get("explanation", "")
        result["columns_returned"] = parsed.get("columns_returned", [])
        if sql: return _clean_sql(sql), result
    except:
        pass

    # 2. Fallback: Search & Rescue for SELECT
    sql_match = re.search(r'(SELECT[\s\S]+?(?:LIMIT\s+\d+|;|$))', raw, re.IGNORECASE)
    if sql_match:
        sql = _clean_sql(sql_match.group(1))
        if len(sql) > 10:
            return sql, result

    return "", result


DANGEROUS_PATTERNS = [
    r"\bDROP\b", r"\bDELETE\b", r"\bTRUNCATE\b", r"\bALTER\b",
    r"\bCREATE\b", r"\bINSERT\b", r"\bUPDATE\b", r"\bGRANT\b",
    r"\bREVOKE\b", r"\bEXEC\b", r"\bEXECUTE\b", r"--", r";.*SELECT",
]


def _is_safe_sql(sql: str) -> tuple[bool, str]:
    if not sql: return False, "Empty SQL"
    upper = sql.upper()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, upper):
            return False, f"Dangerous pattern detected: {pattern}"
    if "SELECT" not in upper:
        return False, "Only SELECT queries allowed"
    return True, "OK"


async def generate_sql(state: AnalyticsState) -> AnalyticsState:
    intent = state.get("intent", {})
    schema_context = state.get("schema_context", {})
    question = intent.get("rephrased_question", state["user_question"])

    tables = schema_context.get("relevant_tables", [])
    datasource_id = state.get("datasource_id", "")
    is_clickhouse = datasource_id == "limese"

    db_intelligence_context = ""
    if is_clickhouse:
        try:
            from backend.services.db_intelligence import get_db_context, build_sql_context_prompt
            relevant_table_names = [t.get("name") for t in tables if t.get("name")]
            ctx = get_db_context()
            db_intelligence_context = build_sql_context_prompt(ctx, question, relevant_table_names)
        except Exception as exc:
            log.warning("sql_gen.db_intelligence_failed", error=str(exc))

    schema_section = db_intelligence_context if db_intelligence_context else "Use the provided schema."
    
    similar_queries = vector_memory.search_similar_queries(question, limit=2)
    examples_str = ""
    if similar_queries:
        examples_str = "\nPAST EXAMPLES:\n" + "\n".join([f"Q: {q['question']}\nSQL: {q['sql']}" for q in similar_queries])

    heatmap_example = """
EXAMPLE (Heatmap of Platform vs Month):
Question: "Revenue by platform and month for 2025"
SQL: SELECT sales_platform, formatDateTime(date_created, '%Y-%m') AS month, sum(row_subtotal) AS revenue
     FROM combined_sales_final
     WHERE final_status NOT IN ('cancelled','returned') AND date_created >= '2025-01-01'
     GROUP BY sales_platform, month
     ORDER BY month ASC, revenue DESC
     LIMIT 500
""" if is_clickhouse else ""

    prompt = f"""You are a ClickHouse SQL expert.
{schema_section}
{heatmap_example}
{examples_str}
User question: "{question}"

Return ONLY this JSON:
{{
  "sql": "<complete SQL query>",
  "explanation": "<one sentence what it does>",
  "columns_returned": ["col1", "col2"],
  "is_aggregated": true
}}"""

    from backend.config import settings as _s
    try:
        resp = await call_llm(
            messages=[{"role": "user", "content": prompt}],
            model=_s.llm_smart_model,
            task="sql",
            max_tokens=800,
            temperature=0.1,
        )
    except Exception as exc:
        return {**state, "error": f"AI model failed: {str(exc)[:100]}", "sql_query": ""}

    sql, result = _parse_sql_from_llm(resp.content)
    is_safe, reason = _is_safe_sql(sql)
    
    if not is_safe:
        return {**state, "error": f"Invalid SQL: {reason}", "sql_query": ""}

    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(";") + f" LIMIT {settings.max_rows_returned}"

    return {
        **state,
        "sql_query": sql,
        "sql_validated": True,
        "sql_explanation": result.get("explanation", ""),
        "model_used": resp.model,
    }
