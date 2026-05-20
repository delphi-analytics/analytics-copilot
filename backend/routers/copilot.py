"""
AI Copilot Chat Router — the main endpoint.
POST /api/v1/copilot/query     → send question, get chart + insights
POST /api/v1/copilot/upload    → upload CSV/Excel for analysis
GET  /api/v1/copilot/history   → conversation history
GET  /api/v1/copilot/schema    → datasource schema
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agent.graph import run_analytics_agent
from backend.data.connector import upload_csv_as_datasource, get_schema, register_datasource
from backend.database import get_db
from backend.models.conversation import Conversation, Message
from backend.services.llm_cache import get_cache as _get_llm_cache

router = APIRouter()
DbDep = Annotated[AsyncSession, Depends(get_db)]


# ─── Request / Response models ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    datasource_id: str = "default"
    conversation_id: str | None = None
    user_id: str = "anonymous"


class QueryResponse(BaseModel):
    conversation_id: str
    message_id: str
    text: str
    chart: dict | None = None
    insights: list[str] = []
    key_metrics: dict = {}
    follow_up_questions: list[str] = []
    sql: str = ""
    sql_explanation: str = ""
    row_count: int = 0
    viz_type: str | None = None
    columns: list = []
    rows: list = []
    total_latency_ms: int = 0
    model_used: str = ""
    error: str | None = None


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest, db: DbDep) -> QueryResponse:
    """
    Main chat endpoint. Send a question, get AI-powered chart + insights.
    Includes LLM caching (15-min TTL) — repeat questions return instantly.

    Example:
      POST /api/v1/copilot/query
      {"question": "Show me sales by region last quarter", "datasource_id": "mydb"}
    """
    # ─── SECURITY: Block modification requests BEFORE cache check ─────────────
    question_upper = payload.question.upper()
    dangerous_keywords = ["UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "INSERT", "CREATE", "GRANT"]
    found_keyword = next((kw for kw in dangerous_keywords if kw in question_upper), None)
    if found_keyword:
        return QueryResponse(
            conversation_id=str(uuid.uuid4()),
            message_id=str(uuid.uuid4()),
            text=(
                "🔒 **You don't have permission to perform this action**\n\n"
                f"You asked me to **{found_keyword}** data, but I only have **read-only access**.\n\n"
                "I can:\n"
                "• ✅ Query and analyze data\n"
                "• ✅ Generate charts and visualizations\n"
                "• ✅ Provide insights and explanations\n\n"
                "I **cannot**:\n"
                "• ❌ Modify, update, or delete records\n"
                "• ❌ Create or drop tables\n"
                "• ❌ Change database structure\n\n"
                "Please use your database admin tools if you need to modify data. "
                "I'm here to help you analyze and explore your data!"
            ),
            chart=None,
            insights=["You attempted a data modification operation", "The system has read-only access enabled"],
            key_metrics={},
            follow_up_questions=[
                "Show me the current data",
                "What tables are available?",
                "Help me analyze the data"
            ],
            sql="",
            row_count=0,
            viz_type=None,
            columns=[],
            rows=[],
            total_latency_ms=0,
            model_used="",
            error=f"Read-only access: {found_keyword} operation not permitted",
        )

    # Check LLM cache first (Canary pattern — 80% latency reduction on repeats)
    cache = _get_llm_cache()
    cached = await cache.get_async(question=payload.question, datasource_id=payload.datasource_id)
    if cached and not payload.conversation_id:
        # Only use cache for fresh conversations (not follow-ups)
        # Note: run_analytics_agent is imported at module level — do NOT re-import here
        cache_fields = {k: v for k, v in cached.items()
                        if k in QueryResponse.model_fields}
        return QueryResponse(
            conversation_id=str(uuid.uuid4()),
            message_id=str(uuid.uuid4()),
            **cache_fields,
        )

    # Get or create conversation
    conversation_id = payload.conversation_id
    conversation = None

    if conversation_id:
        result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conversation = result.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=payload.user_id,
            datasource_id=payload.datasource_id,
            title=payload.question[:100],
        )
        db.add(conversation)
        await db.flush()
        conversation_id = conversation.id

    # Load conversation history (last N messages)
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    history_messages = list(reversed(history_result.scalars().all()))
    conversation_history = [
        {"role": m.role, "content": m.content}
        for m in history_messages
    ]

    # Save user message
    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="user",
        content=payload.question,
    )
    db.add(user_msg)
    await db.flush()

    # Run the 7-step agent pipeline
    try:
        agent_result = await run_analytics_agent(
            question=payload.question,
            datasource_id=payload.datasource_id,
            session_id=conversation_id,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
            user_id=payload.user_id,
        )
    except PermissionError as exc:
        # Read-only access violation - user-friendly error
        agent_result = {
            "error": str(exc),
            "text": (
                "🔒 **Read-Only Access**\n\n"
                "I can only query and analyze data — I cannot modify, delete, or create records. "
                "This is a security restriction to protect your data.\n\n"
                "If you need to modify data, please use your database admin tools directly. "
                "I'm here to help you explore and analyze your data!"
            ),
            "insights": [],
            "key_metrics": {},
            "follow_up_questions": [],
            "sql": "",
            "chart": None,
            "viz_type": None,
            "row_count": 0,
            "columns": [],
            "rows": [],
            "total_latency_ms": 0,
            "model_used": "",
        }

    # Save assistant message
    assistant_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="assistant",
        content=agent_result.get("text", ""),
        sql_query=agent_result.get("sql"),
        query_results={
            "columns": agent_result.get("columns", []),
            "rows": agent_result.get("rows", [])[:50],
            "row_count": agent_result.get("row_count", 0),
        },
        viz_config=agent_result.get("chart"),
        insights=agent_result.get("insights", []),
        follow_up_questions=agent_result.get("follow_up_questions", []),
        model_used=agent_result.get("model_used", ""),
        latency_ms=agent_result.get("total_latency_ms", 0),
        error=agent_result.get("error"),
    )
    db.add(assistant_msg)
    await db.commit()

    # Cache successful results (Canary-style 15-min cache)
    if not agent_result.get("error") and agent_result.get("row_count", 0) > 0:
        await cache.set_async(   # reuse cache object from top of function
            question=payload.question,
            datasource_id=payload.datasource_id,
            result={
                "text": agent_result.get("text", ""),
                "chart": agent_result.get("chart"),
                "insights": agent_result.get("insights", []),
                "key_metrics": agent_result.get("key_metrics", {}),
                "follow_up_questions": agent_result.get("follow_up_questions", []),
                "sql": agent_result.get("sql", ""),
                "sql_explanation": agent_result.get("sql_explanation", ""),
                "row_count": agent_result.get("row_count", 0),
                "viz_type": agent_result.get("viz_type"),
                "columns": agent_result.get("columns", []),
                "rows": agent_result.get("rows", []),
                "total_latency_ms": agent_result.get("total_latency_ms", 0),
                "model_used": agent_result.get("model_used", ""),
            },
        )

    return QueryResponse(
        conversation_id=conversation_id,
        message_id=assistant_msg.id,
        text=agent_result.get("text", ""),
        chart=agent_result.get("chart"),
        insights=agent_result.get("insights", []),
        key_metrics=agent_result.get("key_metrics", {}),
        follow_up_questions=agent_result.get("follow_up_questions", []),
        sql=agent_result.get("sql", ""),
        sql_explanation=agent_result.get("sql_explanation", ""),
        row_count=agent_result.get("row_count", 0),
        viz_type=agent_result.get("viz_type"),
        columns=agent_result.get("columns", []),
        rows=agent_result.get("rows", []),
        total_latency_ms=agent_result.get("total_latency_ms", 0),
        model_used=agent_result.get("model_used", ""),
        error=agent_result.get("error"),
    )


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    datasource_name: str = Form("uploaded_data"),
    user_id: str = Form("anonymous"),
) -> dict:
    """Upload a CSV or Excel file for analysis."""
    allowed_types = {"text/csv", "application/vnd.ms-excel",
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    if file.content_type not in allowed_types and not (
        file.filename or "").endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only CSV and Excel files supported")

    ds_id = str(uuid.uuid4())
    file_bytes = await file.read()

    result = await upload_csv_as_datasource(file_bytes, file.filename or "upload.csv", ds_id)

    return {
        "datasource_id": ds_id,
        "name": datasource_name,
        "filename": file.filename,
        "schema": result.get("schema", {}),
        "message": f"File uploaded. You can now ask questions about '{datasource_name}'",
    }


@router.get("/schema/{datasource_id}")
async def get_datasource_schema(datasource_id: str) -> dict:
    """Get the schema (tables + columns) for a datasource."""
    schema = await get_schema(datasource_id)
    return schema


@router.get("/history/{conversation_id}")
async def get_history(conversation_id: str, db: DbDep) -> dict:
    """Get conversation history."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "chart": m.viz_config,
                "insights": m.insights or [],
                "sql": m.sql_query,
                "row_count": (m.query_results or {}).get("row_count", 0),
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.post("/datasource")
async def register_ds(payload: dict) -> dict:
    """Register a new database datasource."""
    ds_id = payload.get("id") or str(uuid.uuid4())
    register_datasource(ds_id, payload["type"], payload.get("config", {}))
    schema = await get_schema(ds_id)
    return {"datasource_id": ds_id, "schema": schema, "status": "registered"}
