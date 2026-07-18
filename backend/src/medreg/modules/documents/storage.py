import asyncio
from io import BytesIO
from typing import Protocol

from minio import Minio


class ObjectStorage(Protocol):
    bucket_name: str

    async def ready(self) -> bool: ...

    async def put(self, object_key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, object_key: str) -> bytes: ...

    async def delete(self, object_key: str) -> None: ...


class InMemoryObjectStorage:
    def __init__(self, bucket_name: str = "test-documents") -> None:
        self.bucket_name = bucket_name
        self._objects: dict[str, bytes] = {}
        self._lock = asyncio.Lock()

    async def put(self, object_key: str, data: bytes, content_type: str) -> None:
        del content_type
        async with self._lock:
            self._objects[object_key] = data

    async def ready(self) -> bool:
        return True

    async def get(self, object_key: str) -> bytes:
        async with self._lock:
            return self._objects[object_key]

    async def delete(self, object_key: str) -> None:
        async with self._lock:
            self._objects.pop(object_key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._objects.clear()


class MinioObjectStorage:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool = False,
    ) -> None:
        self.bucket_name = bucket_name
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket_ready = False
        self._bucket_lock = asyncio.Lock()

    async def put(self, object_key: str, data: bytes, content_type: str) -> None:
        await self._ensure_bucket()
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket_name,
            object_key,
            BytesIO(data),
            len(data),
            content_type=content_type,
        )

    async def ready(self) -> bool:
        await self._ensure_bucket()
        return True

    async def get(self, object_key: str) -> bytes:
        await self._ensure_bucket()
        return await asyncio.to_thread(self._read_object, object_key)

    async def delete(self, object_key: str) -> None:
        await self._ensure_bucket()
        await asyncio.to_thread(
            self.client.remove_object, self.bucket_name, object_key
        )

    async def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        async with self._bucket_lock:
            if self._bucket_ready:
                return
            last_error: Exception | None = None
            for _ in range(20):
                try:
                    exists = await asyncio.to_thread(
                        self.client.bucket_exists, self.bucket_name
                    )
                    if not exists:
                        await asyncio.to_thread(
                            self.client.make_bucket, self.bucket_name
                        )
                    self._bucket_ready = True
                    return
                except Exception as exc:  # MinIO may still be starting.
                    last_error = exc
                    await asyncio.sleep(0.25)
            if last_error is not None:
                raise last_error

    def _read_object(self, object_key: str) -> bytes:
        response = self.client.get_object(self.bucket_name, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
