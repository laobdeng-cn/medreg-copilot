from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass

from medreg.modules.agent.schemas import (
    ContextCompressionReport,
    ContextSegment,
    DraftSection,
)
from medreg.modules.applications.consistency import EvidenceText
from medreg.modules.applications.schemas import DossierCategory

CONTEXT_ALGORITHM_VERSION = "evidence-budget-compressor-v1"

SECTION_TERMS = {
    DraftSection.PRODUCT_OVERVIEW: (
        "产品名称",
        "型号",
        "规格",
        "预期用途",
        "组成",
        "工作原理",
    ),
    DraftSection.RISK_MANAGEMENT_SUMMARY: (
        "风险",
        "危害",
        "风险控制",
        "剩余风险",
        "可接受",
        "警示",
    ),
    DraftSection.TECHNICAL_REQUIREMENTS_SUMMARY: (
        "性能",
        "指标",
        "测量范围",
        "精度",
        "检验方法",
        "型号",
    ),
    DraftSection.IFU_LABEL_SUMMARY: (
        "说明书",
        "标签",
        "预期用途",
        "警示",
        "注意事项",
        "禁忌",
    ),
}

CATEGORY_BOOSTS = {
    DraftSection.PRODUCT_OVERVIEW: {
        DossierCategory.TECHNICAL_REQUIREMENTS,
        DossierCategory.IFU_AND_LABEL,
    },
    DraftSection.RISK_MANAGEMENT_SUMMARY: {DossierCategory.RISK_ANALYSIS},
    DraftSection.TECHNICAL_REQUIREMENTS_SUMMARY: {
        DossierCategory.TECHNICAL_REQUIREMENTS,
        DossierCategory.TEST_REPORT,
    },
    DraftSection.IFU_LABEL_SUMMARY: {DossierCategory.IFU_AND_LABEL},
}


@dataclass(frozen=True)
class _Candidate:
    segment: ContextSegment
    source_key: tuple[str, str]


class EvidenceContextCompressor:
    def __init__(
        self,
        max_chars: int = 3200,
        segment_chars: int = 720,
        overlap_chars: int = 100,
    ) -> None:
        self.max_chars = max_chars
        self.segment_chars = segment_chars
        self.overlap_chars = overlap_chars

    def compress(
        self,
        documents: list[EvidenceText],
        target_section: DraftSection,
    ) -> ContextCompressionReport:
        terms = SECTION_TERMS[target_section]
        candidates: list[_Candidate] = []
        original_chars = sum(len(document.text) for document in documents)
        for document in documents:
            for index, (start, end, content) in enumerate(
                self._segments(document.text), start=1
            ):
                matched = [term for term in terms if term.lower() in content.lower()]
                score = len(matched) * 2.0
                if document.category_key in CATEGORY_BOOSTS[target_section]:
                    score += 3.0
                score += min(len(content) / self.segment_chars, 1.0) * 0.25
                candidates.append(
                    _Candidate(
                        segment=ContextSegment(
                            evidence_id=document.evidence_id,
                            category_key=document.category_key,
                            file_name=document.file_name,
                            segment_index=index,
                            char_start=start,
                            char_end=end,
                            content=content,
                            content_hash=hashlib.sha256(content.encode()).hexdigest(),
                            score=round(score, 3),
                            matched_terms=matched,
                        ),
                        source_key=(str(document.evidence_id), document.file_name),
                    )
                )

        selected = self._select(candidates)
        selected.sort(
            key=lambda item: (
                item.file_name,
                item.char_start,
                item.segment_index,
            )
        )
        selected_chars = sum(len(item.content) for item in selected)
        selected_sources = {str(item.evidence_id) for item in selected}
        return ContextCompressionReport(
            algorithm_version=CONTEXT_ALGORITHM_VERSION,
            source_count=len(documents),
            original_chars=original_chars,
            selected_chars=selected_chars,
            max_chars=self.max_chars,
            compression_ratio=(
                round(selected_chars / original_chars, 4) if original_chars else 0.0
            ),
            omitted_source_count=max(len(documents) - len(selected_sources), 0),
            segments=selected,
        )

    def _select(self, candidates: list[_Candidate]) -> list[ContextSegment]:
        if not candidates:
            return []
        by_source: dict[tuple[str, str], list[_Candidate]] = defaultdict(list)
        for candidate in candidates:
            by_source[candidate.source_key].append(candidate)
        for items in by_source.values():
            items.sort(key=lambda item: (-item.segment.score, item.segment.char_start))

        selected: list[ContextSegment] = []
        selected_hashes: set[str] = set()
        used = 0

        def add(candidate: _Candidate) -> None:
            nonlocal used
            size = len(candidate.segment.content)
            if candidate.segment.content_hash in selected_hashes:
                return
            if used + size > self.max_chars and selected:
                return
            selected.append(candidate.segment)
            selected_hashes.add(candidate.segment.content_hash)
            used += size

        for source_key in sorted(by_source):
            add(by_source[source_key][0])
        for candidate in sorted(
            candidates,
            key=lambda item: (-item.segment.score, item.segment.char_start),
        ):
            add(candidate)
        return selected

    def _segments(self, text: str) -> list[tuple[int, int, str]]:
        cleaned = re.sub(r"\r\n?", "\n", text).strip()
        if not cleaned:
            return []
        segments: list[tuple[int, int, str]] = []
        start = 0
        while start < len(cleaned):
            tentative_end = min(start + self.segment_chars, len(cleaned))
            end = tentative_end
            if tentative_end < len(cleaned):
                boundary = max(
                    cleaned.rfind("\n", start + self.segment_chars // 2, tentative_end),
                    cleaned.rfind("。", start + self.segment_chars // 2, tentative_end),
                )
                if boundary > start:
                    end = boundary + 1
            content = cleaned[start:end].strip()
            if content:
                content_start = cleaned.find(content, start, end)
                segments.append((content_start, content_start + len(content), content))
            if end >= len(cleaned):
                break
            start = max(end - self.overlap_chars, start + 1)
        return segments
