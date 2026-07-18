from datetime import date

import pytest
from neo4j import AsyncGraphDatabase
from sqlalchemy import delete

from medreg.core.config import get_settings
from medreg.core.database import async_session_factory
from medreg.modules.knowledge_graph.repository import Neo4jKnowledgeGraphRepository
from medreg.modules.knowledge_graph.schemas import GraphRelationshipType
from medreg.modules.knowledge_graph.service import KnowledgeGraphService
from medreg.modules.knowledge_graph.source import (
    SQLAlchemyKnowledgeGraphProjectionSource,
)
from medreg.modules.regulations.models import RegulationSourceModel
from medreg.modules.regulations.repository import SQLAlchemyRegulationRepository
from medreg.modules.regulations.schemas import (
    RegulationSourceCreate,
    RegulationType,
    RegulationVersionCreate,
    ReviewDecision,
    VersionReviewCreate,
)
from medreg.modules.regulations.service import RegulationService


@pytest.mark.integration
async def test_regulation_projection_survives_neo4j_round_trip() -> None:
    settings = get_settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )
    graph_repository = Neo4jKnowledgeGraphRepository(
        driver,
        database=settings.neo4j_database,
    )
    source_id = None
    try:
        async with async_session_factory() as session:
            regulation_service = RegulationService(
                SQLAlchemyRegulationRepository(session)
            )
            source = await regulation_service.create(
                RegulationSourceCreate(
                    title="医疗器械注册图谱集成测试",
                    issuing_authority="集成测试机关",
                    regulation_type=RegulationType.REGULATION,
                    scope_summary="验证法规版本、适用范围和资料要求图谱投影。",
                    initial_version=RegulationVersionCreate(
                        version_label="2014版",
                        document_number="TEST-GRAPH-OLD",
                        official_url="https://example.gov.cn/graph-old",
                        published_on=date(2014, 7, 30),
                        effective_on=date(2014, 10, 1),
                        expires_on=date(2021, 9, 30),
                    ),
                )
            )
            source_id = source.id
            source = await regulation_service.review_version(
                source.id,
                source.versions[0].id,
                VersionReviewCreate(
                    decision=ReviewDecision.VERIFIED,
                    reviewed_by="集成测试人员",
                    note="已核验旧版测试来源。",
                ),
                date(2026, 7, 18),
            )
            source = await regulation_service.add_version(
                source.id,
                RegulationVersionCreate(
                    version_label="2021版",
                    document_number="TEST-GRAPH-NEW",
                    official_url="https://example.gov.cn/graph-new",
                    published_on=date(2021, 8, 26),
                    effective_on=date(2021, 10, 1),
                ),
                date(2026, 7, 18),
            )
            current = next(
                item for item in source.versions if item.version_label == "2021版"
            )
            await regulation_service.review_version(
                source.id,
                current.id,
                VersionReviewCreate(
                    decision=ReviewDecision.VERIFIED,
                    reviewed_by="集成测试人员",
                    note="已核验新版测试来源。",
                ),
                date(2026, 7, 18),
            )
            graph_service = KnowledgeGraphService(
                SQLAlchemyKnowledgeGraphProjectionSource(session),
                graph_repository,
            )
            synced = await graph_service.sync(source.id)

        restored = await graph_repository.get(source.id)

        assert synced.nodes_written >= 12
        assert synced.relationships_written >= 12
        assert restored is not None
        assert restored.node_count == synced.nodes_written
        assert restored.relationship_count == synced.relationships_written
        relation_types = {
            relationship.relationship_type for relationship in restored.relationships
        }
        assert GraphRelationshipType.SUPERSEDES in relation_types
        assert GraphRelationshipType.APPLIES_TO in relation_types
        assert GraphRelationshipType.REQUIRES in relation_types
        assert all(
            relationship.verified
            for relationship in restored.relationships
            if relationship.relationship_type != GraphRelationshipType.HAS_VERSION
        )
    finally:
        if source_id is not None:
            await graph_repository.delete(source_id)
            async with async_session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(RegulationSourceModel).where(
                        RegulationSourceModel.id == source_id
                    )
                )
                await cleanup_session.commit()
        await driver.close()
