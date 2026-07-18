#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import uuid
from datetime import date
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from neo4j import AsyncGraphDatabase

from medreg.core.config import get_settings
from medreg.core.database import async_session_factory
from medreg.modules.agent.model import DeterministicDraftModel
from medreg.modules.agent.repository import SQLAlchemyAgentRepository
from medreg.modules.agent.schemas import (
    AgentDraftRunCreate,
    DraftLanguageMode,
    DraftSection,
)
from medreg.modules.agent.service import AgentService
from medreg.modules.applications.repository import SQLAlchemyApplicationRepository
from medreg.modules.applications.schemas import (
    DossierCategory,
    PrecheckCreate,
    RegistrationApplicationCreate,
    RequirementReviewCreate,
    RequirementReviewDecision,
    RequirementStatus,
)
from medreg.modules.applications.service import ApplicationService
from medreg.modules.documents.dispatcher import InMemoryDocumentTaskDispatcher
from medreg.modules.documents.fetcher import InMemoryOfficialSourceFetcher
from medreg.modules.documents.parser import ControlledDocumentParser
from medreg.modules.documents.repository import SQLAlchemyDocumentRepository
from medreg.modules.documents.schemas import ParseStatus
from medreg.modules.documents.segmenter import LegalDocumentSegmenter
from medreg.modules.documents.service import DocumentService
from medreg.modules.documents.storage import MinioObjectStorage
from medreg.modules.evaluation.repository import SQLAlchemyEvaluationRepository
from medreg.modules.evaluation.schemas import EvaluationRunCreate
from medreg.modules.evaluation.service import EvaluationService
from medreg.modules.knowledge_graph.repository import Neo4jKnowledgeGraphRepository
from medreg.modules.knowledge_graph.service import KnowledgeGraphService
from medreg.modules.knowledge_graph.source import (
    SQLAlchemyKnowledgeGraphProjectionSource,
)
from medreg.modules.regulations.repository import SQLAlchemyRegulationRepository
from medreg.modules.regulations.schemas import (
    RegulationSourceCreate,
    RegulationVersionCreate,
    ReviewStatus,
    VersionReviewCreate,
)
from medreg.modules.regulations.service import RegulationService
from medreg.modules.retrieval.repository import SQLAlchemyRetrievalRepository
from medreg.modules.retrieval.schemas import VectorIndexStatus
from medreg.modules.retrieval.service import RetrievalService
from medreg.modules.retrieval.vector_store import QdrantFastEmbedVectorStore
from medreg.modules.security.repository import SQLAlchemySecurityRepository
from medreg.modules.security.service import SecurityService

ROOT = Path(__file__).resolve().parents[1]
DEMO_PRODUCT_NAME = "便携式心电记录仪"
DEMO_REGULATION_TITLE = "医疗器械注册与备案管理办法"
DEMO_SUPERVISION_REGULATION_TITLE = "医疗器械监督管理条例"


class DirectRetrievalDispatcher:
    def enqueue_index(self, document_id: uuid.UUID, task_id: str) -> None:
        return None


def object_storage() -> MinioObjectStorage:
    settings = get_settings()
    return MinioObjectStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket_name=settings.minio_bucket,
        secure=settings.minio_secure,
    )


def build_demo_xlsx() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "申报资料矩阵"
    worksheet.append(["资料类别", "当前状态", "责任角色", "法规依据"])
    worksheet.append(
        [
            "产品风险分析资料",
            "已接受",
            "法规专员",
            "第47号令第五十二条（一）",
        ]
    )
    worksheet.append(
        [
            "产品技术要求",
            "已接受",
            "研发工程师",
            "第47号令第五十二条（二）",
        ]
    )
    worksheet.append(
        [
            "产品检验报告",
            "待补充",
            "质量工程师",
            "第47号令第五十二条（三）",
        ]
    )
    worksheet.append(
        [
            "临床评价资料",
            "待补充",
            "临床评价专员",
            "第47号令第五十二条（四）",
        ]
    )
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


