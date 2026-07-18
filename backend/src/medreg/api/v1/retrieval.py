import uuid

from fastapi import APIRouter, HTTPException, Query, status

from medreg.api.dependencies import RetrievalServiceDependency
from medreg.modules.retrieval.schemas import (
    HybridSearchRequest,
    HybridSearchResponse,
    VectorIndexRead,
)
from medreg.modules.retrieval.service import (
    RetrievalDocumentNotReadyError,
    VectorIndexingError,
)

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.get("/documents/{document_id}/index", response_model=VectorIndexRead)
async def get_document_index(
    document_id: uuid.UUID,
    service: RetrievalServiceDependency,
) -> VectorIndexRead:
    try:
        return await service.get_index_status(document_id)
    except RetrievalDocumentNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/documents/{document_id}/index",
    response_model=VectorIndexRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def index_document(
    document_id: uuid.UUID,
    service: RetrievalServiceDependency,
    force: bool = Query(default=False),
) -> VectorIndexRead:
    try:
        return await service.queue_index(document_id, force=force)
    except RetrievalDocumentNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except VectorIndexingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.post("/search", response_model=HybridSearchResponse)
async def hybrid_search(
    payload: HybridSearchRequest,
    service: RetrievalServiceDependency,
) -> HybridSearchResponse:
    try:
        return await service.search(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Hybrid retrieval is unavailable: {exc}",
        ) from exc
