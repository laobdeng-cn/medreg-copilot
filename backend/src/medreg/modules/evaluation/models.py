import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from medreg.core.database import Base


class EvaluationRunModel(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        Index(
            "ix_evaluation_runs_dataset_created",
            "dataset_version",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    dataset_version: Mapped[str] = mapped_column(String(64), index=True)
    dataset_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    requested_by: Mapped[str] = mapped_column(String(80))
    baseline_name: Mapped[str] = mapped_column(String(80))
    candidate_name: Mapped[str] = mapped_column(String(80))
    case_count: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[list] = mapped_column(JSON)
    task_summaries: Mapped[list] = mapped_column(JSON)
    quality_gate: Mapped[dict] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
