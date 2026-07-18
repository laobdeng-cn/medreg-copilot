import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medreg.modules.documents.models import DocumentChunkModel, RegulationDocumentModel
from medreg.modules.documents.schemas import ParseStatus
from medreg.modules.regulations.models import (
    RegulationSourceModel,
    RegulationVersionModel,
)
from medreg.modules.retrieval.models import DocumentVectorIndexModel
from medreg.modules.retrieval.schemas import (
    IndexChunkInput,
    IndexDocumentInput,
    VectorIndexRead,
)


class RetrievalRepository(Protocol):
    async def get_index(self, document_id: uuid.UUID) -> VectorIndexRead | None: ...

    async def save_index(
        self,
        index: VectorIndexRead,
        expected_task_id: str | None = None,
    ) -> VectorIndexRead | None: ...

    async def get_index_input(
        self, document_id: uuid.UUID
    ) -> IndexDocumentInput | None: ...


class SQLAlchemyRetrievalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_index(self, document_id: uuid.UUID) -> VectorIndexRead | None:
        model = await self.session.get(DocumentVectorIndexModel, document_id)
        return self._to_read_model(model) if model is not None else None

    async def save_index(
        self,
        index: VectorIndexRead,
        expected_task_id: str | None = None,
    ) -> VectorIndexRead | None:
        model = await self.session.scalar(
            select(DocumentVectorIndexModel)
            .where(DocumentVectorIndexModel.document_id == index.document_id)
            .with_for_update()
        )
        if expected_task_id is not None and (
            model is None or model.task_id != expected_task_id
        ):
            await self.session.rollback()
            return self._to_read_model(model) if model is not None else None
        if model is None:
            model = DocumentVectorIndexModel(**index.model_dump())
            self.session.add(model)
        else:
            for field, value in index.model_dump().items():
                setattr(model, field, value)
        await self.session.commit()
        return self._to_read_model(model)

    async def get_index_input(
        self, document_id: uuid.UUID
    ) -> IndexDocumentInput | None:
        row = (
            await self.session.execute(
                select(
                    RegulationDocumentModel,
                    RegulationVersionModel,
                    RegulationSourceModel,
                )
                .join(
                    RegulationVersionModel,
                    RegulationVersionModel.id
                    == RegulationDocumentModel.regulation_version_id,
                )
                .join(
                    RegulationSourceModel,
                    RegulationSourceModel.id == RegulationVersionModel.source_id,
                )
                .where(RegulationDocumentModel.id == document_id)
            )
        ).one_or_none()
        if row is None:
            return None
        document, version, source = row
        if (
            document.parse_status != ParseStatus.COMPLETED.value
            or not document.parser_version
            or not document.segmenter_version
        ):
            return None
        chunk_result = await self.session.scalars(
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.ordinal)
        )
        chunks = [
            IndexChunkInput(
                id=chunk.id,
                section_id=chunk.section_id,
                ordinal=chunk.ordinal,
                citation_label=chunk.citation_label,
                content=chunk.content,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                content_hash=chunk.content_hash,
            )
            for chunk in chunk_result.all()
        ]
        if not chunks:
            return None
        return IndexDocumentInput(
            document_id=document.id,
            regulation_version_id=version.id,
            source_id=source.id,
            source_title=source.title,
            issuing_authority=source.issuing_authority,
            version_label=version.version_label,
            document_number=version.document_number,
            parser_version=document.parser_version,
            segmenter_version=document.segmenter_version,
            chunks=chunks,
        )

    @staticmethod
    def _to_read_model(model: DocumentVectorIndexModel) -> VectorIndexRead:
        return VectorIndexRead(
            document_id=model.document_id,
            status=model.status,
            attempts=model.attempts,
            task_id=model.task_id,
            collection_name=model.collection_name,
            dense_model=model.dense_model,
            sparse_model=model.sparse_model,
            content_fingerprint=model.content_fingerprint,
            indexed_chunk_count=model.indexed_chunk_count,
            index_error=model.index_error,
            queued_at=model.queued_at,
            processing_started_at=model.processing_started_at,
            indexed_at=model.indexed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
