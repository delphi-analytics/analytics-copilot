"""
Node 1: Intent Understanding
Classifies what the user wants: chart, query, follow-up, comparison, trend, etc.
Fast model — runs in <500ms.
"""
from __future__ import annotations
import json
import structlog
from backend.agent.state import AnalyticsState
from backend.agent.llm import call_llm

log = structlog.get_logger(__name__)


async def understand_intent(state: AnalyticsState) -> AnalyticsState:
    question = state["user_question"]
    history = state.get("conversation_history", [])[-4:]  # last 2 turns for context

    history_text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in history) if history else "None"

    prompt = f"""You are classifying a data analytics question.

Previous conversation:
{history_text}

Current question: "{question}"

Classify this question and return JSON only:
{{
  "type": "<chart_request|data_query|follow_up|insight_request|comparison|trend_analysis|export_request|greeting>",
  "chart_type_hint": "<bar|line|pie|scatter|heatmap|gauge|table|area|treemap|null>",
  "time_range": "<last_7_days|last_30_days|last_quarter|last_year|ytd|custom|null>",
  "aggregation": "<sum|count|avg|max|min|null>",
  "entities": ["<entity1>", "<entity2>"],
  "filters": {{"<field>": "<value>"}},
  "is_follow_up": <true|false>,
  "needs_comparison": <true|false>,
  "confidence": <0.0-1.0>,
  "rephrased_question": "<clearer version of the question for SQL generation>"
}}

Rules:
- chart_request: user explicitly wants a chart/graph/visualization
- data_query: user wants to see/query data without specifying chart
- follow_up: references previous result ("now break that down by...", "make it a line chart")
- insight_request: wants analysis ("why is X dropping?", "what's the trend?")
- comparison: comparing two things, periods, or categories
- trend_analysis: wants to see changes over time"""

    try:
        resp = await call_llm(
            messages=[{"role": "user", "content": prompt}],
            task="routing",
            max_tokens=300,
            temperature=0.0,
        )
        raw = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        intent = json.loads(raw)
    except Exception as exc:
        log.warning("intent.parse_failed", error=str(exc))
        intent = {
            "type": "data_query",
            "entities": [],
            "is_follow_up": False,
            "confidence": 0.5,
            "rephrased_question": question,
        }

    log.info("intent.classified", type=intent.get("type"), confidence=intent.get("confidence"))
    return {**state, "intent": intent}
