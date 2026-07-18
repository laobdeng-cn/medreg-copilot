from __future__ import annotations

import asyncio
import hashlib
import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path

from medreg.modules.applications.consistency import (
    DossierConsistencyAnalyzer,
    EvidenceText,
)
from medreg.modules.applications.repository import ApplicationRepository
from medreg.modules.applications.schemas import (
    DOSSIER_CATEGORY_DEFINITIONS,
    ApplicationStatus,
    DossierCategory,
    DossierConsistencyReport,
    DossierEvidenceList,
    DossierEvidenceRead,
    DossierRequirement,
    EvidenceMatrix,
    EvidenceMatrixRow,
    FindingRemediationStatus,
    FindingRemediationUpdate,
    FindingSeverity,
    InternalPrecheckReport,
    PrecheckCreate,
    PrecheckFinding,
    PrecheckReportEvidence,
    PrecheckRun,
    PrecheckRunList,
    PrecheckStatus,
    RegistrationApplicationCreate,
    RegistrationApplicationList,
    RegistrationApplicationRead,
    RequirementReviewCreate,
    RequirementStatus,
    UnreadableEvidence,
)
from medreg.modules.documents.parser import ControlledDocumentParser, DocumentParser
from medreg.modules.documents.storage import ObjectStorage

ALLOWED_EVIDENCE_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".html", ".htm"}
PRECHECK_RULE_SET_VERSION = "nmpa-dossier-precheck-v2"


class ApplicationNotFoundError(LookupError):
    pass


class RequirementNotFoundError(LookupError):
    pass


class EvidenceValidationError(ValueError):
    pass


class DuplicateEvidenceError(ValueError):
    pass


class RequirementStateError(ValueError):
    pass


class PrecheckFindingNotFoundError(LookupError):
    pass


class FindingRemediationStateError(ValueError):
    pass


class PrecheckReportUnavailableError(ValueError):
    pass


