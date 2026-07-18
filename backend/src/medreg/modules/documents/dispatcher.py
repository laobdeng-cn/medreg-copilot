import uuid
from typing import Protocol


class DocumentTaskDispatcher(Protocol):
    def enqueue_parse(self, document_id: uuid.UUID, task_id: str) -> None: ...

    def enqueue_fetch(self, request_id: uuid.UUID, task_id: str) -> None: ...


class InMemoryDocumentTaskDispatcher:
    def __init__(self) -> None:
        self.parse_tasks: list[tuple[uuid.UUID, str]] = []
        self.fetch_tasks: list[tuple[uuid.UUID, str]] = []

    def enqueue_parse(self, document_id: uuid.UUID, task_id: str) -> None:
        self.parse_tasks.append((document_id, task_id))

    def enqueue_fetch(self, request_id: uuid.UUID, task_id: str) -> None:
        self.fetch_tasks.append((request_id, task_id))

    def clear(self) -> None:
        self.parse_tasks.clear()
        self.fetch_tasks.clear()


class CeleryDocumentTaskDispatcher:
    def enqueue_parse(self, document_id: uuid.UUID, task_id: str) -> None:
        from medreg.modules.documents.tasks import parse_document_task

        parse_document_task.apply_async(args=[str(document_id)], task_id=task_id)

    def enqueue_fetch(self, request_id: uuid.UUID, task_id: str) -> None:
        from medreg.modules.documents.tasks import fetch_official_source_task

        fetch_official_source_task.apply_async(args=[str(request_id)], task_id=task_id)
