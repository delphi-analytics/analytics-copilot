import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from passlib.context import CryptContext
from backend.database import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="business_analyst")  # business_analyst | non_tech_user | team_member | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime)
    preferences: Mapped[dict | None] = mapped_column(JSON, default=None)  # User preferences like theme, sidebar state

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.hashed_password)

    def can_view_sql(self) -> bool:
        return self.role in ("admin", "business_analyst")

    def can_export_data(self) -> bool:
        return self.role in ("admin", "business_analyst")

    def can_modify_documents(self) -> bool:
        return self.role in ("admin", "business_analyst")
