import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from medreg.core.celery_app import celery_app
from medreg.core.config import get_settings
from medreg.core.database import async_session_factory, engine
from medreg.modules.retrieval.dispatcher import CeleryRetrievalTaskDispatcher
from medreg.modules.retrieval.repository import SQLAlchemyRetrievalRepository
from medreg.modules.retrieval.service import RetrievalService, VectorIndexingError
from medreg.modules.retrieval.vector_store import QdrantFastEmbedVectorStore


def _build_service(session: AsyncSession) -> RetrievalService:
    settings = get_settings()
    return RetrievalService(
        repository=SQLAlchemyRetrievalRepository(session),
        vector_store=QdrantFastEmbedVectorStore(
            url=settings.qdrant_url,
            collection_name=settings.qdrant_collection,
            dense_model=settings.embedding_dense_model,
            sparse_model=settings.embedding_sparse_model,
            cache_dir=settings.embedding_cache_dir,
            api_key=settings.qdrant_api_key_value,
        ),
        dispatcher=CeleryRetrievalTaskDispatcher(),
        collection_name=settings.qdrant_collection,
        dense_model=settings.embedding_dense_model,
        sparse_model=settings.embedding_sparse_model,
    )


async def _run_with_service(
    action: Callable[[RetrievalService], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    try:
        async with async_session_factory() as session:
            return await action(_build_service(session))
    finally:
        await engine.dispose()


@celery_app.task(bind=True, name="medreg.retrieval.index_document")
def index_document_task(task: Any, document_id: str) -> dict[str, Any]:
    async def execute(service: RetrievalService) -> dict[str, Any]:
        try:
            index = await service.execute_index(
                uuid.UUID(document_id), str(task.request.id)
            )
        except VectorIndexingError as exc:
            return {"document_id": document_id, "status": "failed", "error": str(exc)}
        return {
            "document_id": document_id,
            "status": index.status.value,
            "indexed_chunks": index.indexed_chunk_count,
        }

    return asyncio.run(_run_with_service(execute))
