import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from medreg.core.database import Base


class AgentDraftRunModel(Base):
    __tablename__ = "agent_draft_runs"
    __table_args__ = (
        Index(
            "ix_agent_draft_runs_application_created",
            "application_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("registration_applications.id", ondelete="CASCADE"),
        index=True,
    )
    workflow_version: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(24), index=True)
    target_section: Mapped[str] = mapped_column(String(64), index=True)
    language_mode: Mapped[str] = mapped_column(String(24), index=True)
    requested_by: Mapped[str] = mapped_column(String(80))
    input_snapshot_hash: Mapped[str] = mapped_column(String(64), index=True)
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    prompt_version: Mapped[str] = mapped_column(String(48))
    prompt_snapshot: Mapped[str] = mapped_column(Text)
    model_provider: Mapped[str] = mapped_column(String(48))
    model_name: Mapped[str] = mapped_column(String(80))
    model_mode: Mapped[str] = mapped_column(String(24), index=True)
    model_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_title: Mapped[str] = mapped_column(String(200))
    draft_content: Mapped[str] = mapped_column(Text)
    reviewer_summary: Mapped[str] = mapped_column(Text)
    context_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    structured_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    bilingual_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    node_traces: Mapped[list] = mapped_column(JSON)
    citations: Mapped[list] = mapped_column(JSON)
    approval_status: Mapped[str] = mapped_column(String(24), index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
