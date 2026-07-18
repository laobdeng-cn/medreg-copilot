import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class VectorIndexStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    STALE = "stale"


class VectorIndexRead(BaseModel):
    document_id: uuid.UUID
    status: VectorIndexStatus
    attempts: int
    task_id: str | None
    collection_name: str
    dense_model: str
    sparse_model: str
    content_fingerprint: str
    indexed_chunk_count: int
    index_error: str | None
    queued_at: datetime | None
    processing_started_at: datetime | None
    indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IndexChunkInput(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    ordinal: int
    citation_label: str
    content: str
    char_start: int
    char_end: int
    content_hash: str


class IndexDocumentInput(BaseModel):
    document_id: uuid.UUID
    regulation_version_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    issuing_authority: str
    version_label: str
    document_number: str
    parser_version: str
    segmenter_version: str
    chunks: list[IndexChunkInput]


class HybridSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    regulation_version_ids: list[uuid.UUID] = Field(
        default_factory=list, max_length=50
    )
    limit: int = Field(default=6, ge=1, le=20)
    rerank: bool = True


class EvidenceHit(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    regulation_version_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    document_number: str
    version_label: str
    citation_label: str
    content: str
    char_start: int
    char_end: int
    retrieval_score: float
    rerank_score: float
    matched_terms: list[str]


class HybridSearchResponse(BaseModel):
    query: str
    strategy: str
    dense_model: str
    sparse_model: str
    elapsed_ms: int
    total: int
    items: list[EvidenceHit]
