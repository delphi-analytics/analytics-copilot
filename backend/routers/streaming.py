"""
SSE Streaming Endpoint for Real-time Agent Progress
Streams actual node execution progress with partial results.
"""
from __future__ import annotations
import json
import asyncio
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agent.streaming_graph import get_streaming_graph
from backend.agent.state import AnalyticsState
from backend.database import get_db
from backend.models.conversation import Conversation, Message

router = APIRouter()


async def get_db_dep():
    """Dependency for database session."""
    async for session in get_db():
        yield session


class StreamingQueryRequest(BaseModel):
    question: str
    datasource_id: str = "default"
    conversation_id: str | None = None
    user_id: str = "anonymous"


async def _stream_agent_execution(
    question: str,
    datasource_id: str,
    conversation_id: str | None,
    user_id: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Execute agent and stream REAL progress updates via SSE.
    Yields JSON strings as each node completes with partial results.
    """
    # Emit start
    yield f"data: {json.dumps({'type': 'start', 'message': 'Starting analysis...'})}\n\n"

    # Get or create conversation
    conv_id = conversation_id
    if conv_id:
        result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
        conversation = result.scalar_one_or_none()
    else:
        conversation = None

    if not conversation:
        conv_id = str(uuid.uuid4())
        conversation = Conversation(
            id=conv_id,
            user_id=user_id,
            datasource_id=datasource_id,
            title=question[:100],
        )
        db.add(conversation)
        await db.flush()

    # Load history
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
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
        conversation_id=conv_id,
        role="user",
        content=question,
    )
    db.add(user_msg)
    await db.flush()

    # Run agent with REAL progress tracking
    try:
        graph_runner = get_streaming_graph()
        initial_state = AnalyticsState(
            session_id=conv_id,
            conversation_id=conv_id,
            user_question=question,
            datasource_id=datasource_id,
            conversation_history=conversation_history,
            user_id=user_id,
            step_errors=[],
        )

        # Stream real progress from graph execution
        async for update in graph_runner.astream(initial_state):
            yield f"data: {json.dumps(update)}\n\n"

            # If this is the final complete message, save to database
            if update.get("type") == "complete":
                result = update["result"]
                result["conversation_id"] = conv_id

                # Save assistant message
                assistant_msg = Message(
                    id=str(uuid.uuid4()),
                    conversation_id=conv_id,
                    role="assistant",
                    content=result.get("text", ""),
                    sql_query=result.get("sql", ""),
                    query_results={
                        "columns": result.get("columns", []),
                        "rows": result.get("rows", [])[:50],
                        "row_count": result.get("row_count", 0),
                    },
                    viz_config=result.get("chart"),
                    insights=result.get("insights", []),
                    follow_up_questions=result.get("follow_up_questions", []),
                    model_used=result.get("model_used", ""),
                    latency_ms=result.get("total_latency_ms", 0),
                    error=result.get("error"),
                )
                db.add(assistant_msg)
                await db.commit()

    except Exception as exc:
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"


@router.get("/stream")
async def stream_query(
    question: str,
    datasource_id: str = "default",
    conversation_id: str | None = None,
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db_dep),
):
    """
    SSE streaming endpoint for REAL-TIME agent progress.

    Streams actual progress as each pipeline node completes:
    - Intent classification (what the user wants)
    - SQL generation (the query being built)
    - Query execution (row count as soon as available)
    - Insights (key metrics found)
    - Visualization (chart type)
    - Final response

    Usage in frontend:
    ```
    const eventSource = new EventSource('/api/v1/copilot/stream?question=Show+me+sales');
    eventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === 'progress') {
            updateProgress(data.progress, data.message);
            if (data.data.sql) showSQL(data.data.sql);
            if (data.data.row_count !== undefined) showRowCount(data.data.row_count);
        }
        if (data.type === 'complete') displayResult(data.result);
        if (data.type === 'error') showError(data.error);
    };
    ```
    """
    return StreamingResponse(
        _stream_agent_execution(
            question=question,
            datasource_id=datasource_id,
            conversation_id=conversation_id,
            user_id=user_id,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/stream")
async def stream_query_post(
    request: StreamingQueryRequest,
    db: AsyncSession = Depends(get_db_dep),
):
    """
    POST version of streaming endpoint for better request handling.

    Request body:
    ```json
    {
        "question": "Show me revenue by platform",
        "datasource_id": "default",
        "conversation_id": "optional-existing-id",
        "user_id": "user-123"
    }
    ```
    """
    return StreamingResponse(
        _stream_agent_execution(
            question=request.question,
            datasource_id=request.datasource_id,
            conversation_id=request.conversation_id,
            user_id=request.user_id,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
