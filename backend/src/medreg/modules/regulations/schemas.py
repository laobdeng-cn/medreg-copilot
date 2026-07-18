import uuid
from datetime import date, datetime
from enum import StrEnum

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator


class RegulationType(StrEnum):
    REGULATION = "regulation"
    GUIDANCE = "guidance"
    NOTICE = "notice"
    STANDARD = "standard"
    TECHNICAL_GUIDELINE = "technical_guideline"


class ReviewStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ReviewDecision(StrEnum):
    VERIFIED = "verified"
    REJECTED = "rejected"


class LifecycleStatus(StrEnum):
    UNKNOWN = "unknown"
    UPCOMING = "upcoming"
    EFFECTIVE = "effective"
    EXPIRED = "expired"


class RegulationVersionCreate(BaseModel):
    version_label: str = Field(min_length=1, max_length=80)
    document_number: str = Field(min_length=1, max_length=120)
    official_url: AnyHttpUrl
    published_on: date
    effective_on: date
    expires_on: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "RegulationVersionCreate":
        if self.expires_on is not None and self.expires_on < self.effective_on:
            raise ValueError("expires_on must not be earlier than effective_on")
        return self


class RegulationSourceCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    issuing_authority: str = Field(min_length=2, max_length=160)
    jurisdiction: str = Field(default="CN", min_length=2, max_length=32)
    regulation_type: RegulationType
    scope_summary: str = Field(min_length=2, max_length=1000)
    initial_version: RegulationVersionCreate


class RegulationVersionRead(BaseModel):
    id: uuid.UUID
    version_label: str
    document_number: str
    official_url: AnyHttpUrl
    published_on: date
    effective_on: date
    expires_on: date | None
    review_status: ReviewStatus
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None
    lifecycle_status: LifecycleStatus = LifecycleStatus.UNKNOWN
    created_at: datetime
    updated_at: datetime


class RegulationSourceRead(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    issuing_authority: str
    jurisdiction: str
    regulation_type: RegulationType
    scope_summary: str
    versions: list[RegulationVersionRead]
    applicable_version: RegulationVersionRead | None = None
    created_at: datetime
    updated_at: datetime


class RegulationSourceList(BaseModel):
    items: list[RegulationSourceRead]
    total: int
    as_of: date


class VersionReviewCreate(BaseModel):
    decision: ReviewDecision
    reviewed_by: str = Field(min_length=2, max_length=80)
    note: str = Field(min_length=2, max_length=500)
