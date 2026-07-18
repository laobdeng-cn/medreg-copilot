import html
import os
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from medreg.modules.applications.schemas import InternalPrecheckReport

SHANGHAI = ZoneInfo("Asia/Shanghai")
INK = colors.HexColor("#20312E")
MUTED = colors.HexColor("#687875")
LINE = colors.HexColor("#D9E1DF")
SOFT = colors.HexColor("#F3F6F5")
PRIMARY = colors.HexColor("#176B62")
PRIMARY_SOFT = colors.HexColor("#E8F3F0")
DANGER = colors.HexColor("#9A3832")
DANGER_SOFT = colors.HexColor("#F8E9E7")
WARNING = colors.HexColor("#8A6017")
WARNING_SOFT = colors.HexColor("#F8F0DD")

REQUIREMENT_LABELS = {
    "missing": "待上传",
    "uploaded": "待审核",
    "needs_review": "需整改",
    "accepted": "已接受",
    "not_applicable": "不适用",
}
CONSISTENCY_LABELS = {
    "pass": "一致",
    "mismatch": "冲突",
    "insufficient": "样本不足",
}
REMEDIATION_LABELS = {
    "open": "待处理",
    "in_progress": "整改中",
    "resolved": "已处理",
    "waived": "已豁免",
}
APPLICATION_LABELS = {
    "draft": "草稿",
    "intake": "资料接收",
    "precheck": "预审中",
    "in_review": "审核中",
    "needs_action": "需整改",
    "ready_for_submission": "可申报",
    "archived": "已归档",
}


def render_internal_precheck_report(report: InternalPrecheckReport) -> bytes:
    font_name = _register_cjk_font()
    styles = _build_styles(font_name)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=19 * mm,
        bottomMargin=17 * mm,
        title=f"{report.application.product_name}内部预审报告",
        author="MedReg Copilot",
        subject=report.report_code,
    )
    story: list[object] = []

    story.extend(_build_report_header(report, styles))
    story.extend(_build_project_overview(report, styles))
    story.extend(_build_summary(report, styles))
    story.extend(_build_evidence_matrix(report, styles))
    story.extend(_build_consistency_section(report, styles))
    story.extend(_build_findings(report, styles))
    story.extend(_build_traceability_appendix(report, styles))

    def draw_page(canvas, doc) -> None:
        canvas.saveState()
        canvas.setTitle(f"{report.application.product_name}内部预审报告")
        canvas.setAuthor("MedReg Copilot")
        canvas.setFont(font_name, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(15 * mm, A4[1] - 11 * mm, "MedReg Copilot · 内部受控文件")
        canvas.drawRightString(
            A4[0] - 15 * mm,
            A4[1] - 11 * mm,
            report.report_code,
        )
        canvas.setStrokeColor(LINE)
        canvas.line(15 * mm, 13 * mm, A4[0] - 15 * mm, 13 * mm)
        canvas.drawString(15 * mm, 8.5 * mm, f"预审运行 ID：{report.precheck.id}")
        canvas.drawRightString(
            A4[0] - 15 * mm,
            8.5 * mm,
            f"第 {doc.page} 页",
        )
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return buffer.getvalue()


def _register_cjk_font() -> str:
    registered = set(pdfmetrics.getRegisteredFontNames())
    if "MedRegCJK" in registered:
        return "MedRegCJK"

    candidates = [
        os.getenv("MEDREG_PDF_FONT_PATH", ""),
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont("MedRegCJK", candidate))
            return "MedRegCJK"
        except Exception:
            continue

    if "STSong-Light" not in registered:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light"


def _build_styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "MedRegTitle",
            parent=base["Title"],
            fontName=font_name,
            fontSize=21,
            leading=28,
            alignment=TA_LEFT,
            textColor=INK,
            spaceAfter=4 * mm,
        ),
        "subtitle": ParagraphStyle(
            "MedRegSubtitle",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=8.5,
            leading=13,
            textColor=MUTED,
        ),
        "section": ParagraphStyle(
            "MedRegSection",
            parent=base["Heading2"],
            fontName=font_name,
            fontSize=13,
            leading=18,
            textColor=INK,
            spaceBefore=6 * mm,
            spaceAfter=2.5 * mm,
        ),
        "body": ParagraphStyle(
            "MedRegBody",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=8,
            leading=12,
            textColor=INK,
            wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "MedRegSmall",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=6.8,
            leading=9.5,
            textColor=MUTED,
            wordWrap="CJK",
        ),
        "table_header": ParagraphStyle(
            "MedRegTableHeader",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=7.2,
            leading=10,
            textColor=INK,
            alignment=TA_LEFT,
        ),
        "metric": ParagraphStyle(
            "MedRegMetric",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=15,
            leading=18,
            textColor=INK,
            alignment=TA_CENTER,
        ),
        "metric_label": ParagraphStyle(
            "MedRegMetricLabel",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=6.8,
            leading=9,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def _build_report_header(report, styles) -> list[object]:
    freshness_text = "报告有效" if not report.is_stale else "报告已过期"
    freshness_color = PRIMARY_SOFT if not report.is_stale else DANGER_SOFT
    freshness_ink = PRIMARY if not report.is_stale else DANGER
    status_table = Table(
        [[_p(freshness_text, styles["body"], color=freshness_ink)]],
        colWidths=[35 * mm],
    )
    status_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), freshness_color),
                ("BOX", (0, 0), (-1, -1), 0.5, freshness_ink),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return [
        Spacer(1, 3 * mm),
        _p("医疗器械注册申报", styles["subtitle"], color=PRIMARY),
        _p("内部预审报告", styles["title"]),
        Table(
            [
                [
                    _p(
                        f"报告编号：{report.report_code}\n"
                        f"生成时间：{_format_dt(report.generated_at)}\n"
                        f"规则集：{report.precheck.rule_set_version}",
                        styles["subtitle"],
                    ),
                    status_table,
                ]
            ],
            colWidths=[140 * mm, 35 * mm],
            hAlign="LEFT",
        ),
        Spacer(1, 3 * mm),
    ]


