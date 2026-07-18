from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from medreg.modules.applications.schemas import DOSSIER_CATEGORY_DEFINITIONS
from medreg.modules.documents.models import DocumentChunkModel, RegulationDocumentModel
from medreg.modules.knowledge_graph.schemas import (
    GraphNodeType,
    GraphRelationshipType,
    KnowledgeGraphNode,
    KnowledgeGraphProjection,
    KnowledgeGraphRelationship,
)
from medreg.modules.regulations.models import (
    RegulationSourceModel,
    RegulationVersionModel,
)

PROJECTION_VERSION = "controlled-regulation-graph-v1"
REGISTRATION_TITLE_FRAGMENT = "医疗器械注册"
SUPERVISION_REGULATION_TITLE = "医疗器械监督管理条例"


class KnowledgeGraphSourceNotFoundError(LookupError):
    pass


class KnowledgeGraphProjectionSource(Protocol):
    async def build(self, source_id: uuid.UUID) -> KnowledgeGraphProjection: ...


class InMemoryKnowledgeGraphProjectionSource:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, KnowledgeGraphProjection] = {}

    def set(self, projection: KnowledgeGraphProjection) -> None:
        self._items[projection.source_id] = projection.model_copy(deep=True)

    async def build(self, source_id: uuid.UUID) -> KnowledgeGraphProjection:
        projection = self._items.get(source_id)
        if projection is None:
            raise KnowledgeGraphSourceNotFoundError(str(source_id))
        return projection.model_copy(deep=True)

    def clear(self) -> None:
        self._items.clear()


