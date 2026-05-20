"""
Universal Database Scanner — Auto-discovers any database schema
================================================================
Works with SQLite, PostgreSQL, ClickHouse, MySQL, and any SQLAlchemy-supported database.

Generates comprehensive documentation including:
- All tables and their structures
- Column types, constraints, and sample values
- Foreign key relationships between tables
- Primary keys and indexes
- Business-friendly descriptions
- Sample queries for common patterns

STORAGE LOCATION:
- Default: ./data/db_scans/ (project directory)
- Each database scan creates: {scan_id}.json and {scan_id}.md
- Structure:
  {
    "database_name": "limese",
    "tables": {
      "table1": {
        "columns": [...],
        "primary_keys": [...],
        "foreign_keys": [...],
        "row_count": 12345
      }
    },
    "relationships": [...],
    "global_rules": [...]
  }

The generated README helps LLMs write better SQL by understanding:
- Which tables to JOIN and on which columns
- Which columns contain what kind of data
- The cardinality of relationships
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict
import structlog

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from backend.config import settings

log = structlog.get_logger(__name__)

# Storage directory for database scans
# Can be overridden by environment variable DB_SCANS_PATH
DB_SCANS_PATH = Path(getattr(settings, "db_scans_path", "./data/db_scans"))
DB_SCANS_PATH.mkdir(parents=True, exist_ok=True)


@dataclass
class ColumnInfo:
    """Information about a database column."""
    name: str
    type: str
    nullable: bool
    default: Optional[str]
    is_primary_key: bool
    is_foreign_key: bool
    foreign_key_target: Optional[str]  # "table.column"
    sample_values: list[str]
    unique_count: Optional[int]
    min_value: Optional[str]
    max_value: Optional[str]
    description: str = ""


@dataclass
class TableInfo:
    """Information about a database table."""
    name: str
    row_count: int
    columns: list[ColumnInfo]
    primary_keys: list[str]
    foreign_keys: list[dict]  # {"column": "col", "ref_table": "table", "ref_column": "col"}
    indexes: list[str]
    description: str = ""
    business_purpose: str = ""


@dataclass
class DatabaseDocumentation:
    """Complete database documentation."""
    database_name: str
    database_type: str  # "postgresql", "sqlite", "clickhouse", etc.
    connection_info: str
    scanned_at: str
    tables: dict[str, TableInfo]
    relationships: list[dict]  # Discovered relationships
    global_rules: list[str]
    suggested_queries: list[str]


class UniversalDatabaseScanner:
    """Scan any database and generate comprehensive documentation."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine: Optional[Engine] = None
        self.inspector: Optional[any] = None

    def connect(self) -> bool:
        """Establish database connection."""
        try:
            self.engine = create_engine(self.database_url)
            self.inspector = inspect(self.engine)
            log.info("db_scanner.connected", database_type=self.inspector.dialect.name)
            return True
        except Exception as e:
            log.error("db_scanner.connection_failed", error=str(e))
            return False

    def scan_database(self, max_sample_values: int = 10) -> DatabaseDocumentation:
        """Perform complete database scan."""
        if not self.engine or not self.inspector:
            if not self.connect():
                raise RuntimeError("Cannot connect to database")

        log.info("db_scanner.starting_scan")

        table_names = self.inspector.get_table_names()
        log.info("db_scanner.tables_found", count=len(table_names))

        tables = {}
        relationships = []

        for table_name in table_names:
            try:
                table_info = self._scan_table(table_name, max_sample_values)
                tables[table_name] = table_info

                # Collect foreign key relationships
                for fk in table_info.foreign_keys:
                    relationships.append({
                        "from_table": table_name,
                        "from_column": fk["column"],
                        "to_table": fk["ref_table"],
                        "to_column": fk["ref_column"],
                        "type": "many_to_one"  # Simplified; could detect one_to_one
                    })
            except Exception as e:
                log.warning("db_scanner.table_failed", table=table_name, error=str(e))

        # Generate global rules and suggested queries
        global_rules = self._generate_global_rules(tables)
        suggested_queries = self._generate_suggested_queries(tables)

        doc = DatabaseDocumentation(
            database_name=self.engine.url.database or "unknown",
            database_type=self.inspector.dialect.name,
            connection_info=self._sanitize_connection_info(),
            scanned_at=datetime.utcnow().isoformat(),
            tables=tables,
            relationships=relationships,
            global_rules=global_rules,
            suggested_queries=suggested_queries,
        )

        log.info("db_scanner.scan_complete",
                 tables=len(tables),
                 relationships=len(relationships))
        return doc

    def _scan_table(self, table_name: str, max_samples: int) -> TableInfo:
        """Scan a single table in detail."""
        with self.engine.connect() as conn:
            # Get row count
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                row_count = result.scalar() or 0
            except Exception:
                row_count = 0

            # Get column info
            columns = self.inspector.get_columns(table_name)
            primary_keys = self.inspector.get_pk_constraint(table_name).get("constrained_columns", [])
            foreign_keys = self.inspector.get_foreign_keys(table_name)
            indexes = [idx.get("name", "") for idx in self.inspector.get_indexes(table_name)]

            column_infos = []
            for col in columns:
                col_info = self._scan_column(table_name, col, primary_keys, foreign_keys, conn, max_samples)
                column_infos.append(col_info)

            # Build FK list in simple format
            fk_list = []
            for fk in foreign_keys:
                for col in fk.get("constrained_columns", []):
                    fk_list.append({
                        "column": col,
                        "ref_table": fk.get("referred_table"),
                        "ref_column": fk.get("referred_columns", [""])[0] if fk.get("referred_columns") else ""
                    })

            return TableInfo(
                name=table_name,
                row_count=row_count,
                columns=column_infos,
                primary_keys=primary_keys,
                foreign_keys=fk_list,
                indexes=indexes,
            )

    def _scan_column(
        self,
        table_name: str,
        col_def: dict,
        primary_keys: list[str],
        foreign_keys: list[dict],
        conn: Any,
        max_samples: int
    ) -> ColumnInfo:
        """Scan a single column."""
        col_name = col_def["name"]
        col_type = str(col_def["type"])

        # Check if PK
        is_pk = col_name in primary_keys

        # Check if FK
        is_fk = False
        fk_target = None
        for fk in foreign_keys:
            if col_name in fk.get("constrained_columns", []):
                is_fk = True
                ref_table = fk.get("referred_table", "")
                ref_cols = fk.get("referred_columns", [])
                if ref_table and ref_cols:
                    fk_target = f"{ref_table}.{ref_cols[0]}"
                break

        # Get sample values and stats
        sample_values = []
        unique_count = None
        min_val = None
        max_val = None

        try:
            # Get unique count
            result = conn.execute(text(f'SELECT COUNT(DISTINCT "{col_name}") FROM "{table_name}"'))
            unique_count = result.scalar()

            # Get sample values
            if unique_count and unique_count <= max_samples:
                result = conn.execute(text(f'SELECT DISTINCT "{col_name}" FROM "{table_name}" WHERE "{col_name}" IS NOT NULL ORDER BY "{col_name}" LIMIT {max_samples}'))
            else:
                result = conn.execute(text(f'SELECT "{col_name}" FROM "{table_name}" WHERE "{col_name}" IS NOT NULL ORDER BY RANDOM() LIMIT {max_samples}'))
            sample_values = [str(row[0]) for row in result.fetchall() if row[0] is not None]

            # Get min/max for appropriate types
            if any(t in col_type.lower() for t in ["int", "float", "decimal", "numeric", "date", "time"]):
                try:
                    result = conn.execute(text(f'SELECT MIN("{col_name}"), MAX("{col_name}") FROM "{table_name}"'))
                    row = result.fetchone()
                    if row:
                        min_val = str(row[0]) if row[0] is not None else None
                        max_val = str(row[1]) if row[1] is not None else None
                except Exception:
                    pass

        except Exception as e:
            log.debug("db_scanner.column_stats_failed", table=table_name, column=col_name, error=str(e))

        # Generate description
        description = self._generate_column_description(col_name, col_type, is_pk, is_fk, sample_values)

        return ColumnInfo(
            name=col_name,
            type=col_type,
            nullable=col_def.get("nullable", True),
            default=str(col_def.get("default", "")) if col_def.get("default") else None,
            is_primary_key=is_pk,
            is_foreign_key=is_fk,
            foreign_key_target=fk_target,
            sample_values=sample_values,
            unique_count=unique_count,
            min_value=min_val,
            max_value=max_val,
            description=description,
        )

    def _generate_column_description(
        self,
        name: str,
        type_str: str,
        is_pk: bool,
        is_fk: bool,
        samples: list[str]
    ) -> str:
        """Generate a human-friendly description for a column."""
        parts = []

        if is_pk:
            parts.append("Primary key")

        if is_fk:
            parts.append("Foreign key")

        # Heuristic descriptions based on name patterns
        name_lower = name.lower()
        if "id" in name_lower and is_pk:
            parts.append("Unique identifier")
        elif "id" in name_lower and is_fk:
            parts.append("Reference to related record")
        elif "name" in name_lower:
            parts.append("Display name")
        elif "email" in name_lower:
            parts.append("Email address")
        elif "phone" in name_lower:
            parts.append("Phone number")
        elif "date" in name_lower or "time" in name_lower:
            parts.append("Timestamp/date field")
        elif "amount" in name_lower or "price" in name_lower or "cost" in name_lower or "revenue" in name_lower:
            parts.append("Monetary value")
        elif "quantity" in name_lower or "count" in name_lower or "num" in name_lower:
            parts.append("Numeric count/quantity")
        elif "status" in name_lower:
            parts.append("Status indicator")
        elif any(t in type_str.lower() for t in ["text", "varchar", "char"]):
            parts.append("Text field")
        elif any(t in type_str.lower() for t in ["int", "numeric", "decimal"]):
            parts.append("Numeric field")
        elif "bool" in type_str.lower():
            parts.append("Boolean flag")

        if samples:
            parts.append(f"Example values: {', '.join(samples[:3])}")

        return ". ".join(parts) if parts else ""

    def _generate_global_rules(self, tables: dict[str, TableInfo]) -> list[str]:
        """Generate global SQL rules based on schema analysis."""
        rules = [
            "READ-ONLY: Never generate INSERT, UPDATE, DELETE, DROP, CREATE, or ALTER statements.",
            "Always use proper table quoting for identifiers.",
            "Include LIMIT clause (max 10000 rows) for detail queries.",
        ]

        # Add database-specific rules
        if self.inspector:
            dialect = self.inspector.dialect.name
            if dialect == "postgresql":
                rules.append("PostgreSQL: Use ILIKE for case-insensitive pattern matching.")
            elif dialect == "sqlite":
                rules.append("SQLite: Use LIKE for case-insensitive matching.")
            elif dialect == "mysql":
                rules.append("MySQL: Use backticks ` for table/column names if needed.")

        # Add relationship-based rules
        if tables:
            biggest_table = max(tables.values(), key=lambda t: t.row_count, default=None)
            if biggest_table:
                rules.append(f"Largest table: {biggest_table.name} ({biggest_table.row_count:,} rows) - consider filtering early.")

        return rules

    def _generate_suggested_queries(self, tables: dict[str, TableInfo]) -> list[str]:
        """Generate sample queries based on schema."""
        queries = []

        # Get tables with relationships
        tables_with_fks = {name: t for name, t in tables.items() if t.foreign_keys}

        # Generate JOIN suggestions
        for table_name, table_info in tables_with_fks.items():
            for fk in table_info.foreign_keys[:2]:  # Max 2 per table
                ref_table = fk["ref_table"]
                queries.append(
                    f"SELECT * FROM {table_name} t "
                    f"JOIN {ref_table} r ON t.{fk['column']} = r.{fk['ref_column']} "
                    f"LIMIT 100"
                )

        # Generate aggregation suggestions for larger tables
        for table_name, table_info in list(tables.items())[:5]:
            if table_info.row_count > 100:
                # Find a good group-by column
                group_col = None
                for col in table_info.columns:
                    if col.unique_count and 2 < col.unique_count < 50:
                        group_col = col.name
                        break

                if group_col:
                    queries.append(
                        f"SELECT {group_col}, COUNT(*) as count FROM {table_name} "
                        f"GROUP BY {group_col} ORDER BY count DESC LIMIT 20"
                    )

        return queries[:10]  # Max 10 suggested queries

    def _sanitize_connection_info(self) -> str:
        """Return safe connection info for logging."""
        if not self.engine:
            return "not connected"

        url = self.engine.url
        return f"{url.drivername}://***@{url.host or 'local'}:{url.port or 'N/A'}/{url.database or 'N/A'}"

    def generate_markdown_readme(self, doc: DatabaseDocumentation) -> str:
        """Generate a comprehensive README in markdown format."""
        lines = [
            f"# Database Documentation: {doc.database_name}",
            "",
            f"**Generated:** {doc.scanned_at}",
            f"**Database Type:** {doc.database_type}",
            f"**Connection:** {doc.connection_info}",
            "",
            "---",
            "",
            "## Overview",
            "",
            f"This database contains **{len(doc.tables)} tables** with **{len(doc.relationships)} known relationships**.",
            "",
        ]

        # Global Rules
        if doc.global_rules:
            lines.extend([
                "## Global SQL Rules",
                "",
            ])
            for rule in doc.global_rules:
                lines.append(f"- {rule}")
            lines.append("")

        # Relationships
        if doc.relationships:
            lines.extend([
                "## Table Relationships",
                "",
                "| From Table | From Column | To Table | To Column | Type |",
                "|------------|-------------|----------|-----------|------|",
            ])
            for rel in doc.relationships:
                lines.append(
                    f"| {rel['from_table']} | {rel['from_column']} | "
                    f"{rel['to_table']} | {rel['to_column']} | {rel['type']} |"
                )
            lines.append("")

        # Tables
        lines.extend([
            "## Tables",
            "",
        ])

        for table_name, table_info in sorted(doc.tables.items()):
            lines.extend([
                f"### {table_name}",
                "",
                f"**Rows:** {table_info.row_count:,}",
                "",
            ])

            if table_info.primary_keys:
                lines.append(f"**Primary Key:** {', '.join(table_info.primary_keys)}")
                lines.append("")

            # Columns
            lines.extend([
                "| Column | Type | Nullable | Key | Description |",
                "|--------|------|----------|-----|-------------|",
            ])

            for col in table_info.columns:
                keys = []
                if col.is_primary_key:
                    keys.append("PK")
                if col.is_foreign_key:
                    keys.append(f"FK → {col.foreign_key_target}")

                key_str = ", ".join(keys) if keys else ""
                desc = col.description[:100] + "..." if len(col.description) > 100 else col.description

                lines.append(
                    f"| {col.name} | {col.type} | "
                    f"{'Yes' if col.nullable else 'No'} | {key_str} | {desc} |"
                )

            lines.append("")

        # Suggested Queries
        if doc.suggested_queries:
            lines.extend([
                "## Suggested Sample Queries",
                "",
            ])
            for i, query in enumerate(doc.suggested_queries, 1):
                lines.extend([
                    f"### Query {i}",
                    "",
                    "```sql",
                    query,
                    "```",
                    "",
                ])

        return "\n".join(lines)

    def generate_llm_context(self, doc: DatabaseDocumentation, max_tables: int = 10) -> str:
        """Generate compact context for LLM consumption."""
        lines = [
            f"DATABASE: {doc.database_name} ({doc.database_type})",
            "",
            "=== CRITICAL RULES ===",
        ]

        for rule in doc.global_rules:
            lines.append(f"• {rule}")

        lines.extend([
            "",
            "=== TABLE RELATIONSHIPS (JOIN patterns) ===",
        ])

        for rel in doc.relationships[:20]:  # Limit relationships
            lines.append(
                f"• {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}"
            )

        lines.extend([
            "",
            "=== TABLE SCHEMAS ===",
        ])

        # Sort tables by row count (most important first)
        sorted_tables = sorted(
            doc.tables.items(),
            key=lambda x: x[1].row_count,
            reverse=True
        )[:max_tables]

        for table_name, table_info in sorted_tables:
            lines.append(f"\nTABLE: {table_name} ({table_info.row_count:,} rows)")

            if table_info.primary_keys:
                lines.append(f"  PRIMARY KEY: {', '.join(table_info.primary_keys)}")

            # Show columns with most useful info first
            priority_cols = []
            other_cols = []

            for col in table_info.columns:
                if col.is_primary_key or col.is_foreign_key or (col.unique_count and col.unique_count <= 50):
                    priority_cols.append(col)
                else:
                    other_cols.append(col)

            for col in priority_cols + other_cols[:15]:  # Limit columns per table
                col_line = f"  • `{col.name}` ({col.type})"
                if not col.nullable:
                    col_line += " NOT NULL"
                if col.is_primary_key:
                    col_line += " PRIMARY KEY"
                if col.is_foreign_key:
                    col_line += f" → {col.foreign_key_target}"
                if col.sample_values:
                    col_line += f" -- examples: {col.sample_values[:3]}"
                lines.append(col_line)

        return "\n".join(lines)


