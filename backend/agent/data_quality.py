"""
Data Quality Validation
Validates query results before displaying them to users.
Checks for empty/null values in critical columns and provides helpful feedback.
"""
from __future__ import annotations
import structlog
from backend.agent.state import AnalyticsState

log = structlog.get_logger(__name__)


# Columns that should NEVER be empty or null for meaningful results
CRITICAL_COLUMNS = {
    "item_name": "product name",
    "product_name": "product name",
    "internal_sku": "SKU/product code",
    "name": "name field",
    "title": "title field",
    "product": "product identifier",
}


def _check_empty_critical_columns(rows: list, columns: list) -> dict | None:
    """
    Check if critical columns have too many empty/null values.
    Returns a dict with the issue info if problems found, None otherwise.
    """
    if not rows or not columns:
        return None

    columns_lower = [c.lower() for c in columns]
    issues = []

    for critical_col, display_name in CRITICAL_COLUMNS.items():
        if critical_col in columns_lower:
            col_idx = columns_lower.index(critical_col)

            # Count empty/null values in this column
            empty_count = 0
            for row in rows:
                val = row.get(columns[col_idx]) if isinstance(row, dict) else None
                if val is None or val == "" or (isinstance(val, str) and val.strip() == ""):
                    empty_count += 1

            # If more than 50% of critical column is empty, it's a problem
            if empty_count > len(rows) / 2:
                issues.append({
                    "column": columns[col_idx],
                    "display_name": display_name,
                    "empty_count": empty_count,
                    "total_count": len(rows),
                    "empty_percentage": (empty_count / len(rows)) * 100
                })

    if issues:
        return {
            "has_empty_critical_data": True,
            "issues": issues
        }
    return None


def _check_all_null_results(rows: list, columns: list) -> dict | None:
    """
    Check if all returned values are null or zero.
    This can happen when filters are too restrictive.
    """
    if not rows or not columns:
        return None

    # Check if all numeric values are null/0 and all strings are empty/null
    all_empty = True
    sample_values = {}

    for row in rows[:10]:  # Check first 10 rows
        for col in columns:
            val = row.get(col) if isinstance(row, dict) else None
            if val is not None and val != "" and val != 0:
                all_empty = False
                sample_values[col] = val
                break
        if not all_empty:
            break

    if all_empty:
        return {
            "has_empty_critical_data": True,
            "all_null_or_empty": True,
            "issues": [{
                "column": "all",
                "display_name": "all data",
                "empty_count": len(rows),
                "total_count": len(rows),
                "empty_percentage": 100
            }]
        }
    return None


def validate_data_quality(state: AnalyticsState) -> AnalyticsState:
    """
    Validate query results for data quality issues.
    Returns appropriate error messages if data quality is poor.
    """
    query_results = state.get("query_results", {})
    rows = query_results.get("rows", [])
    columns = query_results.get("columns", [])
    row_count = query_results.get("row_count", 0)

    # No results at all
    if row_count == 0:
        return {**state, "data_quality_issue": "no_results"}

    # Check for all-null/empty results
    all_null_check = _check_all_null_results(rows, columns)
    if all_null_check:
        log.warning("data_quality.all_null_results", row_count=row_count)
        return {
            **state,
            "data_quality_issue": "all_null",
            "data_quality_details": all_null_check
        }

    # Check for empty critical columns
    empty_critical = _check_empty_critical_columns(rows, columns)
    if empty_critical:
        log.warning("data_quality.empty_critical_columns", issues=empty_critical["issues"])
        return {
            **state,
            "data_quality_issue": "empty_critical_columns",
            "data_quality_details": empty_critical
        }

    # Data quality looks good
    return {**state, "data_quality_issue": None}


def get_data_quality_error_message(state: AnalyticsState) -> str | None:
    """
    Generate a user-friendly error message for data quality issues.
    """
    issue = state.get("data_quality_issue")
    details = state.get("data_quality_details")

    if not issue:
        return None

    if issue == "no_results":
        question = state.get("user_question", "")
        return (
            f"I couldn't find any data matching your query about **{question[:50]}...**\n\n"
            f"This could mean:\n"
            f"• The filters are too restrictive\n"
            f"• The date range has no data\n"
            f"• The specific products/entities don't exist in the database\n\n"
            f"**Suggestions:**\n"
            f"• Try a broader date range (e.g., 2025 instead of a specific month)\n"
            f"• Check available products or categories first\n"
            f"• Ask about overall trends instead of specific items"
        )

    if issue == "all_null":
        return (
            f"The query returned **{state.get('query_results', {}).get('row_count', 0)} rows** "
            f"but all values are empty or null.\n\n"
            f"This suggests the data for your query might not be available yet. "
            f"Try asking about:\n"
            f"• Overall revenue by platform\n"
            f"• Top selling products\n"
            f"• Monthly sales trends"
        )

    if issue == "empty_critical_columns" and details:
        issues_list = details.get("issues", [])
        if issues_list:
            worst_issue = max(issues_list, key=lambda x: x["empty_percentage"])
            col_name = worst_issue.get("column", "")
            display_name = worst_issue.get("display_name", col_name)
            empty_pct = worst_issue.get("empty_percentage", 0)

            return (
                f"The query returned results, but **{empty_pct:.0f}% of {display_name} values are empty or missing**.\n\n"
                f"This means the data quality is insufficient to provide meaningful insights.\n\n"
                f"**This could indicate:**\n"
                f"• The products haven't been fully catalogued yet\n"
                f"• Data synchronization is incomplete\n"
                f"• The specific subset of data hasn't been populated\n\n"
                f"**Suggestions:**\n"
                f"• Try querying at a higher level (e.g., by platform or category instead of by product)\n"
                f"• Check overall metrics first before drilling into specifics\n"
                f"• Contact the data team about missing product information"
            )

    return None
