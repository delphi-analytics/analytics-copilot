import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36))
    datasource_id: Mapped[str | None] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(500), default="New Conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    messages: Mapped[list["Message"]] = relationship("Message", back_populates="conversation",
                                                      order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20))       # user | assistant | system
    content: Mapped[str] = mapped_column(Text)

    # Structured data attached to assistant messages
    sql_query: Mapped[str | None] = mapped_column(Text)
    query_results: Mapped[dict | None] = mapped_column(JSON)
    viz_config: Mapped[dict | None] = mapped_column(JSON)     # Apache ECharts config
    insights: Mapped[list | None] = mapped_column(JSON)
    follow_up_questions: Mapped[list | None] = mapped_column(JSON)

    # Agent pipeline metadata
    intent: Mapped[dict | None] = mapped_column(JSON)
    model_used: Mapped[str | None] = mapped_column(String(100))
    latency_ms: Mapped[int | None] = mapped_column()
    tokens_used: Mapped[int | None] = mapped_column()
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
