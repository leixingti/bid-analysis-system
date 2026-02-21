"""Excel 报告生成器 — 生成串标围标分析报告 (.xlsx)"""
import io
from datetime import datetime
from typing import List, Dict, Any
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# === Style Presets ===
HEADER_FONT = Font(name="微软雅黑", size=12, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
TITLE_FONT = Font(name="微软雅黑", size=16, bold=True, color="1F4E79")
SUBTITLE_FONT = Font(name="微软雅黑", size=11, bold=True, color="333333")
BODY_FONT = Font(name="微软雅黑", size=10, color="333333")
DETAIL_FONT = Font(name="微软雅黑", size=9, color="555555")
THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
WRAP_LEFT = Alignment(horizontal="left", vertical="top", wrap_text=True)

RISK_COLORS = {
    "critical": PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid"),
    "high": PatternFill(start_color="FF6600", end_color="FF6600", fill_type="solid"),
    "medium": PatternFill(start_color="FFD700", end_color="FFD700", fill_type="solid"),
    "low": PatternFill(start_color="00B050", end_color="00B050", fill_type="solid"),
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

HIGHLIGHT_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")


class ExcelReportGenerator:
    """生成串标围标分析 Excel 报告"""

    @staticmethod
    def generate(project: Dict, documents: List[Dict], results: List[Dict],
                 risk_summary: Dict) -> io.BytesIO:
        wb = Workbook()

        # Sheet 1: 项目概览
        ExcelReportGenerator._build_overview_sheet(wb, project, risk_summary)
        # Sheet 2: 文档清单
        ExcelReportGenerator._build_documents_sheet(wb, documents)
        # Sheet 3: 检测结果明细（含分项得分）
        ExcelReportGenerator._build_results_sheet(wb, results)
        # Sheet 4: 相似段落对比
        ExcelReportGenerator._build_segments_sheet(wb, results)
        # Sheet 5: 风险预警汇总
        ExcelReportGenerator._build_alerts_sheet(wb, results)

        # Remove default sheet if extra
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    @staticmethod
    def _build_overview_sheet(wb: Workbook, project: Dict, risk_summary: Dict):
        ws = wb.create_sheet("项目概览", 0)

        # Title
        ws.merge_cells("A1:F1")
        ws["A1"] = "串标围标分析报告"
        ws["A1"].font = TITLE_FONT
        ws["A1"].alignment = CENTER
        ws.row_dimensions[1].height = 40

        ws.merge_cells("A2:F2")
        ws["A2"] = f"报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ws["A2"].font = Font(name="微软雅黑", size=9, color="666666")
        ws["A2"].alignment = CENTER

        # Project Info
        info_rows = [
            ("项目名称", project.get("name", "")),
            ("项目编号", project.get("project_code", "N/A")),
            ("项目状态", project.get("status", "")),
            ("文档数量", str(project.get("document_count", 0))),
            ("综合风险评分", f"{(project.get('risk_score') or 0.0):.1f} / 100"),
            ("风险等级", RISK_NAMES.get(project.get("risk_level") or "low", "低风险")),
        ]

        row = 4
        ws.merge_cells(f"A{row}:F{row}")
        ws[f"A{row}"] = "项目基本信息"
        ws[f"A{row}"].font = SUBTITLE_FONT
        row += 1

        for label, value in info_rows:
            ws[f"A{row}"] = label
            ws[f"A{row}"].font = Font(name="微软雅黑", size=10, bold=True)
            ws[f"A{row}"].alignment = LEFT
            ws.merge_cells(f"B{row}:F{row}")
            ws[f"B{row}"] = value
            ws[f"B{row}"].font = BODY_FONT
            ws[f"B{row}"].alignment = LEFT
            for col in range(1, 7):
                ws.cell(row=row, column=col).border = THIN_BORDER
            row += 1

        # Dimension Scores
        row += 1
        ws.merge_cells(f"A{row}:F{row}")
        ws[f"A{row}"] = "各维度检测得分"
        ws[f"A{row}"].font = SUBTITLE_FONT
        row += 1

        dimension_scores = risk_summary.get("dimension_scores", {})
        headers = ["检测维度", "得分", "风险等级"]
        for i, h in enumerate(headers):
            cell = ws.cell(row=row, column=i + 1)
            cell.value = h
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER
            cell.border = THIN_BORDER
        row += 1

        for dim_key, dim_name in TYPE_NAMES.items():
            score = dimension_scores.get(dim_key, 0.0)
            risk = "critical" if score >= 0.7 else "high" if score >= 0.5 else "medium" if score >= 0.3 else "low"
            ws.cell(row=row, column=1, value=dim_name).font = BODY_FONT
            ws.cell(row=row, column=2, value=f"{score:.1%}").font = BODY_FONT
            ws.cell(row=row, column=2).alignment = CENTER
            risk_cell = ws.cell(row=row, column=3, value=RISK_NAMES[risk])
            risk_cell.fill = RISK_COLORS[risk]
            risk_cell.font = Font(name="微软雅黑", size=10, bold=True,
                                  color="FFFFFF" if risk in ["critical", "high"] else "333333")
            risk_cell.alignment = CENTER
            for c in range(1, 4):
                ws.cell(row=row, column=c).border = THIN_BORDER
            row += 1

        # Column widths
        ws.column_dimensions["A"].width = 18
        for col in "BCDEF":
            ws.column_dimensions[col].width = 16

    @staticmethod
    def _build_documents_sheet(wb: Workbook, documents: List[Dict]):
        ws = wb.create_sheet("文档清单")

        headers = ["序号", "投标单位", "文件名", "文件类型", "文件大小(KB)",
                   "文档作者", "创建软件", "创建时间", "页数", "解析状态"]

        for i, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=i)
            cell.value = h
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER
            cell.border = THIN_BORDER

        for idx, doc in enumerate(documents, 1):
            row = idx + 1
            values = [
                idx,
                doc.get("company_name", ""),
                doc.get("file_name", ""),
                doc.get("file_type", ""),
                round(doc.get("file_size", 0) / 1024, 1),
                doc.get("meta_author", ""),
                doc.get("meta_creator", ""),
                doc.get("meta_created_time", ""),
                doc.get("page_count", 0),
                "已解析" if doc.get("parsed") == 1 else "失败" if doc.get("parsed") == 2 else "未解析",
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.font = BODY_FONT
                cell.alignment = CENTER if col != 3 else LEFT
                cell.border = THIN_BORDER

        # Auto width
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].width = max(
                12, len(str(headers[col - 1])) * 2
            )

    @staticmethod
    def _build_results_sheet(wb: Workbook, results: List[Dict]):
        ws = wb.create_sheet("检测结果明细")

        # 扩展表头：加入分项得分
        headers = ["序号", "检测类型", "涉及单位A", "涉及单位B", "综合得分", "风险等级",
                   "SimHash", "TF-IDF余弦", "Jaccard", "说明"]
        for i, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=i)
            cell.value = h
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER
            cell.border = THIN_BORDER

        for idx, r in enumerate(sorted(results, key=lambda x: x.get("score", 0), reverse=True), 1):
            row = idx + 1
            risk = r.get("risk_level") or "low"
            details = r.get("details") or {}

            values = [
                idx,
                TYPE_NAMES.get(r.get("analysis_type", ""), r.get("analysis_type", "")),
                r.get("company_a") or "",
                r.get("company_b") or "",
                f"{(r.get('score') or 0):.1%}",
                RISK_NAMES.get(risk, risk),
                f"{details.get('simhash_similarity', 0):.1%}" if r.get("analysis_type") == "content_similarity" else "-",
                f"{details.get('cosine_similarity', 0):.1%}" if r.get("analysis_type") == "content_similarity" else "-",
                f"{details.get('jaccard_similarity', 0):.1%}" if r.get("analysis_type") == "content_similarity" else "-",
                r.get("summary") or "",
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.font = BODY_FONT
                cell.alignment = LEFT if col == 10 else CENTER
                cell.border = THIN_BORDER
                if col == 6:
                    cell.fill = RISK_COLORS.get(risk, PatternFill())
                    if risk in ["critical", "high"]:
                        cell.font = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")

        ws.column_dimensions["A"].width = 6
        ws.column_dimensions["B"].width = 14
        ws.column_dimensions["C"].width = 18
        ws.column_dimensions["D"].width = 18
        ws.column_dimensions["E"].width = 10
        ws.column_dimensions["F"].width = 10
        ws.column_dimensions["G"].width = 10
        ws.column_dimensions["H"].width = 12
        ws.column_dimensions["I"].width = 10
        ws.column_dimensions["J"].width = 50

    @staticmethod
    def _build_segments_sheet(wb: Workbook, results: List[Dict]):
        """新增 Sheet：相似段落对比详情"""
        ws = wb.create_sheet("相似段落对比")

        # Title
        ws.merge_cells("A1:E1")
        ws["A1"] = "文本相似度 — 相似段落对比详情"
        ws["A1"].font = SUBTITLE_FONT
        ws.row_dimensions[1].height = 28

        headers = ["序号", "涉及单位", "相似度", "文档A段落", "文档B段落"]
        for i, h in enumerate(headers, 1):
            cell = ws.cell(row=3, column=i)
            cell.value = h
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER
            cell.border = THIN_BORDER

        row = 4
        seg_idx = 0
        has_segments = False

        for r in sorted(results, key=lambda x: x.get("score", 0), reverse=True):
            if r.get("analysis_type") != "content_similarity":
                continue
            details = r.get("details") or {}
            segments = details.get("similar_segments", [])
            company_a = r.get("company_a") or "文档A"
            company_b = r.get("company_b") or "文档B"

            if not segments:
                continue

            has_segments = True

            # 组标题行
            ws.merge_cells(f"A{row}:E{row}")
            ws[f"A{row}"] = f"▎{company_a}  vs  {company_b}（综合相似度 {(r.get('score') or 0):.1%}）"
            ws[f"A{row}"].font = Font(name="微软雅黑", size=10, bold=True, color="1F4E79")
            ws.row_dimensions[row].height = 24
            row += 1

            for seg in segments[:20]:
                seg_idx += 1
                text_a = seg.get("text_a_segment", "")
                text_b = seg.get("text_b_segment", "")
                sim = seg.get("similarity", 0)

                ws.cell(row=row, column=1, value=seg_idx).font = BODY_FONT
                ws.cell(row=row, column=1).alignment = CENTER
                ws.cell(row=row, column=2, value=f"{company_a} vs {company_b}").font = DETAIL_FONT
                ws.cell(row=row, column=2).alignment = CENTER

                sim_cell = ws.cell(row=row, column=3, value=f"{sim:.0%}")
                sim_cell.font = Font(name="微软雅黑", size=10, bold=True,
                                     color="FF0000" if sim >= 0.7 else "FF6600" if sim >= 0.5 else "333333")
                sim_cell.alignment = CENTER

                cell_a = ws.cell(row=row, column=4, value=text_a)
                cell_a.font = DETAIL_FONT
                cell_a.alignment = WRAP_LEFT

                cell_b = ws.cell(row=row, column=5, value=text_b)
                cell_b.font = DETAIL_FONT
                cell_b.alignment = WRAP_LEFT

                # 高相似度行高亮
                if sim >= 0.6:
                    for c in range(1, 6):
                        ws.cell(row=row, column=c).fill = HIGHLIGHT_FILL

                for c in range(1, 6):
                    ws.cell(row=row, column=c).border = THIN_BORDER

                ws.row_dimensions[row].height = max(40, min(80, len(text_a) // 2))
                row += 1

            row += 1  # blank row between groups

        if not has_segments:
            ws.merge_cells(f"A{row}:E{row}")
            ws[f"A{row}"] = "未检测到高相似度段落"
            ws[f"A{row}"].font = Font(name="微软雅黑", size=10, color="999999")
            ws[f"A{row}"].alignment = CENTER

        ws.column_dimensions["A"].width = 6
        ws.column_dimensions["B"].width = 22
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 45
        ws.column_dimensions["E"].width = 45

    @staticmethod
    def _build_alerts_sheet(wb: Workbook, results: List[Dict]):
        ws = wb.create_sheet("风险预警汇总")

        # Count by type
        type_counts = {}
        risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for r in results:
            t = r.get("analysis_type", "other")
            type_counts[t] = type_counts.get(t, 0) + 1
            rl = r.get("risk_level") or "low"
            if rl in risk_counts:
                risk_counts[rl] += 1

        ws["A1"] = "预警统计"
        ws["A1"].font = SUBTITLE_FONT
        ws.merge_cells("A1:D1")

        # By risk level
        ws["A3"] = "风险等级"
        ws["B3"] = "数量"
        ws["A3"].font = HEADER_FONT
        ws["A3"].fill = HEADER_FILL
        ws["B3"].font = HEADER_FONT
        ws["B3"].fill = HEADER_FILL

        for i, (level, count) in enumerate(risk_counts.items()):
            row = 4 + i
            ws.cell(row=row, column=1, value=RISK_NAMES[level]).font = BODY_FONT
            ws.cell(row=row, column=1).fill = RISK_COLORS[level]
            ws.cell(row=row, column=2, value=count).font = BODY_FONT
            ws.cell(row=row, column=2).alignment = CENTER

        # By type
        ws["A9"] = "检测类型"
        ws["B9"] = "数量"
        ws["A9"].font = HEADER_FONT
        ws["A9"].fill = HEADER_FILL
        ws["B9"].font = HEADER_FONT
        ws["B9"].fill = HEADER_FILL

        for i, (t, count) in enumerate(type_counts.items()):
            row = 10 + i
            ws.cell(row=row, column=1, value=TYPE_NAMES.get(t, t)).font = BODY_FONT
            ws.cell(row=row, column=2, value=count).font = BODY_FONT
            ws.cell(row=row, column=2).alignment = CENTER

        ws.column_dimensions["A"].width = 20
        ws.column_dimensions["B"].width = 12
