import uuid

from fastapi import APIRouter, HTTPException, status

from medreg.api.dependencies import (
    KnowledgeGraphServiceDependency,
    ReviewerActor,
    SecurityServiceDependency,
)
from medreg.modules.knowledge_graph.repository import KnowledgeGraphUnavailableError
from medreg.modules.knowledge_graph.schemas import (
    KnowledgeGraphProjection,
    KnowledgeGraphSyncResult,
)
from medreg.modules.knowledge_graph.service import KnowledgeGraphNotSyncedError
from medreg.modules.knowledge_graph.source import KnowledgeGraphSourceNotFoundError

router = APIRouter(tags=["regulation knowledge graph"])


@router.get(
    "/regulation-sources/{source_id}/graph",
    response_model=KnowledgeGraphProjection,
)
async def get_regulation_graph(
    source_id: uuid.UUID,
    service: KnowledgeGraphServiceDependency,
) -> KnowledgeGraphProjection:
    try:
        return await service.get(source_id)
    except KnowledgeGraphSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Regulation source not found") from exc
    except KnowledgeGraphNotSyncedError as exc:
        raise HTTPException(
            status_code=409,
            detail="Knowledge graph has not been synchronized",
        ) from exc
    except KnowledgeGraphUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Knowledge graph is unavailable",
        ) from exc


@router.post(
    "/regulation-sources/{source_id}/graph/sync",
    response_model=KnowledgeGraphSyncResult,
)
async def sync_regulation_graph(
    source_id: uuid.UUID,
    service: KnowledgeGraphServiceDependency,
    actor: ReviewerActor,
    security: SecurityServiceDependency,
) -> KnowledgeGraphSyncResult:
    try:
        result = await service.sync(source_id)
        await security.record(
            actor,
            action="knowledge_graph.synced",
            resource_type="regulation_source",
            resource_id=source_id,
            request_method="POST",
            request_path=f"/regulation-sources/{source_id}/graph/sync",
            status_code=status.HTTP_200_OK,
            detail={
                "projection_version": result.projection_version,
                "nodes_written": result.nodes_written,
                "relationships_written": result.relationships_written,
            },
        )
        return result
    except KnowledgeGraphSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Regulation source not found") from exc
    except KnowledgeGraphUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Knowledge graph is unavailable",
        ) from exc
