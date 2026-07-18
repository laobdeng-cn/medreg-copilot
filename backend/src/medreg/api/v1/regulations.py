import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from medreg.api.dependencies import (
    RegulationServiceDependency,
    ReviewerActor,
    SecurityServiceDependency,
)
from medreg.modules.regulations.schemas import (
    RegulationSourceCreate,
    RegulationSourceList,
    RegulationSourceRead,
    RegulationVersionCreate,
    VersionReviewCreate,
)
from medreg.modules.regulations.service import (
    RegulationSourceNotFoundError,
    RegulationVersionAlreadyExistsError,
    RegulationVersionNotFoundError,
)

router = APIRouter(tags=["regulation sources"])


@router.get("/regulation-sources", response_model=RegulationSourceList)
async def list_regulation_sources(
    service: RegulationServiceDependency,
    as_of: Annotated[date | None, Query()] = None,
) -> RegulationSourceList:
    return await service.list(as_of or date.today())


@router.post(
    "/regulation-sources",
    response_model=RegulationSourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_regulation_source(
    payload: RegulationSourceCreate,
    service: RegulationServiceDependency,
    actor: ReviewerActor,
    security: SecurityServiceDependency,
) -> RegulationSourceRead:
    source = await service.create(payload)
    await security.record(
        actor,
        action="regulation_source.created",
        resource_type="regulation_source",
        resource_id=source.id,
        request_method="POST",
        request_path="/regulation-sources",
        status_code=status.HTTP_201_CREATED,
        detail={"code": source.code, "title": source.title},
    )
    return source


@router.get("/regulation-sources/{source_id}", response_model=RegulationSourceRead)
async def get_regulation_source(
    source_id: uuid.UUID,
    service: RegulationServiceDependency,
    as_of: Annotated[date | None, Query()] = None,
) -> RegulationSourceRead:
    try:
        return await service.get(source_id, as_of or date.today())
    except RegulationSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Regulation source not found") from exc


@router.post(
    "/regulation-sources/{source_id}/versions",
    response_model=RegulationSourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_regulation_version(
    source_id: uuid.UUID,
    payload: RegulationVersionCreate,
    service: RegulationServiceDependency,
    actor: ReviewerActor,
    security: SecurityServiceDependency,
    as_of: Annotated[date | None, Query()] = None,
) -> RegulationSourceRead:
    try:
        source = await service.add_version(source_id, payload, as_of or date.today())
        version = next(
            item for item in source.versions if item.version_label == payload.version_label
        )
        await security.record(
            actor,
            action="regulation_version.created",
            resource_type="regulation_version",
            resource_id=version.id,
            request_method="POST",
            request_path=f"/regulation-sources/{source_id}/versions",
            status_code=status.HTTP_201_CREATED,
            detail={"version_label": version.version_label},
        )
        return source
    except RegulationSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Regulation source not found") from exc
    except RegulationVersionAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail="A version with this label already exists",
        ) from exc


@router.post(
    "/regulation-sources/{source_id}/versions/{version_id}/review",
    response_model=RegulationSourceRead,
)
async def review_regulation_version(
    source_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: VersionReviewCreate,
    service: RegulationServiceDependency,
    actor: ReviewerActor,
    security: SecurityServiceDependency,
    as_of: Annotated[date | None, Query()] = None,
) -> RegulationSourceRead:
    try:
        source = await service.review_version(
            source_id, version_id, payload, as_of or date.today()
        )
        await security.record(
            actor,
            action="regulation_version.reviewed",
            resource_type="regulation_version",
            resource_id=version_id,
            request_method="POST",
            request_path=(
                f"/regulation-sources/{source_id}/versions/{version_id}/review"
            ),
            status_code=status.HTTP_200_OK,
            detail={"decision": payload.decision.value},
        )
        return source
    except RegulationSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Regulation source not found") from exc
    except RegulationVersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Regulation version not found") from exc