def scan_datasource(database_url: str, output_path: Optional[str] = None) -> DatabaseDocumentation:
    """
    Scan a database and optionally save documentation to file.

    Args:
        database_url: SQLAlchemy database URL
        output_path: Optional path to save JSON documentation

    Returns:
        DatabaseDocumentation object
    """
    scanner = UniversalDatabaseScanner(database_url)
    doc = scanner.scan_database()

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save JSON
        json_path = output_file.with_suffix(".json")
        with open(json_path, "w") as f:
            json.dump(asdict(doc), f, indent=2, default=str)

        # Save Markdown
        md_path = output_file.with_suffix(".md")
        with open(md_path, "w") as f:
            f.write(scanner.generate_markdown_readme(doc))

        log.info("db_scanner.documentation_saved",
                 json=str(json_path),
                 markdown=str(md_path))

    return doc


def get_llm_db_context(database_url: str) -> str:
    """
    Get LLM-friendly context string for a database.
    Cached for 1 hour.
    """
    cache_file = DB_SCANS_PATH / f"db_context_{hash(database_url)}.txt"

    # Check cache (1 hour TTL)
    if cache_file.exists():
        age = datetime.now().timestamp() - cache_file.stat().st_mtime
        if age < 3600:
            return cache_file.read_text()

    # Generate fresh
    scanner = UniversalDatabaseScanner(database_url)
    doc = scanner.scan_database()
    context = scanner.generate_llm_context(doc)

    # Cache
    cache_file.write_text(context)

    return context


