import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class UserQuotaRecord(Base):
    """Tracks the user's current quota state."""
    __tablename__ = "user_quotas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    # type: none | single | pass_3month
    quota_type: Mapped[str] = mapped_column(String, default="none", nullable=False)
    remaining: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # -1 = unlimited
    pass_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    user: Mapped["User"] = relationship(back_populates="quota_records")
