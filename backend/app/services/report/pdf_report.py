"""PDF 报告生成器 — 生成串标围标分析报告 (.pdf)"""
import io
from datetime import datetime
from typing import List, Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Chinese font (fallback to Helvetica if not available)
FONT_NAME = "Helvetica"
FONT_NAME_BOLD = "Helvetica-Bold"
try:
    pdfmetrics.registerFont(TTFont("SimHei", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"))
    FONT_NAME = "SimHei"
    FONT_NAME_BOLD = "SimHei"
except Exception:
    try:
        pdfmetrics.registerFont(TTFont("SimHei", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"))
        FONT_NAME = "SimHei"
        FONT_NAME_BOLD = "SimHei"
    except Exception:
        pass

RISK_COLORS = {
    "critical": colors.HexColor("#FF0000"),
    "high": colors.HexColor("#FF6600"),
    "medium": colors.HexColor("#FFD700"),
    "low": colors.HexColor("#00B050"),
}
RISK_NAMES = {"critical": "严重", "high": "高风险", "medium": "中等", "low": "低风险"}
TYPE_NAMES = {
    "content_similarity": "文本相似度",
    "metadata_match": "元数据关联",
    "format_match": "格式指纹",
    "timestamp_cluster": "时间戳聚集",
    "entity_cross": "实体交叉",
    "error_pattern": "错误模式",
    "price_analysis": "报价分析",
}


class PDFReportGenerator:
    """生成串标围标分析 PDF 报告"""

    @staticmethod
    def generate(project: Dict, documents: List[Dict], results: List[Dict],
                 risk_summary: Dict) -> io.BytesIO:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm, bottomMargin=2 * cm,
        )

        styles = PDFReportGenerator._create_styles()
        story = []

        # === Title Page ===
        story.append(Spacer(1, 3 * cm))
        story.append(Paragraph("串标围标自动分析报告", styles["title"]))
        story.append(Spacer(1, 1 * cm))
        story.append(Paragraph(project.get("name", "未命名项目"), styles["subtitle"]))
        story.append(Spacer(1, 0.5 * cm))
        story.append(HRFlowable(width="60%", thickness=2, color=colors.HexColor("#1F4E79")))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(
            f"报告编号：{project.get('project_code', 'N/A')}", styles["meta"]
        ))
        story.append(Paragraph(
            f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}", styles["meta"]
        ))
        risk_score = project.get("risk_score", 0)
        risk_level = project.get("risk_level", "low")
        story.append(Paragraph(
            f"综合风险评分：{risk_score:.1f} / 100（{RISK_NAMES.get(risk_level, '低风险')}）",
            styles["meta"]
        ))
        story.append(PageBreak())

        # === Section 1: Project Overview ===
        story.append(Paragraph("一、项目概况", styles["h1"]))
        story.append(Spacer(1, 3 * mm))

        info_data = [
            ["项目名称", project.get("name", "")],
            ["项目编号", project.get("project_code", "N/A")],
            ["投标文档数", str(len(documents))],
            ["分析状态", project.get("status", "")],
            ["风险评分", f"{risk_score:.1f} / 100"],
            ["风险等级", RISK_NAMES.get(risk_level, "低风险")],
        ]
        info_table = Table(info_data, colWidths=[4 * cm, 12 * cm])
        info_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTNAME", (0, 0), (0, -1), FONT_NAME_BOLD),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 8 * mm))

        # === Section 2: Dimension Scores ===
        story.append(Paragraph("二、各维度检测结果", styles["h1"]))
        story.append(Spacer(1, 3 * mm))

        dimension_scores = risk_summary.get("dimension_scores", {})
        dim_header = ["检测维度", "得分", "风险等级"]
        dim_data = [dim_header]
        for dim_key, dim_name in TYPE_NAMES.items():
            score = dimension_scores.get(dim_key, 0.0)
            risk = "critical" if score >= 0.7 else "high" if score >= 0.5 else "medium" if score >= 0.3 else "low"
            dim_data.append([dim_name, f"{score:.1%}", RISK_NAMES[risk]])

        dim_table = Table(dim_data, colWidths=[5 * cm, 4 * cm, 4 * cm])
        dim_style = [
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTNAME", (0, 0), (-1, 0), FONT_NAME_BOLD),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        # Color code risk cells
        for i, row in enumerate(dim_data[1:], 1):
            score_val = dimension_scores.get(list(TYPE_NAMES.keys())[i - 1], 0.0)
            risk = "critical" if score_val >= 0.7 else "high" if score_val >= 0.5 else "medium" if score_val >= 0.3 else "low"
            dim_style.append(("BACKGROUND", (2, i), (2, i), RISK_COLORS[risk]))
            if risk in ["critical", "high"]:
                dim_style.append(("TEXTCOLOR", (2, i), (2, i), colors.white))

        dim_table.setStyle(TableStyle(dim_style))
        story.append(dim_table)
        story.append(Spacer(1, 8 * mm))

        # === Section 3: Detailed Results ===
        story.append(Paragraph("三、检测结果明细", styles["h1"]))
        story.append(Spacer(1, 3 * mm))

        sorted_results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)

        if sorted_results:
            res_header = ["序号", "检测类型", "单位A", "单位B", "得分", "风险", "说明"]
            res_data = [res_header]
            for idx, r in enumerate(sorted_results[:30], 1):  # Top 30
                risk = r.get("risk_level", "low")
                summary_text = r.get("summary", "")
                if len(summary_text) > 40:
                    summary_text = summary_text[:40] + "..."
                res_data.append([
                    str(idx),
                    TYPE_NAMES.get(r.get("analysis_type", ""), ""),
                    r.get("company_a", "")[:10],
                    r.get("company_b", "")[:10],
                    f"{r.get('score', 0):.0%}",
                    RISK_NAMES.get(risk, risk),
                    summary_text,
                ])

            res_table = Table(res_data, colWidths=[1 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 1.5 * cm, 1.5 * cm, 5.5 * cm])
            res_style = [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 0), (-1, 0), FONT_NAME_BOLD),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (5, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F8F8")]),
            ]
            res_table.setStyle(TableStyle(res_style))
            story.append(res_table)
        else:
            story.append(Paragraph("暂无检测结果", styles["body"]))

        story.append(Spacer(1, 8 * mm))

        # === Section 4: Conclusion ===
        story.append(Paragraph("四、分析结论", styles["h1"]))
        story.append(Spacer(1, 3 * mm))

        alert_count = len(results)
        critical_count = sum(1 for r in results if r.get("risk_level") == "critical")
        high_count = sum(1 for r in results if r.get("risk_level") == "high")

        conclusion_lines = [
            f"本次分析共检测 {len(documents)} 份投标文档，发现 {alert_count} 项异常预警。",
        ]
        if critical_count > 0:
            conclusion_lines.append(f"其中严重风险 {critical_count} 项，高风险 {high_count} 项，建议重点审查。")
        elif high_count > 0:
            conclusion_lines.append(f"其中高风险 {high_count} 项，建议关注相关投标文件。")
        elif alert_count > 0:
            conclusion_lines.append("未发现严重异常，但仍有部分指标需要关注。")
        else:
            conclusion_lines.append("各项检测指标正常，未发现明显串标围标迹象。")

        conclusion_lines.append("")
        conclusion_lines.append("注：本报告由系统自动生成，仅供参考，最终判定需结合人工审查。")

        for line in conclusion_lines:
            story.append(Paragraph(line, styles["body"]))

        # Build
        doc.build(story)
        buf.seek(0)
        return buf

    @staticmethod
    def _create_styles():
        styles = getSampleStyleSheet()
        custom = {
            "title": ParagraphStyle(
                "custom_title", parent=styles["Title"],
                fontName=FONT_NAME_BOLD, fontSize=24, alignment=TA_CENTER,
                textColor=colors.HexColor("#1F4E79"), spaceAfter=12,
            ),
            "subtitle": ParagraphStyle(
                "custom_subtitle", parent=styles["Title"],
                fontName=FONT_NAME, fontSize=16, alignment=TA_CENTER,
                textColor=colors.HexColor("#333333"), spaceAfter=6,
            ),
            "meta": ParagraphStyle(
                "custom_meta", parent=styles["Normal"],
                fontName=FONT_NAME, fontSize=11, alignment=TA_CENTER,
                textColor=colors.HexColor("#666666"), spaceAfter=4,
            ),
            "h1": ParagraphStyle(
                "custom_h1", parent=styles["Heading1"],
                fontName=FONT_NAME_BOLD, fontSize=14,
                textColor=colors.HexColor("#1F4E79"), spaceBefore=12, spaceAfter=6,
                borderWidth=0, borderColor=colors.HexColor("#1F4E79"),
            ),
            "body": ParagraphStyle(
                "custom_body", parent=styles["Normal"],
                fontName=FONT_NAME, fontSize=10,
                textColor=colors.HexColor("#333333"),
                leading=16, spaceAfter=4,
            ),
        }
        return custom