class ApplicationService:
    def __init__(
        self,
        repository: ApplicationRepository,
        storage: ObjectStorage | None = None,
        parser: DocumentParser | None = None,
        max_upload_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.parser = parser or ControlledDocumentParser()
        self.consistency_analyzer = DossierConsistencyAnalyzer()
        self.max_upload_bytes = max_upload_bytes

    async def create(
        self, payload: RegistrationApplicationCreate
    ) -> RegistrationApplicationRead:
        now = datetime.now(UTC)
        code = await self._next_code(now.year)
        requirements = [
            DossierRequirement(**definition.model_dump())
            for definition in DOSSIER_CATEGORY_DEFINITIONS
        ]
        application = RegistrationApplicationRead(
            id=uuid.uuid4(),
            code=code,
            **payload.model_dump(),
            status=ApplicationStatus.DRAFT,
            requirements=requirements,
            completion_rate=0.0,
            created_at=now,
            updated_at=now,
        )
        return await self.repository.add(application)

    async def list(self) -> RegistrationApplicationList:
        items = await self.repository.list()
        return RegistrationApplicationList(items=items, total=len(items))

    async def get(self, application_id: uuid.UUID) -> RegistrationApplicationRead:
        application = await self.repository.get(application_id)
        if application is None:
            raise ApplicationNotFoundError(str(application_id))
        return application

    async def archive_evidence(
        self,
        application_id: uuid.UUID,
        category_key: DossierCategory,
        file_name: str,
        content_type: str | None,
        data: bytes,
        uploaded_by: str,
    ) -> DossierEvidenceRead:
        application = await self.get(application_id)
        self._get_requirement(application, category_key)
        if self.storage is None:
            raise RuntimeError("Object storage is not configured")

        safe_name = Path(file_name).name.strip()
        suffix = Path(safe_name).suffix.lower()
        if not safe_name or suffix not in ALLOWED_EVIDENCE_SUFFIXES:
            raise EvidenceValidationError(
                "Only PDF, DOCX, TXT, Markdown and HTML files are supported"
            )
        if not data:
            raise EvidenceValidationError("The uploaded file is empty")
        if len(data) > self.max_upload_bytes:
            raise EvidenceValidationError(
                f"The uploaded file exceeds {self.max_upload_bytes} bytes"
            )

        digest = hashlib.sha256(data).hexdigest()
        duplicate = await self.repository.get_evidence_by_sha256(
            application_id, category_key, digest
        )
        if duplicate is not None:
            raise DuplicateEvidenceError(digest)

        now = datetime.now(UTC)
        evidence_id = uuid.uuid4()
        object_key = (
            f"applications/{application_id}/{category_key.value}/"
            f"{evidence_id}/{safe_name}"
        )
        resolved_content_type = content_type or "application/octet-stream"
        await self.storage.put(object_key, data, resolved_content_type)
        evidence = DossierEvidenceRead(
            id=evidence_id,
            application_id=application_id,
            category_key=category_key,
            file_name=safe_name,
            content_type=resolved_content_type,
            size_bytes=len(data),
            sha256=digest,
            bucket_name=self.storage.bucket_name,
            object_key=object_key,
            uploaded_by=uploaded_by,
            created_at=now,
        )
        try:
            return await self.repository.add_evidence(evidence)
        except Exception:
            await self.storage.delete(object_key)
            raise

    async def list_evidence(
        self,
        application_id: uuid.UUID,
        category_key: DossierCategory,
    ) -> DossierEvidenceList:
        application = await self.get(application_id)
        self._get_requirement(application, category_key)
        items = await self.repository.list_evidence(application_id, category_key)
        return DossierEvidenceList(items=items, total=len(items))

    async def review_requirement(
        self,
        application_id: uuid.UUID,
        category_key: DossierCategory,
        payload: RequirementReviewCreate,
    ) -> RegistrationApplicationRead:
        application = await self.get(application_id)
        requirement = self._get_requirement(application, category_key)
        if requirement.evidence_count == 0:
            raise RequirementStateError(
                "Evidence must be uploaded before the requirement can be reviewed"
            )
        updated = await self.repository.update_requirement(
            application_id=application_id,
            category_key=category_key,
            status=RequirementStatus(payload.decision.value),
            updated_at=datetime.now(UTC),
        )
        if updated is None:
            raise RequirementNotFoundError(category_key.value)
        return updated

    async def run_precheck(
        self,
        application_id: uuid.UUID,
        payload: PrecheckCreate,
    ) -> PrecheckRun:
        application = await self.get(application_id)
        started_at = datetime.now(UTC)
        findings: list[PrecheckFinding] = []
        pass_count = 0

        for requirement in application.requirements:
            if not requirement.required:
                continue
            if requirement.evidence_count == 0:
                findings.append(
                    PrecheckFinding(
                        id=uuid.uuid4(),
                        category_key=requirement.key,
                        rule_code="DOSSIER_REQUIRED_MISSING",
                        severity=FindingSeverity.BLOCKER,
                        title=f"缺少{requirement.title}",
                        description=(
                            f"项目尚未归档“{requirement.title}”的任何申报证据，"
                            "当前材料包不满足完整性预审要求。"
                        ),
                        regulatory_basis=requirement.regulatory_basis,
                        remediation=(
                            "上传受控版本文件，确认文件归属和版本后提交法规人员审核。"
                        ),
                        position=len(findings) + 1,
                        created_at=started_at,
                        updated_at=started_at,
                    )
                )
            elif requirement.status != RequirementStatus.ACCEPTED:
                findings.append(
                    PrecheckFinding(
                        id=uuid.uuid4(),
                        category_key=requirement.key,
                        rule_code="DOSSIER_EVIDENCE_UNREVIEWED",
                        severity=FindingSeverity.WARNING,
                        title=f"{requirement.title}尚未完成审核",
                        description=(
                            f"已归档 {requirement.evidence_count} 份证据，"
                            "但尚未形成可用于申报的受控审核结论。"
                        ),
                        regulatory_basis=requirement.regulatory_basis,
                        remediation=(
                            "由法规负责人核对文件内容、版本和适用性后接受或退回整改。"
                        ),
                        position=len(findings) + 1,
                        created_at=started_at,
                        updated_at=started_at,
                    )
                )
            else:
                pass_count += 1

        consistency = await self._build_consistency_report(
            application,
            generated_at=started_at,
        )
        pass_count += consistency.pass_count
        accepted_categories = {
            requirement.key
            for requirement in application.requirements
            if requirement.status == RequirementStatus.ACCEPTED
        }
        for unreadable in consistency.unreadable_evidence:
            if unreadable.category_key not in accepted_categories:
                continue
            definition = self._get_requirement(application, unreadable.category_key)
            findings.append(
                PrecheckFinding(
                    id=uuid.uuid4(),
                    category_key=unreadable.category_key,
                    rule_code="CONSISTENCY_DOCUMENT_UNREADABLE",
                    severity=FindingSeverity.WARNING,
                    title=f"{unreadable.file_name}无法参与一致性检查",
                    description=(
                        f"已接受的“{definition.title}”证据无法提取可比文本："
                        f"{unreadable.reason}"
                    ),
                    regulatory_basis=definition.regulatory_basis,
                    remediation=(
                        "核对文件是否损坏或为扫描件，补充可检索 PDF、DOCX 或文本版本。"
                    ),
                    position=len(findings) + 1,
                    created_at=started_at,
                    updated_at=started_at,
                )
            )

        for check in consistency.checks:
            if check.status.value != "mismatch":
                continue
            rule = self.consistency_analyzer.rule_for(check.field)
            category_key = next(
                (
                    occurrence.category_key
                    for occurrence in reversed(check.occurrences)
                    if occurrence.category_key is not None
                ),
                rule.default_category,
            )
            compared_values = "；".join(
                f"{occurrence.source_label}：{occurrence.value}"
                for occurrence in check.occurrences[:4]
            )
            findings.append(
                PrecheckFinding(
                    id=uuid.uuid4(),
                    category_key=category_key,
                    rule_code=rule.rule_code,
                    severity=rule.severity,
                    title=f"{rule.label}存在跨文档不一致",
                    description=f"{check.message} 比对值：{compared_values}",
                    regulatory_basis=rule.regulatory_basis,
                    remediation=rule.remediation,
                    position=len(findings) + 1,
                    created_at=started_at,
                    updated_at=started_at,
                )
            )

        blocker_count = sum(
            item.severity == FindingSeverity.BLOCKER for item in findings
        )
        warning_count = sum(
            item.severity == FindingSeverity.WARNING for item in findings
        )
        application_status = (
            ApplicationStatus.NEEDS_ACTION
            if blocker_count
            else (
                ApplicationStatus.IN_REVIEW
                if warning_count
                else ApplicationStatus.READY_FOR_SUBMISSION
            )
        )
        completed_at = datetime.now(UTC)
        run = PrecheckRun(
            id=uuid.uuid4(),
            application_id=application_id,
            status=PrecheckStatus.COMPLETED,
            rule_set_version=PRECHECK_RULE_SET_VERSION,
            application_status=application_status,
            blocker_count=blocker_count,
            warning_count=warning_count,
            pass_count=pass_count,
            initiated_by=payload.initiated_by,
            started_at=started_at,
            completed_at=completed_at,
            created_at=started_at,
            findings=findings,
        )
        return await self.repository.add_precheck(run)

    async def list_prechecks(
        self, application_id: uuid.UUID
    ) -> PrecheckRunList:
        await self.get(application_id)
        items = await self.repository.list_prechecks(application_id)
        return PrecheckRunList(items=items, total=len(items))

    async def get_evidence_matrix(
        self, application_id: uuid.UUID
    ) -> EvidenceMatrix:
        application = await self.get(application_id)
        runs = await self.repository.list_prechecks(application_id)
        latest = runs[0] if runs else None
        rows: list[EvidenceMatrixRow] = []
        for requirement in application.requirements:
            evidence = await self.repository.list_evidence(
                application_id, requirement.key
            )
            findings = (
                [
                    finding
                    for finding in latest.findings
                    if finding.category_key == requirement.key
                ]
                if latest
                else []
            )
            rows.append(
                EvidenceMatrixRow(
                    category_key=requirement.key,
                    title=requirement.title,
                    regulatory_basis=requirement.regulatory_basis,
                    requirement_status=requirement.status,
                    evidence_count=requirement.evidence_count,
                    evidence=evidence,
                    findings=findings,
                )
            )

        all_findings = latest.findings if latest else []
        open_finding_count = sum(
            finding.remediation_status
            in {
                FindingRemediationStatus.OPEN,
                FindingRemediationStatus.IN_PROGRESS,
            }
            for finding in all_findings
        )
        return EvidenceMatrix(
            application_id=application.id,
            application_code=application.code,
            application_name=application.name,
            completion_rate=application.completion_rate,
            latest_precheck_id=latest.id if latest else None,
            latest_precheck_at=latest.completed_at if latest else None,
            blocker_count=latest.blocker_count if latest else 0,
            warning_count=latest.warning_count if latest else 0,
            open_finding_count=open_finding_count,
            rows=rows,
        )

    async def get_consistency_report(
        self, application_id: uuid.UUID
    ) -> DossierConsistencyReport:
        application = await self.get(application_id)
        return await self._build_consistency_report(application)

    async def get_drafting_evidence_texts(
        self, application_id: uuid.UUID
    ) -> list[EvidenceText]:
        application = await self.get(application_id)
        accepted_categories = {
            requirement.key
            for requirement in application.requirements
            if requirement.status == RequirementStatus.ACCEPTED
        }
        evidence_items: list[DossierEvidenceRead] = []
        for category_key in accepted_categories:
            evidence_items.extend(
                await self.repository.list_evidence(application_id, category_key)
            )
        parsed = await asyncio.gather(
            *(self._parse_evidence(item) for item in evidence_items)
        )
        return [text for text, _ in parsed if text is not None]

    async def get_internal_precheck_report(
        self, application_id: uuid.UUID
    ) -> InternalPrecheckReport:
        application = await self.get(application_id)
        runs = await self.repository.list_prechecks(application_id)
        if not runs:
            raise PrecheckReportUnavailableError(
                "Run a precheck before generating an internal report"
            )
        latest = runs[0]
        evidence_manifest: list[PrecheckReportEvidence] = []
        for requirement in application.requirements:
            evidence = await self.repository.list_evidence(
                application_id,
                requirement.key,
            )
            evidence_manifest.extend(
                PrecheckReportEvidence(
                    evidence_id=item.id,
                    category_key=item.category_key,
                    category_title=requirement.title,
                    requirement_status=requirement.status,
                    file_name=item.file_name,
                    size_bytes=item.size_bytes,
                    sha256=item.sha256,
                    uploaded_by=item.uploaded_by,
                    created_at=item.created_at,
                )
                for item in evidence
            )

        consistency = await self._build_consistency_report(
            application,
            generated_at=latest.completed_at,
        )
        is_stale = application.updated_at > latest.completed_at
        report_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"medreg-precheck-report:{application.id}:{latest.id}",
        )
        return InternalPrecheckReport(
            report_id=report_id,
            report_code=(
                f"{application.code}-PR-"
                f"{latest.completed_at:%Y%m%d}-{str(latest.id)[:8].upper()}"
            ),
            generated_at=datetime.now(UTC),
            generated_by=latest.initiated_by,
            is_stale=is_stale,
            stale_reason=(
                "申报资料在本轮预审后发生变更，请重新执行预审。"
                if is_stale
                else None
            ),
            application=application,
            precheck=latest,
            evidence_count=len(evidence_manifest),
            accepted_category_count=sum(
                requirement.status == RequirementStatus.ACCEPTED
                for requirement in application.requirements
            ),
            open_finding_count=sum(
                finding.remediation_status
                in {
                    FindingRemediationStatus.OPEN,
                    FindingRemediationStatus.IN_PROGRESS,
                }
                for finding in latest.findings
            ),
            evidence_manifest=evidence_manifest,
            consistency=consistency,
        )

    async def update_finding_remediation(
        self,
        finding_id: uuid.UUID,
        payload: FindingRemediationUpdate,
    ) -> PrecheckFinding:
        if (
            payload.status == FindingRemediationStatus.IN_PROGRESS
            and not payload.assignee
        ):
            raise FindingRemediationStateError(
                "An assignee is required when remediation starts"
            )
        if (
            payload.status
            in {
                FindingRemediationStatus.RESOLVED,
                FindingRemediationStatus.WAIVED,
            }
            and not (payload.note or "").strip()
        ):
            raise FindingRemediationStateError(
                "A resolution note is required when closing a finding"
            )

        now = datetime.now(UTC)
        finding = await self.repository.update_finding(
            finding_id=finding_id,
            status=payload.status,
            assignee=payload.assignee,
            resolution_note=(payload.note or "").strip() or None,
            updated_by=payload.updated_by,
            resolved_at=(
                now
                if payload.status
                in {
                    FindingRemediationStatus.RESOLVED,
                    FindingRemediationStatus.WAIVED,
                }
                else None
            ),
            updated_at=now,
        )
        if finding is None:
            raise PrecheckFindingNotFoundError(str(finding_id))
        return finding

    async def _next_code(self, year: int) -> str:
        while True:
            code = f"MR-{year}-{secrets.token_hex(3).upper()}"
            if not await self.repository.code_exists(code):
                return code

    async def _build_consistency_report(
        self,
        application: RegistrationApplicationRead,
        generated_at: datetime | None = None,
    ) -> DossierConsistencyReport:
        evidence_items: list[DossierEvidenceRead] = []
        for requirement in application.requirements:
            evidence_items.extend(
                await self.repository.list_evidence(application.id, requirement.key)
            )

        parsed_documents: list[EvidenceText] = []
        unreadable: list[UnreadableEvidence] = []
        if self.storage is not None:
            results = await asyncio.gather(
                *(self._parse_evidence(item) for item in evidence_items)
            )
            for parsed, failure in results:
                if parsed is not None:
                    parsed_documents.append(parsed)
                if failure is not None:
                    unreadable.append(failure)

        checks = self.consistency_analyzer.analyze(
            application.product_name,
            parsed_documents,
        )
        return DossierConsistencyReport(
            application_id=application.id,
            application_code=application.code,
            generated_at=generated_at or datetime.now(UTC),
            parser_version=self.parser.version,
            check_count=len(checks),
            pass_count=sum(item.status.value == "pass" for item in checks),
            mismatch_count=sum(
                item.status.value == "mismatch" for item in checks
            ),
            insufficient_count=sum(
                item.status.value == "insufficient" for item in checks
            ),
            unreadable_evidence=unreadable,
            checks=checks,
        )

    async def _parse_evidence(
        self,
        evidence: DossierEvidenceRead,
    ) -> tuple[EvidenceText | None, UnreadableEvidence | None]:
        if self.storage is None:
            return None, None
        try:
            data = await self.storage.get(evidence.object_key)
            text = await asyncio.to_thread(
                self.parser.extract,
                evidence.file_name,
                data,
            )
            return (
                EvidenceText(
                    evidence_id=evidence.id,
                    category_key=evidence.category_key,
                    file_name=evidence.file_name,
                    text=text,
                ),
                None,
            )
        except Exception as exc:
            reason = str(exc).strip() or type(exc).__name__
            return (
                None,
                UnreadableEvidence(
                    evidence_id=evidence.id,
                    category_key=evidence.category_key,
                    file_name=evidence.file_name,
                    reason=reason[:240],
                ),
            )

    @staticmethod
    def _get_requirement(
        application: RegistrationApplicationRead,
        category_key: DossierCategory,
    ) -> DossierRequirement:
        requirement = next(
            (
                item
                for item in application.requirements
                if item.key == category_key
            ),
            None,
        )
        if requirement is None:
            raise RequirementNotFoundError(category_key.value)
        return requirement
