import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medreg.core.database import Base


class RegistrationApplicationModel(Base):
    __tablename__ = "registration_applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        index=True,
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    product_name: Mapped[str] = mapped_column(String(160))
    applicant_name: Mapped[str] = mapped_column(String(160))
    jurisdiction: Mapped[str] = mapped_column(String(32))
    device_class: Mapped[str] = mapped_column(String(8))
    application_type: Mapped[str] = mapped_column(String(48))
    regulation_effective_on: Mapped[date] = mapped_column(Date)
    owner_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), index=True)
    completion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    requirements: Mapped[list["DossierRequirementModel"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="DossierRequirementModel.position",
        lazy="selectin",
    )


class DossierRequirementModel(Base):
    __tablename__ = "dossier_requirements"
    __table_args__ = (
        Index(
            "ix_dossier_requirements_application_key",
            "application_id",
            "category_key",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("registration_applications.id", ondelete="CASCADE"),
        index=True,
    )
    category_key: Mapped[str] = mapped_column(String(48))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    regulatory_basis: Mapped[str] = mapped_column(Text)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer)

    application: Mapped[RegistrationApplicationModel] = relationship(
        back_populates="requirements"
    )


class DossierEvidenceModel(Base):
    __tablename__ = "dossier_evidence"
    __table_args__ = (
        Index(
            "ix_dossier_evidence_application_category_sha256",
            "application_id",
            "category_key",
            "sha256",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("registration_applications.id", ondelete="CASCADE"),
        index=True,
    )
    category_key: Mapped[str] = mapped_column(String(48), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    bucket_name: Mapped[str] = mapped_column(String(80))
    object_key: Mapped[str] = mapped_column(String(600), unique=True)
    uploaded_by: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PrecheckRunModel(Base):
    __tablename__ = "precheck_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("registration_applications.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    rule_set_version: Mapped[str] = mapped_column(String(48))
    application_status: Mapped[str] = mapped_column(String(32))
    blocker_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    pass_count: Mapped[int] = mapped_column(Integer, default=0)
    initiated_by: Mapped[str] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    findings: Mapped[list["PrecheckFindingModel"]] = relationship(
        cascade="all, delete-orphan",
        order_by="PrecheckFindingModel.position",
        lazy="selectin",
    )


class PrecheckFindingModel(Base):
    __tablename__ = "precheck_findings"
    __table_args__ = (
        Index(
            "ix_precheck_findings_run_rule_category",
            "run_id",
            "rule_code",
            "category_key",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("precheck_runs.id", ondelete="CASCADE"),
        index=True,
    )
    category_key: Mapped[str] = mapped_column(String(48), index=True)
    rule_code: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    regulatory_basis: Mapped[str] = mapped_column(Text)
    remediation: Mapped[str] = mapped_column(Text)
    remediation_status: Mapped[str] = mapped_column(String(24), index=True)
    assignee: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
