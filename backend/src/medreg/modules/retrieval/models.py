import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from medreg.core.database import Base


class DocumentVectorIndexModel(Base):
    __tablename__ = "document_vector_indexes"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("regulation_documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    task_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    collection_name: Mapped[str] = mapped_column(String(120))
    dense_model: Mapped[str] = mapped_column(String(160))
    sparse_model: Mapped[str] = mapped_column(String(160))
    content_fingerprint: Mapped[str] = mapped_column(String(64))
    indexed_chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    index_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