def _build_project_overview(report, styles) -> list[object]:
    application = report.application
    rows = [
        ["申报项目", application.name, "项目编号", application.code],
        ["产品名称", application.product_name, "申请人", application.applicant_name],
        [
            "管理类别",
            f"境内 {application.device_class.value} 类",
            "申报类型",
            "首次注册",
        ],
        [
            "法规基准日",
            application.regulation_effective_on.isoformat(),
            "负责人",
            application.owner_name,
        ],
        [
            "项目状态",
            APPLICATION_LABELS[application.status.value],
            "资料完成率",
            f"{application.completion_rate:.1f}%",
        ],
    ]
    table_data = [
        [_p(cell, styles["body"]) for cell in row]
        for row in rows
    ]
    table = Table(table_data, colWidths=[24 * mm, 62 * mm, 24 * mm, 65 * mm])
    table.setStyle(_detail_table_style())
    return [_p("1. 项目概况", styles["section"]), table]


def _build_summary(report, styles) -> list[object]:
    metrics = [
        ("已归档证据", str(report.evidence_count)),
        ("已接受类别", f"{report.accepted_category_count}/7"),
        ("阻断项", str(report.precheck.blocker_count)),
        ("警告项", str(report.precheck.warning_count)),
        ("通过项", str(report.precheck.pass_count)),
        ("待整改", str(report.open_finding_count)),
    ]
    cells = [
        [
            _p(value, styles["metric"]),
            _p(label, styles["metric_label"]),
        ]
        for label, value in metrics
    ]
    table = Table([cells], colWidths=[175 * mm / len(cells)] * len(cells))
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    output: list[object] = [_p("2. 预审结论", styles["section"]), table]
    if report.stale_reason:
        output.extend(
            [
                Spacer(1, 2 * mm),
                _callout(report.stale_reason, styles, DANGER_SOFT, DANGER),
            ]
        )
    return output


def _build_evidence_matrix(report, styles) -> list[object]:
    evidence_by_category: dict[str, list] = {}
    for evidence in report.evidence_manifest:
        evidence_by_category.setdefault(evidence.category_key.value, []).append(evidence)

    rows = [
        [
            _p("资料类别", styles["table_header"]),
            _p("审核", styles["table_header"]),
            _p("归档证据", styles["table_header"]),
            _p("法规依据", styles["table_header"]),
        ]
    ]
    for requirement in report.application.requirements:
        evidence = evidence_by_category.get(requirement.key.value, [])
        evidence_text = "<br/>".join(
            f"{html.escape(item.file_name)}<br/>"
            f"<font color='#687875'>SHA-256 {item.sha256[:12]}...</font>"
            for item in evidence
        ) or "未归档"
        rows.append(
            [
                _p(requirement.title, styles["body"]),
                _p(REQUIREMENT_LABELS[requirement.status.value], styles["small"]),
                Paragraph(evidence_text, styles["small"]),
                _p(requirement.regulatory_basis, styles["small"]),
            ]
        )
    table = Table(
        rows,
        colWidths=[38 * mm, 20 * mm, 58 * mm, 59 * mm],
        repeatRows=1,
    )
    table.setStyle(_data_table_style())
    return [_p("3. 证据覆盖矩阵", styles["section"]), table]


def _build_consistency_section(report, styles) -> list[object]:
    rows = [
        [
            _p("检查字段", styles["table_header"]),
            _p("判定", styles["table_header"]),
            _p("来源取值", styles["table_header"]),
            _p("结果说明", styles["table_header"]),
        ]
    ]
    for check in report.consistency.checks:
        values = "<br/>".join(
            f"<font color='#687875'>{html.escape(item.source_label)}</font>："
            f"{html.escape(item.value)}"
            for item in check.occurrences
        ) or "未提取到字段"
        rows.append(
            [
                _p(check.label, styles["body"]),
                _p(CONSISTENCY_LABELS[check.status.value], styles["small"]),
                Paragraph(values, styles["small"]),
                _p(check.message, styles["small"]),
            ]
        )
    table = Table(
        rows,
        colWidths=[28 * mm, 20 * mm, 76 * mm, 51 * mm],
        repeatRows=1,
    )
    table.setStyle(_data_table_style())
    return [_p("4. 跨文档一致性", styles["section"]), table]


