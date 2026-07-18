import hashlib
import re
import uuid
from dataclasses import dataclass

LEGAL_NUMBER = "零〇○一二两三四五六七八九十百千万0-9"
HEADING_PATTERN = re.compile(
    rf"^第[{LEGAL_NUMBER}]+(?P<unit>章|节|条)(?P<title>[^\n]*)$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class SectionSegment:
    id: uuid.UUID
    parent_id: uuid.UUID | None
    kind: str
    ordinal: int
    heading: str
    citation_path: str
    content: str
    char_start: int
    char_end: int
    content_hash: str


@dataclass(frozen=True)
class ChunkSegment:
    id: uuid.UUID
    section_id: uuid.UUID
    ordinal: int
    section_chunk_index: int
    citation_label: str
    content: str
    char_start: int
    char_end: int
    char_count: int
    token_estimate: int
    content_hash: str


@dataclass(frozen=True)
class SegmentedDocument:
    sections: list[SectionSegment]
    chunks: list[ChunkSegment]


class LegalDocumentSegmenter:
    version = "legal-hierarchy-v1"

    def __init__(self, max_chunk_chars: int = 900, overlap_chars: int = 120) -> None:
        if max_chunk_chars < 200:
            raise ValueError("max_chunk_chars must be at least 200")
        if overlap_chars < 0 or overlap_chars >= max_chunk_chars:
            raise ValueError("overlap_chars must be smaller than max_chunk_chars")
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars

    def segment(self, document_id: uuid.UUID, text: str) -> SegmentedDocument:
        matches = list(HEADING_PATTERN.finditer(text))
        if not matches:
            section = self._build_unstructured_section(document_id, text)
            chunks = self._chunk_section(document_id, section, 0)
            return SegmentedDocument(sections=[section], chunks=chunks)

        sections: list[SectionSegment] = []
        chunks: list[ChunkSegment] = []
        current_chapter: SectionSegment | None = None
        current_subsection: SectionSegment | None = None
        chunk_ordinal = 0

        for ordinal, match in enumerate(matches):
            end = matches[ordinal + 1].start() if ordinal + 1 < len(matches) else len(text)
            char_start, char_end = self._trim_span(text, match.start(), end)
            content = text[char_start:char_end]
            heading = self._normalize_heading(match.group(0))
            kind = self._kind_for_unit(match.group("unit"))

            if kind == "chapter":
                parent = None
                current_subsection = None
            elif kind == "section":
                parent = current_chapter
            else:
                parent = current_subsection or current_chapter

            path_parts = self._path_parts(parent, sections)
            citation_path = " / ".join([*path_parts, heading])
            section_id = uuid.uuid5(
                document_id,
                f"section:{ordinal}:{kind}:{heading}",
            )
            section = SectionSegment(
                id=section_id,
                parent_id=parent.id if parent else None,
                kind=kind,
                ordinal=ordinal,
                heading=heading,
                citation_path=citation_path,
                content=content,
                char_start=char_start,
                char_end=char_end,
                content_hash=self._hash(content),
            )
            sections.append(section)

            if kind == "chapter":
                current_chapter = section
            elif kind == "section":
                current_subsection = section

            section_chunks = self._chunk_section(
                document_id,
                section,
                chunk_ordinal,
            )
            chunks.extend(section_chunks)
            chunk_ordinal += len(section_chunks)

        return SegmentedDocument(sections=sections, chunks=chunks)

    def _build_unstructured_section(
        self, document_id: uuid.UUID, text: str
    ) -> SectionSegment:
        char_start, char_end = self._trim_span(text, 0, len(text))
        content = text[char_start:char_end]
        return SectionSegment(
            id=uuid.uuid5(document_id, "section:0:body:全文"),
            parent_id=None,
            kind="body",
            ordinal=0,
            heading="全文",
            citation_path="全文",
            content=content,
            char_start=char_start,
            char_end=char_end,
            content_hash=self._hash(content),
        )

    def _chunk_section(
        self,
        document_id: uuid.UUID,
        section: SectionSegment,
        first_ordinal: int,
    ) -> list[ChunkSegment]:
        body = section.content.partition("\n")[2].strip()
        if section.kind in {"chapter", "section"} and not body:
            return []
        if not section.content:
            return []

        chunks: list[ChunkSegment] = []
        relative_start = 0
        chunk_index = 0
        while relative_start < len(section.content):
            relative_end = min(
                relative_start + self.max_chunk_chars,
                len(section.content),
            )
            if relative_end < len(section.content):
                relative_end = self._natural_break(
                    section.content,
                    relative_start,
                    relative_end,
                )
            content = section.content[relative_start:relative_end].strip()
            leading_space = len(
                section.content[relative_start:relative_end]
            ) - len(section.content[relative_start:relative_end].lstrip())
            chunk_start = section.char_start + relative_start + leading_space
            chunk_end = chunk_start + len(content)
            content_hash = self._hash(content)
            chunks.append(
                ChunkSegment(
                    id=uuid.uuid5(
                        document_id,
                        f"chunk:{section.ordinal}:{chunk_index}:{content_hash}",
                    ),
                    section_id=section.id,
                    ordinal=first_ordinal + chunk_index,
                    section_chunk_index=chunk_index,
                    citation_label=section.citation_path,
                    content=content,
                    char_start=chunk_start,
                    char_end=chunk_end,
                    char_count=len(content),
                    token_estimate=max(1, (len(content) + 1) // 2),
                    content_hash=content_hash,
                )
            )
            if relative_end >= len(section.content):
                break
            next_start = max(relative_end - self.overlap_chars, relative_start + 1)
            relative_start = self._skip_leading_whitespace(
                section.content, next_start
            )
            chunk_index += 1
        return chunks

    def _natural_break(self, content: str, start: int, proposed_end: int) -> int:
        minimum_end = start + self.max_chunk_chars // 2
        candidates = [
            content.rfind(separator, minimum_end, proposed_end)
            for separator in ("\n", "。", "；")
        ]
        best = max(candidates)
        return best + 1 if best >= minimum_end else proposed_end

    @staticmethod
    def _skip_leading_whitespace(content: str, position: int) -> int:
        while position < len(content) and content[position].isspace():
            position += 1
        return position

    @staticmethod
    def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end

    @staticmethod
    def _normalize_heading(heading: str) -> str:
        return re.sub(r"[ \t\u3000]+", " ", heading).strip()

    @staticmethod
    def _kind_for_unit(unit: str) -> str:
        return {"章": "chapter", "节": "section", "条": "article"}[unit]

    @staticmethod
    def _path_parts(
        parent: SectionSegment | None,
        sections: list[SectionSegment],
    ) -> list[str]:
        if parent is None:
            return []
        path = [parent.heading]
        current_parent_id = parent.parent_id
        section_by_id = {section.id: section for section in sections}
        while current_parent_id is not None:
            ancestor = section_by_id[current_parent_id]
            path.append(ancestor.heading)
            current_parent_id = ancestor.parent_id
        return list(reversed(path))

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()
