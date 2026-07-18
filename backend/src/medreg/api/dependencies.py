import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from neo4j import AsyncDriver, AsyncGraphDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from medreg.core.config import get_settings
from medreg.core.database import get_db_session
from medreg.modules.agent.model import (
    DeepSeekDraftModel,
    DeterministicDraftModel,
    DraftModel,
)
from medreg.modules.agent.repository import (
    AgentRepository,
    SQLAlchemyAgentRepository,
)
from medreg.modules.agent.service import AgentService
from medreg.modules.applications.repository import (
    ApplicationRepository,
    SQLAlchemyApplicationRepository,
)
from medreg.modules.applications.service import ApplicationService
from medreg.modules.documents.dispatcher import (
    CeleryDocumentTaskDispatcher,
    DocumentTaskDispatcher,
)
from medreg.modules.documents.fetcher import (
    ControlledOfficialSourceFetcher,
    OfficialSourceFetcher,
)
from medreg.modules.documents.parser import ControlledDocumentParser, DocumentParser
from medreg.modules.documents.repository import (
    DocumentRepository,
    SQLAlchemyDocumentRepository,
)
from medreg.modules.documents.segmenter import LegalDocumentSegmenter
from medreg.modules.documents.service import DocumentService
from medreg.modules.documents.storage import MinioObjectStorage, ObjectStorage
from medreg.modules.evaluation.repository import (
    EvaluationRepository,
    SQLAlchemyEvaluationRepository,
)
from medreg.modules.evaluation.service import EvaluationService
from medreg.modules.knowledge_graph.repository import (
    KnowledgeGraphRepository,
    Neo4jKnowledgeGraphRepository,
)
from medreg.modules.knowledge_graph.service import KnowledgeGraphService
from medreg.modules.knowledge_graph.source import (
    KnowledgeGraphProjectionSource,
    SQLAlchemyKnowledgeGraphProjectionSource,
)
from medreg.modules.regulations.repository import (
    RegulationRepository,
    SQLAlchemyRegulationRepository,
)
from medreg.modules.regulations.service import RegulationService
from medreg.modules.retrieval.dispatcher import (
    CeleryRetrievalTaskDispatcher,
    RetrievalTaskDispatcher,
)
from medreg.modules.retrieval.repository import (
    RetrievalRepository,
    SQLAlchemyRetrievalRepository,
)
from medreg.modules.retrieval.service import RetrievalService
from medreg.modules.retrieval.vector_store import (
    HybridVectorStore,
    QdrantFastEmbedVectorStore,
)
from medreg.modules.security.repository import (
    SecurityRepository,
    SQLAlchemySecurityRepository,
)
from medreg.modules.security.schemas import ActorContext, Permission
from medreg.modules.security.service import (
    PermissionDeniedError,
    SecurityIdentityError,
    SecurityService,
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]

_knowledge_graph_driver: AsyncDriver | None = None


def get_knowledge_graph_driver() -> AsyncDriver:
    global _knowledge_graph_driver
    if _knowledge_graph_driver is None:
        settings = get_settings()
        _knowledge_graph_driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(
                settings.neo4j_user,
                settings.neo4j_password.get_secret_value(),
            ),
        )
    return _knowledge_graph_driver


async def close_knowledge_graph_driver() -> None:
    global _knowledge_graph_driver
    if _knowledge_graph_driver is not None:
        await _knowledge_graph_driver.close()
        _knowledge_graph_driver = None


async def get_security_repository(
    session: DatabaseSession,
) -> SecurityRepository:
    return SQLAlchemySecurityRepository(session)


SecurityRepositoryDependency = Annotated[
    SecurityRepository, Depends(get_security_repository)
]


async def get_security_service(
    repository: SecurityRepositoryDependency,
) -> SecurityService:
    return SecurityService(repository)


SecurityServiceDependency = Annotated[SecurityService, Depends(get_security_service)]


async def get_current_actor(
    service: SecurityServiceDependency,
    tenant_id: Annotated[
        uuid.UUID | None,
        Header(alias="X-Tenant-ID"),
    ] = None,
    user_id: Annotated[
        uuid.UUID | None,
        Header(alias="X-Actor-ID"),
    ] = None,
) -> ActorContext:
    try:
        return await service.resolve_actor(tenant_id=tenant_id, user_id=user_id)
    except SecurityIdentityError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


CurrentActor = Annotated[ActorContext, Depends(get_current_actor)]


def _require_permission(
    actor: ActorContext,
    permission: Permission,
) -> ActorContext:
    try:
        return SecurityService.require(actor, permission)
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


