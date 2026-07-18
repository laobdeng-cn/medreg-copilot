import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete

from medreg.core.database import async_session_factory
from medreg.modules.applications.models import RegistrationApplicationModel
from medreg.modules.applications.repository import SQLAlchemyApplicationRepository
from medreg.modules.applications.schemas import (
    DeviceClass,
    DossierCategory,
    FindingRemediationStatus,
    FindingRemediationUpdate,
    PrecheckCreate,
    RegistrationApplicationCreate,
    RequirementReviewCreate,
    RequirementReviewDecision,
)
from medreg.modules.applications.service import ApplicationService
from medreg.modules.documents.storage import InMemoryObjectStorage
from medreg.modules.evaluation.models import EvaluationRunModel
from medreg.modules.evaluation.repository import SQLAlchemyEvaluationRepository
from medreg.modules.evaluation.schemas import EvaluationRunCreate
from medreg.modules.evaluation.service import EvaluationService
from medreg.modules.security.models import AuditEventModel, TenantModel
from medreg.modules.security.repository import SQLAlchemySecurityRepository
from medreg.modules.security.schemas import (
    DEMO_OWNER_ID,
    DEMO_TENANT_ID,
    AuditEventCreate,
)


@pytest.mark.integration
async def test_application_survives_a_new_database_session() -> None:
    created_id = None
    try:
        async with async_session_factory() as write_session:
            service = ApplicationService(SQLAlchemyApplicationRepository(write_session))
            created = await service.create(
                RegistrationApplicationCreate(
                    name="数据库持久化集成测试",
                    product_name="集成测试医疗器械",
                    applicant_name="深圳集成测试有限公司",
                    device_class=DeviceClass.CLASS_II,
                    regulation_effective_on=date(2026, 7, 16),
                    owner_name="测试人员",
                )
            )
            created_id = created.id

        async with async_session_factory() as read_session:
            repository = SQLAlchemyApplicationRepository(read_session)
            restored = await repository.get(created.id)

        assert restored is not None
        assert restored.code == created.code
        assert restored.product_name == "集成测试医疗器械"
        assert len(restored.requirements) == 7
    finally:
        if created_id is not None:
            async with async_session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(RegistrationApplicationModel).where(
                        RegistrationApplicationModel.id == created_id
                    )
                )
                await cleanup_session.commit()


@pytest.mark.integration
async def test_evidence_and_precheck_survive_a_new_database_session() -> None:
    created_id = None
    storage = InMemoryObjectStorage()
    try:
        async with async_session_factory() as write_session:
            service = ApplicationService(
                SQLAlchemyApplicationRepository(write_session),
                storage=storage,
            )
            created = await service.create(
                RegistrationApplicationCreate(
                    name="预审持久化集成测试",
                    product_name="集成测试心电记录仪",
                    applicant_name="深圳集成测试有限公司",
                    device_class=DeviceClass.CLASS_II,
                    regulation_effective_on=date(2026, 7, 17),
                    owner_name="测试人员",
                )
            )
            created_id = created.id
            await service.archive_evidence(
                application_id=created.id,
                category_key=DossierCategory.RISK_ANALYSIS,
                file_name="risk-analysis.txt",
                content_type="text/plain",
                data=b"integration risk evidence",
                uploaded_by="测试人员",
            )
            await service.review_requirement(
                application_id=created.id,
                category_key=DossierCategory.RISK_ANALYSIS,
                payload=RequirementReviewCreate(
                    decision=RequirementReviewDecision.ACCEPTED,
                    reviewed_by="审核人员",
                ),
            )
            run = await service.run_precheck(
                created.id,
                PrecheckCreate(initiated_by="测试人员"),
            )
            assert run.blocker_count == 6
            assert run.pass_count == 1
            await service.update_finding_remediation(
                run.findings[0].id,
                FindingRemediationUpdate(
                    status=FindingRemediationStatus.IN_PROGRESS,
                    assignee="测试人员",
                    updated_by="审核人员",
                ),
            )

        async with async_session_factory() as read_session:
            restored_service = ApplicationService(
                SQLAlchemyApplicationRepository(read_session)
            )
            restored = await restored_service.get(created.id)
            history = await restored_service.list_prechecks(created.id)
            matrix = await restored_service.get_evidence_matrix(created.id)

        assert restored.completion_rate == 14.3
        assert restored.requirements[0].evidence_count == 1
        assert restored.requirements[0].status == "accepted"
        assert history.total == 1
        assert history.items[0].findings[0].rule_code == "DOSSIER_REQUIRED_MISSING"
        assert history.items[0].findings[0].remediation_status == "in_progress"
        assert matrix.open_finding_count == 6
    finally:
        if created_id is not None:
            async with async_session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(RegistrationApplicationModel).where(
                        RegistrationApplicationModel.id == created_id
                    )
                )
                await cleanup_session.commit()


