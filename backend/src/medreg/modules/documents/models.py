import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from medreg.core.database import Base


class RegulationDocumentModel(Base):
    __tablename__ = "regulation_documents"
    __table_args__ = (
        Index(
            "ix_regulation_documents_version_sha256",
            "regulation_version_id",
            "sha256",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    regulation_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("regulation_versions.id", ondelete="CASCADE"),
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    security_status: Mapped[str] = mapped_column(String(24), index=True)
    security_engine: Mapped[str] = mapped_column(String(80))
    detected_type: Mapped[str] = mapped_column(String(24), index=True)
    security_findings: Mapped[list[str]] = mapped_column(JSON, default=list)
    bucket_name: Mapped[str] = mapped_column(String(80))
    object_key: Mapped[str] = mapped_column(String(600), unique=True)
    storage_status: Mapped[str] = mapped_column(String(32), index=True)
    parse_status: Mapped[str] = mapped_column(String(32), index=True)
    parse_attempts: Mapped[int] = mapped_column(Integer, default=0)
    parse_task_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )
    parser_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    segmenter_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    section_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    table_count: Mapped[int] = mapped_column(Integer, default=0)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_char_count: Mapped[int] = mapped_column(Integer, default=0)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(80))
    queued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    parsed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DocumentSectionModel(Base):
    __tablename__ = "document_sections"
    __table_args__ = (
        Index(
            "ix_document_sections_document_ordinal",
            "document_id",
            "ordinal",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("regulation_documents.id", ondelete="CASCADE"),
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("document_sections.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(24), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str] = mapped_column(String(300))
    citation_path: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index(
            "ix_document_chunks_document_ordinal",
            "document_id",
            "ordinal",
            unique=True,
        ),
        Index(
            "ix_document_chunks_section_index",
            "section_id",
            "section_chunk_index",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("regulation_documents.id", ondelete="CASCADE"),
        index=True,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("document_sections.id", ondelete="CASCADE"),
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    section_chunk_index: Mapped[int] = mapped_column(Integer)
    citation_label: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    char_count: Mapped[int] = mapped_column(Integer)
    token_estimate: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DocumentTableModel(Base):
    __tablename__ = "document_tables"
    __table_args__ = (
        Index(
            "ix_document_tables_document_ordinal",
            "document_id",
            "ordinal",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("regulation_documents.id", ondelete="CASCADE"),
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    sheet_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer)
    column_count: Mapped[int] = mapped_column(Integer)
    headers: Mapped[list[str]] = mapped_column(JSON)
    rows: Mapped[list[list[str]]] = mapped_column(JSON)
    source_locator: Mapped[str] = mapped_column(String(300))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DocumentFetchRequestModel(Base):
    __tablename__ = "document_fetch_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    regulation_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("regulation_versions.id", ondelete="CASCADE"),
        index=True,
    )
    official_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    requested_by: Mapped[str] = mapped_column(String(80))
    request_reason: Mapped[str] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    task_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    resulting_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("regulation_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    fetch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
