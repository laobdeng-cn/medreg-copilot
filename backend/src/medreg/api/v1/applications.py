import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status

from medreg.api.dependencies import (
    ApplicationServiceDependency,
    ReaderActor,
    ReviewerActor,
    SecurityServiceDependency,
    WriterActor,
)
from medreg.modules.applications.report import render_internal_precheck_report
from medreg.modules.applications.schemas import (
    DOSSIER_CATEGORY_DEFINITIONS,
    DossierCategory,
    DossierCategoryDefinition,
    DossierConsistencyReport,
    DossierEvidenceList,
    DossierEvidenceRead,
    EvidenceMatrix,
    FindingRemediationUpdate,
    InternalPrecheckReport,
    PrecheckCreate,
    PrecheckFinding,
    PrecheckRun,
    PrecheckRunList,
    RegistrationApplicationCreate,
    RegistrationApplicationList,
    RegistrationApplicationRead,
    RequirementReviewCreate,
)
from medreg.modules.applications.service import (
    ApplicationNotFoundError,
    DuplicateEvidenceError,
    EvidenceValidationError,
    FindingRemediationStateError,
    PrecheckFindingNotFoundError,
    PrecheckReportUnavailableError,
    RequirementNotFoundError,
    RequirementStateError,
)

router = APIRouter(tags=["registration applications"])


@router.get("/registration-applications", response_model=RegistrationApplicationList)
async def list_registration_applications(
    service: ApplicationServiceDependency,
) -> RegistrationApplicationList:
    return await service.list()


@router.post(
    "/registration-applications",
    response_model=RegistrationApplicationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_registration_application(
    payload: RegistrationApplicationCreate,
    service: ApplicationServiceDependency,
    actor: WriterActor,
    security: SecurityServiceDependency,
) -> RegistrationApplicationRead:
    application = await service.create(payload)
    await security.record(
        actor,
        action="application.created",
        resource_type="registration_application",
        resource_id=application.id,
        request_method="POST",
        request_path="/registration-applications",
        status_code=status.HTTP_201_CREATED,
        detail={"code": application.code, "device_class": application.device_class.value},
    )
    return application


@router.get(
    "/registration-applications/{application_id}",
    response_model=RegistrationApplicationRead,
)
async def get_registration_application(
    application_id: uuid.UUID,
    service: ApplicationServiceDependency,
) -> RegistrationApplicationRead:
    try:
        return await service.get(application_id)
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Registration application not found") from exc


@router.post(
    "/registration-applications/{application_id}/requirements/{category_key}/evidence",
    response_model=DossierEvidenceRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dossier_evidence(
    application_id: uuid.UUID,
    category_key: DossierCategory,
    service: ApplicationServiceDependency,
    actor: WriterActor,
    security: SecurityServiceDependency,
    file: Annotated[UploadFile, File()],
    uploaded_by: Annotated[str, Form(min_length=2, max_length=80)],
) -> DossierEvidenceRead:
    data = await file.read(service.max_upload_bytes + 1)
    try:
        evidence = await service.archive_evidence(
            application_id=application_id,
            category_key=category_key,
            file_name=file.filename or "",
            content_type=file.content_type,
            data=data,
            uploaded_by=uploaded_by,
        )
        await security.record(
            actor,
            action="evidence.archived",
            resource_type="dossier_evidence",
            resource_id=evidence.id,
            request_method="POST",
            request_path=(
                f"/registration-applications/{application_id}/requirements/"
                f"{category_key.value}/evidence"
            ),
            status_code=status.HTTP_201_CREATED,
            detail={
                "application_id": str(application_id),
                "category_key": category_key.value,
                "sha256": evidence.sha256,
                "size_bytes": evidence.size_bytes,
            },
        )
        return evidence
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Registration application not found") from exc
    except RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dossier requirement not found") from exc
    except DuplicateEvidenceError as exc:
        raise HTTPException(
            status_code=409,
            detail="This exact file is already archived for the dossier category",
        ) from exc
    except EvidenceValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/registration-applications/{application_id}/requirements/{category_key}/evidence",
    response_model=DossierEvidenceList,
)
async def list_dossier_evidence(
    application_id: uuid.UUID,
    category_key: DossierCategory,
    service: ApplicationServiceDependency,
) -> DossierEvidenceList:
    try:
        return await service.list_evidence(application_id, category_key)
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Registration application not found") from exc
    except RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dossier requirement not found") from exc


@router.patch(
    "/registration-applications/{application_id}/requirements/{category_key}/review",
    response_model=RegistrationApplicationRead,
)
async def review_dossier_requirement(
    application_id: uuid.UUID,
    category_key: DossierCategory,
    payload: RequirementReviewCreate,
    service: ApplicationServiceDependency,
    actor: ReviewerActor,
    security: SecurityServiceDependency,
) -> RegistrationApplicationRead:
    try:
        application = await service.review_requirement(
            application_id, category_key, payload
        )
        await security.record(
            actor,
            action="requirement.reviewed",
            resource_type="dossier_requirement",
            resource_id=f"{application_id}:{category_key.value}",
            request_method="PATCH",
            request_path=(
                f"/registration-applications/{application_id}/requirements/"
                f"{category_key.value}/review"
            ),
            status_code=status.HTTP_200_OK,
            detail={"decision": payload.decision.value},
        )
        return application
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Registration application not found") from exc
    except RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dossier requirement not found") from exc
    except RequirementStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/registration-applications/{application_id}/prechecks",
    response_model=PrecheckRun,
    status_code=status.HTTP_201_CREATED,
)
async def run_registration_precheck(
    application_id: uuid.UUID,
    payload: PrecheckCreate,
    service: ApplicationServiceDependency,
    actor: WriterActor,
    security: SecurityServiceDependency,
) -> PrecheckRun:
    try:
        run = await service.run_precheck(application_id, payload)
        await security.record(
            actor,
            action="precheck.completed",
            resource_type="precheck_run",
            resource_id=run.id,
            request_method="POST",
            request_path=f"/registration-applications/{application_id}/prechecks",
            status_code=status.HTTP_201_CREATED,
            detail={
                "application_id": str(application_id),
                "blocker_count": run.blocker_count,
                "warning_count": run.warning_count,
            },
        )
        return run
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Registration application not found") from exc


