import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medreg.core.database import Base


class RegulationSourceModel(Base):
    __tablename__ = "regulation_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    issuing_authority: Mapped[str] = mapped_column(String(160), index=True)
    jurisdiction: Mapped[str] = mapped_column(String(32), index=True)
    regulation_type: Mapped[str] = mapped_column(String(48), index=True)
    scope_summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    versions: Mapped[list["RegulationVersionModel"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="RegulationVersionModel.effective_on.desc()",
        lazy="selectin",
    )


class RegulationVersionModel(Base):
    __tablename__ = "regulation_versions"
    __table_args__ = (
        Index(
            "ix_regulation_versions_source_label",
            "source_id",
            "version_label",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("regulation_sources.id", ondelete="CASCADE"),
        index=True,
    )
    version_label: Mapped[str] = mapped_column(String(80))
    document_number: Mapped[str] = mapped_column(String(120), index=True)
    official_url: Mapped[str] = mapped_column(Text)
    published_on: Mapped[date] = mapped_column(Date)
    effective_on: Mapped[date] = mapped_column(Date, index=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    source: Mapped[RegulationSourceModel] = relationship(back_populates="versions")
