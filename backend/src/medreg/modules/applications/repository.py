from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from medreg.modules.applications.models import (
    DossierEvidenceModel,
    DossierRequirementModel,
    PrecheckFindingModel,
    PrecheckRunModel,
    RegistrationApplicationModel,
)
from medreg.modules.applications.schemas import (
    ApplicationStatus,
    DossierCategory,
    DossierEvidenceRead,
    DossierRequirement,
    FindingRemediationStatus,
    PrecheckFinding,
    PrecheckRun,
    RegistrationApplicationRead,
    RequirementStatus,
)
from medreg.modules.security.schemas import DEMO_TENANT_ID


class ApplicationRepository(Protocol):
    async def add(
        self, application: RegistrationApplicationRead
    ) -> RegistrationApplicationRead: ...

    async def list(self) -> list[RegistrationApplicationRead]: ...

    async def get(
        self, application_id: uuid.UUID
    ) -> RegistrationApplicationRead | None: ...

    async def code_exists(self, code: str) -> bool: ...

    async def get_evidence_by_sha256(
        self,
        application_id: uuid.UUID,
        category_key: DossierCategory,
        sha256: str,
    ) -> DossierEvidenceRead | None: ...

    async def add_evidence(self, evidence: DossierEvidenceRead) -> DossierEvidenceRead: ...

    async def list_evidence(
        self,
        application_id: uuid.UUID,
        category_key: DossierCategory,
    ) -> list[DossierEvidenceRead]: ...

    async def update_requirement(
        self,
        application_id: uuid.UUID,
        category_key: DossierCategory,
        status: RequirementStatus,
        updated_at: datetime,
    ) -> RegistrationApplicationRead | None: ...

    async def add_precheck(self, run: PrecheckRun) -> PrecheckRun: ...

    async def list_prechecks(self, application_id: uuid.UUID) -> list[PrecheckRun]: ...

    async def update_finding(
        self,
        finding_id: uuid.UUID,
        status: FindingRemediationStatus,
        assignee: str | None,
        resolution_note: str | None,
        updated_by: str,
        resolved_at: datetime | None,
        updated_at: datetime,
    ) -> PrecheckFinding | None: ...


