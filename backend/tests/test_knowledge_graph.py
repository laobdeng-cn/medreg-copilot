import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from conftest import test_knowledge_graph_source, test_security_repository
from fastapi.testclient import TestClient

from medreg.main import app
from medreg.modules.knowledge_graph.schemas import (
    GraphNodeType,
    GraphRelationshipType,
    KnowledgeGraphNode,
    KnowledgeGraphProjection,
    KnowledgeGraphRelationship,
)
from medreg.modules.knowledge_graph.source import (
    SQLAlchemyKnowledgeGraphProjectionSource,
)

client = TestClient(app)


def build_projection(source_id: uuid.UUID) -> KnowledgeGraphProjection:
    source_node = f"regulation-source:{source_id}"
    version_node = f"regulation-version:{uuid.uuid4()}"
    relationship = KnowledgeGraphRelationship(
        id="relation:test-has-version",
        relationship_type=GraphRelationshipType.HAS_VERSION,
        source_id=source_node,
        target_id=version_node,
        label="包含版本",
        basis="测试受控关系",
        verified=True,
    )
    return KnowledgeGraphProjection(
        source_id=source_id,
        projection_version="controlled-regulation-graph-v1",
        generated_at=datetime.now(UTC),
        node_count=2,
        relationship_count=1,
        nodes=[
            KnowledgeGraphNode(
                id=source_node,
                node_type=GraphNodeType.REGULATION_SOURCE,
                label="测试法规",
            ),
            KnowledgeGraphNode(
                id=version_node,
                node_type=GraphNodeType.REGULATION_VERSION,
                label="测试版",
            ),
        ],
        relationships=[relationship],
    )


def test_graph_sync_persists_projection_and_audit_event() -> None:
    source_id = uuid.uuid4()
    test_knowledge_graph_source.set(build_projection(source_id))

    synced = client.post(f"/api/v1/regulation-sources/{source_id}/graph/sync")
    restored = client.get(f"/api/v1/regulation-sources/{source_id}/graph")

    assert synced.status_code == 200
    assert synced.json()["nodes_written"] == 2
    assert synced.json()["relationships_written"] == 1
    assert restored.status_code == 200
    assert restored.json()["node_count"] == 2
    assert restored.json()["relationships"][0]["relationship_type"] == "has_version"
    events = test_security_repository._events
    assert events[-1].action == "knowledge_graph.synced"


def test_graph_unknown_source_returns_not_found() -> None:
    response = client.post(
        f"/api/v1/regulation-sources/{uuid.uuid4()}/graph/sync"
    )

    assert response.status_code == 404


def test_graph_evidence_selection_prefers_requested_citation_path() -> None:
    needle = "医疗器械监督管理条例"
    rows = [
        (
            SimpleNamespace(
                citation_label="第二章 基本要求 / 第十四条",
                content=f"较长的代理人义务说明，引用《{needle}》。" * 8,
            ),
            SimpleNamespace(file_name="regulation.html"),
        ),
        (
            SimpleNamespace(
                citation_label="第一章 总则 / 第一条",
                content=f"根据《{needle}》，制定本办法。",
            ),
            SimpleNamespace(file_name="regulation.html"),
        ),
    ]

    selected = SQLAlchemyKnowledgeGraphProjectionSource._find_chunk(
        rows,
        needle,
        citation_hint="第一条",
    )

    assert selected is not None
    assert selected[0].citation_label.endswith("第一条")
