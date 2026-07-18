import uuid
from typing import Protocol

from medreg.core.celery_app import celery_app


class RetrievalTaskDispatcher(Protocol):
    def enqueue_index(self, document_id: uuid.UUID, task_id: str) -> None: ...


class CeleryRetrievalTaskDispatcher:
    def enqueue_index(self, document_id: uuid.UUID, task_id: str) -> None:
        celery_app.send_task(
            "medreg.retrieval.index_document",
            args=[str(document_id)],
            task_id=task_id,
        )
