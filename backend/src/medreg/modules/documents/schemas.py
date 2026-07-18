import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import AnyHttpUrl, BaseModel, Field


class StorageStatus(StrEnum):
    ARCHIVED = "archived"


class ParseStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileSecurityStatus(StrEnum):
    LEGACY = "legacy"
    PASSED = "passed"


class RegulationDocumentRead(BaseModel):
    id: uuid.UUID
    code: str
    regulation_version_id: uuid.UUID
    file_name: str
    content_type: str
    size_bytes: int
    sha256: str
    security_status: FileSecurityStatus
    security_engine: str
    detected_type: str
    security_findings: list[str]
    bucket_name: str
    object_key: str
    storage_status: StorageStatus
    parse_status: ParseStatus
    parse_attempts: int
    parse_task_id: str | None
    parser_version: str | None
    segmenter_version: str | None = None
    section_count: int = 0
    chunk_count: int = 0
    table_count: int = 0
    extracted_char_count: int
    parse_error: str | None
    uploaded_by: str
    queued_at: datetime | None
    processing_started_at: datetime | None
    parsed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RegulationDocumentList(BaseModel):
    items: list[RegulationDocumentRead]
    total: int


class DocumentSectionRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    parent_id: uuid.UUID | None
    kind: str
    ordinal: int
    heading: str
    citation_path: str
    content: str
    char_start: int
    char_end: int
    content_hash: str
    created_at: datetime


class DocumentChunkRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    section_id: uuid.UUID
    ordinal: int
    section_chunk_index: int
    citation_label: str
    content: str
    char_start: int
    char_end: int
    char_count: int
    token_estimate: int
    content_hash: str
    created_at: datetime


class DocumentTableRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    ordinal: int
    title: str
    sheet_name: str | None
    row_count: int
    column_count: int
    headers: list[str]
    rows: list[list[str]]
    source_locator: str
    content_hash: str
    created_at: datetime


class DocumentStructureRead(BaseModel):
    document_id: uuid.UUID
    parser_version: str | None
    segmenter_version: str | None
    section_count: int
    chunk_count: int
    table_count: int
    sections: list[DocumentSectionRead]
    chunks: list[DocumentChunkRead]
    tables: list[DocumentTableRead]


class FetchStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    QUEUED = "queued"
    FETCHING = "fetching"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class FetchReviewDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class FetchRequestCreate(BaseModel):
    official_url: AnyHttpUrl
    requested_by: str = Field(min_length=2, max_length=80)
    reason: str = Field(min_length=2, max_length=500)


class FetchReviewCreate(BaseModel):
    decision: FetchReviewDecision
    reviewed_by: str = Field(min_length=2, max_length=80)
    note: str = Field(min_length=2, max_length=500)


class DocumentFetchRequestRead(BaseModel):
    id: uuid.UUID
    regulation_version_id: uuid.UUID
    official_url: AnyHttpUrl
    status: FetchStatus
    requested_by: str
    request_reason: str
    reviewed_by: str | None
    review_note: str | None
    reviewed_at: datetime | None
    task_id: str | None
    resulting_document_id: uuid.UUID | None
    fetch_error: str | None
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentFetchRequestList(BaseModel):
    items: list[DocumentFetchRequestRead]
    total: int


class ParseRecoveryRead(BaseModel):
    recovered: int
    document_ids: list[uuid.UUID]