class InMemoryApplicationRepository:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, RegistrationApplicationRead] = {}
        self._evidence: dict[uuid.UUID, DossierEvidenceRead] = {}
        self._prechecks: dict[uuid.UUID, PrecheckRun] = {}
        self._lock = asyncio.Lock()

    async def add(self, application: RegistrationApplicationRead) -> RegistrationApplicationRead:
        async with self._lock:
            self._items[application.id] = application.model_copy(deep=True)
        return application.model_copy(deep=True)

    async def list(self) -> list[RegistrationApplicationRead]:
        async with self._lock:
            items = [item.model_copy(deep=True) for item in self._items.values()]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    async def get(self, application_id: uuid.UUID) -> RegistrationApplicationRead | None:
        async with self._lock:
            item = self._items.get(application_id)
        return item.model_copy(deep=True) if item else None

    async def code_exists(self, code: str) -> bool:
        async with self._lock:
            return any(item.code == code for item in self._items.values())

    async def get_evidence_by_sha256(
        self,
        application_id: uuid.UUID,
        category_key: DossierCategory,
        sha256: str,
    ) -> DossierEvidenceRead | None:
        async with self._lock:
            evidence = next(
                (
                    item
                    for item in self._evidence.values()
                    if item.application_id == application_id
                    and item.category_key == category_key
                    and item.sha256 == sha256
                ),
                None,
            )
        return evidence.model_copy(deep=True) if evidence else None

    async def add_evidence(self, evidence: DossierEvidenceRead) -> DossierEvidenceRead:
        async with self._lock:
            application = self._items.get(evidence.application_id)
            if application is None:
                raise KeyError(str(evidence.application_id))
            requirements = []
            for requirement in application.requirements:
                if requirement.key == evidence.category_key:
                    requirement = requirement.model_copy(
                        update={
                            "status": RequirementStatus.UPLOADED,
                            "evidence_count": requirement.evidence_count + 1,
                        }
                    )
                requirements.append(requirement)
            self._items[evidence.application_id] = application.model_copy(
                update={
                    "requirements": requirements,
                    "status": ApplicationStatus.INTAKE,
                    "updated_at": evidence.created_at,
                },
                deep=True,
            )
            self._evidence[evidence.id] = evidence.model_copy(deep=True)
        return evidence.model_copy(deep=True)

    async def list_evidence(
        self,
        application_id: uuid.UUID,
        category_key: DossierCategory,
    ) -> list[DossierEvidenceRead]:
        async with self._lock:
            items = [
                item.model_copy(deep=True)
                for item in self._evidence.values()
                if item.application_id == application_id
                and item.category_key == category_key
            ]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    async def update_requirement(
        self,
        application_id: uuid.UUID,
        category_key: DossierCategory,
        status: RequirementStatus,
        updated_at: datetime,
    ) -> RegistrationApplicationRead | None:
        async with self._lock:
            application = self._items.get(application_id)
            if application is None:
                return None
            found = False
            requirements = []
            for requirement in application.requirements:
                if requirement.key == category_key:
                    found = True
                    requirement = requirement.model_copy(update={"status": status})
                requirements.append(requirement)
            if not found:
                return None
            completion_rate = self._completion_rate(requirements)
            updated = application.model_copy(
                update={
                    "requirements": requirements,
                    "status": (
                        ApplicationStatus.NEEDS_ACTION
                        if status == RequirementStatus.NEEDS_REVIEW
                        else ApplicationStatus.IN_REVIEW
                    ),
                    "completion_rate": completion_rate,
                    "updated_at": updated_at,
                },
                deep=True,
            )
            self._items[application_id] = updated
        return updated.model_copy(deep=True)

    async def add_precheck(self, run: PrecheckRun) -> PrecheckRun:
        async with self._lock:
            application = self._items.get(run.application_id)
            if application is None:
                raise KeyError(str(run.application_id))
            self._items[run.application_id] = application.model_copy(
                update={
                    "status": run.application_status,
                    "updated_at": run.completed_at,
                },
                deep=True,
            )
            self._prechecks[run.id] = run.model_copy(deep=True)
        return run.model_copy(deep=True)

    async def list_prechecks(self, application_id: uuid.UUID) -> list[PrecheckRun]:
        async with self._lock:
            items = [
                item.model_copy(deep=True)
                for item in self._prechecks.values()
                if item.application_id == application_id
            ]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    async def update_finding(
        self,
        finding_id: uuid.UUID,
        status: FindingRemediationStatus,
        assignee: str | None,
        resolution_note: str | None,
        updated_by: str,
        resolved_at: datetime | None,
        updated_at: datetime,
    ) -> PrecheckFinding | None:
        async with self._lock:
            for run_id, run in self._prechecks.items():
                updated_findings = []
                matched: PrecheckFinding | None = None
                for finding in run.findings:
                    if finding.id == finding_id:
                        matched = finding.model_copy(
                            update={
                                "remediation_status": status,
                                "assignee": assignee,
                                "resolution_note": resolution_note,
                                "updated_by": updated_by,
                                "resolved_at": resolved_at,
                                "updated_at": updated_at,
                            }
                        )
                        finding = matched
                    updated_findings.append(finding)
                if matched is not None:
                    self._prechecks[run_id] = run.model_copy(
                        update={"findings": updated_findings},
                        deep=True,
                    )
                    return matched.model_copy(deep=True)
        return None

    async def clear(self) -> None:
        async with self._lock:
            self._items.clear()
            self._evidence.clear()
            self._prechecks.clear()

    @staticmethod
    def _completion_rate(requirements: list[DossierRequirement]) -> float:
        required = [item for item in requirements if item.required]
        complete = [
            item
            for item in required
            if item.status
            in {RequirementStatus.ACCEPTED, RequirementStatus.NOT_APPLICABLE}
        ]
        return round(len(complete) / len(required) * 100, 1) if required else 100.0