@router.get(
    "/registration-applications/{application_id}/prechecks",
    response_model=PrecheckRunList,
)
async def list_registration_prechecks(
    application_id: uuid.UUID,
    service: ApplicationServiceDependency,
) -> PrecheckRunList:
    try:
        return await service.list_prechecks(application_id)
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Registration application not found") from exc


@router.get(
    "/registration-applications/{application_id}/evidence-matrix",
    response_model=EvidenceMatrix,
)
async def get_registration_evidence_matrix(
    application_id: uuid.UUID,
    service: ApplicationServiceDependency,
) -> EvidenceMatrix:
    try:
        return await service.get_evidence_matrix(application_id)
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Registration application not found") from exc


@router.get(
    "/registration-applications/{application_id}/consistency-report",
    response_model=DossierConsistencyReport,
)
async def get_registration_consistency_report(
    application_id: uuid.UUID,
    service: ApplicationServiceDependency,
) -> DossierConsistencyReport:
    try:
        return await service.get_consistency_report(application_id)
    except ApplicationNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Registration application not found",
        ) from exc


@router.get(
    "/registration-applications/{application_id}/precheck-report",
    response_model=InternalPrecheckReport,
)
async def get_internal_precheck_report(
    application_id: uuid.UUID,
    service: ApplicationServiceDependency,
) -> InternalPrecheckReport:
    try:
        return await service.get_internal_precheck_report(application_id)
    except ApplicationNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Registration application not found",
        ) from exc
    except PrecheckReportUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/registration-applications/{application_id}/precheck-report.pdf",
    response_class=Response,
)
async def download_internal_precheck_report(
    application_id: uuid.UUID,
    service: ApplicationServiceDependency,
    actor: ReaderActor,
    security: SecurityServiceDependency,
) -> Response:
    try:
        report = await service.get_internal_precheck_report(application_id)
    except ApplicationNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Registration application not found",
        ) from exc
    except PrecheckReportUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if report.is_stale:
        raise HTTPException(
            status_code=409,
            detail=report.stale_reason,
        )
    pdf = render_internal_precheck_report(report)
    await security.record(
        actor,
        action="precheck_report.exported",
        resource_type="precheck_report",
        resource_id=report.report_code,
        request_method="GET",
        request_path=f"/registration-applications/{application_id}/precheck-report.pdf",
        status_code=status.HTTP_200_OK,
        detail={
            "application_id": str(application_id),
            "precheck_run_id": str(report.precheck.id),
        },
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{report.report_code}.pdf"'
            ),
            "X-MedReg-Report-Code": report.report_code,
            "X-MedReg-Precheck-Run": str(report.precheck.id),
        },
    )


@router.patch(
    "/precheck-findings/{finding_id}/remediation",
    response_model=PrecheckFinding,
)
async def update_precheck_finding_remediation(
    finding_id: uuid.UUID,
    payload: FindingRemediationUpdate,
    service: ApplicationServiceDependency,
    actor: ReviewerActor,
    security: SecurityServiceDependency,
) -> PrecheckFinding:
    try:
        finding = await service.update_finding_remediation(finding_id, payload)
        await security.record(
            actor,
            action="finding.remediation_updated",
            resource_type="precheck_finding",
            resource_id=finding.id,
            request_method="PATCH",
            request_path=f"/precheck-findings/{finding_id}/remediation",
            status_code=status.HTTP_200_OK,
            detail={"status": finding.remediation_status.value},
        )
        return finding
    except PrecheckFindingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Precheck finding not found") from exc
    except FindingRemediationStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/taxonomy/dossier-categories",
    response_model=list[DossierCategoryDefinition],
)
async def list_dossier_categories() -> tuple[DossierCategoryDefinition, ...]:
    return DOSSIER_CATEGORY_DEFINITIONS
