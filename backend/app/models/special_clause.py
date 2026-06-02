import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class SpecialClauseEdit(Base):
    """Stores user edits to AI-generated special clauses."""
    __tablename__ = "special_clause_edits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False, index=True
    )
    # Original clause ID from AI result (stored in contract.result JSONB)
    clause_id: Mapped[str] = mapped_column(String, nullable=False)
    edited_text: Mapped[str] = mapped_column(Text, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    contract: Mapped["Contract"] = relationship(back_populates="special_clause_edits")