class SQLAlchemyKnowledgeGraphProjectionSource:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build(self, source_id: uuid.UUID) -> KnowledgeGraphProjection:
        source = await self.session.scalar(
            select(RegulationSourceModel)
            .options(selectinload(RegulationSourceModel.versions))
            .where(RegulationSourceModel.id == source_id)
        )
        if source is None:
            raise KnowledgeGraphSourceNotFoundError(str(source_id))
        related_sources = (
            await self.session.scalars(
                select(RegulationSourceModel).options(
                    selectinload(RegulationSourceModel.versions)
                )
            )
        ).unique().all()
        chunk_rows = (
            await self.session.execute(
                select(DocumentChunkModel, RegulationDocumentModel)
                .join(
                    RegulationDocumentModel,
                    RegulationDocumentModel.id == DocumentChunkModel.document_id,
                )
                .join(
                    RegulationVersionModel,
                    RegulationVersionModel.id
                    == RegulationDocumentModel.regulation_version_id,
                )
                .where(RegulationVersionModel.source_id == source_id)
            )
        ).all()
        return self._assemble(source, related_sources, chunk_rows)

    def _assemble(
        self,
        source: RegulationSourceModel,
        related_sources: list[RegulationSourceModel],
        chunk_rows: list[tuple[DocumentChunkModel, RegulationDocumentModel]],
    ) -> KnowledgeGraphProjection:
        nodes: dict[str, KnowledgeGraphNode] = {}
        relationships: list[KnowledgeGraphRelationship] = []
        source_node_id = f"regulation-source:{source.id}"
        nodes[source_node_id] = KnowledgeGraphNode(
            id=source_node_id,
            node_type=GraphNodeType.REGULATION_SOURCE,
            label=source.title,
            summary=source.scope_summary,
            metadata={
                "code": source.code,
                "issuing_authority": source.issuing_authority,
                "jurisdiction": source.jurisdiction,
            },
        )
        versions = sorted(source.versions, key=lambda item: item.effective_on)
        for version in versions:
            version_node_id = f"regulation-version:{version.id}"
            nodes[version_node_id] = KnowledgeGraphNode(
                id=version_node_id,
                node_type=GraphNodeType.REGULATION_VERSION,
                label=f"{version.version_label} · {version.document_number}",
                summary=f"自 {version.effective_on.isoformat()} 起生效",
                metadata={
                    "document_number": version.document_number,
                    "effective_on": version.effective_on.isoformat(),
                    "expires_on": (
                        version.expires_on.isoformat() if version.expires_on else None
                    ),
                    "review_status": version.review_status,
                },
            )
            relationships.append(
                self._relationship(
                    GraphRelationshipType.HAS_VERSION,
                    source_node_id,
                    version_node_id,
                    "包含版本",
                    "法规来源与已登记版本的受控主数据关系",
                    verified=version.review_status == "verified",
                )
            )
        for older, newer in zip(versions, versions[1:], strict=False):
            relationships.append(
                self._relationship(
                    GraphRelationshipType.SUPERSEDES,
                    f"regulation-version:{newer.id}",
                    f"regulation-version:{older.id}",
                    "替代旧版",
                    "按法规生效日期及废止日期生成的版本链",
                    verified=(
                        older.review_status == "verified"
                        and newer.review_status == "verified"
                    ),
                )
            )
        verified_versions = [item for item in versions if item.review_status == "verified"]
        current = verified_versions[-1] if verified_versions else versions[-1]
        current_id = f"regulation-version:{current.id}"

        if REGISTRATION_TITLE_FRAGMENT in source.title:
            for device_class, label in (("II", "第二类医疗器械"), ("III", "第三类医疗器械")):
                scope_id = f"device-scope:CN_NMPA:{device_class}"
                nodes[scope_id] = KnowledgeGraphNode(
                    id=scope_id,
                    node_type=GraphNodeType.DEVICE_SCOPE,
                    label=label,
                    summary="境内首次注册申报",
                    metadata={"jurisdiction": "CN_NMPA", "device_class": device_class},
                )
                relationships.append(
                    self._relationship(
                        GraphRelationshipType.APPLIES_TO,
                        current_id,
                        scope_id,
                        "适用于",
                        "受控产品范围规则 controlled-scope-v1",
                        verified=current.review_status == "verified",
                    )
                )

            requirement_chunk = self._find_chunk(chunk_rows, "第五十二条")
            if requirement_chunk is not None:
                chunk, document = requirement_chunk
                self._add_chunk_node(nodes, chunk, document)
            for definition in DOSSIER_CATEGORY_DEFINITIONS:
                requirement_id = f"dossier-requirement:{definition.key.value}"
                nodes[requirement_id] = KnowledgeGraphNode(
                    id=requirement_id,
                    node_type=GraphNodeType.DOSSIER_REQUIREMENT,
                    label=definition.title,
                    summary=definition.description,
                    metadata={
                        "category_key": definition.key.value,
                        "regulatory_basis": definition.regulatory_basis,
                    },
                )
                relationships.append(
                    self._relationship(
                        GraphRelationshipType.REQUIRES,
                        current_id,
                        requirement_id,
                        "要求提交",
                        definition.regulatory_basis,
                        evidence_label=(
                            requirement_chunk[0].citation_label
                            if requirement_chunk is not None
                            else None
                        ),
                        evidence_excerpt=(
                            self._excerpt(requirement_chunk[0].content)
                            if requirement_chunk is not None
                            else None
                        ),
                        verified=current.review_status == "verified",
                    )
                )
                if requirement_chunk is not None:
                    relationships.append(
                        self._relationship(
                            GraphRelationshipType.SUPPORTED_BY,
                            requirement_id,
                            f"legal-chunk:{requirement_chunk[0].id}",
                            "证据条款",
                            definition.regulatory_basis,
                            evidence_label=requirement_chunk[0].citation_label,
                            evidence_excerpt=self._excerpt(
                                requirement_chunk[0].content
                            ),
                            verified=current.review_status == "verified",
                        )
                    )

            supervision_source = next(
                (
                    item
                    for item in related_sources
                    if item.title == SUPERVISION_REGULATION_TITLE
                ),
                None,
            )
            if supervision_source is not None:
                target_id = f"regulation-source:{supervision_source.id}"
                nodes[target_id] = KnowledgeGraphNode(
                    id=target_id,
                    node_type=GraphNodeType.REGULATION_SOURCE,
                    label=supervision_source.title,
                    summary=supervision_source.scope_summary,
                    metadata={
                        "code": supervision_source.code,
                        "issuing_authority": supervision_source.issuing_authority,
                        "jurisdiction": supervision_source.jurisdiction,
                    },
                )
                citation_chunk = self._find_chunk(
                    chunk_rows,
                    SUPERVISION_REGULATION_TITLE,
                    citation_hint="第一条",
                )
                if citation_chunk is not None:
                    self._add_chunk_node(nodes, citation_chunk[0], citation_chunk[1])
                relationships.append(
                    self._relationship(
                        GraphRelationshipType.CITES,
                        current_id,
                        target_id,
                        "制定依据",
                        "《医疗器械注册与备案管理办法》第一条",
                        evidence_label=(
                            citation_chunk[0].citation_label
                            if citation_chunk is not None
                            else "第一条"
                        ),
                        evidence_excerpt=(
                            self._excerpt(citation_chunk[0].content)
                            if citation_chunk is not None
                            else None
                        ),
                        verified=current.review_status == "verified",
                    )
                )

        ordered_nodes = sorted(nodes.values(), key=lambda item: (item.node_type, item.label))
        ordered_relationships = sorted(
            relationships,
            key=lambda item: (item.relationship_type, item.source_id, item.target_id),
        )
        return KnowledgeGraphProjection(
            source_id=source.id,
            projection_version=PROJECTION_VERSION,
            generated_at=datetime.now(UTC),
            node_count=len(ordered_nodes),
            relationship_count=len(ordered_relationships),
            nodes=ordered_nodes,
            relationships=ordered_relationships,
        )

    @staticmethod
    def _find_chunk(
        rows: list[tuple[DocumentChunkModel, RegulationDocumentModel]],
        needle: str,
        citation_hint: str | None = None,
    ) -> tuple[DocumentChunkModel, RegulationDocumentModel] | None:
        candidates = [
            row
            for row in rows
            if needle in row[0].citation_label or needle in row[0].content
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda row: (
                bool(citation_hint and citation_hint in row[0].citation_label),
                needle in row[0].citation_label,
                row[1].file_name.endswith((".html", ".htm")),
                len(row[0].content),
            ),
        )

    @staticmethod
    def _add_chunk_node(
        nodes: dict[str, KnowledgeGraphNode],
        chunk: DocumentChunkModel,
        document: RegulationDocumentModel,
    ) -> None:
        node_id = f"legal-chunk:{chunk.id}"
        nodes[node_id] = KnowledgeGraphNode(
            id=node_id,
            node_type=GraphNodeType.LEGAL_CHUNK,
            label=chunk.citation_label,
            summary=SQLAlchemyKnowledgeGraphProjectionSource._excerpt(chunk.content),
            metadata={
                "document_id": str(document.id),
                "file_name": document.file_name,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "content_hash": chunk.content_hash,
            },
        )

    @staticmethod
    def _excerpt(content: str, limit: int = 220) -> str:
        normalized = " ".join(content.split())
        return normalized if len(normalized) <= limit else f"{normalized[:limit]}..."

    @staticmethod
    def _relationship(
        relationship_type: GraphRelationshipType,
        source_id: str,
        target_id: str,
        label: str,
        basis: str,
        *,
        evidence_label: str | None = None,
        evidence_excerpt: str | None = None,
        verified: bool = False,
    ) -> KnowledgeGraphRelationship:
        digest = hashlib.sha256(
            f"{relationship_type.value}|{source_id}|{target_id}".encode()
        ).hexdigest()[:24]
        return KnowledgeGraphRelationship(
            id=f"relation:{digest}",
            relationship_type=relationship_type,
            source_id=source_id,
            target_id=target_id,
            label=label,
            basis=basis,
            evidence_label=evidence_label,
            evidence_excerpt=evidence_excerpt,
            verified=verified,
        )
