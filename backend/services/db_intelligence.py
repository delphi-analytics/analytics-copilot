"""
Database Intelligence Layer — Limese ClickHouse
================================================
Scans the connected database (READ-ONLY) and builds a comprehensive
context document that is injected into every LLM SQL-generation prompt.

What it extracts per table:
  - Row count & date range
  - Every column: type, unique count, exact categorical values (≤ 200 unique)
  - Key business facts (total revenue, top platforms, date coverage)
  - Column-level annotations (which col = revenue, units, date, etc.)
  - Common query patterns validated against real data

Auto-refreshes every REFRESH_HOURS on a background thread.
Context stored at: /tmp/dvc_metadata/db_intelligence.json
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import clickhouse_connect
import structlog

log = structlog.get_logger(__name__)

CONTEXT_FILE = Path(__file__).parent.parent / "data" / "db_intelligence.json"
CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)

REFRESH_HOURS = 24         # auto-refresh every 24 hours
MAX_CATEGORICAL = 200      # if unique values ≤ this, store all exact values

# Tables to scan deeply — priority order
PRIORITY_TABLES = [
    "combined_sales_final",
    "product_master",
    "product_catlog",
    "inventory_sales_overview_new",
    "platform_sku_mapping",
    "shopify_orders",
    "unicomm_sales_final",
    "zoho_sales_final",
    "lead_time",
]

# Hard-coded business annotations layered on top of auto-discovered schema
# These are facts the LLM MUST know to write correct SQL
COLUMN_ANNOTATIONS: dict[str, dict[str, str]] = {
    "combined_sales_final": {
        "sales_platform":   "DIMENSION — use this to GROUP BY platform. Contains exact platform names shown below.",
        "client_name":      "CONSTANT 'Limese' for all rows — NEVER group by this for platform analysis.",
        "row_subtotal":     "REVENUE per line item — USE THIS for revenue/sales. Do NOT use order_price (full order total).",
        "quantity_ordered": "UNITS per line — USE THIS for unit counts. Do NOT use shipped_qty (always 0).",
        "date_created":     "Primary date column. Filter: date_created >= '2025-01-01'. Group: formatDateTime(date_created, '%Y-%m').",
        "final_status":     "Order outcome. ALWAYS exclude: NOT IN ('cancelled','Cancelled','CANCELLED','returned','Returned').",
        "internal_sku":     "Join key → product_master.internal_sku for product names and category.",
        "external_sku":     "Platform-specific SKU code.",
    },
    "product_master": {
        "internal_sku":   "Primary key. Join with combined_sales_final.internal_sku.",
        "item_name":      "Product display name.",
        "category_l1":    "Top-level category. Values: Skincare, Makeup, Haircare.",
        "mrp":            "Maximum Retail Price.",
        "cogs":           "Cost of Goods Sold — use for margin calculation: mrp - cogs.",
    },
    "inventory_sales_overview_new": {
        "sku":             "Internal SKU — join to product_master.internal_sku.",
        "date":            "Snapshot date. For latest stock: WHERE date >= today() - 2",
        "inventory":       "Units on hand RIGHT NOW. USE THIS for stock level queries.",
        "order_quantity":  "Units sold that day.",
        "gross_sales_rs":  "Daily revenue in ₹.",
        "burn_period":     "Fixed 90-day config value — do NOT use for calculations.",
    },
}

# ─── Core scanner ─────────────────────────────────────────────────────────────

def _get_client() -> Any:
    return clickhouse_connect.get_client(
        host="118.95.209.221", port=8123,
        username="limese_interns", password="ItsInterns!23",
        database="limese", connect_timeout=10,
    )


def _scan_table(client: Any, table: str) -> dict:
    """Deep-scan a single table and return structured context."""
    log.info("db_intelligence.scanning", table=table)

    # Row count
    try:
        cnt = client.query(f"SELECT count() FROM {table}").result_rows[0][0]
    except Exception:
        cnt = 0

    # Schema
    try:
        schema = client.query(f"DESCRIBE TABLE {table}").result_rows
        columns_raw = [{"name": r[0], "type": r[1]} for r in schema]
    except Exception:
        return {"table": table, "error": "could not describe table", "row_count": 0}

    annotations = COLUMN_ANNOTATIONS.get(table, {})
    columns_info: list[dict] = []

    for col in columns_raw:
        col_name = col["name"]
        col_type = col["type"]
        info: dict = {
            "name": col_name,
            "type": col_type,
            "annotation": annotations.get(col_name, ""),
        }

        # Try to get unique count + sample values
        try:
            r = client.query(
                f"SELECT uniq(`{col_name}`) as u, count(`{col_name}`) as nn "
                f"FROM {table}"
            )
            unique = int(r.result_rows[0][0])
            non_null = int(r.result_rows[0][1])
            info["unique_count"] = unique
            info["non_null_count"] = non_null

            # Fetch all values for low-cardinality columns
            if 1 < unique <= MAX_CATEGORICAL:
                try:
                    sv = client.query(
                        f"SELECT DISTINCT `{col_name}` FROM {table} "
                        f"WHERE `{col_name}` IS NOT NULL LIMIT {MAX_CATEGORICAL}"
                    )
                    vals = [str(r[0]) for r in sv.result_rows if r[0] is not None]
                    info["exact_values"] = sorted(vals)
                    info["is_categorical"] = True
                except Exception:
                    pass
            elif unique == 1:
                # Constant column
                try:
                    cv = client.query(f"SELECT `{col_name}` FROM {table} LIMIT 1")
                    info["constant_value"] = str(cv.result_rows[0][0]) if cv.result_rows else "?"
                    info["is_constant"] = True
                except Exception:
                    pass
        except Exception:
            pass

        # Date range for date columns
        type_lower = col_type.lower()
        if "date" in type_lower or "time" in type_lower:
            try:
                dr = client.query(
                    f"SELECT toString(min(`{col_name}`)), toString(max(`{col_name}`)) FROM {table}"
                )
                info["date_range"] = {"min": str(dr.result_rows[0][0]), "max": str(dr.result_rows[0][1])}
            except Exception:
                pass

        # Numerical range for numeric columns
        if any(t in type_lower for t in ["int", "float", "decimal"]) and unique > MAX_CATEGORICAL:
            try:
                nr = client.query(
                    f"SELECT round(min(`{col_name}`),2), round(max(`{col_name}`),2), round(avg(`{col_name}`),2) FROM {table}"
                )
                info["numerical_range"] = {
                    "min": float(nr.result_rows[0][0] or 0),
                    "max": float(nr.result_rows[0][1] or 0),
                    "avg": float(nr.result_rows[0][2] or 0),
                }
            except Exception:
                pass

        columns_info.append(info)

    result = {
        "table": table,
        "row_count": cnt,
        "total_columns": len(columns_info),
        "columns": columns_info,
    }

    # Table-level business facts
    if table == "combined_sales_final":
        try:
            facts = client.query("""
                SELECT
                    round(sum(ifNull(row_subtotal,0))/1e7, 2) as revenue_crore,
                    count() as total_orders,
                    round(sum(ifNull(quantity_ordered,0)),0) as total_units,
                    min(date_created) as earliest,
                    max(date_created) as latest
                FROM combined_sales_final
                WHERE final_status NOT IN ('cancelled','Cancelled','CANCELLED','returned','Returned')
            """)
            row = facts.result_rows[0]
            result["business_facts"] = {
                "total_revenue_crore": float(row[0] or 0),
                "total_orders": int(row[1] or 0),
                "total_units": int(row[2] or 0),
                "date_range": f"{row[3]} to {row[4]}",
            }
        except Exception:
            pass

    if table == "inventory_sales_overview_new":
        try:
            inv = client.query("""
                SELECT count(DISTINCT sku) as skus, round(sum(inventory),0) as total_units
                FROM inventory_sales_overview_new
                WHERE date >= today() - 2
            """)
            row = inv.result_rows[0]
            result["business_facts"] = {
                "tracked_skus": int(row[0] or 0),
                "total_inventory_units": int(row[1] or 0),
            }
        except Exception:
            pass

    return result


def build_db_context() -> dict:
    """
    Full database scan (READ-ONLY).
    Returns a comprehensive context dict with all tables, columns, values, and facts.
    Takes 30-90 seconds on first run; cached to disk.
    """
    client = _get_client()
    log.info("db_intelligence.starting_scan", tables=PRIORITY_TABLES)
    t0 = time.time()

    tables_context = {}
    for table in PRIORITY_TABLES:
        try:
            tables_context[table] = _scan_table(client, table)
        except Exception as exc:
            log.error("db_intelligence.table_failed", table=table, error=str(exc))
            tables_context[table] = {"table": table, "error": str(exc)}

    elapsed = round(time.time() - t0, 1)
    context = {
        "database": "limese",
        "host": "118.95.209.221:8123",
        "scanned_at": datetime.utcnow().isoformat(),
        "scan_duration_seconds": elapsed,
        "tables": tables_context,
        "global_notes": _build_global_notes(tables_context),
    }

    # Save to disk
    try:
        with open(CONTEXT_FILE, "w") as f:
            json.dump(context, f, indent=2, default=str)
        log.info("db_intelligence.saved", path=str(CONTEXT_FILE), seconds=elapsed)
    except Exception as exc:
        log.error("db_intelligence.save_failed", error=str(exc))

    return context


def _build_global_notes(tables: dict) -> list[str]:
    """Human-readable rules derived from the scan, injected as LLM instructions."""
    notes = [
        "DATABASE: Limese — Indian beauty brand. Revenue in Indian Rupees (₹).",
        "READ-ONLY: Never generate INSERT/UPDATE/DELETE/DROP/CREATE/ALTER SQL.",
    ]

    # Extract exact platform names from scan
    csf = tables.get("combined_sales_final", {})
    for col in csf.get("columns", []):
        if col["name"] == "sales_platform" and col.get("exact_values"):
            vals = col["exact_values"]
            notes.append(
                f"PLATFORM NAMES (exact, case-sensitive for WHERE filters): {vals}"
            )
        if col["name"] == "client_name" and col.get("constant_value"):
            notes.append(
                f"client_name is ALWAYS '{col['constant_value']}' — NEVER group by it for platform analysis."
            )

    notes += [
        "REVENUE COLUMN: row_subtotal in combined_sales_final (NOT order_price).",
        "UNITS COLUMN: quantity_ordered in combined_sales_final (NOT shipped_qty — always 0).",
        "DATE FILTER: date_created >= '2025-01-01' (do NOT use toYear() — fails with timezone-aware DateTime).",
        "MANDATORY FILTER: WHERE final_status NOT IN ('cancelled','Cancelled','CANCELLED','returned','Returned').",
        "DATE GROUPING: formatDateTime(date_created, '%Y-%m') for year-month.",
        "JOIN pattern: combined_sales_final csf LEFT JOIN product_master pm ON csf.internal_sku = pm.internal_sku.",
        "INVENTORY: Use inventory_sales_overview_new WHERE date >= today() - 2 for current stock.",
        "CLICKHOUSE FUNCTIONS: ifNull(col, 0), uniq(), groupArray(), toDate(), formatDateTime().",
        "LIMIT: Always add LIMIT (max 10000 for detail, 50 for aggregations).",
    ]
    return notes


# ─── LLM prompt builder ───────────────────────────────────────────────────────

def build_sql_context_prompt(
    context: dict,
    question: str,
    relevant_tables: list[str] | None = None,
    max_cols_per_table: int = 15,   # keep compact — only most useful columns
    max_cat_values: int = 13,       # exact platform/category values only
) -> str:
    """
    Convert the DB intelligence context into a COMPACT LLM-ready string.
    Stays well within model token limits by:
    - Only including relevant tables
    - Skipping columns with no useful info (no annotation, no categorical values, no range)
    - Capping categorical values at max_cat_values
    - Prioritizing annotated and categorical columns
    """
    lines: list[str] = []

    # Global rules first — most critical, always included
    notes = context.get("global_notes", [])
    if notes:
        lines.append("=== CRITICAL RULES ===")
        for note in notes:
            lines.append(f"• {note}")
        lines.append("")

    # Table schemas — only relevant, only useful columns
    lines.append("=== DATABASE SCHEMA ===")
    tables = context.get("tables", {})

    # If no relevant_tables specified, include the 2 most important ones
    tables_to_show = relevant_tables or ["combined_sales_final", "product_master"]

    for tname in tables_to_show:
        tdata = tables.get(tname, {})
        if not tdata or tdata.get("error"):
            continue

        row_count = tdata.get("row_count", 0)
        lines.append(f"\nTABLE: {tname} ({row_count:,} rows)")

        # Business facts
        if tdata.get("business_facts"):
            facts = tdata["business_facts"]
            lines.append(f"  Facts: {json.dumps(facts)}")

        # Sort columns: annotated + categorical first, then others
        all_cols = tdata.get("columns", [])
        priority_cols = [c for c in all_cols if c.get("annotation") or c.get("exact_values") or c.get("is_constant")]
        other_cols = [c for c in all_cols if c not in priority_cols]
        cols_to_show = (priority_cols + other_cols)[:max_cols_per_table]

        for col in cols_to_show:
            col_name = col["name"]
            col_type = col["type"]
            annotation = col.get("annotation", "")

            col_line = f"  • `{col_name}` ({col_type})"

            if col.get("is_constant"):
                col_line += f" — CONSTANT='{col.get('constant_value')}' (never GROUP BY this)"
            elif col.get("exact_values"):
                vals = col["exact_values"][:max_cat_values]
                col_line += f" — VALUES: {vals}"
            elif col.get("date_range"):
                dr = col["date_range"]
                col_line += f" — range: {dr['min'][:10]} to {dr['max'][:10]}"
            elif col.get("numerical_range"):
                nr = col["numerical_range"]
                col_line += f" — range: {nr['min']:,.0f} to {nr['max']:,.0f} (avg: {nr['avg']:,.0f})"

            if annotation:
                col_line += f"\n      ↳ {annotation}"

            lines.append(col_line)

    return "\n".join(lines)


# ─── Context loading / caching ────────────────────────────────────────────────

_context_cache: dict | None = None
_context_loaded_at: float = 0.0
_build_lock = threading.Lock()


def get_db_context(force_refresh: bool = False) -> dict:
    """
    Return the DB intelligence context.
    Loads from disk if available and fresh; otherwise triggers a scan.
    Thread-safe.
    """
    global _context_cache, _context_loaded_at

    # Return in-memory cache if fresh
    if _context_cache and not force_refresh:
        age_hours = (time.time() - _context_loaded_at) / 3600
        if age_hours < REFRESH_HOURS:
            return _context_cache

    # Try loading from disk
    if not force_refresh and CONTEXT_FILE.exists():
        try:
            with open(CONTEXT_FILE) as f:
                ctx = json.load(f)
            scanned_at = ctx.get("scanned_at", "")
            if scanned_at:
                age_hours = (time.time() - datetime.fromisoformat(scanned_at).timestamp()) / 3600
                if age_hours < REFRESH_HOURS:
                    _context_cache = ctx
                    _context_loaded_at = time.time()
                    log.info("db_intelligence.loaded_from_disk", age_hours=round(age_hours, 1))
                    return _context_cache
        except Exception as exc:
            log.warning("db_intelligence.disk_load_failed", error=str(exc))

    # Build fresh (blocking)
    with _build_lock:
        # Double-check after acquiring lock
        if _context_cache and not force_refresh:
            return _context_cache
        log.info("db_intelligence.building_context")
        _context_cache = build_db_context()
        _context_loaded_at = time.time()

    return _context_cache


def start_background_refresh() -> None:
    """Start a daemon thread that refreshes the context every REFRESH_HOURS."""
    def _loop():
        # Initial scan on startup (with small delay to let server start)
        time.sleep(5)
        log.info("db_intelligence.initial_scan_starting")
        try:
            get_db_context(force_refresh=False)
            log.info("db_intelligence.initial_scan_complete")
        except Exception as exc:
            log.error("db_intelligence.initial_scan_failed", error=str(exc))

        # Periodic refresh
        while True:
            time.sleep(REFRESH_HOURS * 3600)
            try:
                get_db_context(force_refresh=True)
                log.info("db_intelligence.periodic_refresh_complete")
            except Exception as exc:
                log.error("db_intelligence.periodic_refresh_failed", error=str(exc))

    t = threading.Thread(target=_loop, daemon=True, name="db-intelligence-refresh")
    t.start()
    log.info("db_intelligence.background_refresh_started", interval_hours=REFRESH_HOURS)
