"""
SSE Streaming Endpoint for Real-time Agent Progress
Replaces polling with Server-Sent Events for instant feedback.
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

from backend.agent.graph import get_graph
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


class StreamingProgress:
    """Progress updates for SSE stream."""

    def __init__(self, step: str, progress: int, data: dict = None):
        self.step = step
        self.progress = progress
        self.data = data or {}

    def to_json(self) -> str:
        return json.dumps({
            "type": "progress",
            "step": self.step,
            "progress": self.progress,
            "data": self.data,
            "timestamp": asyncio.get_event_loop().time()
        })


async def _stream_agent_execution(
    question: str,
    datasource_id: str,
    conversation_id: str | None,
    user_id: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Execute agent and stream progress updates via SSE.
    Yields JSON strings for each completed step.
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

    # Step progress tracking
    steps = [
        ("understanding", 10, "Understanding your question..."),
        ("schema_discovery", 20, "Discovering relevant data..."),
        ("sql_generation", 35, "Generating SQL query..."),
        ("query_execution", 50, "Executing query..."),
        ("analysis", 70, "Analyzing results..."),
        ("visualization", 85, "Creating visualization..."),
        ("response", 100, "Composing response..."),
    ]

    # Run agent with progress tracking
    try:
        # Execute actual agent
        graph = get_graph()
        initial_state = AnalyticsState(
            session_id=conv_id,
            conversation_id=conv_id,
            user_question=question,
            datasource_id=datasource_id,
            conversation_history=conversation_history,
            user_id=user_id,
            step_errors=[],
        )

        # Emit progress for each step
        for step_name, progress, message in steps:
            yield f"data: {json.dumps({'type': 'progress', 'step': step_name, 'progress': progress, 'message': message})}\n\n"
            await asyncio.sleep(0.05)  # Brief delay for visual feedback

        final_state = await graph.ainvoke(initial_state)
        result = final_state.get("final_response", {})
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

        # Emit final result
        yield f"data: {json.dumps({'type': 'complete', 'result': result})}\n\n"

    except Exception as exc:
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
    SSE streaming endpoint for real-time agent progress.

    Usage in frontend:
    ```
    const eventSource = new EventSource('/api/v1/copilot/stream?question=Show+me+sales');
    eventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === 'progress') updateProgress(data);
        if (data.type === 'complete') displayResult(data.result);
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