class SQLAlchemyApplicationRepository:
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID = DEMO_TENANT_ID,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def add(self, application: RegistrationApplicationRead) -> RegistrationApplicationRead:
        model = RegistrationApplicationModel(
            id=application.id,
            tenant_id=self.tenant_id,
            code=application.code,
            name=application.name,
            product_name=application.product_name,
            applicant_name=application.applicant_name,
            jurisdiction=application.jurisdiction.value,
            device_class=application.device_class.value,
            application_type=application.application_type.value,
            regulation_effective_on=application.regulation_effective_on,
            owner_name=application.owner_name,
            status=application.status.value,
            completion_rate=application.completion_rate,
            created_at=application.created_at,
            updated_at=application.updated_at,
            requirements=[
                DossierRequirementModel(
                    id=uuid.uuid4(),
                    category_key=requirement.key.value,
                    title=requirement.title,
                    description=requirement.description,
                    regulatory_basis=requirement.regulatory_basis,
                    required=requirement.required,
                    status=requirement.status.value,
                    evidence_count=requirement.evidence_count,
                    position=position,
                )
                for position, requirement in enumerate(application.requirements, start=1)
            ],
        )
        self.session.add(model)
        await self.session.commit()
        return self._to_read_model(model)

    async def list(self) -> list[RegistrationApplicationRead]:
        result = await self.session.scalars(
            select(RegistrationApplicationModel)
            .options(selectinload(RegistrationApplicationModel.requirements))
            .where(RegistrationApplicationModel.tenant_id == self.tenant_id)
            .order_by(RegistrationApplicationModel.created_at.desc())
        )
        return [self._to_read_model(model) for model in result.unique().all()]

    async def get(
        self, application_id: uuid.UUID
    ) -> RegistrationApplicationRead | None:
        result = await self.session.scalar(
            select(RegistrationApplicationModel)
            .options(selectinload(RegistrationApplicationModel.requirements))
            .where(
                RegistrationApplicationModel.id == application_id,
                RegistrationApplicationModel.tenant_id == self.tenant_id,
            )
        )
        return self._to_read_model(result) if result is not None else None

    async def code_exists(self, code: str) -> bool:
        return bool(
            await self.session.scalar(
                select(exists().where(RegistrationApplicationModel.code == code))
            )
        )

    async def get_evidence_by_sha256(
        self,
        application_id: uuid.UUID,
        category_key: DossierCategory,
        sha256: str,
    ) -> DossierEvidenceRead | None:
        model = await self.session.scalar(
            select(DossierEvidenceModel)
            .join(
                RegistrationApplicationModel,
                RegistrationApplicationModel.id == DossierEvidenceModel.application_id,
            )
            .where(
                DossierEvidenceModel.application_id == application_id,
                DossierEvidenceModel.category_key == category_key.value,
                DossierEvidenceModel.sha256 == sha256,
                RegistrationApplicationModel.tenant_id == self.tenant_id,
            )
        )
        return self._to_evidence_read(model) if model else None

    async def add_evidence(self, evidence: DossierEvidenceRead) -> DossierEvidenceRead:
        application = await self.session.scalar(
            select(RegistrationApplicationModel)
            .options(selectinload(RegistrationApplicationModel.requirements))
            .where(
                RegistrationApplicationModel.id == evidence.application_id,
                RegistrationApplicationModel.tenant_id == self.tenant_id,
            )
            .with_for_update()
        )
        if application is None:
            raise KeyError(str(evidence.application_id))
        requirement = next(
            (
                item
                for item in application.requirements
                if item.category_key == evidence.category_key.value
            ),
            None,
        )
        if requirement is None:
            raise KeyError(evidence.category_key.value)

        model = DossierEvidenceModel(
            id=evidence.id,
            application_id=evidence.application_id,
            category_key=evidence.category_key.value,
            file_name=evidence.file_name,
            content_type=evidence.content_type,
            size_bytes=evidence.size_bytes,
            sha256=evidence.sha256,
            bucket_name=evidence.bucket_name,
            object_key=evidence.object_key,
            uploaded_by=evidence.uploaded_by,
            created_at=evidence.created_at,
        )
        self.session.add(model)
        requirement.evidence_count += 1
        requirement.status = RequirementStatus.UPLOADED.value
        application.status = "intake"
        application.updated_at = evidence.created_at
        await self.session.commit()
        return self._to_evidence_read(model)

    async def list_evidence(
        self,
        application_id: uuid.UUID,
        category_key: DossierCategory,
    ) -> list[DossierEvidenceRead]:
        models = await self.session.scalars(
            select(DossierEvidenceModel)
            .join(
                RegistrationApplicationModel,
                RegistrationApplicationModel.id == DossierEvidenceModel.application_id,
            )
            .where(
                DossierEvidenceModel.application_id == application_id,
                DossierEvidenceModel.category_key == category_key.value,
                RegistrationApplicationModel.tenant_id == self.tenant_id,
            )
            .order_by(DossierEvidenceModel.created_at.desc())
        )
        return [self._to_evidence_read(model) for model in models.all()]

    async def update_requirement(
        self,
        application_id: uuid.UUID,
        category_key: DossierCategory,
        status: RequirementStatus,
        updated_at: datetime,
    ) -> RegistrationApplicationRead | None:
        application = await self.session.scalar(
            select(RegistrationApplicationModel)
            .options(selectinload(RegistrationApplicationModel.requirements))
            .where(
                RegistrationApplicationModel.id == application_id,
                RegistrationApplicationModel.tenant_id == self.tenant_id,
            )
            .with_for_update()
        )
        if application is None:
            return None
        requirement = next(
            (
                item
                for item in application.requirements
                if item.category_key == category_key.value
            ),
            None,
        )
        if requirement is None:
            return None
        requirement.status = status.value
        application.completion_rate = self._completion_rate_models(
            application.requirements
        )
        application.status = (
            "needs_action"
            if status == RequirementStatus.NEEDS_REVIEW
            else "in_review"
        )
        application.updated_at = updated_at
        await self.session.commit()
        return self._to_read_model(application)

    async def add_precheck(self, run: PrecheckRun) -> PrecheckRun:
        application = await self.session.scalar(
            select(RegistrationApplicationModel).where(
                RegistrationApplicationModel.id == run.application_id,
                RegistrationApplicationModel.tenant_id == self.tenant_id,
            )
        )
        if application is None:
            raise KeyError(str(run.application_id))
        model = PrecheckRunModel(
            id=run.id,
            application_id=run.application_id,
            status=run.status.value,
            rule_set_version=run.rule_set_version,
            application_status=run.application_status.value,
            blocker_count=run.blocker_count,
            warning_count=run.warning_count,
            pass_count=run.pass_count,
            initiated_by=run.initiated_by,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
            findings=[
                PrecheckFindingModel(
                    id=finding.id,
                    category_key=finding.category_key.value,
                    rule_code=finding.rule_code,
                    severity=finding.severity.value,
                    title=finding.title,
                    description=finding.description,
                    regulatory_basis=finding.regulatory_basis,
                    remediation=finding.remediation,
                    remediation_status=finding.remediation_status.value,
                    assignee=finding.assignee,
                    resolution_note=finding.resolution_note,
                    updated_by=finding.updated_by,
                    resolved_at=finding.resolved_at,
                    position=finding.position,
                    created_at=finding.created_at,
                    updated_at=finding.updated_at,
                )
                for finding in run.findings
            ],
        )
        self.session.add(model)
        application.status = run.application_status.value
        application.updated_at = run.completed_at
        await self.session.commit()
        return self._to_precheck_read(model)

    async def list_prechecks(self, application_id: uuid.UUID) -> list[PrecheckRun]:
        models = await self.session.scalars(
            select(PrecheckRunModel)
            .join(
                RegistrationApplicationModel,
                RegistrationApplicationModel.id == PrecheckRunModel.application_id,
            )
            .options(selectinload(PrecheckRunModel.findings))
            .where(
                PrecheckRunModel.application_id == application_id,
                RegistrationApplicationModel.tenant_id == self.tenant_id,
            )
            .order_by(PrecheckRunModel.created_at.desc())
        )
        return [self._to_precheck_read(model) for model in models.unique().all()]

    async def update_finding(
        self,
        finding_id: uuid.UUID,
        status: FindingRemediationStatus,
        assignee: str | None,
        resolution_note: str | None,
        updated_by: str,
        resolved_at: datetime | None,
        updated_at: datetime,
    ) -> PrecheckFinding | None:
        model = await self.session.scalar(
            select(PrecheckFindingModel)
            .join(PrecheckRunModel, PrecheckRunModel.id == PrecheckFindingModel.run_id)
            .join(
                RegistrationApplicationModel,
                RegistrationApplicationModel.id == PrecheckRunModel.application_id,
            )
            .where(
                PrecheckFindingModel.id == finding_id,
                RegistrationApplicationModel.tenant_id == self.tenant_id,
            )
        )
        if model is None:
            return None
        model.remediation_status = status.value
        model.assignee = assignee
        model.resolution_note = resolution_note
        model.updated_by = updated_by
        model.resolved_at = resolved_at
        model.updated_at = updated_at
        await self.session.commit()
        return self._to_finding_read(model)

    @staticmethod
    def _to_read_model(
        model: RegistrationApplicationModel,
    ) -> RegistrationApplicationRead:
        requirements = [
            DossierRequirement(
                key=requirement.category_key,
                title=requirement.title,
                description=requirement.description,
                regulatory_basis=requirement.regulatory_basis,
                required=requirement.required,
                status=requirement.status,
                evidence_count=requirement.evidence_count,
            )
            for requirement in sorted(model.requirements, key=lambda item: item.position)
        ]
        return RegistrationApplicationRead(
            id=model.id,
            code=model.code,
            name=model.name,
            product_name=model.product_name,
            applicant_name=model.applicant_name,
            jurisdiction=model.jurisdiction,
            device_class=model.device_class,
            application_type=model.application_type,
            regulation_effective_on=model.regulation_effective_on,
            owner_name=model.owner_name,
            status=model.status,
            requirements=requirements,
            completion_rate=model.completion_rate,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_evidence_read(model: DossierEvidenceModel) -> DossierEvidenceRead:
        return DossierEvidenceRead(
            id=model.id,
            application_id=model.application_id,
            category_key=model.category_key,
            file_name=model.file_name,
            content_type=model.content_type,
            size_bytes=model.size_bytes,
            sha256=model.sha256,
            bucket_name=model.bucket_name,
            object_key=model.object_key,
            uploaded_by=model.uploaded_by,
            created_at=model.created_at,
        )

    @staticmethod
    def _to_precheck_read(model: PrecheckRunModel) -> PrecheckRun:
        return PrecheckRun(
            id=model.id,
            application_id=model.application_id,
            status=model.status,
            rule_set_version=model.rule_set_version,
            application_status=model.application_status,
            blocker_count=model.blocker_count,
            warning_count=model.warning_count,
            pass_count=model.pass_count,
            initiated_by=model.initiated_by,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            findings=[
                SQLAlchemyApplicationRepository._to_finding_read(finding)
                for finding in sorted(model.findings, key=lambda item: item.position)
            ],
        )

    @staticmethod
    def _to_finding_read(model: PrecheckFindingModel) -> PrecheckFinding:
        return PrecheckFinding(
            id=model.id,
            category_key=model.category_key,
            rule_code=model.rule_code,
            severity=model.severity,
            title=model.title,
            description=model.description,
            regulatory_basis=model.regulatory_basis,
            remediation=model.remediation,
            remediation_status=model.remediation_status,
            assignee=model.assignee,
            resolution_note=model.resolution_note,
            updated_by=model.updated_by,
            resolved_at=model.resolved_at,
            position=model.position,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _completion_rate_models(
        requirements: list[DossierRequirementModel],
    ) -> float:
        required = [item for item in requirements if item.required]
        complete = [
            item
            for item in required
            if item.status
            in {RequirementStatus.ACCEPTED.value, RequirementStatus.NOT_APPLICABLE.value}
        ]
        return round(len(complete) / len(required) * 100, 1) if required else 100.0
