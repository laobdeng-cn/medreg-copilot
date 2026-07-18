import asyncio
import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from medreg.modules.regulations.models import (
    RegulationSourceModel,
    RegulationVersionModel,
)
from medreg.modules.regulations.schemas import (
    RegulationSourceRead,
    RegulationVersionRead,
    ReviewDecision,
    ReviewStatus,
)


class RegulationRepository(Protocol):
    async def add(self, source: RegulationSourceRead) -> RegulationSourceRead: ...

    async def add_version(
        self, source_id: uuid.UUID, version: RegulationVersionRead
    ) -> RegulationSourceRead | None: ...

    async def list(self) -> list[RegulationSourceRead]: ...

    async def get(self, source_id: uuid.UUID) -> RegulationSourceRead | None: ...

    async def code_exists(self, code: str) -> bool: ...

    async def review_version(
        self,
        source_id: uuid.UUID,
        version_id: uuid.UUID,
        decision: ReviewDecision,
        reviewed_by: str,
        reviewed_at: datetime,
        note: str,
    ) -> RegulationSourceRead | None: ...


class InMemoryRegulationRepository:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, RegulationSourceRead] = {}
        self._lock = asyncio.Lock()

    async def add(self, source: RegulationSourceRead) -> RegulationSourceRead:
        async with self._lock:
            self._items[source.id] = source.model_copy(deep=True)
        return source.model_copy(deep=True)

    async def add_version(
        self, source_id: uuid.UUID, version: RegulationVersionRead
    ) -> RegulationSourceRead | None:
        async with self._lock:
            source = self._items.get(source_id)
            if source is None:
                return None
            updated = source.model_copy(
                update={
                    "versions": [*source.versions, version],
                    "updated_at": version.updated_at,
                }
            )
            self._items[source_id] = updated.model_copy(deep=True)
        return updated.model_copy(deep=True)

    async def list(self) -> list[RegulationSourceRead]:
        async with self._lock:
            items = [item.model_copy(deep=True) for item in self._items.values()]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    async def get(self, source_id: uuid.UUID) -> RegulationSourceRead | None:
        async with self._lock:
            item = self._items.get(source_id)
        return item.model_copy(deep=True) if item else None

    async def code_exists(self, code: str) -> bool:
        async with self._lock:
            return any(item.code == code for item in self._items.values())

    async def review_version(
        self,
        source_id: uuid.UUID,
        version_id: uuid.UUID,
        decision: ReviewDecision,
        reviewed_by: str,
        reviewed_at: datetime,
        note: str,
    ) -> RegulationSourceRead | None:
        async with self._lock:
            source = self._items.get(source_id)
            if source is None:
                return None
            versions = []
            found = False
            for version in source.versions:
                if version.id == version_id:
                    found = True
                    versions.append(
                        version.model_copy(
                            update={
                                "review_status": ReviewStatus(decision.value),
                                "reviewed_by": reviewed_by,
                                "reviewed_at": reviewed_at,
                                "review_note": note,
                                "updated_at": reviewed_at,
                            }
                        )
                    )
                else:
                    versions.append(version)
            if not found:
                return source.model_copy(deep=True)
            updated = source.model_copy(
                update={"versions": versions, "updated_at": reviewed_at}
            )
            self._items[source_id] = updated.model_copy(deep=True)
        return updated.model_copy(deep=True)

    async def clear(self) -> None:
        async with self._lock:
            self._items.clear()


class SQLAlchemyRegulationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, source: RegulationSourceRead) -> RegulationSourceRead:
        model = RegulationSourceModel(
            id=source.id,
            code=source.code,
            title=source.title,
            issuing_authority=source.issuing_authority,
            jurisdiction=source.jurisdiction,
            regulation_type=source.regulation_type.value,
            scope_summary=source.scope_summary,
            created_at=source.created_at,
            updated_at=source.updated_at,
            versions=[self._version_to_model(version) for version in source.versions],
        )
        self.session.add(model)
        await self.session.commit()
        return self._to_read_model(model)

    async def add_version(
        self, source_id: uuid.UUID, version: RegulationVersionRead
    ) -> RegulationSourceRead | None:
        source = await self.session.get(RegulationSourceModel, source_id)
        if source is None:
            return None
        model = self._version_to_model(version)
        model.source_id = source_id
        source.updated_at = version.updated_at
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(source, attribute_names=["versions"])
        return self._to_read_model(source)

    async def list(self) -> list[RegulationSourceRead]:
        result = await self.session.scalars(
            select(RegulationSourceModel)
            .options(selectinload(RegulationSourceModel.versions))
            .order_by(RegulationSourceModel.created_at.desc())
        )
        return [self._to_read_model(model) for model in result.unique().all()]

    async def get(self, source_id: uuid.UUID) -> RegulationSourceRead | None:
        model = await self.session.scalar(
            select(RegulationSourceModel)
            .options(selectinload(RegulationSourceModel.versions))
            .where(RegulationSourceModel.id == source_id)
        )
        return self._to_read_model(model) if model is not None else None

    async def code_exists(self, code: str) -> bool:
        return bool(
            await self.session.scalar(
                select(exists().where(RegulationSourceModel.code == code))
            )
        )

    async def review_version(
        self,
        source_id: uuid.UUID,
        version_id: uuid.UUID,
        decision: ReviewDecision,
        reviewed_by: str,
        reviewed_at: datetime,
        note: str,
    ) -> RegulationSourceRead | None:
        version = await self.session.scalar(
            select(RegulationVersionModel).where(
                RegulationVersionModel.id == version_id,
                RegulationVersionModel.source_id == source_id,
            )
        )
        if version is None:
            return None
        version.review_status = decision.value
        version.reviewed_by = reviewed_by
        version.reviewed_at = reviewed_at
        version.review_note = note
        version.updated_at = reviewed_at
        source = await self.session.get(RegulationSourceModel, source_id)
        if source is not None:
            source.updated_at = reviewed_at
        await self.session.commit()
        return await self.get(source_id)

    @staticmethod
    def _version_to_model(version: RegulationVersionRead) -> RegulationVersionModel:
        return RegulationVersionModel(
            id=version.id,
            version_label=version.version_label,
            document_number=version.document_number,
            official_url=str(version.official_url),
            published_on=version.published_on,
            effective_on=version.effective_on,
            expires_on=version.expires_on,
            review_status=version.review_status.value,
            reviewed_by=version.reviewed_by,
            reviewed_at=version.reviewed_at,
            review_note=version.review_note,
            created_at=version.created_at,
            updated_at=version.updated_at,
        )

    @staticmethod
    def _to_read_model(model: RegulationSourceModel) -> RegulationSourceRead:
        versions = [
            RegulationVersionRead(
                id=version.id,
                version_label=version.version_label,
                document_number=version.document_number,
                official_url=version.official_url,
                published_on=version.published_on,
                effective_on=version.effective_on,
                expires_on=version.expires_on,
                review_status=version.review_status,
                reviewed_by=version.reviewed_by,
                reviewed_at=version.reviewed_at,
                review_note=version.review_note,
                created_at=version.created_at,
                updated_at=version.updated_at,
            )
            for version in sorted(
                model.versions,
                key=lambda item: (item.effective_on, item.created_at),
                reverse=True,
            )
        ]
        return RegulationSourceRead(
            id=model.id,
            code=model.code,
            title=model.title,
            issuing_authority=model.issuing_authority,
            jurisdiction=model.jurisdiction,
            regulation_type=model.regulation_type,
            scope_summary=model.scope_summary,
            versions=versions,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
