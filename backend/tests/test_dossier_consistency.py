import uuid

from medreg.modules.applications.consistency import (
    DossierConsistencyAnalyzer,
    EvidenceText,
)
from medreg.modules.applications.schemas import (
    ConsistencyField,
    ConsistencyStatus,
    DossierCategory,
)


def evidence(
    category_key: DossierCategory,
    file_name: str,
    text: str,
) -> EvidenceText:
    return EvidenceText(
        evidence_id=uuid.uuid4(),
        category_key=category_key,
        file_name=file_name,
        text=text,
    )


def test_consistency_analyzer_accepts_equivalent_structured_fields() -> None:
    documents = [
        evidence(
            DossierCategory.TECHNICAL_REQUIREMENTS,
            "产品技术要求.txt",
            """产品名称：便携式心电记录仪
型号规格：ECG-100、ECG-200
预期用途：用于医疗机构采集成人动态心电信号
性能指标：心率测量范围 30-240 bpm
警示语：不得用于生命支持监护
""",
        ),
        evidence(
            DossierCategory.IFU_AND_LABEL,
            "产品说明书.txt",
            """产品名称：便携式心电记录仪
规格型号：ECG-200/ECG-100
适用范围：用于医疗机构采集成人动态心电信号。
主要性能：心率测量范围30—240 bpm
注意事项：不得用于生命支持监护。
""",
        ),
    ]

    checks = DossierConsistencyAnalyzer().analyze(
        "便携式心电记录仪", documents
    )

    assert {item.status for item in checks} == {ConsistencyStatus.PASS}
    model = next(
        item for item in checks if item.field == ConsistencyField.MODEL_SPECIFICATION
    )
    assert model.occurrence_count == 2
    assert model.distinct_value_count == 1


def test_consistency_analyzer_reports_real_conflicts_and_missing_samples() -> None:
    documents = [
        evidence(
            DossierCategory.RISK_ANALYSIS,
            "风险分析.txt",
            "产品名称：便携式心电记录仪\n预期用途：用于成人动态心电信号采集",
        ),
        evidence(
            DossierCategory.IFU_AND_LABEL,
            "说明书.txt",
            "产品名称：动态血压监测仪\n预期用途：用于儿童血压连续监测",
        ),
    ]

    checks = DossierConsistencyAnalyzer().analyze(
        "便携式心电记录仪", documents
    )
    by_field = {item.field: item for item in checks}

    assert by_field[ConsistencyField.PRODUCT_NAME].status == (
        ConsistencyStatus.MISMATCH
    )
    assert by_field[ConsistencyField.INTENDED_USE].status == (
        ConsistencyStatus.MISMATCH
    )
    assert by_field[ConsistencyField.MODEL_SPECIFICATION].status == (
        ConsistencyStatus.INSUFFICIENT
    )
    assert by_field[ConsistencyField.PRODUCT_NAME].severity == "blocker"


def test_consistency_analyzer_never_hides_changed_performance_numbers() -> None:
    documents = [
        evidence(
            DossierCategory.TECHNICAL_REQUIREMENTS,
            "技术要求.txt",
            "性能指标：心率测量范围 30-240 bpm，误差不超过 +/- 2 bpm",
        ),
        evidence(
            DossierCategory.IFU_AND_LABEL,
            "说明书.txt",
            "主要性能：心率测量范围 30-250 bpm，误差不超过 +/- 2 bpm",
        ),
    ]

    checks = DossierConsistencyAnalyzer().analyze("便携式心电记录仪", documents)
    performance = next(
        item for item in checks if item.field == ConsistencyField.PERFORMANCE
    )

    assert performance.status == ConsistencyStatus.MISMATCH
    assert "关键数值" in performance.message
