from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Protocol
from zipfile import BadZipFile, ZipFile

EICAR_MARKER = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!"
OOXML_MACRO_PARTS = ("vbaproject.bin", "vbaData.xml")
OOXML_ACTIVE_PARTS = ("embeddings/oleobject", "externallinks/")


class FileSecurityError(ValueError):
    pass


@dataclass(frozen=True)
class FileSecurityReport:
    status: str
    engine: str
    detected_type: str
    findings: tuple[str, ...]


class FileSecurityInspector(Protocol):
    version: str

    def inspect(
        self,
        file_name: str,
        content_type: str | None,
        data: bytes,
    ) -> FileSecurityReport: ...


class ControlledFileSecurityInspector:
    version = "controlled-intake-v1"

    def __init__(
        self,
        *,
        max_entries: int = 2000,
        max_uncompressed_bytes: int = 200 * 1024 * 1024,
        max_compression_ratio: int = 200,
    ) -> None:
        self.max_entries = max_entries
        self.max_uncompressed_bytes = max_uncompressed_bytes
        self.max_compression_ratio = max_compression_ratio

    def inspect(
        self,
        file_name: str,
        content_type: str | None,
        data: bytes,
    ) -> FileSecurityReport:
        del content_type
        suffix = Path(file_name).suffix.lower()
        if EICAR_MARKER in data:
            raise FileSecurityError("Known antivirus test signature detected")
        if suffix == ".pdf":
            if not data.startswith(b"%PDF-"):
                raise FileSecurityError("PDF extension does not match file signature")
            return self._passed("pdf", "pdf_signature_verified")
        if suffix in {".docx", ".xlsx"}:
            return self._inspect_ooxml(suffix, data)
        if suffix in {".txt", ".md", ".html", ".htm"}:
            return self._inspect_text(suffix, data)
        raise FileSecurityError(f"Unsupported file type: {suffix or 'unknown'}")

    def _inspect_ooxml(self, suffix: str, data: bytes) -> FileSecurityReport:
        if not data.startswith(b"PK"):
            raise FileSecurityError("OOXML extension does not match ZIP signature")
        try:
            with ZipFile(BytesIO(data)) as archive:
                entries = archive.infolist()
                names = [entry.filename.replace("\\", "/") for entry in entries]
                lowered = [name.lower() for name in names]
                required = "word/document.xml" if suffix == ".docx" else "xl/workbook.xml"
                if required not in lowered:
                    raise FileSecurityError(
                        f"{suffix.upper()[1:]} package is missing {required}"
                    )
                if len(entries) > self.max_entries:
                    raise FileSecurityError("OOXML package contains too many entries")
                total_uncompressed = sum(entry.file_size for entry in entries)
                total_compressed = max(sum(entry.compress_size for entry in entries), 1)
                if total_uncompressed > self.max_uncompressed_bytes:
                    raise FileSecurityError("OOXML expanded size exceeds the safety limit")
                if total_uncompressed / total_compressed > self.max_compression_ratio:
                    raise FileSecurityError("OOXML compression ratio exceeds the safety limit")
                for entry, normalized, lower in zip(entries, names, lowered, strict=True):
                    path = PurePosixPath(normalized)
                    if path.is_absolute() or ".." in path.parts:
                        raise FileSecurityError("OOXML package contains an unsafe path")
                    if entry.flag_bits & 0x1:
                        raise FileSecurityError("Encrypted OOXML entries are not supported")
                    if any(part in lower for part in OOXML_MACRO_PARTS):
                        raise FileSecurityError("Macro-enabled OOXML content is blocked")
                    if any(part in lower for part in OOXML_ACTIVE_PARTS):
                        raise FileSecurityError(
                            "Embedded objects or external workbook links are blocked"
                        )
        except BadZipFile as exc:
            raise FileSecurityError("Invalid OOXML ZIP package") from exc
        detected = "docx" if suffix == ".docx" else "xlsx"
        return self._passed(
            detected,
            "zip_signature_verified",
            "archive_paths_safe",
            "macro_free",
            "embedded_objects_absent",
        )

    def _inspect_text(self, suffix: str, data: bytes) -> FileSecurityReport:
        if b"\x00" in data:
            raise FileSecurityError("Text document contains binary null bytes")
        try:
            decoded = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise FileSecurityError("Text document must use UTF-8 encoding") from exc
        if suffix in {".html", ".htm"}:
            lowered = decoded.lower()
            active_tags = ("<script", "<iframe", "<object", "<embed")
            if any(tag in lowered for tag in active_tags):
                raise FileSecurityError("Active HTML content is blocked")
            return self._passed("html", "utf8_verified", "active_html_absent")
        return self._passed("text", "utf8_verified")

    def _passed(self, detected_type: str, *findings: str) -> FileSecurityReport:
        return FileSecurityReport(
            status="passed",
            engine=self.version,
            detected_type=detected_type,
            findings=findings,
        )
