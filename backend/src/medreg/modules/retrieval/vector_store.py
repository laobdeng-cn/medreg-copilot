import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models

from medreg.modules.retrieval.schemas import IndexDocumentInput

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "bm25"


@dataclass(frozen=True)
class VectorSearchCandidate:
    chunk_id: uuid.UUID
    score: float
    payload: dict[str, Any]


class HybridVectorStore(Protocol):
    def index_document(self, document: IndexDocumentInput) -> int: ...

    def search(
        self,
        query: str,
        limit: int,
        document_ids: list[uuid.UUID],
        regulation_version_ids: list[uuid.UUID],
    ) -> list[VectorSearchCandidate]: ...


class QdrantFastEmbedVectorStore:
    def __init__(
        self,
        url: str,
        collection_name: str,
        dense_model: str,
        sparse_model: str,
        cache_dir: str,
        api_key: str | None = None,
    ) -> None:
        self.collection_name = collection_name
        self.dense_model_name = dense_model
        self.sparse_model_name = sparse_model
        self._client = QdrantClient(url=url, api_key=api_key, timeout=60)
        self._model_cache = Path(cache_dir).expanduser()
        self._model_cache.mkdir(parents=True, exist_ok=True)
        self._dense: TextEmbedding | None = None
        self._sparse: SparseTextEmbedding | None = None

    def index_document(self, document: IndexDocumentInput) -> int:
        texts = [
            self._embedding_text(chunk.citation_label, chunk.content)
            for chunk in document.chunks
        ]
        dense_vectors = list(self._dense_encoder().passage_embed(texts))
        sparse_vectors = list(self._sparse_encoder().passage_embed(texts))
        if not dense_vectors:
            return 0
        self._ensure_collection(len(dense_vectors[0]))
        document_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=str(document.document_id)),
                )
            ]
        )
        self._client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(filter=document_filter),
            wait=True,
        )
        points = []
        for chunk, dense, sparse in zip(
            document.chunks, dense_vectors, sparse_vectors, strict=True
        ):
            payload = {
                "document_id": str(document.document_id),
                "regulation_version_id": str(document.regulation_version_id),
                "source_id": str(document.source_id),
                "source_title": document.source_title,
                "issuing_authority": document.issuing_authority,
                "version_label": document.version_label,
                "document_number": document.document_number,
                "section_id": str(chunk.section_id),
                "ordinal": chunk.ordinal,
                "citation_label": chunk.citation_label,
                "content": chunk.content,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "content_hash": chunk.content_hash,
                "parser_version": document.parser_version,
                "segmenter_version": document.segmenter_version,
            }
            points.append(
                models.PointStruct(
                    id=str(chunk.id),
                    vector={
                        DENSE_VECTOR_NAME: dense.tolist(),
                        SPARSE_VECTOR_NAME: models.SparseVector(
                            indices=sparse.indices.tolist(),
                            values=sparse.values.tolist(),
                        ),
                    },
                    payload=payload,
                )
            )
        for batch in self._batches(points, 32):
            self._client.upsert(
                collection_name=self.collection_name,
                points=batch,
                wait=True,
            )
        return len(points)

    def search(
        self,
        query: str,
        limit: int,
        document_ids: list[uuid.UUID],
        regulation_version_ids: list[uuid.UUID],
    ) -> list[VectorSearchCandidate]:
        if not self._client.collection_exists(self.collection_name):
            return []
        dense = next(iter(self._dense_encoder().query_embed(query)))
        sparse = next(iter(self._sparse_encoder().query_embed(query)))
        query_filter = self._build_filter(document_ids, regulation_version_ids)
        candidate_limit = max(limit * 4, 20)
        response = self._client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense.tolist(),
                    using=DENSE_VECTOR_NAME,
                    filter=query_filter,
                    limit=candidate_limit,
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse.indices.tolist(),
                        values=sparse.values.tolist(),
                    ),
                    using=SPARSE_VECTOR_NAME,
                    filter=query_filter,
                    limit=candidate_limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=candidate_limit,
            with_payload=True,
            with_vectors=False,
        )
        candidates: list[VectorSearchCandidate] = []
        for point in response.points:
            if not isinstance(point.payload, dict):
                continue
            candidates.append(
                VectorSearchCandidate(
                    chunk_id=uuid.UUID(str(point.id)),
                    score=float(point.score),
                    payload=point.payload,
                )
            )
        return candidates

    def _ensure_collection(self, dense_size: int) -> None:
        if self._client.collection_exists(self.collection_name):
            return
        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                DENSE_VECTOR_NAME: models.VectorParams(
                    size=dense_size,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: models.SparseVectorParams(
                    modifier=models.Modifier.IDF
                )
            },
        )
        for field_name in ("document_id", "regulation_version_id", "source_id"):
            self._client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
                wait=True,
            )

    def _dense_encoder(self) -> TextEmbedding:
        if self._dense is None:
            kwargs: dict[str, Any] = {}
            local_model = self._find_local_dense_model()
            if local_model is not None:
                kwargs["specific_model_path"] = str(local_model)
            self._dense = TextEmbedding(
                model_name=self.dense_model_name,
                cache_dir=str(self._model_cache / "dense"),
                **kwargs,
            )
        return self._dense

    def _sparse_encoder(self) -> SparseTextEmbedding:
        if self._sparse is None:
            self._sparse = SparseTextEmbedding(
                model_name=self.sparse_model_name,
                cache_dir=str(self._model_cache / "sparse"),
            )
        return self._sparse

    def _find_local_dense_model(self) -> Path | None:
        dense_cache = self._model_cache / "dense"
        for model_file in dense_cache.glob("*/model_optimized.onnx"):
            return model_file.parent
        return None

    @staticmethod
    def _embedding_text(citation_label: str, content: str) -> str:
        return f"{citation_label}\n{content}".strip()

    @staticmethod
    def _build_filter(
        document_ids: list[uuid.UUID],
        regulation_version_ids: list[uuid.UUID],
    ) -> models.Filter | None:
        conditions: list[models.Condition] = []
        if document_ids:
            conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchAny(any=[str(item) for item in document_ids]),
                )
            )
        if regulation_version_ids:
            conditions.append(
                models.FieldCondition(
                    key="regulation_version_id",
                    match=models.MatchAny(
                        any=[str(item) for item in regulation_version_ids]
                    ),
                )
            )
        return models.Filter(must=conditions) if conditions else None

    @staticmethod
    def _batches(items: list[Any], size: int) -> Iterable[list[Any]]:
        for start in range(0, len(items), size):
            yield items[start : start + size]