def save_scan_to_storage(doc: DatabaseDocumentation, scan_id: str) -> dict:
    """
    Save database scan to storage (currently local files).
    In the future, this can be extended to save to MinIO.

    Returns dict with file paths and metadata.
    """
    scan_dir = DB_SCANS_PATH / scan_id
    scan_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON
    json_path = scan_dir / "documentation.json"
    with open(json_path, "w") as f:
        json.dump(asdict(doc), f, indent=2, default=str)

    # Save Markdown
    md_path = scan_dir / "README.md"
    with open(md_path, "w") as f:
        f.write(generate_markdown_readme_from_dict(asdict(doc)))

    # Save LLM context
    scanner = UniversalDatabaseScanner("")  # Just for method access
    context_path = scan_dir / "llm_context.txt"
    with open(context_path, "w") as f:
        f.write(_generate_llm_context_from_dict(asdict(doc)))

    return {
        "scan_id": scan_id,
        "storage_path": str(scan_dir),
        "files": {
            "json": str(json_path),
            "markdown": str(md_path),
            "llm_context": str(context_path),
        },
        "database": doc.database_name,
        "tables_count": len(doc.tables),
        "relationships_count": len(doc.relationships),
    }


def generate_markdown_readme_from_dict(doc_dict: dict) -> str:
    """Generate markdown from dict (for use when we have dict instead of object)."""
    # Simple version - can be expanded
    lines = [
        f"# Database Documentation: {doc_dict.get('database_name', 'Unknown')}",
        "",
        f"**Generated:** {doc_dict.get('scanned_at', 'Unknown')}",
        f"**Database Type:** {doc_dict.get('database_type', 'Unknown')}",
        "",
        "## Tables",
        "",
    ]

    for table_name, table_data in doc_dict.get("tables", {}).items():
        row_count = table_data.get("row_count", 0)
        columns = table_data.get("columns", [])
        lines.extend([
            f"### {table_name}",
            f"**Rows:** {row_count:,}",
            "",
            "| Column | Type | Key |",
            "|--------|------|-----|",
        ])

        for col in columns[:20]:  # Limit columns
            keys = []
            if col.get("is_primary_key"):
                keys.append("PK")
            if col.get("is_foreign_key"):
                keys.append(f"FK → {col.get('foreign_key_target', '')}")

            key_str = ", ".join(keys) if keys else ""
            lines.append(
                f"| {col.get('name', '')} | {col.get('type', '')} | {key_str} |"
            )
        lines.append("")

    return "\n".join(lines)


def _generate_llm_context_from_dict(doc_dict: dict) -> str:
    """Generate LLM context from dict."""
    lines = [
        f"DATABASE: {doc_dict.get('database_name', 'Unknown')}",
        "",
        "=== TABLES ===",
    ]

    for table_name, table_data in doc_dict.get("tables", {}).items():
        row_count = table_data.get("row_count", 0)
        lines.append(f"\nTABLE: {table_name} ({row_count:,} rows)")

        pks = table_data.get("primary_keys", [])
        if pks:
            lines.append(f"  PRIMARY KEY: {', '.join(pks)}")

        for col in table_data.get("columns", [])[:15]:
            col_line = f"  • `{col.get('name', '')}` ({col.get('type', '')})"
            if col.get("is_primary_key"):
                col_line += " PRIMARY KEY"
            if col.get("is_foreign_key"):
                col_line += f" → {col.get('foreign_key_target', '')}"
            lines.append(col_line)

    return "\n".join(lines)
