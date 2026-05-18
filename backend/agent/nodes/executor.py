"""
Node 4: Query Execution
Runs the validated SQL against the connected datasource.
Handles errors gracefully, formats results for downstream nodes.
"""
from __future__ import annotations
import time
import structlog
from backend.agent.state import AnalyticsState
from backend.data.connector import execute_query
from backend.config import settings

log = structlog.get_logger(__name__)


async def execute_sql(state: AnalyticsState) -> AnalyticsState:
    sql = state.get("sql_query", "")
    datasource_id = state.get("datasource_id")

    if not sql:
        return {**state, "error": "No SQL query to execute", "query_results": {"rows": [], "columns": []}}

    if state.get("error"):
        return state  # propagate upstream error

    try:
        t0 = time.perf_counter()
        result = await execute_query(datasource_id, sql, timeout=settings.query_timeout_seconds)
        execution_ms = int((time.perf_counter() - t0) * 1000)

        rows = result.get("rows", [])
        columns = result.get("columns", [])

        log.info("sql.executed",
                 rows=len(rows),
                 columns=len(columns),
                 execution_ms=execution_ms)

        query_results = {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": execution_ms,
            "truncated": len(rows) >= settings.max_rows_returned,
        }

        return {**state, "query_results": query_results}

    except Exception as exc:
        error_msg = str(exc)
        log.error("sql.execution_failed", error=error_msg, sql=sql[:100])

        # Try to auto-fix common errors
        if "no such table" in error_msg.lower() or "does not exist" in error_msg.lower():
            return {**state,
                    "error": f"Table not found. Available tables may have changed. Error: {error_msg}",
                    "query_results": {"rows": [], "columns": [], "row_count": 0}}

        if "syntax error" in error_msg.lower():
            return {**state,
                    "error": f"SQL syntax error: {error_msg}",
                    "query_results": {"rows": [], "columns": [], "row_count": 0}}

        return {**state,
                "error": f"Query failed: {error_msg}",
                "query_results": {"rows": [], "columns": [], "row_count": 0}}
