"""
Node 6: Visualization Config Generation
Generates a complete Apache ECharts option object from query results.
The frontend renders this directly — no chart logic on the client side.
"""
from __future__ import annotations
import json
import structlog
from backend.agent.state import AnalyticsState
from backend.agent.llm import call_llm

log = structlog.get_logger(__name__)

# ECharts color palette
COLORS = ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de",
          "#3ba272", "#fc8452", "#9a60b4", "#ea7ccc"]

# Chart type → ECharts series type mapping
CHART_TYPE_MAP = {
    "bar": "bar", "line": "line", "area": "line", "pie": "pie",
    "scatter": "scatter", "heatmap": "heatmap", "gauge": "gauge",
    "funnel": "funnel", "radar": "radar", "table": "table",
}


def _build_bar_chart(columns: list, rows: list, title: str) -> dict:
    """Build bar chart config directly from data — fast path."""
    if len(columns) < 2:
        return {}
    x_col, y_col = columns[0], columns[1]
    x_data = [str(r.get(x_col, "") if isinstance(r, dict) else r[0]) for r in rows[:50]]
    y_data = []
    for r in rows[:50]:
        val = r.get(y_col) if isinstance(r, dict) else r[1]
        try:
            y_data.append(round(float(val), 2) if val is not None else 0)
        except (ValueError, TypeError):
            y_data.append(0)

    return {
        "title": {"text": title, "left": "center"},
        "color": COLORS,
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": x_data, "axisLabel": {"rotate": 30 if len(x_data) > 8 else 0}},
        "yAxis": {"type": "value"},
        "series": [{"name": y_col, "type": "bar", "data": y_data, "label": {"show": len(rows) <= 20, "position": "top"}}],
        "grid": {"left": "10%", "right": "5%", "bottom": "15%"},
    }


def _build_line_chart(columns: list, rows: list, title: str) -> dict:
    config = _build_bar_chart(columns, rows, title)
    if config:
        config["series"][0]["type"] = "line"
        config["series"][0]["smooth"] = True
        config["series"][0]["areaStyle"] = {"opacity": 0.1}
    return config


def _build_pie_chart(columns: list, rows: list, title: str) -> dict:
    if len(columns) < 2:
        return {}
    name_col, val_col = columns[0], columns[1]
    data = []
    for r in rows[:20]:
        name = str(r.get(name_col, "") if isinstance(r, dict) else r[0])
        val_raw = r.get(val_col) if isinstance(r, dict) else r[1]
        try:
            data.append({"name": name, "value": round(float(val_raw or 0), 2)})
        except (ValueError, TypeError):
            pass

    return {
        "title": {"text": title, "left": "center"},
        "color": COLORS,
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "legend": {"orient": "vertical", "left": "left"},
        "series": [{"type": "pie", "radius": ["40%", "70%"], "data": data,
                    "label": {"show": True, "formatter": "{b}: {d}%"}}],
    }


def _build_scatter_chart(columns: list, rows: list, title: str) -> dict:
    if len(columns) < 2:
        return {}
    x_col, y_col = columns[0], columns[1]
    data = []
    for r in rows[:200]:
        try:
            xv = float(r.get(x_col, 0) if isinstance(r, dict) else r[0])
            yv = float(r.get(y_col, 0) if isinstance(r, dict) else r[1])
            data.append([xv, yv])
        except (ValueError, TypeError):
            pass

    return {
        "title": {"text": title, "left": "center"},
        "tooltip": {"trigger": "item"},
        "xAxis": {"name": x_col},
        "yAxis": {"name": y_col},
        "series": [{"type": "scatter", "data": data, "symbolSize": 8}],
    }


def _build_funnel_chart(columns: list, rows: list, title: str) -> dict:
    if len(columns) < 2:
        return {}
    
    # Try to find the first numeric column for values, first string for names
    name_col = next((c for c in columns if 'status' in c.lower() or 'stage' in c.lower()), columns[0])
    val_col = next((c for c in columns if 'count' in c.lower() or 'units' in c.lower() or 'orders' in c.lower()), columns[1])

    def _safe_float(v):
        if v is None: return 0
        if isinstance(v, (int, float)): return float(v)
        # Strip commas, currency symbols, and spaces
        try:
            clean = str(v).replace(',', '').replace('₹', '').replace('$', '').strip()
            return float(clean)
        except: return 0

    data = []
    # Sort rows by the value column safely
    try:
        sorted_rows = sorted(rows, key=lambda r: _safe_float(r.get(val_col) if isinstance(r, dict) else r[1]), reverse=True)
    except:
        sorted_rows = rows[:10]

    for r in sorted_rows[:12]:
        name = str(r.get(name_col, "") if isinstance(r, dict) else r[0])
        val = _safe_float(r.get(val_col) if isinstance(r, dict) else r[1])
        if val > 0:
            data.append({"name": name, "value": val})

    return {
        "title": {"text": title, "left": "center"},
        "tooltip": {"trigger": "item", "formatter": "{b} : {c}"},
        "legend": {"orient": "vertical", "left": "left", "top": "15%"},
        "series": [
            {
                "name": "Conversion",
                "type": "funnel",
                "left": "15%",
                "top": "15%",
                "bottom": "10%",
                "width": "70%",
                "min": 0,
                "label": {"show": True, "position": "inside"},
                "data": data,
            }
        ]
    }


