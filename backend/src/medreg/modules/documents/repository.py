import asyncio
import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy import delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from medreg.modules.documents.models import (
    DocumentChunkModel,
    DocumentFetchRequestModel,
    DocumentSectionModel,
    DocumentTableModel,
    RegulationDocumentModel,
)
from medreg.modules.documents.schemas import (
    DocumentChunkRead,
    DocumentFetchRequestRead,
    DocumentSectionRead,
    DocumentStructureRead,
    DocumentTableRead,
    ParseStatus,
    RegulationDocumentRead,
)
from medreg.modules.regulations.models import RegulationVersionModel


class DocumentRepository(Protocol):
    async def version_exists(self, version_id: uuid.UUID) -> bool: ...

    async def add(self, document: RegulationDocumentRead) -> RegulationDocumentRead: ...

    async def get(self, document_id: uuid.UUID) -> RegulationDocumentRead | None: ...

    async def get_by_sha256(
        self, version_id: uuid.UUID, sha256: str
    ) -> RegulationDocumentRead | None: ...

    async def list_for_version(
        self, version_id: uuid.UUID
    ) -> list[RegulationDocumentRead]: ...

    async def update_parse(
        self,
        document_id: uuid.UUID,
        status: ParseStatus,
        attempts: int,
        task_id: str | None,
        parser_version: str | None,
        extracted_text: str | None,
        error: str | None,
        queued_at: datetime | None,
        processing_started_at: datetime | None,
        parsed_at: datetime | None,
        updated_at: datetime,
        expected_task_id: str | None = None,
    ) -> RegulationDocumentRead | None: ...

    async def list_stale_parses(
        self, cutoff: datetime
    ) -> list[RegulationDocumentRead]: ...

    async def replace_structure(
        self,
        document_id: uuid.UUID,
        sections: list[DocumentSectionRead],
        chunks: list[DocumentChunkRead],
        tables: list[DocumentTableRead],
        segmenter_version: str,
        updated_at: datetime,
        expected_task_id: str | None = None,
    ) -> DocumentStructureRead | None: ...

    async def get_structure(
        self, document_id: uuid.UUID
    ) -> DocumentStructureRead | None: ...

    async def clear_structure(self, document_id: uuid.UUID) -> bool: ...

    async def add_fetch_request(
        self, request: DocumentFetchRequestRead
    ) -> DocumentFetchRequestRead: ...

    async def get_fetch_request(
        self, request_id: uuid.UUID
    ) -> DocumentFetchRequestRead | None: ...

    async def list_fetch_requests(
        self, version_id: uuid.UUID
    ) -> list[DocumentFetchRequestRead]: ...

    async def save_fetch_request(
        self, request: DocumentFetchRequestRead
    ) -> DocumentFetchRequestRead: ...


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, RegulationDocumentRead] = {}
        self._fetch_requests: dict[uuid.UUID, DocumentFetchRequestRead] = {}
        self._structures: dict[uuid.UUID, DocumentStructureRead] = {}
        self._version_ids: set[uuid.UUID] = set()
        self._lock = asyncio.Lock()

    async def register_version(self, version_id: uuid.UUID) -> None:
        async with self._lock:
            self._version_ids.add(version_id)

    async def version_exists(self, version_id: uuid.UUID) -> bool:
        async with self._lock:
            return version_id in self._version_ids

    async def add(self, document: RegulationDocumentRead) -> RegulationDocumentRead:
        async with self._lock:
            self._items[document.id] = document.model_copy(deep=True)
        return document.model_copy(deep=True)

    async def get(self, document_id: uuid.UUID) -> RegulationDocumentRead | None:
        async with self._lock:
            item = self._items.get(document_id)
        return item.model_copy(deep=True) if item else None

    async def get_by_sha256(
        self, version_id: uuid.UUID, sha256: str
    ) -> RegulationDocumentRead | None:
        async with self._lock:
            item = next(
                (
                    item
                    for item in self._items.values()
                    if item.regulation_version_id == version_id and item.sha256 == sha256
                ),
                None,
            )
        return item.model_copy(deep=True) if item else None

    async def list_for_version(
        self, version_id: uuid.UUID
    ) -> list[RegulationDocumentRead]:
        async with self._lock:
            items = [
                item.model_copy(deep=True)
                for item in self._items.values()
                if item.regulation_version_id == version_id
            ]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    async def update_parse(
        self,
        document_id: uuid.UUID,
        status: ParseStatus,
        attempts: int,
        task_id: str | None,
        parser_version: str | None,
        extracted_text: str | None,
        error: str | None,
        queued_at: datetime | None,
        processing_started_at: datetime | None,
        parsed_at: datetime | None,
        updated_at: datetime,
        expected_task_id: str | None = None,
    ) -> RegulationDocumentRead | None:
        async with self._lock:
            item = self._items.get(document_id)
            if item is None:
                return None
            if (
                expected_task_id is not None
                and item.parse_task_id != expected_task_id
            ):
                return item.model_copy(deep=True)
            updated = item.model_copy(
                update={
                    "parse_status": status,
                    "parse_attempts": attempts,
                    "parse_task_id": task_id,
                    "parser_version": parser_version,
                    "extracted_char_count": len(extracted_text or ""),
                    "parse_error": error,
                    "queued_at": queued_at,
                    "processing_started_at": processing_started_at,
                    "parsed_at": parsed_at,
                    "updated_at": updated_at,
                }
            )
            self._items[document_id] = updated.model_copy(deep=True)
        return updated.model_copy(deep=True)

    async def list_stale_parses(
        self, cutoff: datetime
    ) -> list[RegulationDocumentRead]:
        async with self._lock:
            items = [
                item.model_copy(deep=True)
                for item in self._items.values()
                if item.parse_status in {ParseStatus.QUEUED, ParseStatus.PROCESSING}
                and item.updated_at < cutoff
            ]
        return items

    async def replace_structure(
        self,
        document_id: uuid.UUID,
        sections: list[DocumentSectionRead],
        chunks: list[DocumentChunkRead],
        tables: list[DocumentTableRead],
        segmenter_version: str,
        updated_at: datetime,
        expected_task_id: str | None = None,
    ) -> DocumentStructureRead | None:
        async with self._lock:
            document = self._items.get(document_id)
            if document is None:
                return None
            if (
                expected_task_id is not None
                and document.parse_task_id != expected_task_id
            ):
                return None
            updated = document.model_copy(
                update={
                    "segmenter_version": segmenter_version,
                    "section_count": len(sections),
                    "chunk_count": len(chunks),
                    "table_count": len(tables),
                    "updated_at": updated_at,
                }
            )
            self._items[document_id] = updated.model_copy(deep=True)
            structure = DocumentStructureRead(
                document_id=document_id,
                parser_version=updated.parser_version,
                segmenter_version=segmenter_version,
                section_count=len(sections),
                chunk_count=len(chunks),
                table_count=len(tables),
                sections=sections,
                chunks=chunks,
                tables=tables,
            )
            self._structures[document_id] = structure.model_copy(deep=True)
        return structure.model_copy(deep=True)

    async def get_structure(
        self, document_id: uuid.UUID
    ) -> DocumentStructureRead | None:
        async with self._lock:
            structure = self._structures.get(document_id)
        return structure.model_copy(deep=True) if structure else None

    async def clear_structure(self, document_id: uuid.UUID) -> bool:
        async with self._lock:
            document = self._items.get(document_id)
            if document is None:
                return False
            self._structures.pop(document_id, None)
            self._items[document_id] = document.model_copy(
                update={
                    "segmenter_version": None,
                    "section_count": 0,
                    "chunk_count": 0,
                    "table_count": 0,
                },
                deep=True,
            )
        return True

    async def add_fetch_request(
        self, request: DocumentFetchRequestRead
    ) -> DocumentFetchRequestRead:
        async with self._lock:
            self._fetch_requests[request.id] = request.model_copy(deep=True)
        return request.model_copy(deep=True)

    async def get_fetch_request(
        self, request_id: uuid.UUID
    ) -> DocumentFetchRequestRead | None:
        async with self._lock:
            request = self._fetch_requests.get(request_id)
        return request.model_copy(deep=True) if request else None

    async def list_fetch_requests(
        self, version_id: uuid.UUID
    ) -> list[DocumentFetchRequestRead]:
        async with self._lock:
            items = [
                item.model_copy(deep=True)
                for item in self._fetch_requests.values()
                if item.regulation_version_id == version_id
            ]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    async def save_fetch_request(
        self, request: DocumentFetchRequestRead
    ) -> DocumentFetchRequestRead:
        async with self._lock:
            self._fetch_requests[request.id] = request.model_copy(deep=True)
        return request.model_copy(deep=True)

    async def clear(self) -> None:
        async with self._lock:
            self._items.clear()
            self._fetch_requests.clear()
            self._structures.clear()
            self._version_ids.clear()


class SQLAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def version_exists(self, version_id: uuid.UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(exists().where(RegulationVersionModel.id == version_id))
            )
        )

    async def add(self, document: RegulationDocumentRead) -> RegulationDocumentRead:
        model = RegulationDocumentModel(
            id=document.id,
            code=document.code,
            regulation_version_id=document.regulation_version_id,
            file_name=document.file_name,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            sha256=document.sha256,
            security_status=document.security_status.value,
            security_engine=document.security_engine,
            detected_type=document.detected_type,
            security_findings=document.security_findings,
            bucket_name=document.bucket_name,
            object_key=document.object_key,
            storage_status=document.storage_status.value,
            parse_status=document.parse_status.value,
            parse_attempts=document.parse_attempts,
            parse_task_id=document.parse_task_id,
            parser_version=document.parser_version,
            segmenter_version=document.segmenter_version,
            section_count=document.section_count,
            chunk_count=document.chunk_count,
            table_count=document.table_count,
            extracted_text=None,
            extracted_char_count=document.extracted_char_count,
            parse_error=document.parse_error,
            uploaded_by=document.uploaded_by,
            queued_at=document.queued_at,
            processing_started_at=document.processing_started_at,
            parsed_at=document.parsed_at,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
        self.session.add(model)
        await self.session.commit()
        return self._to_read_model(model)

    async def get(self, document_id: uuid.UUID) -> RegulationDocumentRead | None:
        model = await self.session.get(RegulationDocumentModel, document_id)
        return self._to_read_model(model) if model is not None else None

    async def get_by_sha256(
        self, version_id: uuid.UUID, sha256: str
    ) -> RegulationDocumentRead | None:
        model = await self.session.scalar(
            select(RegulationDocumentModel).where(
                RegulationDocumentModel.regulation_version_id == version_id,
                RegulationDocumentModel.sha256 == sha256,
            )
        )
        return self._to_read_model(model) if model is not None else None

    async def list_for_version(
        self, version_id: uuid.UUID
    ) -> list[RegulationDocumentRead]:
        result = await self.session.scalars(
            select(RegulationDocumentModel)
            .where(RegulationDocumentModel.regulation_version_id == version_id)
            .order_by(RegulationDocumentModel.created_at.desc())
        )
        return [self._to_read_model(model) for model in result.all()]

    async def update_parse(
        self,
        document_id: uuid.UUID,
        status: ParseStatus,
        attempts: int,
        task_id: str | None,
        parser_version: str | None,
        extracted_text: str | None,
        error: str | None,
        queued_at: datetime | None,
        processing_started_at: datetime | None,
        parsed_at: datetime | None,
        updated_at: datetime,
        expected_task_id: str | None = None,
    ) -> RegulationDocumentRead | None:
        if expected_task_id is not None:
            await self.session.execute(
                update(RegulationDocumentModel)
                .where(
                    RegulationDocumentModel.id == document_id,
                    RegulationDocumentModel.parse_task_id == expected_task_id,
                )
                .values(
                    parse_status=status.value,
                    parse_attempts=attempts,
                    parse_task_id=task_id,
                    parser_version=parser_version,
                    extracted_text=extracted_text,
                    extracted_char_count=len(extracted_text or ""),
                    parse_error=error,
                    queued_at=queued_at,
                    processing_started_at=processing_started_at,
                    parsed_at=parsed_at,
                    updated_at=updated_at,
                )
            )
            await self.session.commit()
            self.session.expire_all()
            return await self.get(document_id)

        model = await self.session.get(RegulationDocumentModel, document_id)
        if model is None:
            return None
        model.parse_status = status.value
        model.parse_attempts = attempts
        model.parse_task_id = task_id
        model.parser_version = parser_version
        model.extracted_text = extracted_text
        model.extracted_char_count = len(extracted_text or "")
        model.parse_error = error
        model.queued_at = queued_at
        model.processing_started_at = processing_started_at
        model.parsed_at = parsed_at
        model.updated_at = updated_at
        await self.session.commit()
        return self._to_read_model(model)

    async def list_stale_parses(
        self, cutoff: datetime
    ) -> list[RegulationDocumentRead]:
        result = await self.session.scalars(
            select(RegulationDocumentModel).where(
                RegulationDocumentModel.parse_status.in_(
                    [ParseStatus.QUEUED.value, ParseStatus.PROCESSING.value]
                ),
                RegulationDocumentModel.updated_at < cutoff,
            )
        )
        return [self._to_read_model(model) for model in result.all()]

    async def replace_structure(
        self,
        document_id: uuid.UUID,
        sections: list[DocumentSectionRead],
        chunks: list[DocumentChunkRead],
        tables: list[DocumentTableRead],
        segmenter_version: str,
        updated_at: datetime,
        expected_task_id: str | None = None,
    ) -> DocumentStructureRead | None:
        model = await self.session.scalar(
            select(RegulationDocumentModel)
            .where(RegulationDocumentModel.id == document_id)
            .with_for_update()
        )
        if model is None:
            return None
        if expected_task_id is not None and model.parse_task_id != expected_task_id:
            await self.session.rollback()
            return None
        await self.session.execute(
            delete(DocumentChunkModel).where(
                DocumentChunkModel.document_id == document_id
            )
        )
        await self.session.execute(
            delete(DocumentTableModel).where(
                DocumentTableModel.document_id == document_id
            )
        )
        await self.session.execute(
            delete(DocumentSectionModel).where(
                DocumentSectionModel.document_id == document_id
            )
        )
        self.session.add_all(
            [self._section_to_model(section) for section in sections]
        )
        await self.session.flush()
        self.session.add_all([self._chunk_to_model(chunk) for chunk in chunks])
        self.session.add_all([self._table_to_model(table) for table in tables])
        model.segmenter_version = segmenter_version
        model.section_count = len(sections)
        model.chunk_count = len(chunks)
        model.table_count = len(tables)
        model.updated_at = updated_at
        await self.session.commit()
        return await self.get_structure(document_id)

    async def get_structure(
        self, document_id: uuid.UUID
    ) -> DocumentStructureRead | None:
        document = await self.session.get(RegulationDocumentModel, document_id)
        if document is None:
            return None
        section_result = await self.session.scalars(
            select(DocumentSectionModel)
            .where(DocumentSectionModel.document_id == document_id)
            .order_by(DocumentSectionModel.ordinal)
        )
        chunk_result = await self.session.scalars(
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.ordinal)
        )
        table_result = await self.session.scalars(
            select(DocumentTableModel)
            .where(DocumentTableModel.document_id == document_id)
            .order_by(DocumentTableModel.ordinal)
        )
        sections = [
            self._section_to_read_model(model) for model in section_result.all()
        ]
        chunks = [self._chunk_to_read_model(model) for model in chunk_result.all()]
        tables = [self._table_to_read_model(model) for model in table_result.all()]
        return DocumentStructureRead(
            document_id=document_id,
            parser_version=document.parser_version,
            segmenter_version=document.segmenter_version,
            section_count=len(sections),
            chunk_count=len(chunks),
            table_count=len(tables),
            sections=sections,
            chunks=chunks,
            tables=tables,
        )

    async def clear_structure(self, document_id: uuid.UUID) -> bool:
        model = await self.session.get(RegulationDocumentModel, document_id)
        if model is None:
            return False
        await self.session.execute(
            delete(DocumentChunkModel).where(
                DocumentChunkModel.document_id == document_id
            )
        )
        await self.session.execute(
            delete(DocumentTableModel).where(
                DocumentTableModel.document_id == document_id
            )
        )
        await self.session.execute(
            delete(DocumentSectionModel).where(
                DocumentSectionModel.document_id == document_id
            )
        )
        model.segmenter_version = None
        model.section_count = 0
        model.chunk_count = 0
        model.table_count = 0
        await self.session.commit()
        return True

    async def add_fetch_request(
        self, request: DocumentFetchRequestRead
    ) -> DocumentFetchRequestRead:
        model = self._fetch_to_model(request)
        self.session.add(model)
        await self.session.commit()
        return self._fetch_to_read_model(model)

    async def get_fetch_request(
        self, request_id: uuid.UUID
    ) -> DocumentFetchRequestRead | None:
        model = await self.session.get(DocumentFetchRequestModel, request_id)
        return self._fetch_to_read_model(model) if model is not None else None

    async def list_fetch_requests(
        self, version_id: uuid.UUID
    ) -> list[DocumentFetchRequestRead]:
        result = await self.session.scalars(
            select(DocumentFetchRequestModel)
            .where(DocumentFetchRequestModel.regulation_version_id == version_id)
            .order_by(DocumentFetchRequestModel.created_at.desc())
        )
        return [self._fetch_to_read_model(model) for model in result.all()]

    async def save_fetch_request(
        self, request: DocumentFetchRequestRead
    ) -> DocumentFetchRequestRead:
        model = await self.session.get(DocumentFetchRequestModel, request.id)
        if model is None:
            raise LookupError(str(request.id))
        model.status = request.status.value
        model.reviewed_by = request.reviewed_by
        model.review_note = request.review_note
        model.reviewed_at = request.reviewed_at
        model.task_id = request.task_id
        model.resulting_document_id = request.resulting_document_id
        model.fetch_error = request.fetch_error
        model.queued_at = request.queued_at
        model.started_at = request.started_at
        model.completed_at = request.completed_at
        model.updated_at = request.updated_at
        await self.session.commit()
        return self._fetch_to_read_model(model)

    @staticmethod
    def _to_read_model(model: RegulationDocumentModel) -> RegulationDocumentRead:
        return RegulationDocumentRead(
            id=model.id,
            code=model.code,
            regulation_version_id=model.regulation_version_id,
            file_name=model.file_name,
            content_type=model.content_type,
            size_bytes=model.size_bytes,
            sha256=model.sha256,
            security_status=model.security_status,
            security_engine=model.security_engine,
            detected_type=model.detected_type,
            security_findings=model.security_findings,
            bucket_name=model.bucket_name,
            object_key=model.object_key,
            storage_status=model.storage_status,
            parse_status=model.parse_status,
            parse_attempts=model.parse_attempts,
            parse_task_id=model.parse_task_id,
            parser_version=model.parser_version,
            segmenter_version=model.segmenter_version,
            section_count=model.section_count,
            chunk_count=model.chunk_count,
            table_count=model.table_count,
            extracted_char_count=model.extracted_char_count,
            parse_error=model.parse_error,
            uploaded_by=model.uploaded_by,
            queued_at=model.queued_at,
            processing_started_at=model.processing_started_at,
            parsed_at=model.parsed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _fetch_to_model(request: DocumentFetchRequestRead) -> DocumentFetchRequestModel:
        return DocumentFetchRequestModel(
            id=request.id,
            regulation_version_id=request.regulation_version_id,
            official_url=str(request.official_url),
            status=request.status.value,
            requested_by=request.requested_by,
            request_reason=request.request_reason,
            reviewed_by=request.reviewed_by,
            review_note=request.review_note,
            reviewed_at=request.reviewed_at,
            task_id=request.task_id,
            resulting_document_id=request.resulting_document_id,
            fetch_error=request.fetch_error,
            queued_at=request.queued_at,
            started_at=request.started_at,
            completed_at=request.completed_at,
            created_at=request.created_at,
            updated_at=request.updated_at,
        )

    @staticmethod
    def _fetch_to_read_model(
        model: DocumentFetchRequestModel,
    ) -> DocumentFetchRequestRead:
        return DocumentFetchRequestRead(
            id=model.id,
            regulation_version_id=model.regulation_version_id,
            official_url=model.official_url,
            status=model.status,
            requested_by=model.requested_by,
            request_reason=model.request_reason,
            reviewed_by=model.reviewed_by,
            review_note=model.review_note,
            reviewed_at=model.reviewed_at,
            task_id=model.task_id,
            resulting_document_id=model.resulting_document_id,
            fetch_error=model.fetch_error,
            queued_at=model.queued_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _section_to_model(section: DocumentSectionRead) -> DocumentSectionModel:
        return DocumentSectionModel(**section.model_dump())

    @staticmethod
    def _section_to_read_model(model: DocumentSectionModel) -> DocumentSectionRead:
        return DocumentSectionRead(
            id=model.id,
            document_id=model.document_id,
            parent_id=model.parent_id,
            kind=model.kind,
            ordinal=model.ordinal,
            heading=model.heading,
            citation_path=model.citation_path,
            content=model.content,
            char_start=model.char_start,
            char_end=model.char_end,
            content_hash=model.content_hash,
            created_at=model.created_at,
        )

    @staticmethod
    def _chunk_to_model(chunk: DocumentChunkRead) -> DocumentChunkModel:
        return DocumentChunkModel(**chunk.model_dump())

    @staticmethod
    def _chunk_to_read_model(model: DocumentChunkModel) -> DocumentChunkRead:
        return DocumentChunkRead(
            id=model.id,
            document_id=model.document_id,
            section_id=model.section_id,
            ordinal=model.ordinal,
            section_chunk_index=model.section_chunk_index,
            citation_label=model.citation_label,
            content=model.content,
            char_start=model.char_start,
            char_end=model.char_end,
            char_count=model.char_count,
            token_estimate=model.token_estimate,
            content_hash=model.content_hash,
            created_at=model.created_at,
        )

    @staticmethod
    def _table_to_model(table: DocumentTableRead) -> DocumentTableModel:
        return DocumentTableModel(**table.model_dump())

    @staticmethod
    def _table_to_read_model(model: DocumentTableModel) -> DocumentTableRead:
        return DocumentTableRead(
            id=model.id,
            document_id=model.document_id,
            ordinal=model.ordinal,
            title=model.title,
            sheet_name=model.sheet_name,
            row_count=model.row_count,
            column_count=model.column_count,
            headers=model.headers,
            rows=model.rows,
            source_locator=model.source_locator,
            content_hash=model.content_hash,
            created_at=model.created_at,
        )
