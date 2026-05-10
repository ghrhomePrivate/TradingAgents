"""Report export utilities — Markdown and PDF.

Assembles the complete analysis report from individual section data
collected during the analysis run, then exports to .md or .pdf.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

_SECTION_ORDER = [
    ("market_report", "市场分析", "I"),
    ("sentiment_report", "社交情绪分析", "II"),
    ("news_report", "新闻分析", "III"),
    ("fundamentals_report", "基本面分析", "IV"),
    ("investment_plan", "研究团队决策", "V"),
    ("trader_investment_plan", "交易计划", "VI"),
    ("risk_aggressive", "激进风控分析师", "VII"),
    ("risk_conservative", "保守风控分析师", "VIII"),
    ("risk_neutral", "中性风控分析师", "IX"),
    ("risk_debate_history", "风控辩论记录", "X"),
    ("risk_pm_decision", "投资组合经理决策", "XI"),
    ("final_trade_decision", "最终投资组合决策", "XII"),
]


def assemble_report_markdown(
    reports: Dict[str, str],
    ticker: str = "",
    analysis_date: str = "",
) -> str:
    """Assemble all report sections into a single Markdown document.

    Args:
        reports: Dict mapping section keys to their Markdown content.
        ticker: Stock ticker symbol.
        analysis_date: Analysis date string.

    Returns:
        Complete Markdown report as a string.
    """
    parts: list[str] = []

    # Title
    title = "交易分析报告"
    if ticker:
        title += f"：{ticker}"
    parts.append(f"# {title}\n")

    # Metadata
    meta_lines = []
    if analysis_date:
        meta_lines.append(f"**分析日期：** {analysis_date}")
    meta_lines.append(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    parts.append("\n".join(meta_lines))
    parts.append("---\n")

    # Sections
    for key, label, num in _SECTION_ORDER:
        content = reports.get(key, "").strip()
        if not content or (content.startswith("*") and content.endswith("*")):
            continue
        # Strip any leading "## 最终决策" prefix we add for UI display
        if key == "final_trade_decision" and content.startswith("## 最终决策"):
            content = content[len("## 最终决策") :].strip()
        parts.append(f"## {num}. {label}\n")
        parts.append(content)
        parts.append("")  # blank line

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Export to Markdown file
# ---------------------------------------------------------------------------


def export_markdown(
    reports: Dict[str, str],
    ticker: str = "",
    analysis_date: str = "",
    output_dir: Optional[Path] = None,
) -> str:
    """Export the report as a .md file. Returns the file path."""
    md_content = assemble_report_markdown(reports, ticker, analysis_date)

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="tradingagents_export_"))
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    safe_ticker = ticker.replace("/", "_").replace("\\", "_") or "report"
    safe_date = (
        analysis_date.replace("/", "-")
        if analysis_date
        else datetime.now().strftime("%Y%m%d")
    )
    filename = f"{safe_ticker}_{safe_date}_report.md"
    filepath = output_dir / filename
    filepath.write_text(md_content, encoding="utf-8")
    return str(filepath)


# ---------------------------------------------------------------------------
# Export to PDF
# ---------------------------------------------------------------------------

# Candidate CJK font paths, checked in order.  The first existing file wins.
# xhtml2pdf requires a real font file path for @font-face src: url(...).
# .ttf files are strongly preferred; .ttc (TrueType Collection) files may
# work in some reportlab versions but are unreliable for glyph subsetting.
_CJK_FONT_CANDIDATES: List[Tuple[str, str]] = [
    # macOS
    ("/Library/Fonts/Arial Unicode.ttf", "ArialUnicode"),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "ArialUnicode"),
    ("/System/Library/Fonts/STHeiti Medium.ttc", "STHeiti"),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", "HiraginoSansGB"),
    # Linux — Noto Sans CJK (commonly installed via fonts-noto-cjk)
    ("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf", "NotoSansCJK"),
    ("/usr/share/fonts/noto-cjk/NotoSansCJKsc-Regular.otf", "NotoSansCJK"),
    ("/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc", "NotoSansCJK"),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJK"),
    # Linux — WenQuanYi
    (
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "WenQuanYiMicroHei",
    ),
    (
        "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
        "WenQuanYiMicroHei",
    ),
    # Windows
    ("C:/Windows/Fonts/msyh.ttc", "MicrosoftYaHei"),
    ("C:/Windows/Fonts/simsun.ttc", "SimSun"),
    ("C:/Windows/Fonts/simhei.ttf", "SimHei"),
]

_cached_cjk_font: Optional[Tuple[str, str]] = None


def _find_cjk_font() -> Optional[Tuple[str, str]]:
    """Return (file_path, family_name) of the first available CJK font, or None."""
    global _cached_cjk_font
    if _cached_cjk_font is not None:
        return _cached_cjk_font
    for path, name in _CJK_FONT_CANDIDATES:
        if Path(path).is_file():
            _cached_cjk_font = (path, name)
            return _cached_cjk_font
    return None


def _build_pdf_css(font_info: Optional[Tuple[str, str]] = None) -> str:
    """Build the CSS for PDF rendering, with CJK @font-face if available."""
    font_face_css = ""
    if font_info:
        font_path, font_name = font_info
        font_face_css = f"""
