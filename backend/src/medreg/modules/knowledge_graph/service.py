import uuid
from datetime import UTC, datetime

from medreg.modules.knowledge_graph.repository import KnowledgeGraphRepository
from medreg.modules.knowledge_graph.schemas import (
    KnowledgeGraphProjection,
    KnowledgeGraphSyncResult,
)
from medreg.modules.knowledge_graph.source import KnowledgeGraphProjectionSource


class KnowledgeGraphNotSyncedError(LookupError):
    pass


class KnowledgeGraphService:
    def __init__(
        self,
        source: KnowledgeGraphProjectionSource,
        repository: KnowledgeGraphRepository,
    ) -> None:
        self.source = source
        self.repository = repository

    async def sync(self, source_id: uuid.UUID) -> KnowledgeGraphSyncResult:
        projection = await self.source.build(source_id)
        await self.repository.replace(projection)
        return KnowledgeGraphSyncResult(
            source_id=source_id,
            projection_version=projection.projection_version,
            nodes_written=projection.node_count,
            relationships_written=projection.relationship_count,
            synced_at=datetime.now(UTC),
        )

    async def get(self, source_id: uuid.UUID) -> KnowledgeGraphProjection:
        projection = await self.repository.get(source_id)
        if projection is not None:
            return projection
        await self.source.build(source_id)
        raise KnowledgeGraphNotSyncedError(str(source_id))
