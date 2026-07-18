import re

from medreg.modules.agent.schemas import (
    BilingualCheckStatus,
    BilingualConsistencyReport,
    BilingualTerm,
    BilingualTermCheck,
    DraftLanguageMode,
    DraftSection,
)

GLOSSARY_VERSION = "medreg-zh-en-glossary-v1"

PRODUCT_TRANSLATIONS = {
    "便携式心电记录仪": "Portable Electrocardiograph Recorder",
}

COMMON_TERMS = {
    "产品名称": "product name",
    "型号规格": "model and specification",
    "预期用途": "intended purpose",
    "风险管理": "risk management",
    "风险控制": "risk control",
    "剩余风险": "residual risk",
    "性能指标": "performance specifications",
    "检验方法": "test method",
    "测量范围": "measurement range",
    "说明书": "instructions for use",
    "标签": "label",
    "警示语": "warnings",
}

SECTION_GLOSSARY = {
    DraftSection.PRODUCT_OVERVIEW: ("产品名称", "型号规格", "预期用途"),
    DraftSection.RISK_MANAGEMENT_SUMMARY: ("风险管理", "风险控制", "剩余风险"),
    DraftSection.TECHNICAL_REQUIREMENTS_SUMMARY: (
        "性能指标",
        "检验方法",
        "测量范围",
    ),
    DraftSection.IFU_LABEL_SUMMARY: ("说明书", "标签", "警示语", "预期用途"),
}


class BilingualConsistencyChecker:
    def expected_terms(
        self,
        product_name: str,
        target_section: DraftSection,
    ) -> list[BilingualTerm]:
        terms: list[BilingualTerm] = []
        product_translation = PRODUCT_TRANSLATIONS.get(product_name)
        if product_translation:
            terms.append(BilingualTerm(zh=product_name, en=product_translation))
        terms.extend(
            BilingualTerm(zh=term, en=COMMON_TERMS[term])
            for term in SECTION_GLOSSARY[target_section]
        )
        return terms

    def check(
        self,
        language_mode: DraftLanguageMode,
        expected: list[BilingualTerm],
        actual: list[BilingualTerm],
    ) -> BilingualConsistencyReport:
        if language_mode == DraftLanguageMode.ZH_CN:
            return BilingualConsistencyReport(
                glossary_version=GLOSSARY_VERSION,
                language_mode=language_mode,
                status=BilingualCheckStatus.NOT_APPLICABLE,
                pass_count=0,
                missing_count=0,
                mismatch_count=0,
                checks=[],
            )
        actual_by_zh = {item.zh.strip(): item.en.strip() for item in actual}
        checks: list[BilingualTermCheck] = []
        for term in expected:
            actual_en = actual_by_zh.get(term.zh)
            if actual_en is None:
                status = BilingualCheckStatus.MISSING
                message = "结构化输出缺少该受控术语。"
            elif self._normalize(actual_en) != self._normalize(term.en):
                status = BilingualCheckStatus.MISMATCH
                message = "英文译法与受控术语表不一致。"
            else:
                status = BilingualCheckStatus.PASS
                message = "中英文术语与受控词表一致。"
            checks.append(
                BilingualTermCheck(
                    zh=term.zh,
                    expected_en=term.en,
                    actual_en=actual_en,
                    status=status,
                    message=message,
                )
            )
        mismatch_count = sum(item.status == BilingualCheckStatus.MISMATCH for item in checks)
        missing_count = sum(item.status == BilingualCheckStatus.MISSING for item in checks)
        pass_count = sum(item.status == BilingualCheckStatus.PASS for item in checks)
        overall = (
            BilingualCheckStatus.MISMATCH
            if mismatch_count
            else (
                BilingualCheckStatus.MISSING
                if missing_count
                else BilingualCheckStatus.PASS
            )
        )
        return BilingualConsistencyReport(
            glossary_version=GLOSSARY_VERSION,
            language_mode=language_mode,
            status=overall,
            pass_count=pass_count,
            missing_count=missing_count,
            mismatch_count=mismatch_count,
            checks=checks,
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())
