from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class FetchedSource:
    file_name: str
    content_type: str
    data: bytes
    final_url: str


class OfficialSourceFetcher(Protocol):
    def validate_url(self, url: str) -> None: ...

    async def fetch(self, url: str) -> FetchedSource: ...


class ControlledOfficialSourceFetcher:
    def __init__(
        self,
        allowed_hosts: list[str],
        timeout_seconds: float,
        max_bytes: int,
    ) -> None:
        self.allowed_hosts = tuple(host.lower().lstrip(".") for host in allowed_hosts)
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            raise ValueError("Official source URL must be a public HTTPS URL")
        if parsed.port not in {None, 443}:
            raise ValueError("Official source URL must use the standard HTTPS port")
        is_allowed = any(
            host == allowed or host.endswith(f".{allowed}")
            for allowed in self.allowed_hosts
        )
        if not is_allowed:
            raise ValueError("Official source domain is not in the approved allowlist")

    async def fetch(self, url: str) -> FetchedSource:
        self.validate_url(url)
        timeout = httpx.Timeout(self.timeout_seconds)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 MedRegCopilot/0.1"
            )
        }
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
        ) as client, client.stream("GET", url) as response:
            response.raise_for_status()
            final_url = str(response.url)
            self.validate_url(final_url)
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > self.max_bytes:
                    raise ValueError("Official source exceeds the archive size limit")

            content_type = response.headers.get("content-type", "").split(";", 1)[0]
            file_name = self._resolve_file_name(final_url, content_type)
            return FetchedSource(
                file_name=file_name,
                content_type=content_type or "application/octet-stream",
                data=bytes(data),
                final_url=final_url,
            )

    @staticmethod
    def _resolve_file_name(url: str, content_type: str) -> str:
        path_name = Path(urlparse(url).path).name or "official-source"
        suffix = Path(path_name).suffix.lower()
        if suffix in {".pdf", ".docx", ".txt", ".md", ".html", ".htm"}:
            return path_name
        if content_type == "application/pdf":
            return f"{path_name}.pdf"
        if content_type == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            return f"{path_name}.docx"
        if content_type in {"text/html", "application/xhtml+xml"}:
            return f"{path_name}.html"
        if content_type.startswith("text/"):
            return f"{path_name}.txt"
        raise ValueError("Official source response is not a supported document type")


class InMemoryOfficialSourceFetcher:
    def __init__(self) -> None:
        self.responses: dict[str, FetchedSource | Exception] = {}

    def validate_url(self, url: str) -> None:
        if not url.startswith("https://"):
            raise ValueError("Official source URL must be HTTPS")

    async def fetch(self, url: str) -> FetchedSource:
        self.validate_url(url)
        response = self.responses.get(url)
        if isinstance(response, Exception):
            raise response
        if response is None:
            raise ValueError("No test response configured")
        return response

    def add(self, url: str, response: FetchedSource | Exception) -> None:
        self.responses[url] = response

    def clear(self) -> None:
        self.responses.clear()