async def ensure_regulation_and_retrieval(
    session,
) -> tuple[RetrievalService, uuid.UUID]:
    settings = get_settings()
    regulation_service = RegulationService(SQLAlchemyRegulationRepository(session))
    sources = await regulation_service.list(date(2026, 7, 18))
    source = next(
        (item for item in sources.items if item.title == DEMO_REGULATION_TITLE),
        None,
    )
    if source is None:
        source = await regulation_service.create(
            RegulationSourceCreate(
                title=DEMO_REGULATION_TITLE,
                issuing_authority="国家市场监督管理总局",
                jurisdiction="CN",
                regulation_type="regulation",
                scope_summary="医疗器械注册、备案及监督管理的演示法规基线。",
                initial_version=RegulationVersionCreate(
                    version_label="2021版",
                    document_number="国家市场监督管理总局令第47号",
                    official_url=(
                        "https://gkml.samr.gov.cn/nsjg/fgs/202108/"
                        "t20210831_334228.html"
                    ),
                    published_on=date(2021, 8, 26),
                    effective_on=date(2021, 10, 1),
                ),
            )
        )
    version = next(
        item
        for item in source.versions
        if item.document_number == "国家市场监督管理总局令第47号"
    )
    if version.review_status != ReviewStatus.VERIFIED:
        source = await regulation_service.review_version(
            source.id,
            version.id,
            VersionReviewCreate(
                decision="verified",
                reviewed_by="演示法规负责人",
                note="固定演示版本，已核对文号与生效日期。",
            ),
            date(2026, 7, 18),
        )
        version = next(item for item in source.versions if item.id == version.id)

    legacy_version = next(
        (item for item in source.versions if item.version_label == "2014版"),
        None,
    )
    if legacy_version is None:
        source = await regulation_service.add_version(
            source.id,
            RegulationVersionCreate(
                version_label="2014版",
                document_number="原国家食品药品监督管理总局令第4号",
                official_url=(
                    "https://english.nmpa.gov.cn/2019-07/25/c_390617.htm"
                ),
                published_on=date(2014, 7, 30),
                effective_on=date(2014, 10, 1),
                expires_on=date(2021, 9, 30),
            ),
            date(2026, 7, 18),
        )
        legacy_version = next(
            item for item in source.versions if item.version_label == "2014版"
        )
    if legacy_version.review_status != ReviewStatus.VERIFIED:
        source = await regulation_service.review_version(
            source.id,
            legacy_version.id,
            VersionReviewCreate(
                decision="verified",
                reviewed_by="演示法规负责人",
                note="第47号令第一百二十四条明确该版本同时废止。",
            ),
            date(2026, 7, 18),
        )

    supervision_source = next(
        (
            item
            for item in sources.items
            if item.title == DEMO_SUPERVISION_REGULATION_TITLE
        ),
        None,
    )
    if supervision_source is None:
        supervision_source = await regulation_service.create(
            RegulationSourceCreate(
                title=DEMO_SUPERVISION_REGULATION_TITLE,
                issuing_authority="国务院",
                jurisdiction="CN",
                regulation_type="regulation",
                scope_summary="医疗器械研制、生产、经营、使用及监督管理的上位法规。",
                initial_version=RegulationVersionCreate(
                    version_label="2024修订版",
                    document_number="国务院令第739号（依据第797号令修订）",
                    official_url=(
                        "https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/fgs/"
                        "art/2023/art_70607fc4160041a383e68ff6bfb2826f.html"
                    ),
                    published_on=date(2024, 12, 6),
                    effective_on=date(2025, 1, 20),
                ),
            )
        )
    supervision_version = supervision_source.versions[0]
    if supervision_version.review_status != ReviewStatus.VERIFIED:
        await regulation_service.review_version(
            supervision_source.id,
            supervision_version.id,
            VersionReviewCreate(
                decision="verified",
                reviewed_by="演示法规负责人",
                note="已核验国务院令第739号及第797号令修订信息。",
            ),
            date(2026, 7, 18),
        )

    document_service = DocumentService(
        repository=SQLAlchemyDocumentRepository(session),
        storage=object_storage(),
        parser=ControlledDocumentParser(),
        segmenter=LegalDocumentSegmenter(),
        dispatcher=InMemoryDocumentTaskDispatcher(),
        fetcher=InMemoryOfficialSourceFetcher(),
        max_upload_bytes=settings.document_max_upload_bytes,
        parse_stale_after_seconds=settings.document_parse_stale_after_seconds,
    )
    documents = await document_service.list_for_version(version.id)
    document = next(
        (item for item in documents.items if item.file_name == "samr-order-47-demo.md"),
        None,
    )
    if document is None:
        data = (ROOT / "samples" / "samr-order-47-demo.md").read_bytes()
        document = await document_service.archive(
            version_id=version.id,
            file_name="samr-order-47-demo.md",
            content_type="text/markdown",
            data=data,
            uploaded_by="演示数据脚本",
        )
    if document.parse_status != ParseStatus.COMPLETED:
        queued = await document_service.queue_parse(document.id)
        document = await document_service.execute_parse(document.id, queued.parse_task_id)

    documents = await document_service.list_for_version(version.id)
    matrix_document = next(
        (
            item
            for item in documents.items
            if item.file_name == "device-dossier-checklist.xlsx"
        ),
        None,
    )
    if matrix_document is None:
        matrix_document = await document_service.archive(
            version_id=version.id,
            file_name="device-dossier-checklist.xlsx",
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            data=build_demo_xlsx(),
            uploaded_by="演示数据脚本",
        )
    if matrix_document.parse_status != ParseStatus.COMPLETED:
        queued = await document_service.queue_parse(matrix_document.id)
        matrix_document = await document_service.execute_parse(
            matrix_document.id, queued.parse_task_id
        )

    retrieval_service = RetrievalService(
        repository=SQLAlchemyRetrievalRepository(session),
        vector_store=QdrantFastEmbedVectorStore(
            url=settings.qdrant_url,
            collection_name=settings.qdrant_collection,
            dense_model=settings.embedding_dense_model,
            sparse_model=settings.embedding_sparse_model,
            cache_dir=settings.embedding_cache_dir,
            api_key=settings.qdrant_api_key_value,
        ),
        dispatcher=DirectRetrievalDispatcher(),
        collection_name=settings.qdrant_collection,
        dense_model=settings.embedding_dense_model,
        sparse_model=settings.embedding_sparse_model,
    )
    for current_document in (document, matrix_document):
        index = await retrieval_service.get_index_status(current_document.id)
        if index.status != VectorIndexStatus.COMPLETED:
            queued_index = await retrieval_service.queue_index(current_document.id)
            await retrieval_service.execute_index(
                current_document.id, queued_index.task_id
            )
    return retrieval_service, source.id


