import asyncio
import hashlib
import re
import time
import uuid
from datetime import UTC, datetime

from medreg.modules.retrieval.dispatcher import RetrievalTaskDispatcher
from medreg.modules.retrieval.repository import RetrievalRepository
from medreg.modules.retrieval.schemas import (
    EvidenceHit,
    HybridSearchRequest,
    HybridSearchResponse,
    IndexDocumentInput,
    VectorIndexRead,
    VectorIndexStatus,
)
from medreg.modules.retrieval.vector_store import HybridVectorStore, VectorSearchCandidate

ARTICLE_REFERENCE_RE = re.compile(r"第[零〇○一二两三四五六七八九十百千万0-9]+条")
HAN_SEQUENCE_RE = re.compile(r"[\u4e00-\u9fff]{2,}")


class RetrievalDocumentNotReadyError(ValueError):
    pass


class VectorIndexNotFoundError(LookupError):
    pass


class VectorIndexingError(RuntimeError):
    pass


class RetrievalService:
    def __init__(
        self,
        repository: RetrievalRepository,
        vector_store: HybridVectorStore,
        dispatcher: RetrievalTaskDispatcher,
        collection_name: str,
        dense_model: str,
        sparse_model: str,
    ) -> None:
        self.repository = repository
        self.vector_store = vector_store
        self.dispatcher = dispatcher
        self.collection_name = collection_name
        self.dense_model = dense_model
        self.sparse_model = sparse_model

    async def get_index_status(self, document_id: uuid.UUID) -> VectorIndexRead:
        index_input = await self.repository.get_index_input(document_id)
        if index_input is None:
            raise RetrievalDocumentNotReadyError(
                "Document must be parsed into citation chunks before indexing"
            )
        fingerprint = self._fingerprint(index_input)
        index = await self.repository.get_index(document_id)
        if index is None:
            now = datetime.now(UTC)
            return VectorIndexRead(
                document_id=document_id,
                status=VectorIndexStatus.PENDING,
                attempts=0,
                task_id=None,
                collection_name=self.collection_name,
                dense_model=self.dense_model,
                sparse_model=self.sparse_model,
                content_fingerprint=fingerprint,
                indexed_chunk_count=0,
                index_error=None,
                queued_at=None,
                processing_started_at=None,
                indexed_at=None,
                created_at=now,
                updated_at=now,
            )
        if (
            index.status == VectorIndexStatus.COMPLETED
            and index.content_fingerprint != fingerprint
        ):
            return index.model_copy(update={"status": VectorIndexStatus.STALE})
        return index

    async def queue_index(
        self, document_id: uuid.UUID, force: bool = False
    ) -> VectorIndexRead:
        index_input = await self.repository.get_index_input(document_id)
        if index_input is None:
            raise RetrievalDocumentNotReadyError(
                "Document must be parsed into citation chunks before indexing"
            )
        fingerprint = self._fingerprint(index_input)
        existing = await self.repository.get_index(document_id)
        if existing is not None:
            if existing.status in {
                VectorIndexStatus.QUEUED,
                VectorIndexStatus.PROCESSING,
            }:
                return existing
            if (
                existing.status == VectorIndexStatus.COMPLETED
                and existing.content_fingerprint == fingerprint
                and existing.dense_model == self.dense_model
                and existing.sparse_model == self.sparse_model
                and not force
            ):
                return existing

        now = datetime.now(UTC)
        task_id = str(uuid.uuid4())
        queued = VectorIndexRead(
            document_id=document_id,
            status=VectorIndexStatus.QUEUED,
            attempts=existing.attempts if existing else 0,
            task_id=task_id,
            collection_name=self.collection_name,
            dense_model=self.dense_model,
            sparse_model=self.sparse_model,
            content_fingerprint=fingerprint,
            indexed_chunk_count=0,
            index_error=None,
            queued_at=now,
            processing_started_at=None,
            indexed_at=None,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        saved = await self.repository.save_index(queued)
        if saved is None:
            raise VectorIndexNotFoundError(str(document_id))
        try:
            self.dispatcher.enqueue_index(document_id, task_id)
        except Exception as exc:
            failed = saved.model_copy(
                update={
                    "status": VectorIndexStatus.FAILED,
                    "index_error": f"Task dispatch failed: {exc}"[:1000],
                    "updated_at": datetime.now(UTC),
                }
            )
            await self.repository.save_index(failed, expected_task_id=task_id)
            raise VectorIndexingError("Unable to enqueue vector indexing") from exc
        return saved

    async def execute_index(
        self, document_id: uuid.UUID, task_id: str | None = None
    ) -> VectorIndexRead:
        index = await self.repository.get_index(document_id)
        if index is None:
            raise VectorIndexNotFoundError(str(document_id))
        if task_id is not None and index.task_id != task_id:
            return index
        if index.status not in {
            VectorIndexStatus.QUEUED,
            VectorIndexStatus.PROCESSING,
        }:
            return index
        index_input = await self.repository.get_index_input(document_id)
        if index_input is None:
            raise RetrievalDocumentNotReadyError(
                "Document must be parsed into citation chunks before indexing"
            )

        started_at = datetime.now(UTC)
        processing = index.model_copy(
            update={
                "status": VectorIndexStatus.PROCESSING,
                "attempts": index.attempts + 1,
                "processing_started_at": started_at,
                "index_error": None,
                "updated_at": started_at,
            }
        )
        saved = await self.repository.save_index(
            processing, expected_task_id=task_id
        )
        if saved is None:
            raise VectorIndexNotFoundError(str(document_id))
        if task_id is not None and saved.task_id != task_id:
            return saved

        try:
            indexed_count = await asyncio.to_thread(
                self.vector_store.index_document, index_input
            )
        except Exception as exc:
            failed = processing.model_copy(
                update={
                    "status": VectorIndexStatus.FAILED,
                    "index_error": str(exc)[:1000],
                    "updated_at": datetime.now(UTC),
                }
            )
            await self.repository.save_index(failed, expected_task_id=task_id)
            raise VectorIndexingError(failed.index_error or "Vector indexing failed") from exc

        completed_at = datetime.now(UTC)
        completed = processing.model_copy(
            update={
                "status": VectorIndexStatus.COMPLETED,
                "content_fingerprint": self._fingerprint(index_input),
                "indexed_chunk_count": indexed_count,
                "indexed_at": completed_at,
                "index_error": None,
                "updated_at": completed_at,
            }
        )
        result = await self.repository.save_index(
            completed, expected_task_id=task_id
        )
        if result is None:
            raise VectorIndexNotFoundError(str(document_id))
        return result

    async def search(self, payload: HybridSearchRequest) -> HybridSearchResponse:
        started = time.perf_counter()
        candidates = await asyncio.to_thread(
            self.vector_store.search,
            payload.query.strip(),
            payload.limit,
            payload.document_ids,
            payload.regulation_version_ids,
        )
        hits = self._rerank(payload.query, candidates, payload.limit, payload.rerank)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return HybridSearchResponse(
            query=payload.query.strip(),
            strategy="dense + BM25 + RRF + lexical rerank",
            dense_model=self.dense_model,
            sparse_model=self.sparse_model,
            elapsed_ms=elapsed_ms,
            total=len(hits),
            items=hits,
        )

    @classmethod
    def _rerank(
        cls,
        query: str,
        candidates: list[VectorSearchCandidate],
        limit: int,
        enabled: bool,
    ) -> list[EvidenceHit]:
        query_terms = cls._terms(query)
        max_score = max((item.score for item in candidates), default=1.0)
        scored: list[tuple[float, VectorSearchCandidate, list[str]]] = []
        for candidate in candidates:
            searchable = " ".join(
                [
                    str(candidate.payload.get("source_title", "")),
                    str(candidate.payload.get("document_number", "")),
                    str(candidate.payload.get("citation_label", "")),
                    str(candidate.payload.get("content", "")),
                ]
            )
            matched = sorted(
                query_terms & cls._terms(searchable), key=lambda item: (-len(item), item)
            )
            lexical_score = len(matched) / max(len(query_terms), 1)
            retrieval_score = candidate.score / max(max_score, 1e-9)
            final_score = (
                0.50 * retrieval_score + 0.50 * lexical_score
                if enabled
                else retrieval_score
            )
            scored.append((final_score, candidate, matched[:8]))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            cls._to_hit(candidate, matched, final_score)
            for final_score, candidate, matched in scored[:limit]
        ]

    @staticmethod
    def _to_hit(
        candidate: VectorSearchCandidate,
        matched_terms: list[str],
        rerank_score: float,
    ) -> EvidenceHit:
        payload = candidate.payload
        return EvidenceHit(
            chunk_id=candidate.chunk_id,
            document_id=uuid.UUID(str(payload["document_id"])),
            regulation_version_id=uuid.UUID(str(payload["regulation_version_id"])),
            source_id=uuid.UUID(str(payload["source_id"])),
            source_title=str(payload["source_title"]),
            document_number=str(payload["document_number"]),
            version_label=str(payload["version_label"]),
            citation_label=str(payload["citation_label"]),
            content=str(payload["content"]),
            char_start=int(payload["char_start"]),
            char_end=int(payload["char_end"]),
            retrieval_score=round(candidate.score, 6),
            rerank_score=round(rerank_score, 6),
            matched_terms=matched_terms,
        )

    @staticmethod
    def _fingerprint(document: IndexDocumentInput) -> str:
        digest = hashlib.sha256()
        digest.update(document.parser_version.encode())
        digest.update(document.segmenter_version.encode())
        for chunk in document.chunks:
            digest.update(chunk.content_hash.encode())
        return digest.hexdigest()

    @staticmethod
    def _terms(text: str) -> set[str]:
        compact = re.sub(r"\s+", "", text.lower())
        terms = set(ARTICLE_REFERENCE_RE.findall(compact))
        for sequence in HAN_SEQUENCE_RE.findall(compact):
            if len(sequence) <= 6:
                terms.add(sequence)
            for width in (2, 3):
                terms.update(
                    sequence[index : index + width]
                    for index in range(max(len(sequence) - width + 1, 0))
                )
        terms.update(re.findall(r"[a-z0-9][a-z0-9._/-]+", compact))
        return terms
