import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from medreg.modules.documents.dispatcher import DocumentTaskDispatcher
from medreg.modules.documents.fetcher import OfficialSourceFetcher
from medreg.modules.documents.parser import DocumentParser
from medreg.modules.documents.repository import DocumentRepository
from medreg.modules.documents.schemas import (
    DocumentChunkRead,
    DocumentFetchRequestList,
    DocumentFetchRequestRead,
    DocumentSectionRead,
    DocumentStructureRead,
    DocumentTableRead,
    FetchRequestCreate,
    FetchReviewCreate,
    FetchReviewDecision,
    FetchStatus,
    ParseRecoveryRead,
    ParseStatus,
    RegulationDocumentList,
    RegulationDocumentRead,
    StorageStatus,
)
from medreg.modules.documents.security import (
    ControlledFileSecurityInspector,
    FileSecurityError,
    FileSecurityInspector,
)
from medreg.modules.documents.segmenter import LegalDocumentSegmenter
from medreg.modules.documents.storage import ObjectStorage

ALLOWED_SUFFIXES = {".pdf", ".docx", ".xlsx", ".txt", ".md", ".html", ".htm"}


class DocumentNotFoundError(LookupError):
    pass


class RegulationVersionNotFoundError(LookupError):
    pass


class FetchRequestNotFoundError(LookupError):
    pass


class DocumentValidationError(ValueError):
    pass


class DuplicateDocumentError(ValueError):
    pass


class DocumentParseError(ValueError):
    pass


class DocumentFetchError(ValueError):
    pass


class FetchRequestStateError(ValueError):
    pass


