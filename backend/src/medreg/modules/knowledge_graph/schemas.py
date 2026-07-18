import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class GraphNodeType(StrEnum):
    REGULATION_SOURCE = "regulation_source"
    REGULATION_VERSION = "regulation_version"
    DEVICE_SCOPE = "device_scope"
    DOSSIER_REQUIREMENT = "dossier_requirement"
    LEGAL_CHUNK = "legal_chunk"


class GraphRelationshipType(StrEnum):
    HAS_VERSION = "has_version"
    SUPERSEDES = "supersedes"
    CITES = "cites"
    APPLIES_TO = "applies_to"
    REQUIRES = "requires"
    SUPPORTED_BY = "supported_by"


GraphMetadataValue = str | int | float | bool | None


class KnowledgeGraphNode(BaseModel):
    id: str
    node_type: GraphNodeType
    label: str
    summary: str = ""
    metadata: dict[str, GraphMetadataValue] = Field(default_factory=dict)


class KnowledgeGraphRelationship(BaseModel):
    id: str
    relationship_type: GraphRelationshipType
    source_id: str
    target_id: str
    label: str
    basis: str
    evidence_label: str | None = None
    evidence_excerpt: str | None = None
    verified: bool = False


class KnowledgeGraphProjection(BaseModel):
    source_id: uuid.UUID
    projection_version: str
    generated_at: datetime
    node_count: int
    relationship_count: int
    nodes: list[KnowledgeGraphNode]
    relationships: list[KnowledgeGraphRelationship]


class KnowledgeGraphSyncResult(BaseModel):
    source_id: uuid.UUID
    projection_version: str
    nodes_written: int
    relationships_written: int
    synced_at: datetime
