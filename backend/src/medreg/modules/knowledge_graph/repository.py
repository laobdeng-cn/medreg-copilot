from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Protocol

from neo4j import AsyncDriver, AsyncManagedTransaction
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from medreg.modules.knowledge_graph.schemas import (
    GraphNodeType,
    GraphRelationshipType,
    KnowledgeGraphNode,
    KnowledgeGraphProjection,
    KnowledgeGraphRelationship,
)


class KnowledgeGraphUnavailableError(ConnectionError):
    pass


class KnowledgeGraphRepository(Protocol):
    async def replace(self, projection: KnowledgeGraphProjection) -> None: ...

    async def get(self, source_id: uuid.UUID) -> KnowledgeGraphProjection | None: ...

    async def delete(self, source_id: uuid.UUID) -> None: ...

    async def ready(self) -> None: ...


class InMemoryKnowledgeGraphRepository:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, KnowledgeGraphProjection] = {}
        self._lock = asyncio.Lock()

    async def replace(self, projection: KnowledgeGraphProjection) -> None:
        async with self._lock:
            self._items[projection.source_id] = projection.model_copy(deep=True)

    async def get(self, source_id: uuid.UUID) -> KnowledgeGraphProjection | None:
        async with self._lock:
            projection = self._items.get(source_id)
        return projection.model_copy(deep=True) if projection is not None else None

    async def delete(self, source_id: uuid.UUID) -> None:
        async with self._lock:
            self._items.pop(source_id, None)

    async def ready(self) -> None:
        return None

    async def clear(self) -> None:
        async with self._lock:
            self._items.clear()


class Neo4jKnowledgeGraphRepository:
    def __init__(self, driver: AsyncDriver, database: str = "neo4j") -> None:
        self.driver = driver
        self.database = database
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()

    async def replace(self, projection: KnowledgeGraphProjection) -> None:
        try:
            await self._ensure_schema()
            async with self.driver.session(database=self.database) as session:
                await session.execute_write(self._replace_projection, projection)
        except (Neo4jError, ServiceUnavailable) as exc:
            raise KnowledgeGraphUnavailableError("Knowledge graph is unavailable") from exc

    async def get(self, source_id: uuid.UUID) -> KnowledgeGraphProjection | None:
        source_value = str(source_id)
        try:
            node_records, _, _ = await self.driver.execute_query(
                """
                MATCH (n:KnowledgeNode {graph_source_id: $source_id})
                RETURN n
                ORDER BY n.node_type, n.label
                """,
                parameters_={"source_id": source_value},
                database_=self.database,
            )
            if not node_records:
                return None
            relationship_records, _, _ = await self.driver.execute_query(
                """
                MATCH (a:KnowledgeNode {graph_source_id: $source_id})
                      -[r:KNOWLEDGE_RELATION]->
                      (b:KnowledgeNode {graph_source_id: $source_id})
                RETURN a.canonical_id AS source_id,
                       b.canonical_id AS target_id,
                       r
                ORDER BY r.relationship_type, r.label
                """,
                parameters_={"source_id": source_value},
                database_=self.database,
            )
        except (Neo4jError, ServiceUnavailable) as exc:
            raise KnowledgeGraphUnavailableError("Knowledge graph is unavailable") from exc

        nodes: list[KnowledgeGraphNode] = []
        for record in node_records:
            properties = dict(record["n"])
            nodes.append(
                KnowledgeGraphNode(
                    id=properties["canonical_id"],
                    node_type=GraphNodeType(properties["node_type"]),
                    label=properties["label"],
                    summary=properties.get("summary", ""),
                    metadata=json.loads(properties.get("metadata_json", "{}")),
                )
            )
        relationships: list[KnowledgeGraphRelationship] = []
        for record in relationship_records:
            properties = dict(record["r"])
            relationships.append(
                KnowledgeGraphRelationship(
                    id=properties["id"],
                    relationship_type=GraphRelationshipType(
                        properties["relationship_type"]
                    ),
                    source_id=record["source_id"],
                    target_id=record["target_id"],
                    label=properties["label"],
                    basis=properties["basis"],
                    evidence_label=properties.get("evidence_label"),
                    evidence_excerpt=properties.get("evidence_excerpt"),
                    verified=properties.get("verified", False),
                )
            )
        first = dict(node_records[0]["n"])
        generated_at = datetime.fromisoformat(first["generated_at"])
        return KnowledgeGraphProjection(
            source_id=source_id,
            projection_version=first["projection_version"],
            generated_at=generated_at,
            node_count=len(nodes),
            relationship_count=len(relationships),
            nodes=nodes,
            relationships=relationships,
        )

    async def delete(self, source_id: uuid.UUID) -> None:
        try:
            await self.driver.execute_query(
                """
                MATCH (n:KnowledgeNode {graph_source_id: $source_id})
                DETACH DELETE n
                """,
                parameters_={"source_id": str(source_id)},
                database_=self.database,
            )
        except (Neo4jError, ServiceUnavailable) as exc:
            raise KnowledgeGraphUnavailableError("Knowledge graph is unavailable") from exc

    async def ready(self) -> None:
        try:
            await self.driver.verify_connectivity()
        except (Neo4jError, ServiceUnavailable) as exc:
            raise KnowledgeGraphUnavailableError("Knowledge graph is unavailable") from exc

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return
            await self.driver.execute_query(
                """
                CREATE CONSTRAINT knowledge_projection_key IF NOT EXISTS
                FOR (n:KnowledgeNode) REQUIRE n.projection_key IS UNIQUE
                """,
                database_=self.database,
            )
            self._schema_ready = True

    @staticmethod
    async def _replace_projection(
        transaction: AsyncManagedTransaction,
        projection: KnowledgeGraphProjection,
    ) -> None:
        source_id = str(projection.source_id)
        deleted = await transaction.run(
            """
            MATCH (n:KnowledgeNode {graph_source_id: $source_id})
            DETACH DELETE n
            """,
            source_id=source_id,
        )
        await deleted.consume()
        generated_at = projection.generated_at.astimezone(UTC).isoformat()
        node_rows = [
            {
                "projection_key": f"{source_id}:{node.id}",
                "canonical_id": node.id,
                "graph_source_id": source_id,
                "node_type": node.node_type.value,
                "label": node.label,
                "summary": node.summary,
                "metadata_json": json.dumps(node.metadata, ensure_ascii=False),
                "projection_version": projection.projection_version,
                "generated_at": generated_at,
            }
            for node in projection.nodes
        ]
        created_nodes = await transaction.run(
            """
            UNWIND $rows AS row
            CREATE (n:KnowledgeNode)
            SET n = row
            """,
            rows=node_rows,
        )
        await created_nodes.consume()
        relationship_rows = [
            {
                "id": relationship.id,
                "source_key": f"{source_id}:{relationship.source_id}",
                "target_key": f"{source_id}:{relationship.target_id}",
                "relationship_type": relationship.relationship_type.value,
                "label": relationship.label,
                "basis": relationship.basis,
                "evidence_label": relationship.evidence_label,
                "evidence_excerpt": relationship.evidence_excerpt,
                "verified": relationship.verified,
            }
            for relationship in projection.relationships
        ]
        created_relationships = await transaction.run(
            """
            UNWIND $rows AS row
            MATCH (a:KnowledgeNode {projection_key: row.source_key})
            MATCH (b:KnowledgeNode {projection_key: row.target_key})
            CREATE (a)-[r:KNOWLEDGE_RELATION]->(b)
            SET r = row
            """,
            rows=relationship_rows,
        )
        await created_relationships.consume()