async def require_reader(actor: CurrentActor) -> ActorContext:
    return _require_permission(actor, Permission.READ)


async def require_writer(actor: CurrentActor) -> ActorContext:
    return _require_permission(actor, Permission.WRITE)


async def require_reviewer(actor: CurrentActor) -> ActorContext:
    return _require_permission(actor, Permission.REVIEW)


async def require_admin(actor: CurrentActor) -> ActorContext:
    return _require_permission(actor, Permission.ADMIN)


ReaderActor = Annotated[ActorContext, Depends(require_reader)]
WriterActor = Annotated[ActorContext, Depends(require_writer)]
ReviewerActor = Annotated[ActorContext, Depends(require_reviewer)]
AdminActor = Annotated[ActorContext, Depends(require_admin)]


async def get_application_repository(
    session: DatabaseSession,
    actor: CurrentActor,
) -> ApplicationRepository:
    return SQLAlchemyApplicationRepository(session, tenant_id=actor.tenant_id)


ApplicationRepositoryDependency = Annotated[
    ApplicationRepository, Depends(get_application_repository)
]


async def get_regulation_repository(
    session: DatabaseSession,
) -> RegulationRepository:
    return SQLAlchemyRegulationRepository(session)


RegulationRepositoryDependency = Annotated[
    RegulationRepository, Depends(get_regulation_repository)
]


async def get_regulation_service(
    repository: RegulationRepositoryDependency,
) -> RegulationService:
    return RegulationService(repository)


RegulationServiceDependency = Annotated[
    RegulationService, Depends(get_regulation_service)
]


async def get_knowledge_graph_projection_source(
    session: DatabaseSession,
) -> KnowledgeGraphProjectionSource:
    return SQLAlchemyKnowledgeGraphProjectionSource(session)


KnowledgeGraphProjectionSourceDependency = Annotated[
    KnowledgeGraphProjectionSource,
    Depends(get_knowledge_graph_projection_source),
]


def get_knowledge_graph_repository() -> KnowledgeGraphRepository:
    settings = get_settings()
    return Neo4jKnowledgeGraphRepository(
        get_knowledge_graph_driver(),
        database=settings.neo4j_database,
    )


KnowledgeGraphRepositoryDependency = Annotated[
    KnowledgeGraphRepository,
    Depends(get_knowledge_graph_repository),
]


async def get_knowledge_graph_service(
    source: KnowledgeGraphProjectionSourceDependency,
    repository: KnowledgeGraphRepositoryDependency,
) -> KnowledgeGraphService:
    return KnowledgeGraphService(source, repository)


KnowledgeGraphServiceDependency = Annotated[
    KnowledgeGraphService,
    Depends(get_knowledge_graph_service),
]


async def get_document_repository(
    session: DatabaseSession,
) -> DocumentRepository:
    return SQLAlchemyDocumentRepository(session)


DocumentRepositoryDependency = Annotated[
    DocumentRepository, Depends(get_document_repository)
]


@lru_cache
def get_object_storage() -> ObjectStorage:
    settings = get_settings()
    return MinioObjectStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket_name=settings.minio_bucket,
        secure=settings.minio_secure,
    )


ObjectStorageDependency = Annotated[ObjectStorage, Depends(get_object_storage)]


async def get_application_service(
    repository: ApplicationRepositoryDependency,
    storage: ObjectStorageDependency,
) -> ApplicationService:
    settings = get_settings()
    return ApplicationService(
        repository=repository,
        storage=storage,
        max_upload_bytes=settings.document_max_upload_bytes,
    )


ApplicationServiceDependency = Annotated[
    ApplicationService, Depends(get_application_service)
]


@lru_cache
def get_document_parser() -> DocumentParser:
    return ControlledDocumentParser()


DocumentParserDependency = Annotated[DocumentParser, Depends(get_document_parser)]


@lru_cache
def get_document_segmenter() -> LegalDocumentSegmenter:
    return LegalDocumentSegmenter()


DocumentSegmenterDependency = Annotated[
    LegalDocumentSegmenter, Depends(get_document_segmenter)
]


@lru_cache
def get_document_task_dispatcher() -> DocumentTaskDispatcher:
    return CeleryDocumentTaskDispatcher()


DocumentTaskDispatcherDependency = Annotated[
    DocumentTaskDispatcher, Depends(get_document_task_dispatcher)
]


