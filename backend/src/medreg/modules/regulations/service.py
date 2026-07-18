import secrets
import uuid
from datetime import UTC, date, datetime

from medreg.modules.regulations.repository import RegulationRepository
from medreg.modules.regulations.schemas import (
    LifecycleStatus,
    RegulationSourceCreate,
    RegulationSourceList,
    RegulationSourceRead,
    RegulationVersionCreate,
    RegulationVersionRead,
    ReviewStatus,
    VersionReviewCreate,
)


class RegulationSourceNotFoundError(LookupError):
    pass


class RegulationVersionNotFoundError(LookupError):
    pass


class RegulationVersionAlreadyExistsError(ValueError):
    pass


class RegulationService:
    def __init__(self, repository: RegulationRepository) -> None:
        self.repository = repository

    async def create(self, payload: RegulationSourceCreate) -> RegulationSourceRead:
        now = datetime.now(UTC)
        source = RegulationSourceRead(
            id=uuid.uuid4(),
            code=await self._next_code(now.year),
            title=payload.title,
            issuing_authority=payload.issuing_authority,
            jurisdiction=payload.jurisdiction,
            regulation_type=payload.regulation_type,
            scope_summary=payload.scope_summary,
            versions=[
                RegulationVersionRead(
                    id=uuid.uuid4(),
                    **payload.initial_version.model_dump(),
                    review_status=ReviewStatus.PENDING_REVIEW,
                    reviewed_by=None,
                    reviewed_at=None,
                    review_note=None,
                    created_at=now,
                    updated_at=now,
                )
            ],
            created_at=now,
            updated_at=now,
        )
        created = await self.repository.add(source)
        return self._apply_as_of(created, date.today())

    async def list(self, as_of: date) -> RegulationSourceList:
        sources = [self._apply_as_of(item, as_of) for item in await self.repository.list()]
        return RegulationSourceList(items=sources, total=len(sources), as_of=as_of)

    async def add_version(
        self,
        source_id: uuid.UUID,
        payload: RegulationVersionCreate,
        as_of: date,
    ) -> RegulationSourceRead:
        existing = await self.repository.get(source_id)
        if existing is None:
            raise RegulationSourceNotFoundError(str(source_id))
        if any(version.version_label == payload.version_label for version in existing.versions):
            raise RegulationVersionAlreadyExistsError(payload.version_label)

        now = datetime.now(UTC)
        version = RegulationVersionRead(
            id=uuid.uuid4(),
            **payload.model_dump(),
            review_status=ReviewStatus.PENDING_REVIEW,
            reviewed_by=None,
            reviewed_at=None,
            review_note=None,
            created_at=now,
            updated_at=now,
        )
        updated = await self.repository.add_version(source_id, version)
        if updated is None:
            raise RegulationSourceNotFoundError(str(source_id))
        return self._apply_as_of(updated, as_of)

    async def get(self, source_id: uuid.UUID, as_of: date) -> RegulationSourceRead:
        source = await self.repository.get(source_id)
        if source is None:
            raise RegulationSourceNotFoundError(str(source_id))
        return self._apply_as_of(source, as_of)

    async def review_version(
        self,
        source_id: uuid.UUID,
        version_id: uuid.UUID,
        payload: VersionReviewCreate,
        as_of: date,
    ) -> RegulationSourceRead:
        existing = await self.repository.get(source_id)
        if existing is None:
            raise RegulationSourceNotFoundError(str(source_id))
        if all(version.id != version_id for version in existing.versions):
            raise RegulationVersionNotFoundError(str(version_id))
        reviewed = await self.repository.review_version(
            source_id=source_id,
            version_id=version_id,
            decision=payload.decision,
            reviewed_by=payload.reviewed_by,
            reviewed_at=datetime.now(UTC),
            note=payload.note,
        )
        if reviewed is None:
            raise RegulationVersionNotFoundError(str(version_id))
        return self._apply_as_of(reviewed, as_of)

    @staticmethod
    def _apply_as_of(source: RegulationSourceRead, as_of: date) -> RegulationSourceRead:
        versions = []
        ordered_versions = sorted(
            source.versions,
            key=lambda version: (version.effective_on, version.published_on, version.created_at),
            reverse=True,
        )
        for version in ordered_versions:
            if version.expires_on is not None and as_of > version.expires_on:
                lifecycle = LifecycleStatus.EXPIRED
            elif version.effective_on > as_of:
                lifecycle = LifecycleStatus.UPCOMING
            else:
                lifecycle = LifecycleStatus.EFFECTIVE
            versions.append(version.model_copy(update={"lifecycle_status": lifecycle}))

        applicable_candidates = [
            version
            for version in versions
            if version.review_status == ReviewStatus.VERIFIED
            and version.lifecycle_status == LifecycleStatus.EFFECTIVE
        ]
        applicable = max(
            applicable_candidates,
            key=lambda version: (version.effective_on, version.published_on),
            default=None,
        )
        return source.model_copy(
            update={"versions": versions, "applicable_version": applicable}
        )

    async def _next_code(self, year: int) -> str:
        while True:
            code = f"REG-{year}-{secrets.token_hex(3).upper()}"
            if not await self.repository.code_exists(code):
                return code
