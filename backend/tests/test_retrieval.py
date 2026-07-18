import uuid
from datetime import UTC, datetime

import pytest

from medreg.modules.retrieval.schemas import (
    HybridSearchRequest,
    IndexChunkInput,
    IndexDocumentInput,
    VectorIndexRead,
)
from medreg.modules.retrieval.service import RetrievalService
from medreg.modules.retrieval.vector_store import VectorSearchCandidate


def make_input() -> IndexDocumentInput:
    return IndexDocumentInput(
        document_id=uuid.uuid4(),
        regulation_version_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        source_title="医疗器械监督管理条例",
        issuing_authority="国务院",
        version_label="2021 年修订",
        document_number="国务院令第739号",
        parser_version="controlled-parser-v2",
        segmenter_version="legal-hierarchy-v1",
        chunks=[
            IndexChunkInput(
                id=uuid.uuid4(),
                section_id=uuid.uuid4(),
                ordinal=0,
                citation_label="第八章 监督管理 / 第一百零一条",
                content="医疗器械注册人、备案人应当按照规定提交唯一标识相关数据。",
                char_start=12883,
                char_end=12957,
                content_hash="a" * 64,
            )
        ],
    )


class FakeRepository:
    def __init__(self, index_input: IndexDocumentInput) -> None:
        self.index_input = index_input
        self.index: VectorIndexRead | None = None

    async def get_index(self, document_id: uuid.UUID) -> VectorIndexRead | None:
        return self.index

    async def save_index(
        self, index: VectorIndexRead, expected_task_id: str | None = None
    ) -> VectorIndexRead | None:
        if (
            expected_task_id is not None
            and self.index is not None
            and self.index.task_id != expected_task_id
        ):
            return self.index
        self.index = index
        return index

    async def get_index_input(
        self, document_id: uuid.UUID
    ) -> IndexDocumentInput | None:
        if document_id != self.index_input.document_id:
            return None
        return self.index_input


class FakeDispatcher:
    def __init__(self) -> None:
        self.task_id: str | None = None

    def enqueue_index(self, document_id: uuid.UUID, task_id: str) -> None:
        self.task_id = task_id


class FakeVectorStore:
    def __init__(self, index_input: IndexDocumentInput) -> None:
        self.index_input = index_input

    def index_document(self, document: IndexDocumentInput) -> int:
        return len(document.chunks)

    def search(
        self,
        query: str,
        limit: int,
        document_ids: list[uuid.UUID],
        regulation_version_ids: list[uuid.UUID],
    ) -> list[VectorSearchCandidate]:
        chunk = self.index_input.chunks[0]
        return [
            VectorSearchCandidate(
                chunk_id=chunk.id,
                score=0.75,
                payload={
                    "document_id": str(self.index_input.document_id),
                    "regulation_version_id": str(
                        self.index_input.regulation_version_id
                    ),
                    "source_id": str(self.index_input.source_id),
                    "source_title": self.index_input.source_title,
                    "document_number": self.index_input.document_number,
                    "version_label": self.index_input.version_label,
                    "citation_label": chunk.citation_label,
                    "content": chunk.content,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                },
            )
        ]


@pytest.fixture
def retrieval_fixture():
    index_input = make_input()
    repository = FakeRepository(index_input)
    dispatcher = FakeDispatcher()
    vector_store = FakeVectorStore(index_input)
    service = RetrievalService(
        repository=repository,
        vector_store=vector_store,
        dispatcher=dispatcher,
        collection_name="test_chunks",
        dense_model="BAAI/bge-small-zh-v1.5",
        sparse_model="Qdrant/bm25",
    )
    return service, repository, dispatcher, index_input


async def test_index_lifecycle(retrieval_fixture) -> None:
    service, repository, dispatcher, index_input = retrieval_fixture

    pending = await service.get_index_status(index_input.document_id)
    assert pending.status == "pending"

    queued = await service.queue_index(index_input.document_id)
    assert queued.status == "queued"
    assert dispatcher.task_id == queued.task_id

    completed = await service.execute_index(
        index_input.document_id, dispatcher.task_id
    )
    assert completed.status == "completed"
    assert completed.indexed_chunk_count == 1
    assert repository.index == completed


async def test_completed_index_becomes_stale_when_chunks_change(
    retrieval_fixture,
) -> None:
    service, repository, dispatcher, index_input = retrieval_fixture
    await service.queue_index(index_input.document_id)
    await service.execute_index(index_input.document_id, dispatcher.task_id)
    repository.index_input = index_input.model_copy(
        update={
            "chunks": [
                index_input.chunks[0].model_copy(update={"content_hash": "b" * 64})
            ]
        }
    )

    status = await service.get_index_status(index_input.document_id)

    assert status.status == "stale"


async def test_hybrid_search_returns_auditable_evidence(retrieval_fixture) -> None:
    service, _, _, _ = retrieval_fixture

    result = await service.search(
        HybridSearchRequest(query="唯一标识信息由谁提交", limit=5)
    )

    assert result.total == 1
    assert result.items[0].citation_label.endswith("第一百零一条")
    assert result.items[0].char_start == 12883
    assert result.items[0].rerank_score > 0
    assert "唯一" in result.items[0].matched_terms


def test_vector_index_schema_accepts_timezone_aware_dates() -> None:
    now = datetime.now(UTC)
    data = make_input()
    index = VectorIndexRead(
        document_id=data.document_id,
        status="pending",
        attempts=0,
        task_id=None,
        collection_name="test",
        dense_model="dense",
        sparse_model="sparse",
        content_fingerprint="f" * 64,
        indexed_chunk_count=0,
        index_error=None,
        queued_at=None,
        processing_started_at=None,
        indexed_at=None,
        created_at=now,
        updated_at=now,
    )
    assert index.created_at.tzinfo is not None