async def ensure_knowledge_graph(session, source_id: uuid.UUID) -> None:
    settings = get_settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )
    try:
        await KnowledgeGraphService(
            SQLAlchemyKnowledgeGraphProjectionSource(session),
            Neo4jKnowledgeGraphRepository(driver, database=settings.neo4j_database),
        ).sync(source_id)
    finally:
        await driver.close()


async def ensure_application(
    session, retrieval_service: RetrievalService
) -> uuid.UUID:
    storage = object_storage()
    application_service = ApplicationService(
        SQLAlchemyApplicationRepository(session),
        storage=storage,
    )
    applications = await application_service.list()
    application = next(
        (item for item in applications.items if item.product_name == DEMO_PRODUCT_NAME),
        None,
    )
    if application is None:
        application = await application_service.create(
            RegistrationApplicationCreate(
                name="便携式心电记录仪首次注册",
                product_name=DEMO_PRODUCT_NAME,
                applicant_name="深圳示例医疗科技有限公司",
                device_class="II",
                regulation_effective_on=date(2026, 7, 16),
                owner_name="刘凯旗",
            )
        )

    evidence_files = {
        DossierCategory.RISK_ANALYSIS: "portable-ecg-risk-analysis.md",
        DossierCategory.TECHNICAL_REQUIREMENTS: (
            "portable-ecg-technical-requirements.md"
        ),
        DossierCategory.IFU_AND_LABEL: (
            "portable-ecg-ifu-with-controlled-conflict.md"
        ),
    }
    for category, file_name in evidence_files.items():
        evidence = await application_service.list_evidence(application.id, category)
        if not any(item.file_name == file_name for item in evidence.items):
            await application_service.archive_evidence(
                application_id=application.id,
                category_key=category,
                file_name=file_name,
                content_type="text/markdown",
                data=(ROOT / "samples" / file_name).read_bytes(),
                uploaded_by="演示数据脚本",
            )
        application = await application_service.get(application.id)
        requirement = next(item for item in application.requirements if item.key == category)
        if requirement.status != RequirementStatus.ACCEPTED:
            await application_service.review_requirement(
                application.id,
                category,
                RequirementReviewCreate(
                    decision=RequirementReviewDecision.ACCEPTED,
                    reviewed_by="演示法规负责人",
                ),
            )

    prechecks = await application_service.list_prechecks(application.id)
    if not prechecks.items:
        await application_service.run_precheck(
            application.id,
            PrecheckCreate(initiated_by="刘凯旗"),
        )

    agent_repository = SQLAlchemyAgentRepository(session)
    agent_history = await agent_repository.list(application.id)
    if not agent_history:
        await AgentService(
            repository=agent_repository,
            application_service=application_service,
            retrieval_service=retrieval_service,
            model=DeterministicDraftModel(),
        ).create_run(
            application.id,
            AgentDraftRunCreate(
                target_section=DraftSection.RISK_MANAGEMENT_SUMMARY,
                language_mode=DraftLanguageMode.BILINGUAL,
                requested_by="刘凯旗",
            ),
        )
    return application.id