@pytest.mark.integration
async def test_evaluation_run_survives_a_new_database_session() -> None:
    run_id = None
    try:
        async with async_session_factory() as write_session:
            service = EvaluationService(SQLAlchemyEvaluationRepository(write_session))
            created = await service.create_run(
                EvaluationRunCreate(requested_by="集成测试人员")
            )
            run_id = created.id

        async with async_session_factory() as read_session:
            history = await EvaluationService(
                SQLAlchemyEvaluationRepository(read_session)
            ).list_runs()

        restored = next(item for item in history.items if item.id == run_id)
        assert restored.dataset_version == "medreg-eval-v1-60"
        assert restored.case_count == 60
        assert restored.quality_gate.status == "passed"
        assert len(restored.metrics) == 10
    finally:
        if run_id is not None:
            async with async_session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(EvaluationRunModel).where(EvaluationRunModel.id == run_id)
                )
                await cleanup_session.commit()


@pytest.mark.integration
async def test_registration_applications_are_isolated_by_tenant() -> None:
    tenant_id = uuid.uuid4()
    created_id = None
    try:
        async with async_session_factory() as write_session:
            write_session.add(
                TenantModel(
                    id=tenant_id,
                    slug=f"integration-{tenant_id.hex[:12]}",
                    name="集成测试隔离租户",
                    status="active",
                    created_at=datetime.now(UTC),
                )
            )
            await write_session.commit()
            service = ApplicationService(
                SQLAlchemyApplicationRepository(write_session, tenant_id=tenant_id)
            )
            created = await service.create(
                RegistrationApplicationCreate(
                    name="租户隔离集成测试",
                    product_name="隔离测试医疗器械",
                    applicant_name="租户隔离测试有限公司",
                    device_class=DeviceClass.CLASS_II,
                    regulation_effective_on=date(2026, 7, 18),
                    owner_name="隔离测试人员",
                )
            )
            created_id = created.id

        async with async_session_factory() as read_session:
            own_repository = SQLAlchemyApplicationRepository(
                read_session, tenant_id=tenant_id
            )
            demo_repository = SQLAlchemyApplicationRepository(
                read_session, tenant_id=DEMO_TENANT_ID
            )
            own_item = await own_repository.get(created.id)
            leaked_item = await demo_repository.get(created.id)

        assert own_item is not None
        assert leaked_item is None
    finally:
        async with async_session_factory() as cleanup_session:
            if created_id is not None:
                await cleanup_session.execute(
                    delete(RegistrationApplicationModel).where(
                        RegistrationApplicationModel.id == created_id
                    )
                )
            await cleanup_session.execute(
                delete(TenantModel).where(TenantModel.id == tenant_id)
            )
            await cleanup_session.commit()


@pytest.mark.integration
async def test_audit_event_survives_a_new_database_session() -> None:
    event_id = None
    try:
        async with async_session_factory() as write_session:
            repository = SQLAlchemySecurityRepository(write_session)
            actor = await repository.resolve_actor(DEMO_TENANT_ID, DEMO_OWNER_ID)
            assert actor is not None
            created = await repository.add_audit_event(
                AuditEventCreate(
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.user_id,
                    actor_name=actor.user_name,
                    actor_role=actor.role,
                    action="integration.audit_verified",
                    resource_type="integration_test",
                    resource_id="tenant-audit",
                    request_method="POST",
                    request_path="/integration/audit",
                    status_code=201,
                    created_at=datetime.now(UTC),
                )
            )
            event_id = created.id

        async with async_session_factory() as read_session:
            history = await SQLAlchemySecurityRepository(
                read_session
            ).list_audit_events(DEMO_TENANT_ID, limit=20)

        restored = next(item for item in history if item.id == event_id)
        assert restored.action == "integration.audit_verified"
        assert restored.actor_role == "owner"
    finally:
        if event_id is not None:
            async with async_session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(AuditEventModel).where(AuditEventModel.id == event_id)
                )
                await cleanup_session.commit()
