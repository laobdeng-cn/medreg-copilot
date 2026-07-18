import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from medreg.api.dependencies import DocumentServiceDependency
from medreg.modules.documents.schemas import (
    DocumentFetchRequestList,
    DocumentFetchRequestRead,
    DocumentStructureRead,
    FetchRequestCreate,
    FetchReviewCreate,
    ParseRecoveryRead,
    RegulationDocumentList,
    RegulationDocumentRead,
)
from medreg.modules.documents.service import (
    DocumentNotFoundError,
    DocumentValidationError,
    DuplicateDocumentError,
    FetchRequestNotFoundError,
    FetchRequestStateError,
    RegulationVersionNotFoundError,
    TaskDispatchError,
)

router = APIRouter(tags=["regulation documents"])


@router.post(
    "/regulation-versions/{version_id}/documents",
    response_model=RegulationDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def archive_regulation_document(
    version_id: uuid.UUID,
    service: DocumentServiceDependency,
    file: Annotated[UploadFile, File()],
    uploaded_by: Annotated[str, Form(min_length=2, max_length=80)],
) -> RegulationDocumentRead:
    data = await file.read(service.max_upload_bytes + 1)
    try:
        return await service.archive(
            version_id=version_id,
            file_name=file.filename or "",
            content_type=file.content_type,
            data=data,
            uploaded_by=uploaded_by,
        )
    except RegulationVersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Regulation version not found") from exc
    except DuplicateDocumentError as exc:
        raise HTTPException(
            status_code=409,
            detail="This exact file is already archived for the regulation version",
        ) from exc
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/regulation-versions/{version_id}/documents",
    response_model=RegulationDocumentList,
)
async def list_regulation_documents(
    version_id: uuid.UUID,
    service: DocumentServiceDependency,
) -> RegulationDocumentList:
    try:
        return await service.list_for_version(version_id)
    except RegulationVersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Regulation version not found") from exc


@router.post(
    "/documents/{document_id}/parse",
    response_model=RegulationDocumentRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def parse_regulation_document(
    document_id: uuid.UUID,
    service: DocumentServiceDependency,
    force: bool = False,
) -> RegulationDocumentRead:
    try:
        return await service.queue_parse(document_id, force=force)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except TaskDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/documents/{document_id}/structure",
    response_model=DocumentStructureRead,
)
async def get_document_structure(
    document_id: uuid.UUID,
    service: DocumentServiceDependency,
) -> DocumentStructureRead:
    try:
        return await service.get_structure(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc


@router.post(
    "/documents/parse/recover",
    response_model=ParseRecoveryRead,
)
async def recover_stale_document_parses(
    service: DocumentServiceDependency,
) -> ParseRecoveryRead:
    try:
        return await service.recover_stale_parses()
    except TaskDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/regulation-versions/{version_id}/fetch-requests",
    response_model=DocumentFetchRequestRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_document_fetch_request(
    version_id: uuid.UUID,
    payload: FetchRequestCreate,
    service: DocumentServiceDependency,
) -> DocumentFetchRequestRead:
    try:
        return await service.create_fetch_request(version_id, payload)
    except RegulationVersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Regulation version not found") from exc
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/regulation-versions/{version_id}/fetch-requests",
    response_model=DocumentFetchRequestList,
)
async def list_document_fetch_requests(
    version_id: uuid.UUID,
    service: DocumentServiceDependency,
) -> DocumentFetchRequestList:
    try:
        return await service.list_fetch_requests(version_id)
    except RegulationVersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Regulation version not found") from exc


@router.post(
    "/document-fetch-requests/{request_id}/review",
    response_model=DocumentFetchRequestRead,
)
async def review_document_fetch_request(
    request_id: uuid.UUID,
    payload: FetchReviewCreate,
    service: DocumentServiceDependency,
) -> DocumentFetchRequestRead:
    try:
        return await service.review_fetch_request(request_id, payload)
    except FetchRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Fetch request not found") from exc
    except FetchRequestStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/document-fetch-requests/{request_id}/retry",
    response_model=DocumentFetchRequestRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_document_fetch_request(
    request_id: uuid.UUID,
    service: DocumentServiceDependency,
) -> DocumentFetchRequestRead:
    try:
        return await service.retry_fetch_request(request_id)
    except FetchRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Fetch request not found") from exc
    except FetchRequestStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