async def ensure_evaluation(session) -> uuid.UUID:
    service = EvaluationService(SQLAlchemyEvaluationRepository(session))
    history = await service.list_runs()
    if not history.items:
        created = await service.create_run(EvaluationRunCreate(requested_by="刘凯旗"))
        return created.id
    return history.items[0].id


async def ensure_security_audit(
    session,
    application_id: uuid.UUID,
    evaluation_run_id: uuid.UUID,
) -> None:
    repository = SQLAlchemySecurityRepository(session)
    service = SecurityService(repository)
    actor = await service.resolve_actor()
    if await repository.count_audit_events(actor.tenant_id):
        return
    events = (
        (
            "application.created",
            "registration_application",
            application_id,
            "POST",
            "/registration-applications",
            {"source": "fixed_demo_seed"},
        ),
        (
            "evidence.archived",
            "dossier_evidence",
            application_id,
            "POST",
            f"/registration-applications/{application_id}/requirements/evidence",
            {"accepted_categories": 3, "source": "fixed_demo_seed"},
        ),
        (
            "precheck.completed",
            "precheck_run",
            application_id,
            "POST",
            f"/registration-applications/{application_id}/prechecks",
            {"source": "fixed_demo_seed"},
        ),
        (
            "agent_run.created",
            "agent_draft_run",
            application_id,
            "POST",
            f"/registration-applications/{application_id}/agent-runs",
            {"workflow": "six_node_controlled", "source": "fixed_demo_seed"},
        ),
        (
            "evaluation.completed",
            "evaluation_run",
            evaluation_run_id,
            "POST",
            "/evaluation/runs",
            {"dataset_version": "medreg-eval-v1-60", "source": "fixed_demo_seed"},
        ),
    )
    for action, resource_type, resource_id, method, path, detail in events:
        await service.record(
            actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_method=method,
            request_path=path,
            status_code=201,
            detail=detail,
        )


async def seed() -> None:
    async with async_session_factory() as session:
        retrieval_service, graph_source_id = await ensure_regulation_and_retrieval(
            session
        )
        await ensure_knowledge_graph(session, graph_source_id)
        application_id = await ensure_application(session, retrieval_service)
        evaluation_run_id = await ensure_evaluation(session)
        await ensure_security_audit(session, application_id, evaluation_run_id)
    print(
        "Demo data ready: regulation, graph, evidence, precheck, agent, evaluation and audit."
    )


if __name__ == "__main__":
    asyncio.run(seed())
