import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    contract_type: Mapped[str] = mapped_column(String, default="unknown", nullable=False)

    # Analysis job tracking
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True, index=True
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), default=None, nullable=True, unique=True, index=True
    )

    # Status: uploaded | queued | uploading | ocr | analyzing | generating | completed | failed
    status: Mapped[str] = mapped_column(String, default="uploaded", nullable=False)
    progress: Mapped[int] = mapped_column(default=0, nullable=False)
    current_step: Mapped[str] = mapped_column(String, default="upload", nullable=False)
    completed_steps: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Error info
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    # Analysis result (stored when completed)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # OCR text
    ocr_text: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="contracts")
    payments: Mapped[list["Payment"]] = relationship(back_populates="contract")
    special_clause_edits: Mapped[list["SpecialClauseEdit"]] = relationship(back_populates="contract")
