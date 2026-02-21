"""PDF 报告生成器 — 生成串标围标分析报告 (.pdf)"""
import io
from datetime import datetime
from typing import List, Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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
    "critical": colors.HexColor("#FF0000"), "high": colors.HexColor("#FF6600"),
    "medium": colors.HexColor("#FFD700"), "low": colors.HexColor("#00B050"),
}
RISK_NAMES = {"critical": "严重", "high": "高风险", "medium": "中等", "low": "低风险"}
TYPE_NAMES = {
    "content_similarity": "文本相似度", "metadata_match": "元数据关联",
    "format_match": "格式指纹", "timestamp_cluster": "时间戳聚集",
    "entity_cross": "实体交叉", "error_pattern": "错误模式", "price_analysis": "报价分析",
}
DARK_BLUE = colors.HexColor("#1F4E79")
MID_BLUE = colors.HexColor("#2E75B6")
LIGHT_BG = colors.HexColor("#F8F8F8")
GRID_COLOR = colors.HexColor("#D9D9D9")
HIGHLIGHT_BG = colors.HexColor("#FFF2CC")


def _safe(val, default=""):
    return val if val is not None else default


class PDFReportGenerator:

    @staticmethod
    def generate(project: Dict, documents: List[Dict], results: List[Dict],
                 risk_summary: Dict) -> io.BytesIO:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        styles = PDFReportGenerator._create_styles()
        story = []

        # === Cover ===
        risk_score = project.get("risk_score") or 0.0
        risk_level = project.get("risk_level") or "low"
        story.append(Spacer(1, 3*cm))
        story.append(Paragraph("串标围标自动分析报告", styles["title"]))
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph(project.get("name", "未命名项目"), styles["subtitle"]))
        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width="60%", thickness=2, color=DARK_BLUE))
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(f"报告编号：{project.get('project_code','N/A')}", styles["meta"]))
        story.append(Paragraph(f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}", styles["meta"]))
        story.append(Paragraph(f"综合风险评分：{risk_score:.1f} / 100（{RISK_NAMES.get(risk_level,'低风险')}）", styles["meta"]))
        story.append(PageBreak())

        # === Section 1: Project Overview ===
        story.append(Paragraph("一、项目概况", styles["h1"]))
        story.append(Spacer(1, 3*mm))
        info_data = [["项目名称", _safe(project.get("name"))], ["项目编号", _safe(project.get("project_code"), "N/A")],
                     ["文档数", str(len(documents))], ["风险评分", f"{risk_score:.1f} / 100"],
                     ["风险等级", RISK_NAMES.get(risk_level, "低风险")]]
        t = Table(info_data, colWidths=[4*cm, 12*cm])
        t.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),FONT_NAME),("FONTSIZE",(0,0),(-1,-1),10),
            ("FONTNAME",(0,0),(0,-1),FONT_NAME_BOLD),("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F2F2F2")),
            ("GRID",(0,0),(-1,-1),0.5,GRID_COLOR),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),("LEFTPADDING",(0,0),(-1,-1),8)]))
        story.append(t)
        story.append(Spacer(1, 8*mm))

        # === Section 2: Dimension Scores ===
        story.append(Paragraph("二、各维度检测结果", styles["h1"]))
        story.append(Spacer(1, 3*mm))
        dimension_scores = risk_summary.get("dimension_scores", {})
        dim_data = [["检测维度", "得分", "风险等级"]]
        for dk, dn in TYPE_NAMES.items():
            sc = dimension_scores.get(dk, 0.0)
            rk = "critical" if sc >= 0.7 else "high" if sc >= 0.5 else "medium" if sc >= 0.3 else "low"
            dim_data.append([dn, f"{sc:.1%}", RISK_NAMES[rk]])
        dt = Table(dim_data, colWidths=[5*cm, 4*cm, 4*cm])
        ds = [("FONTNAME",(0,0),(-1,-1),FONT_NAME),("FONTSIZE",(0,0),(-1,-1),10),
              ("FONTNAME",(0,0),(-1,0),FONT_NAME_BOLD),("BACKGROUND",(0,0),(-1,0),DARK_BLUE),
              ("TEXTCOLOR",(0,0),(-1,0),colors.white),("ALIGN",(1,0),(-1,-1),"CENTER"),
              ("GRID",(0,0),(-1,-1),0.5,GRID_COLOR),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]
        for i in range(1, len(dim_data)):
            sv = dimension_scores.get(list(TYPE_NAMES.keys())[i-1], 0.0)
            rk = "critical" if sv >= 0.7 else "high" if sv >= 0.5 else "medium" if sv >= 0.3 else "low"
            ds.append(("BACKGROUND",(2,i),(2,i),RISK_COLORS[rk]))
            if rk in ["critical","high"]:
                ds.append(("TEXTCOLOR",(2,i),(2,i),colors.white))
        dt.setStyle(TableStyle(ds))
        story.append(dt)
        story.append(Spacer(1, 8*mm))

        # === Section 3: Result Summary ===
        story.append(Paragraph("三、检测结果明细", styles["h1"]))
        story.append(Spacer(1, 3*mm))
        sorted_results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)
        if sorted_results:
            res_data = [["序号", "检测类型", "单位A", "单位B", "得分", "风险", "说明"]]
            for idx, r in enumerate(sorted_results[:30], 1):
                sm = _safe(r.get("summary"))
                if len(sm) > 40: sm = sm[:40] + "..."
                res_data.append([str(idx), TYPE_NAMES.get(r.get("analysis_type",""),""),
                    _safe(r.get("company_a"))[:10], _safe(r.get("company_b"))[:10],
                    f"{(r.get('score') or 0):.0%}", RISK_NAMES.get(r.get("risk_level") or "low",""), sm])
            rt = Table(res_data, colWidths=[1*cm, 2.5*cm, 2.5*cm, 2.5*cm, 1.5*cm, 1.5*cm, 5.5*cm])
            rt.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),FONT_NAME),("FONTSIZE",(0,0),(-1,-1),8),
                ("FONTNAME",(0,0),(-1,0),FONT_NAME_BOLD),("BACKGROUND",(0,0),(-1,0),DARK_BLUE),
                ("TEXTCOLOR",(0,0),(-1,0),colors.white),("ALIGN",(0,0),(5,-1),"CENTER"),
                ("GRID",(0,0),(-1,-1),0.5,GRID_COLOR),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, LIGHT_BG])]))
            story.append(rt)
        story.append(Spacer(1, 8*mm))

        # === Section 4: Detailed per-alert breakdown ===
        story.append(Paragraph("四、检测详情", styles["h1"]))
        story.append(Spacer(1, 3*mm))

        for r in sorted_results:
            atype = r.get("analysis_type", "")
            details = r.get("details") or {}
            risk = r.get("risk_level") or "low"
            score = r.get("score") or 0
            ca = _safe(r.get("company_a"), "")
            cb = _safe(r.get("company_b"), "")
            pair = f"{ca} vs {cb}" if ca and cb else ""

            # Section title
            story.append(Paragraph(
                f"<b>{TYPE_NAMES.get(atype, atype)}</b>　{pair}　得分: {score:.1%}（{RISK_NAMES.get(risk,'')}）",
                styles["h2"]))
            story.append(Paragraph(_safe(r.get("summary")), styles["body"]))
            story.append(Spacer(1, 2*mm))

            # Type-specific detail table
            detail_elements = PDFReportGenerator._render_detail(atype, details, styles, ca, cb)
            for el in detail_elements:
                story.append(el)
            story.append(Spacer(1, 6*mm))

        # === Section 5: Conclusion ===
        story.append(Paragraph("五、分析结论", styles["h1"]))
        story.append(Spacer(1, 3*mm))
        ac = len(results)
        cc = sum(1 for r in results if r.get("risk_level") == "critical")
        hc = sum(1 for r in results if r.get("risk_level") == "high")
        story.append(Paragraph(f"本次分析共检测 {len(documents)} 份投标文档，发现 {ac} 项异常预警。", styles["body"]))
        if cc > 0:
            story.append(Paragraph(f"其中严重风险 {cc} 项，高风险 {hc} 项，建议重点审查。", styles["body"]))
        elif hc > 0:
            story.append(Paragraph(f"其中高风险 {hc} 项，建议关注相关投标文件。", styles["body"]))
        elif ac > 0:
            story.append(Paragraph("未发现严重异常，但仍有部分指标需要关注。", styles["body"]))
        else:
            story.append(Paragraph("各项检测指标正常，未发现明显串标围标迹象。", styles["body"]))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph("注：本报告由系统自动生成，仅供参考，最终判定需结合人工审查。", styles["body"]))

        doc.build(story)
        buf.seek(0)
        return buf

    @staticmethod
    def _render_detail(atype, details, styles, ca, cb):
        """根据预警类型生成对应的详情元素列表"""
        elements = []
        base_style = [("FONTNAME",(0,0),(-1,-1),FONT_NAME),("FONTSIZE",(0,0),(-1,-1),8),
                      ("FONTNAME",(0,0),(-1,0),FONT_NAME_BOLD),("BACKGROUND",(0,0),(-1,0),MID_BLUE),
                      ("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.5,GRID_COLOR),
                      ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                      ("VALIGN",(0,0),(-1,-1),"TOP")]

        if atype == "content_similarity":
            # Sub-scores
            subs = []
            for label, key in [("SimHash","simhash_similarity"),("TF-IDF余弦","cosine_similarity"),
                                ("Jaccard","jaccard_similarity"),("分词引擎","tokenizer")]:
                v = details.get(key)
                if v is not None:
                    subs.append([label, f"{v:.1%}" if isinstance(v, (int,float)) else str(v)])
            if subs:
                st = Table(subs, colWidths=[4*cm, 6*cm])
                st.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),FONT_NAME),("FONTSIZE",(0,0),(-1,-1),9),
                    ("FONTNAME",(0,0),(0,-1),FONT_NAME_BOLD),("GRID",(0,0),(-1,-1),0.5,GRID_COLOR),
                    ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
                elements.append(st)
                elements.append(Spacer(1, 3*mm))

            # Segments
            segs = details.get("similar_segments", [])
            if segs:
                seg_data = [["#", "相似度", f"{ca or '文档A'}段落", f"{cb or '文档B'}段落"]]
                for i, s in enumerate(segs[:15], 1):
                    ta = _safe(s.get("text_a_segment"))[:100]
                    tb = _safe(s.get("text_b_segment"))[:100]
                    seg_data.append([str(i), f"{s.get('similarity',0):.0%}",
                                     Paragraph(ta, styles["cell"]), Paragraph(tb, styles["cell"])])
                st2 = Table(seg_data, colWidths=[0.8*cm, 1.5*cm, 7*cm, 7*cm])
                ss = list(base_style) + [("ALIGN",(0,0),(1,-1),"CENTER")]
                for i, s in enumerate(segs[:15], 1):
                    if s.get("similarity", 0) >= 0.6:
                        ss.append(("BACKGROUND",(0,i),(-1,i),HIGHLIGHT_BG))
                st2.setStyle(TableStyle(ss))
                elements.append(st2)

        elif atype in ("metadata_match", "format_match"):
            alerts = details.get("alerts", [])
            if alerts:
                data = [["检测项", "文档A", "文档B", "说明"]]
                for a in alerts:
                    data.append([
                        Paragraph(_safe(a.get("field") or a.get("type")), styles["cell"]),
                        Paragraph(str(_safe(a.get("value_a"),"-")), styles["cell"]),
                        Paragraph(str(_safe(a.get("value_b"),"-")), styles["cell"]),
                        Paragraph(_safe(a.get("description") or a.get("message")), styles["cell"]),
                    ])
                t = Table(data, colWidths=[3.5*cm, 4.5*cm, 4.5*cm, 3.8*cm])
                t.setStyle(TableStyle(base_style + [("ALIGN",(0,0),(0,-1),"LEFT")]))
                elements.append(t)

        elif atype == "timestamp_cluster":
            info = [[f"聚集组数: {details.get('cluster_count',0)}",
                     f"时间窗口: {details.get('threshold_minutes',5)} 分钟",
                     f"文档数: {details.get('total_documents',0)}"]]
            t = Table(info, colWidths=[5.4*cm, 5.4*cm, 5.4*cm])
            t.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),FONT_NAME),("FONTSIZE",(0,0),(-1,-1),9),
                ("GRID",(0,0),(-1,-1),0.5,GRID_COLOR),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
            elements.append(t)

        elif atype == "entity_cross":
            hits = details.get("hits", [])
            if hits:
                data = [["实体类型", "泄露值", "说明"]]
                for h in hits:
                    data.append([
                        Paragraph(_safe(h.get("type") or h.get("entity_type")), styles["cell"]),
                        Paragraph(_safe(h.get("value") or h.get("entity")), styles["cell"]),
                        Paragraph(_safe(h.get("description") or h.get("context")), styles["cell"]),
                    ])
                t = Table(data, colWidths=[3*cm, 5*cm, 8.3*cm])
                t.setStyle(TableStyle(base_style))
                elements.append(t)

        elif atype == "error_pattern":
            items = []
            for e in details.get("common_errors", []):
                items.append(["共性错误", str(e) if isinstance(e,str) else _safe(e.get("error") or e.get("word"), str(e))])
            for s in details.get("common_standards", []):
                items.append(["过期标准", str(s) if isinstance(s,str) else _safe(s.get("standard") or s.get("code"), str(s))])
            for p in details.get("common_patterns", []):
                items.append(["共性模式", str(p) if isinstance(p,str) else _safe(p.get("pattern") or p.get("description"), str(p))])
            if details.get("type"):
                items.insert(0, ["错误类型", details["type"]])
            if items:
                data = [["类别", "内容"]]
                for cat, content in items:
                    data.append([cat, Paragraph(content, styles["cell"])])
                t = Table(data, colWidths=[3*cm, 13.3*cm])
                t.setStyle(TableStyle(base_style))
                elements.append(t)

        elif atype == "price_analysis":
            rows = []
            if details.get("alert_type"):
                rows.append(["异常类型", details["alert_type"]])
            for key, label in [("arithmetic","等差数列"),("geometric","等比数列"),("fixed_coeff","固定系数"),("cluster","价格聚集")]:
                sub = details.get(key, {})
                if sub and sub.get("detected"):
                    rows.append([label, str(sub)[:200]])
            if rows:
                data = []
                for label, val in rows:
                    data.append([label, Paragraph(str(val), styles["cell"])])
                t = Table(data, colWidths=[3*cm, 13.3*cm])
                t.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),FONT_NAME),("FONTSIZE",(0,0),(-1,-1),9),
                    ("FONTNAME",(0,0),(0,-1),FONT_NAME_BOLD),("GRID",(0,0),(-1,-1),0.5,GRID_COLOR),
                    ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
                elements.append(t)

        if not elements:
            elements.append(Paragraph("无额外详情数据", styles["body"]))
        return elements

    @staticmethod
    def _create_styles():
        styles = getSampleStyleSheet()
        return {
            "title": ParagraphStyle("t", parent=styles["Title"], fontName=FONT_NAME_BOLD, fontSize=24,
                alignment=TA_CENTER, textColor=DARK_BLUE, spaceAfter=12),
            "subtitle": ParagraphStyle("st", parent=styles["Title"], fontName=FONT_NAME, fontSize=16,
                alignment=TA_CENTER, textColor=colors.HexColor("#333333"), spaceAfter=6),
            "meta": ParagraphStyle("m", parent=styles["Normal"], fontName=FONT_NAME, fontSize=11,
                alignment=TA_CENTER, textColor=colors.HexColor("#666666"), spaceAfter=4),
            "h1": ParagraphStyle("h1", parent=styles["Heading1"], fontName=FONT_NAME_BOLD, fontSize=14,
                textColor=DARK_BLUE, spaceBefore=12, spaceAfter=6),
            "h2": ParagraphStyle("h2", parent=styles["Heading2"], fontName=FONT_NAME_BOLD, fontSize=10,
                textColor=MID_BLUE, spaceBefore=8, spaceAfter=4),
            "body": ParagraphStyle("b", parent=styles["Normal"], fontName=FONT_NAME, fontSize=10,
                textColor=colors.HexColor("#333333"), leading=16, spaceAfter=4),
            "cell": ParagraphStyle("c", parent=styles["Normal"], fontName=FONT_NAME, fontSize=7,
                textColor=colors.HexColor("#333333"), leading=11, spaceAfter=0),
        }