def _build_gauge_chart(columns: list, rows: list, title: str) -> dict:
    # Gauge usually shows a single value vs a target
    val = 0
    name = "KPI"
    if rows:
        r = rows[0]
        name = str(columns[0])
        val_raw = r.get(columns[0]) if isinstance(r, dict) else r[0]
        try:
            val = round(float(val_raw or 0), 2)
        except (ValueError, TypeError):
            pass

    return {
        "title": {"text": title, "left": "center"},
        "series": [
            {
                "name": name,
                "type": "gauge",
                "detail": {"formatter": "{value}"},
                "data": [{"value": val, "name": name}]
            }
        ]
    }


def _build_heatmap_chart(columns: list, rows: list, title: str) -> dict:
    if len(columns) < 3:
        return _build_bar_chart(columns, rows, title)
    
    x_col, y_col, val_col = columns[0], columns[1], columns[2]
    x_labs = list(dict.fromkeys([str(r.get(x_col) if isinstance(r, dict) else r[0]) for r in rows]))
    y_labs = list(dict.fromkeys([str(r.get(y_col) if isinstance(r, dict) else r[1]) for r in rows]))
    
    data = []
    max_val = 0
    for r in rows:
        try:
            x_idx = x_labs.index(str(r.get(x_col) if isinstance(r, dict) else r[0]))
            y_idx = y_labs.index(str(r.get(y_col) if isinstance(r, dict) else r[1]))
            v = float(r.get(val_col, 0) if isinstance(r, dict) else r[2])
            data.append([x_idx, y_idx, v])
            max_val = max(max_val, v)
        except (ValueError, TypeError):
            pass

    return {
        "title": {"text": title, "left": "center"},
        "tooltip": {"position": "top"},
        "xAxis": {"type": "category", "data": x_labs},
        "yAxis": {"type": "category", "data": y_labs},
        "visualMap": {"min": 0, "max": max_val, "calculable": True, "orient": "horizontal", "left": "center", "bottom": "0%"},
        "series": [{"name": val_col, "type": "heatmap", "data": data, "label": {"show": True}}]
    }


def _build_table_config(columns: list, rows: list, title: str) -> dict:
    """Table view — no ECharts needed, just structured data."""
    return {
        "type": "table",
        "title": title,
        "columns": columns,
        "rows": rows[:200],
        "total_rows": len(rows),
    }


CHART_BUILDERS = {
    "bar": _build_bar_chart,
    "line": _build_line_chart,
    "area": _build_line_chart,
    "pie": _build_pie_chart,
    "scatter": _build_scatter_chart,
    "funnel": _build_funnel_chart,
    "gauge": _build_gauge_chart,
    "heatmap": _build_heatmap_chart,
    "table": _build_table_config,
}


async def generate_viz_config(state: AnalyticsState) -> AnalyticsState:
    query_results = state.get("query_results", {})
    intent = state.get("intent", {})
    question = state["user_question"]
    key_metrics = state.get("key_metrics", {})

    rows = query_results.get("rows", [])
    columns = query_results.get("columns", [])

    if not rows:
        return {**state, "viz_config": {}, "viz_type": "table"}

    # Step 1: Determine chart type
    chart_hint = intent.get("chart_type_hint")
    viz_type = chart_hint or _auto_select_chart_type(columns, rows, intent, question)

    # Step 2: Generate title
    title = _generate_title(question, viz_type)

    # Step 3: Build ECharts config
    builder = CHART_BUILDERS.get(viz_type, _build_table_config)
    try:
        viz_config = builder(columns, rows, title)
    except Exception as exc:
        log.warning("viz.build_failed", chart_type=viz_type, error=str(exc))
        viz_config = _build_table_config(columns, rows, title)
        viz_type = "table"

    # Step 4: Enhance with insights if available
    if key_metrics and viz_type != "table":
        viz_config["graphic"] = []  # Could add annotation overlays here

    log.info("viz.generated", type=viz_type, columns=len(columns))
    return {**state, "viz_config": viz_config, "viz_type": viz_type}


def _auto_select_chart_type(columns: list, rows: list, intent: dict, question: str = "") -> str:
    """Heuristic chart type selection based on data shape, intent, and question text."""
    intent_type = intent.get("type", "")
    row_count = len(rows)
    q = question.lower()

    if intent_type == "trend_analysis" or "time" in str(columns).lower() or "date" in str(columns).lower():
        return "line"

    if "funnel" in q or "conversion" in q or "stages" in q:
        return "funnel"

    if "gauge" in q or ("total" in q and row_count == 1):
        return "gauge"

    if len(columns) == 3 and row_count > 10:
        return "heatmap"

    if row_count <= 8 and len(columns) == 2:
        return "pie"

    if len(columns) >= 2:
        return "bar"

    return "table"


def _generate_title(question: str, viz_type: str) -> str:
    # Truncate long questions for chart titles
    q = question.strip().rstrip("?")
    if len(q) > 60:
        q = q[:57] + "..."
    return q
