from collections.abc import AsyncIterator

import pytest

from medreg.api.dependencies import (
    get_application_repository,
    get_document_repository,
    get_document_task_dispatcher,
    get_evaluation_repository,
    get_knowledge_graph_projection_source,
    get_knowledge_graph_repository,
    get_object_storage,
    get_official_source_fetcher,
    get_regulation_repository,
    get_security_repository,
)
from medreg.main import app
from medreg.modules.applications.repository import InMemoryApplicationRepository
from medreg.modules.documents.dispatcher import InMemoryDocumentTaskDispatcher
from medreg.modules.documents.fetcher import InMemoryOfficialSourceFetcher
from medreg.modules.documents.parser import ControlledDocumentParser
from medreg.modules.documents.repository import InMemoryDocumentRepository
from medreg.modules.documents.segmenter import LegalDocumentSegmenter
from medreg.modules.documents.service import DocumentService
from medreg.modules.documents.storage import InMemoryObjectStorage
from medreg.modules.evaluation.repository import InMemoryEvaluationRepository
from medreg.modules.knowledge_graph.repository import InMemoryKnowledgeGraphRepository
from medreg.modules.knowledge_graph.source import (
    InMemoryKnowledgeGraphProjectionSource,
)
from medreg.modules.regulations.repository import InMemoryRegulationRepository
from medreg.modules.security.repository import InMemorySecurityRepository

test_repository = InMemoryApplicationRepository()
test_regulation_repository = InMemoryRegulationRepository()
test_document_repository = InMemoryDocumentRepository()
test_object_storage = InMemoryObjectStorage()
test_task_dispatcher = InMemoryDocumentTaskDispatcher()
test_source_fetcher = InMemoryOfficialSourceFetcher()
test_evaluation_repository = InMemoryEvaluationRepository()
test_knowledge_graph_repository = InMemoryKnowledgeGraphRepository()
test_knowledge_graph_source = InMemoryKnowledgeGraphProjectionSource()
test_security_repository = InMemorySecurityRepository()
test_document_service = DocumentService(
    repository=test_document_repository,
    storage=test_object_storage,
    parser=ControlledDocumentParser(),
    segmenter=LegalDocumentSegmenter(),
    dispatcher=test_task_dispatcher,
    fetcher=test_source_fetcher,
    max_upload_bytes=20 * 1024 * 1024,
    parse_stale_after_seconds=300,
)


async def override_application_repository() -> InMemoryApplicationRepository:
    return test_repository


async def override_regulation_repository() -> InMemoryRegulationRepository:
    return test_regulation_repository


async def override_document_repository() -> InMemoryDocumentRepository:
    return test_document_repository


def override_object_storage() -> InMemoryObjectStorage:
    return test_object_storage


def override_task_dispatcher() -> InMemoryDocumentTaskDispatcher:
    return test_task_dispatcher


def override_source_fetcher() -> InMemoryOfficialSourceFetcher:
    return test_source_fetcher


async def override_evaluation_repository() -> InMemoryEvaluationRepository:
    return test_evaluation_repository


async def override_security_repository() -> InMemorySecurityRepository:
    return test_security_repository


def override_knowledge_graph_repository() -> InMemoryKnowledgeGraphRepository:
    return test_knowledge_graph_repository


async def override_knowledge_graph_source() -> InMemoryKnowledgeGraphProjectionSource:
    return test_knowledge_graph_source


app.dependency_overrides[get_application_repository] = override_application_repository
app.dependency_overrides[get_regulation_repository] = override_regulation_repository
app.dependency_overrides[get_document_repository] = override_document_repository
app.dependency_overrides[get_object_storage] = override_object_storage
app.dependency_overrides[get_document_task_dispatcher] = override_task_dispatcher
app.dependency_overrides[get_official_source_fetcher] = override_source_fetcher
app.dependency_overrides[get_evaluation_repository] = override_evaluation_repository
app.dependency_overrides[get_security_repository] = override_security_repository
app.dependency_overrides[
    get_knowledge_graph_repository
] = override_knowledge_graph_repository
app.dependency_overrides[
    get_knowledge_graph_projection_source
] = override_knowledge_graph_source


@pytest.fixture(autouse=True)
async def clear_repository() -> AsyncIterator[None]:
    await test_repository.clear()
    await test_regulation_repository.clear()
    await test_document_repository.clear()
    await test_object_storage.clear()
    test_task_dispatcher.clear()
    test_source_fetcher.clear()
    await test_evaluation_repository.clear()
    await test_security_repository.clear()
    await test_knowledge_graph_repository.clear()
    test_knowledge_graph_source.clear()
    yield
    await test_repository.clear()
    await test_regulation_repository.clear()
    await test_document_repository.clear()
    await test_object_storage.clear()
    test_task_dispatcher.clear()
    test_source_fetcher.clear()
    await test_evaluation_repository.clear()
    await test_security_repository.clear()
    await test_knowledge_graph_repository.clear()
    test_knowledge_graph_source.clear()