def _build_findings(report, styles) -> list[object]:
    output: list[object] = [_p("5. 问题与整改记录", styles["section"])]
    category_titles = {
        requirement.key.value: requirement.title
        for requirement in report.application.requirements
    }
    if not report.precheck.findings:
        output.append(_callout("本轮预审未发现阻断项或警告项。", styles, PRIMARY_SOFT, PRIMARY))
        return output

    for index, finding in enumerate(report.precheck.findings, start=1):
        severity = "阻断" if finding.severity.value == "blocker" else "警告"
        severity_color = DANGER if finding.severity.value == "blocker" else WARNING
        severity_soft = (
            DANGER_SOFT if finding.severity.value == "blocker" else WARNING_SOFT
        )
        heading = Table(
            [
                [
                    _p(f"{index:02d}  {severity}", styles["small"], color=severity_color),
                    _p(finding.title, styles["body"]),
                    _p(
                        REMEDIATION_LABELS[finding.remediation_status.value],
                        styles["small"],
                    ),
                ]
            ],
            colWidths=[24 * mm, 121 * mm, 30 * mm],
        )
        heading.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), severity_soft),
                    ("BACKGROUND", (1, 0), (-1, 0), SOFT),
                    ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        details = [
            [
                _p("资料类别", styles["small"]),
                _p(category_titles[finding.category_key.value], styles["body"]),
                _p("责任人", styles["small"]),
                _p(finding.assignee or "未分配", styles["body"]),
            ],
            [
                _p("问题说明", styles["small"]),
                _p(finding.description, styles["body"]),
                "",
                "",
            ],
            [
                _p("法规依据", styles["small"]),
                _p(finding.regulatory_basis, styles["body"]),
                "",
                "",
            ],
            [
                _p("整改要求", styles["small"]),
                _p(finding.remediation, styles["body"]),
                "",
                "",
            ],
            [
                _p("处理结论", styles["small"]),
                _p(finding.resolution_note or "尚未形成处理结论", styles["body"]),
                "",
                "",
            ],
        ]
        detail_table = Table(
            details,
            colWidths=[22 * mm, 98 * mm, 20 * mm, 35 * mm],
        )
        detail_style = _detail_table_style()
        for row_index in range(1, len(details)):
            detail_style.add("SPAN", (1, row_index), (3, row_index))
        detail_table.setStyle(detail_style)
        output.append(KeepTogether([heading, detail_table, Spacer(1, 3 * mm)]))
    return output


def _build_traceability_appendix(report, styles) -> list[object]:
    rows = [
        [
            _p("资料类别", styles["table_header"]),
            _p("文件与归档信息", styles["table_header"]),
            _p("SHA-256", styles["table_header"]),
        ]
    ]
    for evidence in report.evidence_manifest:
        digest = " ".join(
            evidence.sha256[index : index + 8]
            for index in range(0, len(evidence.sha256), 8)
        )
        rows.append(
            [
                _p(evidence.category_title, styles["small"]),
                _p(
                    f"{evidence.file_name}\n"
                    f"{_format_size(evidence.size_bytes)} · {evidence.uploaded_by} · "
                    f"{_format_dt(evidence.created_at)}",
                    styles["small"],
                ),
                _p(digest, styles["small"]),
            ]
        )
    trace_table = Table(
        rows,
        colWidths=[40 * mm, 73 * mm, 62 * mm],
        repeatRows=1,
    )
    trace_table.setStyle(_data_table_style())
    return [
        PageBreak(),
        _p("附录 A. 审计追踪", styles["section"]),
        _p(
            f"报告 ID：{report.report_id}\n"
            f"预审运行 ID：{report.precheck.id}\n"
            f"预审完成时间：{_format_dt(report.precheck.completed_at)}\n"
            f"预审发起人：{report.precheck.initiated_by}\n"
            f"报告生成责任人：{report.generated_by}",
            styles["body"],
        ),
        Spacer(1, 3 * mm),
        trace_table,
        Spacer(1, 4 * mm),
        _p(
            "本报告用于申报资料内部预审与整改协作，不替代注册检验、临床评价、"
            "质量体系审核或监管机构的最终审评结论。",
            styles["small"],
        ),
    ]


def _p(text: object, style: ParagraphStyle, color=None) -> Paragraph:
    escaped = html.escape(str(text)).replace("\n", "<br/>")
    if color is not None:
        color_value = color.hexval().replace("0x", "#")
        escaped = f"<font color='{color_value}'>{escaped}</font>"
    return Paragraph(escaped, style)


def _callout(text, styles, background, ink) -> Table:
    table = Table([[_p(text, styles["body"], color=ink)]], colWidths=[175 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.5, ink),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _detail_table_style() -> TableStyle:
    return TableStyle(
        [
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
            ("BACKGROUND", (0, 0), (0, -1), SOFT),
            ("BACKGROUND", (2, 0), (2, -1), SOFT),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )


def _data_table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), SOFT),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )


def _format_dt(value) -> str:
    return value.astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M")


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"
