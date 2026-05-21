"""Schema Scanner Service - Detects database schema changes for approval."""
import structlog
from typing import Any
from pathlib import Path
import json
from datetime import datetime

log = structlog.get_logger(__name__)

SCAN_CACHE_PATH = Path("/tmp/dvc_metadata/schema_scanner_cache.json")


async def scan_and_detect_changes() -> dict[str, Any]:
    """
    Scan the current database schema and compare with the last scanned version.
    Returns a dict with changes detected.
    """
    from backend.services.db_intelligence import get_db_context

    # Get current database context
    current_context = get_db_context(force_refresh=True)

    # Load previous scan
    previous_context = await _load_previous_scan()

    # Generate diff
    diff = _generate_diff(previous_context, current_context)

    # Save current scan for next comparison
    await _save_current_scan(current_context)

    return {
        "scanned_at": datetime.utcnow().isoformat(),
        "previous_scan": previous_context.get("scanned_at") if previous_context else None,
        "diff": diff
    }


async def _load_previous_scan() -> dict[str, Any] | None:
    """Load the previous schema scan from cache."""
    if SCAN_CACHE_PATH.exists():
        try:
            with open(SCAN_CACHE_PATH) as f:
                return json.load(f)
        except Exception as e:
            log.warning("schema_scanner.load_failed", error=str(e))
    return None


async def _save_current_scan(context: dict[str, Any]) -> None:
    """Save the current schema scan to cache."""
    try:
        SCAN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SCAN_CACHE_PATH, "w") as f:
            json.dump(context, f, indent=2, default=str)
        log.info("schema_scanner.saved", path=str(SCAN_CACHE_PATH))
    except Exception as e:
        log.error("schema_scanner.save_failed", error=str(e))


def _generate_diff(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    """Generate diff between previous and current schema scans."""
    if not previous:
        return {
            "type": "initial_scan",
            "summary": "Initial schema scan - no previous version to compare",
            "changes": {
                "tables_added": list(current.get("tables", {}).keys())
            }
        }

    changes = {
        "tables_added": [],
        "tables_removed": [],
        "tables_modified": [],
        "column_changes": {}
    }

    prev_tables = set(previous.get("tables", {}).keys())
    curr_tables = set(current.get("tables", {}).keys())

    # Detect added/removed tables
    changes["tables_added"] = list(curr_tables - prev_tables)
    changes["tables_removed"] = list(prev_tables - curr_tables)

    # Detect modified tables
    common_tables = prev_tables & curr_tables
    for table in common_tables:
        prev_table = previous["tables"][table]
        curr_table = current["tables"][table]

        prev_cols = set(col["name"] for col in prev_table.get("columns", []))
        curr_cols = set(col["name"] for col in curr_table.get("columns", []))

        if prev_cols != curr_cols:
            changes["tables_modified"].append({
                "table": table,
                "columns_added": list(curr_cols - prev_cols),
                "columns_removed": list(prev_cols - curr_cols),
                "row_count_changed": prev_table.get("row_count") != curr_table.get("row_count")
            })

    # Determine diff type
    if any([changes["tables_added"], changes["tables_removed"], changes["tables_modified"]]):
        diff_type = "changes_detected"
    else:
        diff_type = "no_changes"

    return {
        "type": diff_type,
        "summary": _generate_diff_summary(changes),
        "changes": changes
    }


def _generate_diff_summary(changes: dict[str, Any]) -> str:
    """Generate a human-readable summary of the diff."""
    parts = []

    if changes["tables_added"]:
        parts.append(f"{len(changes['tables_added'])} tables added")
    if changes["tables_removed"]:
        parts.append(f"{len(changes['tables_removed'])} tables removed")
    if changes["tables_modified"]:
        parts.append(f"{len(changes['tables_modified'])} tables modified")

    return ", ".join(parts) if parts else "No schema changes"