class TaskDispatchError(RuntimeError):
    pass


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        storage: ObjectStorage,
        parser: DocumentParser,
        segmenter: LegalDocumentSegmenter,
        dispatcher: DocumentTaskDispatcher,
        fetcher: OfficialSourceFetcher,
        max_upload_bytes: int,
        parse_stale_after_seconds: int,
        security_inspector: FileSecurityInspector | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.parser = parser
        self.segmenter = segmenter
        self.dispatcher = dispatcher
        self.fetcher = fetcher
        self.max_upload_bytes = max_upload_bytes
        self.parse_stale_after_seconds = parse_stale_after_seconds
        self.security_inspector = security_inspector or ControlledFileSecurityInspector(
            max_uncompressed_bytes=max_upload_bytes * 10
        )

    async def archive(
        self,
        version_id: uuid.UUID,
        file_name: str,
        content_type: str | None,
        data: bytes,
        uploaded_by: str,
    ) -> RegulationDocumentRead:
        if not await self.repository.version_exists(version_id):
            raise RegulationVersionNotFoundError(str(version_id))

        safe_name = Path(file_name).name.strip()
        suffix = Path(safe_name).suffix.lower()
        if not safe_name or suffix not in ALLOWED_SUFFIXES:
            raise DocumentValidationError(
                "Only PDF, DOCX, XLSX, TXT, Markdown and HTML files are supported"
            )
        if not data:
            raise DocumentValidationError("The uploaded file is empty")
        if len(data) > self.max_upload_bytes:
            raise DocumentValidationError(
                f"The uploaded file exceeds {self.max_upload_bytes} bytes"
            )
        try:
            security_report = self.security_inspector.inspect(
                safe_name,
                content_type,
                data,
            )
        except FileSecurityError as exc:
            raise DocumentValidationError(f"File security check failed: {exc}") from exc

        digest = hashlib.sha256(data).hexdigest()
        if await self.repository.get_by_sha256(version_id, digest) is not None:
            raise DuplicateDocumentError(digest)

        now = datetime.now(UTC)
        document_id = uuid.uuid4()
        object_key = f"regulations/{version_id}/{document_id}/{safe_name}"
        resolved_content_type = content_type or "application/octet-stream"
        await self.storage.put(object_key, data, resolved_content_type)

        document = RegulationDocumentRead(
            id=document_id,
            code=f"DOC-{now.year}-{secrets.token_hex(3).upper()}",
            regulation_version_id=version_id,
            file_name=safe_name,
            content_type=resolved_content_type,
            size_bytes=len(data),
            sha256=digest,
            security_status=security_report.status,
            security_engine=security_report.engine,
            detected_type=security_report.detected_type,
            security_findings=list(security_report.findings),
            bucket_name=self.storage.bucket_name,
            object_key=object_key,
            storage_status=StorageStatus.ARCHIVED,
            parse_status=ParseStatus.PENDING,
            parse_attempts=0,
            parse_task_id=None,
            parser_version=None,
            segmenter_version=None,
            section_count=0,
            chunk_count=0,
            table_count=0,
            extracted_char_count=0,
            parse_error=None,
            uploaded_by=uploaded_by,
            queued_at=None,
            processing_started_at=None,
            parsed_at=None,
            created_at=now,
            updated_at=now,
        )
        try:
            return await self.repository.add(document)
        except Exception:
            await self.storage.delete(object_key)
            raise

    async def list_for_version(
        self, version_id: uuid.UUID
    ) -> RegulationDocumentList:
        if not await self.repository.version_exists(version_id):
            raise RegulationVersionNotFoundError(str(version_id))
        items = await self.repository.list_for_version(version_id)
        return RegulationDocumentList(items=items, total=len(items))

    async def queue_parse(
        self,
        document_id: uuid.UUID,
        force: bool = False,
    ) -> RegulationDocumentRead:
        document = await self.repository.get(document_id)
        if document is None:
            raise DocumentNotFoundError(str(document_id))
        if document.parse_status in {ParseStatus.QUEUED, ParseStatus.PROCESSING}:
            return document
        if document.parse_status == ParseStatus.COMPLETED and not force:
            return document
        return await self._enqueue_parse(document)

    async def get_structure(
        self, document_id: uuid.UUID
    ) -> DocumentStructureRead:
        document = await self.repository.get(document_id)
        if document is None:
            raise DocumentNotFoundError(str(document_id))
        structure = await self.repository.get_structure(document_id)
        if structure is not None:
            return structure
        return DocumentStructureRead(
            document_id=document_id,
            parser_version=document.parser_version,
            segmenter_version=document.segmenter_version,
            section_count=0,
            chunk_count=0,
            table_count=0,
            sections=[],
            chunks=[],
            tables=[],
        )

    async def execute_parse(
        self,
        document_id: uuid.UUID,
        task_id: str | None = None,
    ) -> RegulationDocumentRead:
        document = await self.repository.get(document_id)
        if document is None:
            raise DocumentNotFoundError(str(document_id))
        if task_id is not None and document.parse_task_id != task_id:
            return document
        if document.parse_status in {ParseStatus.COMPLETED, ParseStatus.FAILED}:
            return document

        attempts = document.parse_attempts + 1
        started_at = datetime.now(UTC)
        processing = await self.repository.update_parse(
            document_id=document_id,
            status=ParseStatus.PROCESSING,
            attempts=attempts,
            task_id=document.parse_task_id,
            parser_version=self.parser.version,
            extracted_text=None,
            error=None,
            queued_at=document.queued_at,
            processing_started_at=started_at,
            parsed_at=None,
            updated_at=started_at,
            expected_task_id=task_id,
        )
        if processing is None:
            raise DocumentNotFoundError(str(document_id))
        if task_id is not None and processing.parse_task_id != task_id:
            return processing

        try:
            data = await self.storage.get(document.object_key)
            parsed_document = self.parser.parse(document.file_name, data)
            extracted_text = parsed_document.text
            segmented = self.segmenter.segment(document.id, extracted_text)
            structured_at = datetime.now(UTC)
            sections = [
                DocumentSectionRead(
                    id=item.id,
                    document_id=document.id,
                    parent_id=item.parent_id,
                    kind=item.kind,
                    ordinal=item.ordinal,
                    heading=item.heading,
                    citation_path=item.citation_path,
                    content=item.content,
                    char_start=item.char_start,
                    char_end=item.char_end,
                    content_hash=item.content_hash,
                    created_at=structured_at,
                )
                for item in segmented.sections
            ]
            chunks = [
                DocumentChunkRead(
                    id=item.id,
                    document_id=document.id,
                    section_id=item.section_id,
                    ordinal=item.ordinal,
                    section_chunk_index=item.section_chunk_index,
                    citation_label=item.citation_label,
                    content=item.content,
                    char_start=item.char_start,
                    char_end=item.char_end,
                    char_count=item.char_count,
                    token_estimate=item.token_estimate,
                    content_hash=item.content_hash,
                    created_at=structured_at,
                )
                for item in segmented.chunks
            ]
            tables = [
                DocumentTableRead(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    ordinal=item.ordinal,
                    title=item.title,
                    sheet_name=item.sheet_name,
                    row_count=len(item.rows),
                    column_count=len(item.headers),
                    headers=list(item.headers),
                    rows=[list(row) for row in item.rows],
                    source_locator=item.source_locator,
                    content_hash=self._table_hash(item.headers, item.rows),
                    created_at=structured_at,
                )
                for item in parsed_document.tables
            ]
            structure = await self.repository.replace_structure(
                document_id=document.id,
                sections=sections,
                chunks=chunks,
                tables=tables,
                segmenter_version=self.segmenter.version,
                updated_at=structured_at,
                expected_task_id=task_id,
            )
            if structure is None:
                raise DocumentNotFoundError(str(document_id))
        except Exception as exc:
            failed = await self.repository.update_parse(
                document_id=document_id,
                status=ParseStatus.FAILED,
                attempts=attempts,
                task_id=document.parse_task_id,
                parser_version=self.parser.version,
                extracted_text=None,
                error=str(exc)[:1000],
                queued_at=document.queued_at,
                processing_started_at=started_at,
                parsed_at=None,
                updated_at=datetime.now(UTC),
                expected_task_id=task_id,
            )
            if failed is None:
                raise DocumentNotFoundError(str(document_id)) from exc
            if task_id is not None and failed.parse_task_id != task_id:
                return failed
            raise DocumentParseError(failed.parse_error or "Document parsing failed") from exc

        completed_at = datetime.now(UTC)
        parsed = await self.repository.update_parse(
            document_id=document_id,
            status=ParseStatus.COMPLETED,
            attempts=attempts,
            task_id=document.parse_task_id,
            parser_version=self.parser.version,
            extracted_text=extracted_text,
            error=None,
            queued_at=document.queued_at,
            processing_started_at=started_at,
            parsed_at=completed_at,
            updated_at=completed_at,
            expected_task_id=task_id,
        )
        if parsed is None:
            raise DocumentNotFoundError(str(document_id))
        return parsed

    @staticmethod
    def _table_hash(
        headers: tuple[str, ...],
        rows: tuple[tuple[str, ...], ...],
    ) -> str:
        parts = ["\t".join(headers), *("\t".join(row) for row in rows)]
        return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()

    async def recover_stale_parses(self) -> ParseRecoveryRead:
        cutoff = datetime.now(UTC) - timedelta(
            seconds=self.parse_stale_after_seconds
        )
        stale_documents = await self.repository.list_stale_parses(cutoff)
        recovered: list[uuid.UUID] = []
        for document in stale_documents:
            await self._enqueue_parse(document)
            recovered.append(document.id)
        return ParseRecoveryRead(recovered=len(recovered), document_ids=recovered)

    async def create_fetch_request(
        self,
        version_id: uuid.UUID,
        payload: FetchRequestCreate,
    ) -> DocumentFetchRequestRead:
        if not await self.repository.version_exists(version_id):
            raise RegulationVersionNotFoundError(str(version_id))
        official_url = str(payload.official_url)
        try:
            self.fetcher.validate_url(official_url)
        except ValueError as exc:
            raise DocumentValidationError(str(exc)) from exc

        now = datetime.now(UTC)
        request = DocumentFetchRequestRead(
            id=uuid.uuid4(),
            regulation_version_id=version_id,
            official_url=official_url,
            status=FetchStatus.PENDING_APPROVAL,
            requested_by=payload.requested_by,
            request_reason=payload.reason,
            reviewed_by=None,
            review_note=None,
            reviewed_at=None,
            task_id=None,
            resulting_document_id=None,
            fetch_error=None,
            queued_at=None,
            started_at=None,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        return await self.repository.add_fetch_request(request)

    async def list_fetch_requests(
        self, version_id: uuid.UUID
    ) -> DocumentFetchRequestList:
        if not await self.repository.version_exists(version_id):
            raise RegulationVersionNotFoundError(str(version_id))
        items = await self.repository.list_fetch_requests(version_id)
        return DocumentFetchRequestList(items=items, total=len(items))

    async def review_fetch_request(
        self,
        request_id: uuid.UUID,
        payload: FetchReviewCreate,
    ) -> DocumentFetchRequestRead:
        request = await self._get_fetch_request(request_id)
        if request.status != FetchStatus.PENDING_APPROVAL:
            raise FetchRequestStateError(
                "Only pending fetch requests can be reviewed"
            )

        now = datetime.now(UTC)
        if payload.decision == FetchReviewDecision.REJECTED:
            rejected = request.model_copy(
                update={
                    "status": FetchStatus.REJECTED,
                    "reviewed_by": payload.reviewed_by,
                    "review_note": payload.note,
                    "reviewed_at": now,
                    "completed_at": now,
                    "updated_at": now,
                }
            )
            return await self.repository.save_fetch_request(rejected)

        approved = request.model_copy(
            update={
                "reviewed_by": payload.reviewed_by,
                "review_note": payload.note,
                "reviewed_at": now,
                "updated_at": now,
            }
        )
        await self.repository.save_fetch_request(approved)
        return await self._enqueue_fetch(approved)

    async def retry_fetch_request(
        self, request_id: uuid.UUID
    ) -> DocumentFetchRequestRead:
        request = await self._get_fetch_request(request_id)
        if request.status != FetchStatus.FAILED:
            raise FetchRequestStateError("Only failed fetch requests can be retried")
        return await self._enqueue_fetch(request)

    async def execute_fetch(
        self,
        request_id: uuid.UUID,
        task_id: str | None = None,
    ) -> DocumentFetchRequestRead:
        request = await self._get_fetch_request(request_id)
        if task_id is not None and request.task_id != task_id:
            return request
        if request.status not in {FetchStatus.QUEUED, FetchStatus.FETCHING}:
            return request

        started_at = datetime.now(UTC)
        fetching = request.model_copy(
            update={
                "status": FetchStatus.FETCHING,
                "started_at": started_at,
                "fetch_error": None,
                "updated_at": started_at,
            }
        )
        await self.repository.save_fetch_request(fetching)

        try:
            source = await self.fetcher.fetch(str(request.official_url))
            digest = hashlib.sha256(source.data).hexdigest()
            document = await self.repository.get_by_sha256(
                request.regulation_version_id, digest
            )
            if document is None:
                document = await self.archive(
                    version_id=request.regulation_version_id,
                    file_name=source.file_name,
                    content_type=source.content_type,
                    data=source.data,
                    uploaded_by=f"official-fetch:{request.requested_by}"[:80],
                )
        except Exception as exc:
            failed_at = datetime.now(UTC)
            failed = fetching.model_copy(
                update={
                    "status": FetchStatus.FAILED,
                    "fetch_error": str(exc)[:1000],
                    "completed_at": failed_at,
                    "updated_at": failed_at,
                }
            )
            await self.repository.save_fetch_request(failed)
            raise DocumentFetchError(failed.fetch_error or "Official fetch failed") from exc

        completed_at = datetime.now(UTC)
        completed = fetching.model_copy(
            update={
                "status": FetchStatus.COMPLETED,
                "resulting_document_id": document.id,
                "fetch_error": None,
                "completed_at": completed_at,
                "updated_at": completed_at,
            }
        )
        saved = await self.repository.save_fetch_request(completed)
        if document.parse_status in {ParseStatus.PENDING, ParseStatus.FAILED}:
            await self._enqueue_parse(document)
        return saved

    async def _enqueue_parse(
        self, document: RegulationDocumentRead
    ) -> RegulationDocumentRead:
        queued_at = datetime.now(UTC)
        task_id = str(uuid.uuid4())
        queued = await self.repository.update_parse(
            document_id=document.id,
            status=ParseStatus.QUEUED,
            attempts=document.parse_attempts,
            task_id=task_id,
            parser_version=document.parser_version,
            extracted_text=None,
            error=None,
            queued_at=queued_at,
            processing_started_at=None,
            parsed_at=None,
            updated_at=queued_at,
        )
        if queued is None:
            raise DocumentNotFoundError(str(document.id))
        if not await self.repository.clear_structure(document.id):
            raise DocumentNotFoundError(str(document.id))
        refreshed = await self.repository.get(document.id)
        if refreshed is None:
            raise DocumentNotFoundError(str(document.id))
        queued = refreshed
        try:
            self.dispatcher.enqueue_parse(document.id, task_id)
        except Exception as exc:
            await self.repository.update_parse(
                document_id=document.id,
                status=ParseStatus.FAILED,
                attempts=document.parse_attempts,
                task_id=task_id,
                parser_version=document.parser_version,
                extracted_text=None,
                error=f"Task dispatch failed: {exc}"[:1000],
                queued_at=queued_at,
                processing_started_at=None,
                parsed_at=None,
                updated_at=datetime.now(UTC),
            )
            raise TaskDispatchError("Unable to enqueue document parse") from exc
        return queued

    async def _enqueue_fetch(
        self, request: DocumentFetchRequestRead
    ) -> DocumentFetchRequestRead:
        queued_at = datetime.now(UTC)
        task_id = str(uuid.uuid4())
        queued = request.model_copy(
            update={
                "status": FetchStatus.QUEUED,
                "task_id": task_id,
                "resulting_document_id": None,
                "fetch_error": None,
                "queued_at": queued_at,
                "started_at": None,
                "completed_at": None,
                "updated_at": queued_at,
            }
        )
        saved = await self.repository.save_fetch_request(queued)
        try:
            self.dispatcher.enqueue_fetch(request.id, task_id)
        except Exception as exc:
            failed_at = datetime.now(UTC)
            failed = saved.model_copy(
                update={
                    "status": FetchStatus.FAILED,
                    "fetch_error": f"Task dispatch failed: {exc}"[:1000],
                    "completed_at": failed_at,
                    "updated_at": failed_at,
                }
            )
            await self.repository.save_fetch_request(failed)
            raise TaskDispatchError("Unable to enqueue official source fetch") from exc
        return saved

    async def _get_fetch_request(
        self, request_id: uuid.UUID
    ) -> DocumentFetchRequestRead:
        request = await self.repository.get_fetch_request(request_id)
        if request is None:
            raise FetchRequestNotFoundError(str(request_id))
        return request
