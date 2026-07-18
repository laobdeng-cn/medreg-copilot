import re
import unicodedata
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher

from medreg.modules.applications.schemas import (
    ConsistencyCheck,
    ConsistencyField,
    ConsistencyOccurrence,
    ConsistencyStatus,
    DossierCategory,
    FindingSeverity,
)


@dataclass(frozen=True)
class EvidenceText:
    evidence_id: uuid.UUID
    category_key: DossierCategory
    file_name: str
    text: str


@dataclass(frozen=True)
class ConsistencyRule:
    field: ConsistencyField
    label: str
    aliases: tuple[str, ...]
    threshold: float
    severity: FindingSeverity
    rule_code: str
    default_category: DossierCategory
    regulatory_basis: str
    remediation: str


CONSISTENCY_RULES = (
    ConsistencyRule(
        field=ConsistencyField.PRODUCT_NAME,
        label="产品名称",
        aliases=("产品名称", "产品名", "器械名称"),
        threshold=1.0,
        severity=FindingSeverity.BLOCKER,
        rule_code="CONSISTENCY_PRODUCT_NAME_MISMATCH",
        default_category=DossierCategory.IFU_AND_LABEL,
        regulatory_basis="医疗器械注册申报资料要求及说明书、标签管理要求",
        remediation="以申报主数据为基线，统一各文件中的产品名称并完成受控版本复核。",
    ),
    ConsistencyRule(
        field=ConsistencyField.MODEL_SPECIFICATION,
        label="型号规格",
        aliases=("型号规格", "规格型号", "产品型号", "型号"),
        threshold=1.0,
        severity=FindingSeverity.BLOCKER,
        rule_code="CONSISTENCY_MODEL_SPECIFICATION_MISMATCH",
        default_category=DossierCategory.TECHNICAL_REQUIREMENTS,
        regulatory_basis="医疗器械产品技术要求编写指导原则及注册申报资料要求",
        remediation="核对型号规格清单，统一技术要求、检验报告和说明书中的型号及排序。",
    ),
    ConsistencyRule(
        field=ConsistencyField.INTENDED_USE,
        label="预期用途",
        aliases=("预期用途", "适用范围", "产品用途"),
        threshold=0.78,
        severity=FindingSeverity.BLOCKER,
        rule_code="CONSISTENCY_INTENDED_USE_MISMATCH",
        default_category=DossierCategory.IFU_AND_LABEL,
        regulatory_basis="医疗器械说明书和标签管理规定及临床评价资料要求",
        remediation="由法规与临床人员确认唯一适用范围，统一说明书、临床评价和风险资料表述。",
    ),
    ConsistencyRule(
        field=ConsistencyField.PERFORMANCE,
        label="性能指标",
        aliases=("性能指标", "主要性能", "技术指标", "关键性能"),
        threshold=0.72,
        severity=FindingSeverity.WARNING,
        rule_code="CONSISTENCY_PERFORMANCE_MISMATCH",
        default_category=DossierCategory.TECHNICAL_REQUIREMENTS,
        regulatory_basis="医疗器械产品技术要求编写指导原则及产品检验资料要求",
        remediation="逐项核对性能名称、限值、单位和试验方法，确认技术要求与检验结论一致。",
    ),
    ConsistencyRule(
        field=ConsistencyField.WARNINGS,
        label="警示与注意事项",
        aliases=("警示语", "警告事项", "注意事项", "警告"),
        threshold=0.68,
        severity=FindingSeverity.WARNING,
        rule_code="CONSISTENCY_WARNINGS_MISMATCH",
        default_category=DossierCategory.IFU_AND_LABEL,
        regulatory_basis="医疗器械说明书和标签管理规定",
        remediation="以风险控制措施为依据补齐说明书和标签中的警示、禁忌及注意事项。",
    ),
)

_FIELD_BOUNDARY = re.compile(
    r"\s+(?=(?:产品名称|产品名|器械名称|型号规格|规格型号|产品型号|型号|"
    r"预期用途|适用范围|产品用途|性能指标|主要性能|技术指标|关键性能|"
    r"警示语|警告事项|注意事项|警告)\s*[:：])"
)