@font-face {{
    font-family: '{font_name}';
    src: url('{font_path}');
}}
"""
        body_font = (
            f"'{font_name}', "
            "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', "
            "'Noto Sans CJK SC', sans-serif"
        )
    else:
        body_font = (
            "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', "
            "'Noto Sans CJK SC', 'Source Han Sans SC', 'WenQuanYi Micro Hei', "
            "'Helvetica Neue', Helvetica, Arial, sans-serif"
        )

    return f"""\
{font_face_css}
@page {{
    size: A4;
    margin: 2cm;
}}
body {{
    font-family: {body_font};
    font-size: 11pt;
    line-height: 1.6;
    color: #333;
}}
h1 {{
    font-size: 20pt;
    color: #1a1a2e;
    border-bottom: 2px solid #16213e;
    padding-bottom: 6pt;
    margin-bottom: 12pt;
}}
h2 {{
    font-size: 15pt;
    color: #16213e;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 4pt;
    margin-top: 18pt;
}}
h3 {{
    font-size: 13pt;
    color: #0f3460;
    margin-top: 12pt;
}}
hr {{
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 12pt 0;
}}
p {{
    margin: 6pt 0;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 8pt 0;
}}
th, td {{
    border: 1px solid #cbd5e0;
    padding: 6pt 8pt;
    text-align: left;
    font-size: 10pt;
}}
th {{
    background-color: #edf2f7;
    font-weight: bold;
}}
code {{
    background-color: #f7fafc;
    padding: 1pt 4pt;
    border-radius: 3pt;
    font-size: 10pt;
}}
pre {{
    background-color: #f7fafc;
    padding: 8pt;
    border-radius: 4pt;
    overflow-x: auto;
    font-size: 9pt;
}}
strong {{
    color: #1a1a2e;
}}
ul, ol {{
    margin: 6pt 0;
    padding-left: 20pt;
}}
li {{
    margin: 3pt 0;
}}
"""


def export_pdf(
    reports: Dict[str, str],
    ticker: str = "",
    analysis_date: str = "",
    output_dir: Optional[Path] = None,
) -> str:
    """Export the report as a .pdf file. Returns the file path.

    Uses markdown -> HTML -> PDF pipeline (markdown + xhtml2pdf).
    CJK fonts are auto-discovered from the system for Chinese text support.
    """
    import markdown
    from xhtml2pdf import pisa

    md_content = assemble_report_markdown(reports, ticker, analysis_date)

    # Discover CJK font for Chinese text rendering
    font_info = _find_cjk_font()
    pdf_css = _build_pdf_css(font_info)

    # Convert Markdown -> HTML
    html_body = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "toc", "nl2br"],
    )

    # Wrap in full HTML document
    html_doc = f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<style>{pdf_css}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="tradingagents_export_"))
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    safe_ticker = ticker.replace("/", "_").replace("\\", "_") or "report"
    safe_date = (
        analysis_date.replace("/", "-")
        if analysis_date
        else datetime.now().strftime("%Y%m%d")
    )
    filename = f"{safe_ticker}_{safe_date}_report.pdf"
    filepath = output_dir / filename

    with open(filepath, "wb") as f:
        pisa_status = pisa.CreatePDF(html_doc, dest=f)

    if pisa_status.err:
        raise RuntimeError(f"PDF generation failed with {pisa_status.err} errors")

    return str(filepath)
