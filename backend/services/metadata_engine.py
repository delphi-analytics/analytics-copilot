"""
Metadata Engine — ported and extended from Canary's metadata generation backend.
Generates rich column-level metadata from ClickHouse tables via SQL.
Caches results to avoid repeated expensive introspection queries.

Per-column metadata:
  - Total rows, non-null count, unique count, unique ratio
  - Data type classification (numerical / temporal / categorical / identifier)
  - Sample values (for categorical columns with < 200 unique values)
  - Numerical range (min, max, mean, median) for numeric columns
  - Date range (start, end, unique days) for date columns
  - Auto-generated description + business context hints
  - Suggested aggregation functions
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)

METADATA_DIR = Path("/tmp/dvc_metadata")
METADATA_DIR.mkdir(exist_ok=True)

CACHE_DURATION_HOURS = 24
CATEGORICAL_THRESHOLD = 200   # unique values below this → categorical


def _meta_file(datasource_id: str, table_name: str) -> Path:
    safe = table_name.replace("/", "_").replace(".", "_")
    safe_ds = datasource_id.replace("/", "_")
    return METADATA_DIR / f"{safe_ds}__{safe}_metadata.json"


def _compute_hash(datasource_id: str, table_name: str, total_rows: int) -> str:
    raw = f"{datasource_id}:{table_name}:{total_rows}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _classify_ch_type(ch_type: str) -> str:
    """Map ClickHouse column type string to simplified category."""
    t = ch_type.lower()
    if any(x in t for x in ["int", "float", "decimal", "double", "numeric"]):
        return "number"
    if any(x in t for x in ["date", "datetime", "timestamp"]):
        return "date"
    if "bool" in t:
        return "boolean"
    if "lowcardinality" in t:
        return "categorical"
    return "string"


async def generate_table_metadata(
    datasource_id: str,
    table_name: str,
    execute_fn: Any,   # async fn(sql: str) -> dict with {columns, rows}
    force_refresh: bool = False,
) -> dict:
    """
    Generate or load cached metadata for a ClickHouse table.

    Canary approach: run batched SQL (uniq + count per column), cache result.
    Then inject this metadata as LLM context for accurate SQL generation.
    """
    meta_file = _meta_file(datasource_id, table_name)

    # Load from cache if fresh enough and not forced
    if not force_refresh and meta_file.exists():
        try:
            with open(meta_file) as f:
                cached = json.load(f)
            age_hours = (time.time() - cached.get("generated_at_ts", 0)) / 3600
            if age_hours < CACHE_DURATION_HOURS:
                log.debug("metadata.cache_hit", table=table_name, age_hours=round(age_hours, 1))
                return cached
        except Exception as exc:
            log.warning("metadata.cache_read_failed", error=str(exc))

    log.info("metadata.generating", table=table_name, datasource=datasource_id)
    t0 = time.time()

    # Step 1: Get schema (DESCRIBE TABLE)
    schema_result = await execute_fn(f"DESCRIBE TABLE {table_name}")
    columns_raw = schema_result.get("rows", [])
    if not columns_raw:
        raise ValueError(f"Table {table_name} not found or empty schema")

    # Step 2: Total row count
    count_result = await execute_fn(f"SELECT count() as total_rows FROM {table_name}")
    total_rows = int(count_result["rows"][0].get("total_rows", 0))

    # Step 3: Batch stats — uniq + count per column (20 columns per query)
    BATCH_SIZE = 20
    all_stats: dict = {}

    for i in range(0, len(columns_raw), BATCH_SIZE):
        batch = columns_raw[i: i + BATCH_SIZE]
        parts = []
        for col in batch:
            name = col.get("name") or col.get("name", "")
            parts.append(f"uniq(`{name}`) as `{name}__unique`")
            parts.append(f"count(`{name}`) as `{name}__nonnull`")

        sql = f"SELECT {', '.join(parts)} FROM {table_name}"
        try:
            batch_result = await execute_fn(sql)
            if batch_result.get("rows"):
                all_stats.update(batch_result["rows"][0])
        except Exception as exc:
            log.warning("metadata.batch_failed", batch=i, error=str(exc))

    # Step 4: Build column metadata
    columns_metadata: list[dict] = []

    for col in columns_raw:
        col_name = col.get("name", "")
        col_type_raw = col.get("type", "")
        simplified_type = _classify_ch_type(col_type_raw)

        unique_count = int(all_stats.get(f"{col_name}__unique", 0) or 0)
        non_null_count = int(all_stats.get(f"{col_name}__nonnull", 0) or 0)
        unique_ratio = round(unique_count / non_null_count, 4) if non_null_count > 0 else 0.0

        is_identifier = (unique_ratio > 0.9 and unique_count > 100) or \
                        any(p in col_name.lower() for p in ["_id", "id_", "_key", "_code", "uuid", "guid"])
        is_categorical = unique_count <= CATEGORICAL_THRESHOLD and not is_identifier

        col_meta: dict = {
            "name": col_name,
            "type": simplified_type,
            "clickhouse_type": col_type_raw,
            "total_rows": total_rows,
            "non_null_count": non_null_count,
            "unique_count": unique_count,
            "unique_ratio": unique_ratio,
            "is_identifier": is_identifier,
            "is_categorical": is_categorical,
        }

        # Sample values for categorical columns
        if is_categorical and non_null_count > 0:
            try:
                sample_sql = f"""
                    SELECT `{col_name}` as value, count() as cnt
                    FROM {table_name}
                    WHERE `{col_name}` IS NOT NULL AND `{col_name}` != ''
                    GROUP BY `{col_name}`
                    ORDER BY cnt DESC
                    LIMIT {CATEGORICAL_THRESHOLD}
                """
                sample_result = await execute_fn(sample_sql)
                sample_vals = [str(r.get("value", "")) for r in sample_result.get("rows", [])]
                col_meta["sample_values"] = sample_vals
                col_meta["top_values"] = [
                    {"value": r.get("value"), "count": r.get("cnt")}
                    for r in sample_result.get("rows", [])[:20]
                ]
            except Exception as exc:
                log.debug("metadata.sample_failed", col=col_name, error=str(exc))

        # Numerical range
        if simplified_type == "number" and not is_identifier:
            try:
                num_sql = f"""
                    SELECT
                        min(`{col_name}`) as min_val,
                        max(`{col_name}`) as max_val,
                        avg(`{col_name}`) as mean_val,
                        median(`{col_name}`) as median_val
                    FROM {table_name}
                    WHERE `{col_name}` IS NOT NULL
                """
                num_result = await execute_fn(num_sql)
                if num_result.get("rows"):
                    row = num_result["rows"][0]
                    col_meta["numerical_range"] = {
                        "min": float(row.get("min_val", 0) or 0),
                        "max": float(row.get("max_val", 0) or 0),
                        "mean": round(float(row.get("mean_val", 0) or 0), 2),
                        "median": round(float(row.get("median_val", 0) or 0), 2),
                    }
            except Exception:
                pass

        # Date range
        if simplified_type == "date":
            try:
                date_sql = f"""
                    SELECT
                        toString(min(`{col_name}`)) as start_date,
                        toString(max(`{col_name}`)) as end_date,
                        uniq(toDate(`{col_name}`)) as unique_days
                    FROM {table_name}
                    WHERE `{col_name}` IS NOT NULL
                """
                date_result = await execute_fn(date_sql)
                if date_result.get("rows"):
                    row = date_result["rows"][0]
                    col_meta["date_range"] = {
                        "start": str(row.get("start_date", "")),
                        "end": str(row.get("end_date", "")),
                        "unique_days": int(row.get("unique_days", 0) or 0),
                    }
            except Exception:
                pass

        # Auto-generated description (same pattern as Canary)
        col_meta["description"] = _generate_col_description(col_meta)

        # Suggested aggregation
        col_meta["suggested_aggregation"] = _suggest_aggregation(col_meta)

        columns_metadata.append(col_meta)

    elapsed = round(time.time() - t0, 2)
    metadata = {
        "table_name": table_name,
        "datasource_id": datasource_id,
        "total_rows": total_rows,
        "total_columns": len(columns_metadata),
        "columns": columns_metadata,
        "metadata_hash": _compute_hash(datasource_id, table_name, total_rows),
        "generated_at": datetime.utcnow().isoformat(),
        "generated_at_ts": time.time(),
        "generation_time_seconds": elapsed,
    }

    # Cache to file
    try:
        with open(meta_file, "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        log.info("metadata.cached", table=table_name, columns=len(columns_metadata),
                 rows=total_rows, seconds=elapsed)
    except Exception as exc:
        log.warning("metadata.cache_write_failed", error=str(exc))

    return metadata


def _generate_col_description(col: dict) -> str:
    name = col["name"]
    t = col["type"]
    unique = col["unique_count"]
    non_null = col["non_null_count"]

    desc = f"{name} is a {t} column with {non_null:,} non-null values and {unique:,} unique values"

    if col.get("is_identifier"):
        desc += " (identifier/ID column)"
    elif col.get("is_categorical") and col.get("sample_values"):
        vals = col["sample_values"][:5]
        desc += f". Values: {', '.join(str(v) for v in vals)}"
    elif col.get("numerical_range"):
        r = col["numerical_range"]
        desc += f". Range: {r['min']:,} to {r['max']:,} (mean: {r['mean']:,})"
    elif col.get("date_range"):
        r = col["date_range"]
        desc += f". Date range: {r['start']} to {r['end']} ({r['unique_days']} unique days)"

    return desc


def _suggest_aggregation(col: dict) -> str:
    if col["type"] == "number" and not col.get("is_identifier"):
        return "sum"
    if col.get("is_identifier") or col.get("is_categorical"):
        return "count_distinct"
    if col["type"] == "date":
        return "count"
    return "count"


def load_cached_metadata(datasource_id: str, table_name: str) -> dict | None:
    """Load metadata from cache without regenerating."""
    meta_file = _meta_file(datasource_id, table_name)
    if not meta_file.exists():
        return None
    try:
        with open(meta_file) as f:
            return json.load(f)
    except Exception:
        return None


def list_cached_tables(datasource_id: str) -> list[dict]:
    """List all tables that have cached metadata for a datasource."""
    prefix = datasource_id.replace("/", "_") + "__"
    tables = []
    for f in METADATA_DIR.glob(f"{prefix}*_metadata.json"):
        try:
            with open(f) as fp:
                meta = json.load(fp)
            tables.append({
                "table_name": meta.get("table_name"),
                "total_rows": meta.get("total_rows", 0),
                "total_columns": meta.get("total_columns", 0),
                "generated_at": meta.get("generated_at"),
                "has_metadata": True,
            })
        except Exception:
            pass
    return tables


def build_llm_schema_context(metadata: dict, max_cols: int = 50) -> str:
    """
    Format metadata into a compact context string for LLM SQL generation.
    Mirrors Canary's columns_text building logic.
    """
    lines = [f"TABLE: {metadata['table_name']} ({metadata['total_rows']:,} rows)\n"]
    lines.append("COLUMNS:")

    for col in metadata["columns"][:max_cols]:
        line = f"- `{col['name']}` ({col['clickhouse_type']}): {col['description']}"
        line += f" [{col['unique_count']:,} unique values]"

        # Include possible values for low-cardinality columns (like Canary)
        if col.get("sample_values") and col["unique_count"] <= 20:
            vals = ", ".join(str(v) for v in col["sample_values"][:20])
            line += f"\n  Possible values: {vals}"
        elif col.get("sample_values") and col["unique_count"] <= 100:
            vals = ", ".join(str(v) for v in col["sample_values"][:10])
            line += f"\n  Sample values: {vals}"

        lines.append(line)

    return "\n".join(lines)