class DossierConsistencyAnalyzer:
    def analyze(
        self,
        product_name: str,
        documents: list[EvidenceText],
    ) -> list[ConsistencyCheck]:
        checks: list[ConsistencyCheck] = []
        for rule in CONSISTENCY_RULES:
            occurrences: list[ConsistencyOccurrence] = []
            normalized_values: list[str] = []
            if rule.field == ConsistencyField.PRODUCT_NAME:
                occurrences.append(
                    ConsistencyOccurrence(
                        source_label="申报项目主数据",
                        value=product_name,
                    )
                )
                normalized_values.append(self._normalize(rule.field, product_name))

            for document in documents:
                seen_in_document: set[str] = set()
                for value in self._extract_values(document.text, rule.aliases):
                    normalized = self._normalize(rule.field, value)
                    if not normalized or normalized in seen_in_document:
                        continue
                    seen_in_document.add(normalized)
                    occurrences.append(
                        ConsistencyOccurrence(
                            source_label=document.file_name,
                            category_key=document.category_key,
                            evidence_id=document.evidence_id,
                            file_name=document.file_name,
                            value=value,
                        )
                    )
                    normalized_values.append(normalized)

            checks.append(self._evaluate(rule, occurrences, normalized_values))
        return checks

    @staticmethod
    def rule_for(field: ConsistencyField) -> ConsistencyRule:
        return next(rule for rule in CONSISTENCY_RULES if rule.field == field)

    def _evaluate(
        self,
        rule: ConsistencyRule,
        occurrences: list[ConsistencyOccurrence],
        normalized_values: list[str],
    ) -> ConsistencyCheck:
        distinct_values = set(normalized_values)
        source_count = len({item.source_label for item in occurrences})
        if len(occurrences) < 2 or source_count < 2:
            return ConsistencyCheck(
                field=rule.field,
                label=rule.label,
                status=ConsistencyStatus.INSUFFICIENT,
                threshold=rule.threshold,
                occurrence_count=len(occurrences),
                distinct_value_count=len(distinct_values),
                message="可比来源不足 2 个，待补充结构化字段样本。",
                occurrences=occurrences,
            )

        minimum_similarity = min(
            self._similarity(left, right)
            for index, left in enumerate(normalized_values)
            for right in normalized_values[index + 1 :]
        )
        numeric_conflict = self._has_numeric_conflict(rule.field, occurrences)
        mismatch = minimum_similarity < rule.threshold or numeric_conflict
        status = (
            ConsistencyStatus.MISMATCH if mismatch else ConsistencyStatus.PASS
        )
        if numeric_conflict:
            message = "来源文件中的关键数值不一致，需要逐项核对限值和单位。"
        elif mismatch:
            message = (
                f"发现 {len(distinct_values)} 个不同表述，最低相似度 "
                f"{minimum_similarity:.0%}，需要人工确认。"
            )
        else:
            message = f"已比对 {source_count} 个来源，字段表述一致。"
        return ConsistencyCheck(
            field=rule.field,
            label=rule.label,
            status=status,
            severity=rule.severity if mismatch else None,
            threshold=rule.threshold,
            occurrence_count=len(occurrences),
            distinct_value_count=len(distinct_values),
            message=message,
            occurrences=occurrences,
        )

    @staticmethod
    def _extract_values(text: str, aliases: tuple[str, ...]) -> list[str]:
        alias_pattern = "|".join(re.escape(alias) for alias in aliases)
        pattern = re.compile(
            rf"(?:{alias_pattern})\s*[:：]\s*([^\n\r；;]{{1,300}})"
        )
        values: list[str] = []
        for match in pattern.finditer(text):
            value = _FIELD_BOUNDARY.split(match.group(1), maxsplit=1)[0]
            value = value.strip(" \t。；;，,")
            if value:
                values.append(value)
        return values

    @staticmethod
    def _normalize(field: ConsistencyField, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).strip()
        if field == ConsistencyField.MODEL_SPECIFICATION:
            parts = re.split(r"[、,，/；;|\s]+", normalized.upper())
            tokens = {
                re.sub(r"[^0-9A-Z\u4e00-\u9fff]+", "", part)
                for part in parts
            }
            return "|".join(sorted(token for token in tokens if token))
        return re.sub(
            r"[^0-9A-Za-z\u4e00-\u9fff]+",
            "",
            normalized.casefold(),
        )

    @staticmethod
    def _similarity(left: str, right: str) -> float:
        if left == right:
            return 1.0
        return SequenceMatcher(None, left, right).ratio()

    @staticmethod
    def _has_numeric_conflict(
        field: ConsistencyField,
        occurrences: list[ConsistencyOccurrence],
    ) -> bool:
        if field not in {
            ConsistencyField.INTENDED_USE,
            ConsistencyField.PERFORMANCE,
            ConsistencyField.WARNINGS,
        }:
            return False
        signatures = [
            tuple(re.findall(r"\d+(?:\.\d+)?", unicodedata.normalize("NFKC", item.value)))
            for item in occurrences
        ]
        populated = [signature for signature in signatures if signature]
        return len(populated) >= 2 and len(set(populated)) > 1
