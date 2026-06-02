import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)
    nickname: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str] = mapped_column(String, default="email", nullable=False)
    provider_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Terms agreement
    terms_agreed: Mapped[bool] = mapped_column(Boolean, default=False)
    privacy_agreed: Mapped[bool] = mapped_column(Boolean, default=False)
    marketing_agreed: Mapped[bool] = mapped_column(Boolean, default=False)
    agreed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Refresh token (for rotation validation)
    refresh_token_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    # 시세 조회 쿼터 (무료 3회)
    market_queries_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    contracts: Mapped[list["Contract"]] = relationship(back_populates="user")
    payments: Mapped[list["Payment"]] = relationship(back_populates="user")
    quota_records: Mapped[list["UserQuotaRecord"]] = relationship(back_populates="user")