@lru_cache
def get_official_source_fetcher() -> OfficialSourceFetcher:
    settings = get_settings()
    return ControlledOfficialSourceFetcher(
        allowed_hosts=settings.official_fetch_allowed_hosts,
        timeout_seconds=settings.official_fetch_timeout_seconds,
        max_bytes=settings.document_max_upload_bytes,
    )


OfficialSourceFetcherDependency = Annotated[
    OfficialSourceFetcher, Depends(get_official_source_fetcher)
]


async def get_document_service(
    repository: DocumentRepositoryDependency,
    storage: ObjectStorageDependency,
    parser: DocumentParserDependency,
    segmenter: DocumentSegmenterDependency,
    dispatcher: DocumentTaskDispatcherDependency,
    fetcher: OfficialSourceFetcherDependency,
) -> DocumentService:
    settings = get_settings()
    return DocumentService(
        repository=repository,
        storage=storage,
        parser=parser,
        segmenter=segmenter,
        dispatcher=dispatcher,
        fetcher=fetcher,
        max_upload_bytes=settings.document_max_upload_bytes,
        parse_stale_after_seconds=settings.document_parse_stale_after_seconds,
    )


DocumentServiceDependency = Annotated[DocumentService, Depends(get_document_service)]


async def get_retrieval_repository(
    session: DatabaseSession,
) -> RetrievalRepository:
    return SQLAlchemyRetrievalRepository(session)


RetrievalRepositoryDependency = Annotated[
    RetrievalRepository, Depends(get_retrieval_repository)
]


@lru_cache
def get_hybrid_vector_store() -> HybridVectorStore:
    settings = get_settings()
    return QdrantFastEmbedVectorStore(
        url=settings.qdrant_url,
        collection_name=settings.qdrant_collection,
        dense_model=settings.embedding_dense_model,
        sparse_model=settings.embedding_sparse_model,
        cache_dir=settings.embedding_cache_dir,
        api_key=settings.qdrant_api_key_value,
    )


HybridVectorStoreDependency = Annotated[
    HybridVectorStore, Depends(get_hybrid_vector_store)
]


@lru_cache
def get_retrieval_task_dispatcher() -> RetrievalTaskDispatcher:
    return CeleryRetrievalTaskDispatcher()


RetrievalTaskDispatcherDependency = Annotated[
    RetrievalTaskDispatcher, Depends(get_retrieval_task_dispatcher)
]


async def get_retrieval_service(
    repository: RetrievalRepositoryDependency,
    vector_store: HybridVectorStoreDependency,
    dispatcher: RetrievalTaskDispatcherDependency,
) -> RetrievalService:
    settings = get_settings()
    return RetrievalService(
        repository=repository,
        vector_store=vector_store,
        dispatcher=dispatcher,
        collection_name=settings.qdrant_collection,
        dense_model=settings.embedding_dense_model,
        sparse_model=settings.embedding_sparse_model,
    )


RetrievalServiceDependency = Annotated[
    RetrievalService, Depends(get_retrieval_service)
]


async def get_agent_repository(
    session: DatabaseSession,
    actor: CurrentActor,
) -> AgentRepository:
    return SQLAlchemyAgentRepository(session, tenant_id=actor.tenant_id)


AgentRepositoryDependency = Annotated[
    AgentRepository, Depends(get_agent_repository)
]


@lru_cache
def get_agent_model() -> DraftModel:
    settings = get_settings()
    if settings.deepseek_api_key is None:
        return DeterministicDraftModel()
    return DeepSeekDraftModel(
        api_key=settings.deepseek_api_key.get_secret_value(),
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        timeout_seconds=settings.deepseek_timeout_seconds,
    )


AgentModelDependency = Annotated[DraftModel, Depends(get_agent_model)]


async def get_agent_service(
    repository: AgentRepositoryDependency,
    application_service: ApplicationServiceDependency,
    retrieval_service: RetrievalServiceDependency,
    model: AgentModelDependency,
) -> AgentService:
    return AgentService(
        repository=repository,
        application_service=application_service,
        retrieval_service=retrieval_service,
        model=model,
    )


AgentServiceDependency = Annotated[AgentService, Depends(get_agent_service)]


async def get_evaluation_repository(
    session: DatabaseSession,
) -> EvaluationRepository:
    return SQLAlchemyEvaluationRepository(session)


EvaluationRepositoryDependency = Annotated[
    EvaluationRepository, Depends(get_evaluation_repository)
]


async def get_evaluation_service(
    repository: EvaluationRepositoryDependency,
) -> EvaluationService:
    return EvaluationService(repository)


EvaluationServiceDependency = Annotated[
    EvaluationService, Depends(get_evaluation_service)
]
