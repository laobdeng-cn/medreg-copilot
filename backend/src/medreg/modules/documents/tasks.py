import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from medreg.core.celery_app import celery_app
from medreg.core.config import get_settings
from medreg.core.database import async_session_factory, engine
from medreg.modules.documents.dispatcher import CeleryDocumentTaskDispatcher
from medreg.modules.documents.fetcher import ControlledOfficialSourceFetcher
from medreg.modules.documents.parser import ControlledDocumentParser
from medreg.modules.documents.repository import SQLAlchemyDocumentRepository
from medreg.modules.documents.segmenter import LegalDocumentSegmenter
from medreg.modules.documents.service import (
    DocumentFetchError,
    DocumentParseError,
    DocumentService,
)
from medreg.modules.documents.storage import MinioObjectStorage


def _build_service(session: AsyncSession) -> DocumentService:
    settings = get_settings()
    storage = MinioObjectStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket_name=settings.minio_bucket,
        secure=settings.minio_secure,
    )
    fetcher = ControlledOfficialSourceFetcher(
        allowed_hosts=settings.official_fetch_allowed_hosts,
        timeout_seconds=settings.official_fetch_timeout_seconds,
        max_bytes=settings.document_max_upload_bytes,
    )
    return DocumentService(
        repository=SQLAlchemyDocumentRepository(session),
        storage=storage,
        parser=ControlledDocumentParser(),
        segmenter=LegalDocumentSegmenter(),
        dispatcher=CeleryDocumentTaskDispatcher(),
        fetcher=fetcher,
        max_upload_bytes=settings.document_max_upload_bytes,
        parse_stale_after_seconds=settings.document_parse_stale_after_seconds,
    )


async def _run_with_service(
    action: Callable[[DocumentService], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    try:
        async with async_session_factory() as session:
            return await action(_build_service(session))
    finally:
        # Celery's synchronous task wrapper creates a new event loop per task.
        await engine.dispose()


@celery_app.task(bind=True, name="medreg.documents.parse")
def parse_document_task(task: Any, document_id: str) -> dict[str, Any]:
    async def execute(service: DocumentService) -> dict[str, Any]:
        try:
            document = await service.execute_parse(
                uuid.UUID(document_id), str(task.request.id)
            )
        except DocumentParseError as exc:
            return {"document_id": document_id, "status": "failed", "error": str(exc)}
        return {
            "document_id": document_id,
            "status": document.parse_status.value,
            "characters": document.extracted_char_count,
        }

    return asyncio.run(_run_with_service(execute))


@celery_app.task(bind=True, name="medreg.documents.fetch_official_source")
def fetch_official_source_task(task: Any, request_id: str) -> dict[str, Any]:
    async def execute(service: DocumentService) -> dict[str, Any]:
        try:
            request = await service.execute_fetch(
                uuid.UUID(request_id), str(task.request.id)
            )
        except DocumentFetchError as exc:
            return {"request_id": request_id, "status": "failed", "error": str(exc)}
        return {
            "request_id": request_id,
            "status": request.status.value,
            "document_id": (
                str(request.resulting_document_id)
                if request.resulting_document_id
                else None
            ),
        }

    return asyncio.run(_run_with_service(execute))


@celery_app.task(name="medreg.documents.recover_stale")
def recover_stale_document_tasks() -> dict[str, Any]:
    async def execute(service: DocumentService) -> dict[str, Any]:
        result = await service.recover_stale_parses()
        return {
            "recovered": result.recovered,
            "document_ids": [str(item) for item in result.document_ids],
        }

    return asyncio.run(_run_with_service(execute))
