#!/usr/bin/env python3
"""Render docs/ROADMAP_ANALYSIS.md to a PDF.

A deliberately small Markdown subset renderer built on reportlab Platypus:
headings, paragraphs, bullet and numbered lists, fenced code, tables,
blockquotes and rules. That covers the analysis document and nothing more, which
keeps the output predictable.

Run:  python scripts/build_analysis_pdf.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "ROADMAP_ANALYSIS.md"
OUTPUT = ROOT / "docs" / "pdf" / "Roadmap_Analysis.pdf"

INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#5b6570")
ACCENT = colors.HexColor("#1f4e79")
RULE = colors.HexColor("#c8d0d8")
CODE_BG = colors.HexColor("#f4f6f8")
HEADER_BG = colors.HexColor("#eaeff4")

SEVERITY_COLORS = {
    "critical": colors.HexColor("#b03030"),
    "high": colors.HexColor("#c06000"),
    "medium": colors.HexColor("#1f4e79"),
    "low": MUTED,
}


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontSize=23,
            leading=28,
            textColor=ACCENT,
            spaceAfter=6,
            alignment=0,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontSize=11.5,
            leading=16,
            textColor=MUTED,
            spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontSize=15,
            leading=19,
            textColor=ACCENT,
            spaceBefore=16,
            spaceAfter=7,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=12.5,
            leading=16,
            textColor=INK,
            spaceBefore=12,
            spaceAfter=5,
        ),
        "h3": ParagraphStyle(
            "h3",
            parent=base["Heading3"],
            fontSize=11,
            leading=14,
            textColor=INK,
            spaceBefore=9,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=9.6,
            leading=14.2,
            textColor=INK,
            alignment=TA_JUSTIFY,
            spaceAfter=6.5,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontSize=9.6,
            leading=13.6,
            textColor=INK,
            spaceAfter=2.5,
        ),
        "code": ParagraphStyle(
            "code",
            parent=base["Code"],
            fontSize=8.1,
            leading=10.6,
            textColor=INK,
            backColor=CODE_BG,
            borderPadding=6,
            leftIndent=5,
            spaceBefore=3,
            spaceAfter=8,
        ),
        "quote": ParagraphStyle(
            "quote",
            parent=base["Normal"],
            fontSize=9.4,
            leading=13.4,
            textColor=MUTED,
            leftIndent=13,
            borderPadding=2,
            fontName="Helvetica-Oblique",
            spaceAfter=7,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["Normal"],
            fontSize=8.2,
            leading=11,
            textColor=INK,
        ),
        "cellhead": ParagraphStyle(
            "cellhead",
            parent=base["Normal"],
            fontSize=8.2,
            leading=11,
            textColor=INK,
            fontName="Helvetica-Bold",
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontSize=7.8,
            textColor=MUTED,
        ),
    }


def _emphasis(text: str) -> str:
    """Apply bold and italic, guaranteeing well-formed nesting.

    A regex pass over ``**a *b* c**`` emits ``<b>a <i>b</b></i>``, which
    reportlab's parser rejects outright. Splitting on the bold delimiter first
    and handling italics only *inside* each resulting segment makes correct
    nesting structural rather than something the patterns have to get right.
    """
    parts = text.split("**")
    # An unmatched "**" leaves an even number of parts; treat the trailing
    # fragment as literal rather than opening a tag that never closes.
    bold_upto = len(parts) - 1 if len(parts) % 2 == 0 else len(parts)

    out: list[str] = []
    for index, part in enumerate(parts):
        italic = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", part)
        # Any asterisk left over was never part of a matched pair.
        italic = italic.replace("*", "")
        if index % 2 == 1 and index < bold_upto:
            out.append(f"<b>{italic}</b>")
        else:
            out.append(italic)
    return "".join(out)


def inline(text: str) -> str:
    """Convert inline Markdown to reportlab's mini-HTML.

    Order matters: code spans are extracted first and restored last, so markup
    characters inside them are never interpreted.
    """
    spans: list[str] = []

    def stash(match: re.Match[str]) -> str:
        spans.append(match.group(1))
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)

    # Escape for XML before adding our own tags.
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Links: keep the label, drop the URL (paths mean nothing on paper).
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    text = _emphasis(text)

    # ReportLab's built-in fonts lack these glyphs and render them as black
    # boxes, so map them to ASCII rather than shipping a broken page.
    for bad, good in (
        ("—", "&#8212;"),
        ("–", "&#8211;"),
        ("→", "-&gt;"),
        ("≤", "&lt;="),
        ("≥", "&gt;="),
        ("σ", "sigma"),
        ("²", "<super>2</super>"),
        ("’", "&#8217;"),
        ("“", "&#8220;"),
        ("”", "&#8221;"),
        ("·", "&#183;"),
    ):
        text = text.replace(bad, good)

    def restore(match: re.Match[str]) -> str:
        content = spans[int(match.group(1))]
        content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'<font face="Courier" size="8.6" color="#8a2f5f">{content}</font>'

    text = re.sub(r"\x00(\d+)\x00", restore, text)

    # Last line of defence: reportlab raises on malformed markup and takes the
    # whole build down. If anything above produced unbalanced tags, degrade to
    # readable plain text instead of failing the render.
    if not _is_well_formed(text):
        return re.sub(r"<[^>]+>", "", text)
    return text


def _is_well_formed(markup: str) -> bool:
    """Check that paired inline tags nest correctly."""
    stack: list[str] = []
    for match in re.finditer(r"<(/?)(b|i|super|sub|font)\b[^>]*>", markup):
        closing, tag = match.group(1), match.group(2)
        if closing:
            if not stack or stack.pop() != tag:
                return False
        else:
            stack.append(tag)
    return not stack


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def make_table(rows: list[list[str]], styles, width: float) -> Table:
    """Build a table, sizing columns by measured text width.

    Character counts are a poor proxy here because the cells mix a proportional
    body face with monospace code spans. ``stringWidth`` measures what will
    actually be drawn, and reserving each column's longest unbreakable word as a
    floor stops a long neighbouring column from squeezing an identifier until it
    wraps mid-word.
    """
    header, *body = rows
    n = len(header)

    def measure(cell: str, bold: bool = False) -> tuple[float, float]:
        """Return (total width, longest single word) for a cell, in points."""
        code_spans = re.findall(r"`([^`]+)`", cell)
        plain = re.sub(r"`[^`]+`", "", cell)
        plain = re.sub(r"[*\[\]]|\([^)]*\)", "", plain)

        body_font = "Helvetica-Bold" if bold else "Helvetica"
        total = stringWidth(plain, body_font, 8.2)
        total += sum(stringWidth(c, "Courier", 8.2) for c in code_spans)

        words = [(w, body_font) for w in plain.split()]
        words += [(c, "Courier") for c in code_spans]  # code spans never wrap
        longest = max((stringWidth(w, f, 8.2) for w, f in words), default=0.0)
        return total, longest

    padding = 10.0  # left + right cell padding
    totals, floors = [], []
    for col in range(n):
        head_total, head_word = measure(str(header[col]), bold=True)
        col_total, col_word = head_total, head_word
        for row in body:
            if col < len(row):
                t, w = measure(str(row[col]))
                col_total = max(col_total, t)
                col_word = max(col_word, w)
        totals.append(max(col_total, 1.0))
        floors.append(col_word + padding)

    available = width - padding * n
    if sum(floors) >= width:
        # Cannot honour every floor; fall back to proportional sizing.
        scale = width / sum(totals)
        col_widths = [t * scale for t in totals]
    else:
        # Distribute the space left over after each floor, in proportion to how
        # much text each column actually holds.
        slack = width - sum(floors)
        weight_total = sum(totals)
        col_widths = [floors[c] + slack * (totals[c] / weight_total) for c in range(n)]
        scale = width / sum(col_widths)
        col_widths = [w * scale for w in col_widths]

    del available

    data = [[Paragraph(inline(c), styles["cellhead"]) for c in header]]
    data += [
        [Paragraph(inline(c), styles["cell"]) for c in (row + [""] * (n - len(row)))[:n]]
        for row in body
    ]

    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafbfc")]),
            ]
        )
    )
    return table


def parse(markdown: str, styles, width: float) -> list:
    """Translate the Markdown subset into Platypus flowables."""
    lines = markdown.split("\n")
    flow: list = []
    i = 0
    # The document's own H1 is rendered on the title page instead.
    seen_title = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Fenced code
        if stripped.startswith("```"):
            i += 1
            block: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            if block:
                flow.append(Preformatted("\n".join(block), styles["code"]))
            continue

        # Horizontal rule
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            flow.append(Spacer(1, 3))
            flow.append(HRFlowable(width="100%", thickness=0.5, color=RULE))
            flow.append(Spacer(1, 5))
            i += 1
            continue

        # Table
        if (
            stripped.startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1].strip())
        ):
            rows = [split_row(stripped)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i].strip()))
                i += 1
            flow.append(Spacer(1, 2))
            flow.append(make_table(rows, styles, width))
            flow.append(Spacer(1, 9))
            continue

        # Headings
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            level, text = len(heading.group(1)), heading.group(2)
            if level == 1:
                if not seen_title:
                    seen_title = True
                    i += 1
                    continue
                flow.append(Paragraph(inline(text), styles["h1"]))
            elif level == 2:
                # Findings carry a severity tag; colour it so the document can be
                # skimmed by severity.
                severity = re.search(r"\*\*(Critical|High|Medium|Low)\*\*", text)
                para = Paragraph(inline(text), styles["h2"])
                if severity:
                    colour = SEVERITY_COLORS[severity.group(1).lower()]
                    styled = ParagraphStyle(
                        f"h2_{severity.group(1)}", parent=styles["h2"], textColor=colour
                    )
                    para = Paragraph(inline(text), styled)
                flow.append(Spacer(1, 4))
                flow.append(para)
            else:
                flow.append(Paragraph(inline(text), styles["h3"]))
            i += 1
            continue

        # Blockquote
        if stripped.startswith(">"):
            quoted: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quoted.append(lines[i].strip().lstrip(">").strip())
                i += 1
            kept = [q for q in quoted if q]
            # A quoted list must keep its line breaks; joining with spaces runs
            # the bullets together into one unreadable sentence.
            if any(re.match(r"^([-*+]\s|\d+\.\s)", q) for q in kept):
                text = "<br/>".join(inline(q) for q in kept)
                flow.append(Paragraph(text, styles["quote"]))
            elif kept:
                flow.append(Paragraph(inline(" ".join(kept)), styles["quote"]))
            continue

        # Lists (bulleted or numbered)
        bullet = re.match(r"^[-*+]\s+(.*)$", stripped)
        number = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if bullet or number:
            numbered = bool(number)
            items: list[ListItem] = []
            while i < len(lines):
                current = lines[i].strip()
                match = (
                    re.match(r"^(\d+)\.\s+(.*)$", current)
                    if numbered
                    else re.match(r"^[-*+]\s+(.*)$", current)
                )
                if not match:
                    if current and lines[i].startswith(("  ", "\t")):
                        i += 1  # continuation line; folded into the item above
                        continue
                    break
                text = match.group(2) if numbered else match.group(1)
                items.append(ListItem(Paragraph(inline(text), styles["bullet"]), leftIndent=16))
                i += 1
            flow.append(
                ListFlowable(
                    items,
                    bulletType="1" if numbered else "bullet",
                    start="1" if numbered else None,
                    leftIndent=15,
                    bulletFontSize=8.5,
                    spaceAfter=7,
                )
            )
            continue

        # Paragraph: gather until a blank line or a new block construct.
        para: list[str] = []
        while i < len(lines) and lines[i].strip():
            nxt = lines[i].strip()
            if re.match(r"^(#{1,6}\s|[-*+]\s|\d+\.\s|>|\||```)", nxt) or re.fullmatch(
                r"-{3,}", nxt
            ):
                break
            para.append(nxt)
            i += 1
        if para:
            flow.append(Paragraph(inline(" ".join(para)), styles["body"]))

    return flow


def title_page(styles, width: float) -> list:
    from datetime import date

    flow = [
        Spacer(1, 38 * mm),
        Paragraph("Critical Analysis", styles["title"]),
        Paragraph(
            "Comprehensive Roadmap for Building a Python Machine Learning "
            "Quantitative Hedge Fund Investment Strategy",
            styles["subtitle"],
        ),
        Spacer(1, 7),
        HRFlowable(width="100%", thickness=1.1, color=ACCENT),
        Spacer(1, 13),
    ]

    summary = [
        ["Findings", "11 (2 critical, 4 high, 4 medium, 1 low)"],
        ["Source document", "223 lines, 7 phases"],
        ["Most serious gap", "No correction for multiple testing"],
        ["Headline measurement", "The example model adds 0.000013 of R-squared over doing nothing"],
        ["Companion implementation", "quantlab - 123 tests, 94% coverage"],
        ["Generated", date.today().isoformat()],
    ]
    table = Table(
        [
            [Paragraph(f"<b>{k}</b>", styles["cell"]), Paragraph(v, styles["cell"])]
            for k, v in summary
        ],
        colWidths=[width * 0.32, width * 0.68],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.35, RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    flow.append(table)
    flow.append(Spacer(1, 16))
    flow.append(
        Paragraph(
            "Every finding names the module that addresses it. Corrections that "
            "can be enforced mechanically are enforced by tests rather than left "
            "to reviewer discipline.",
            styles["quote"],
        )
    )
    flow.append(NextPageTemplate("body"))
    flow.append(PageBreak())
    return flow


def main() -> int:
    if not SOURCE.exists():
        print(f"error: {SOURCE} not found", file=sys.stderr)
        return 1

    styles = build_styles()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    margin = 19 * mm
    page_width, page_height = A4
    frame_width = page_width - 2 * margin

    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=18 * mm,
        title="Critical Analysis: ML Quantitative Trading Strategy Roadmap",
        author="quantlab",
        subject="Analysis of a quantitative trading strategy roadmap",
    )

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.6)
        canvas.setFillColor(MUTED)
        if document.page > 1:
            canvas.drawString(margin, 11 * mm, "Critical Analysis - Quantitative Trading Roadmap")
            canvas.drawRightString(page_width - margin, 11 * mm, str(document.page))
            canvas.setStrokeColor(RULE)
            canvas.setLineWidth(0.4)
            canvas.line(margin, 14 * mm, page_width - margin, 14 * mm)
        canvas.restoreState()

    frame = Frame(margin, 18 * mm, frame_width, page_height - margin - 18 * mm, id="f")
    doc.addPageTemplates(
        [
            PageTemplate(id="title", frames=[frame], onPage=footer),
            PageTemplate(id="body", frames=[frame], onPage=footer),
        ]
    )

    story = title_page(styles, frame_width)
    story += parse(SOURCE.read_text(), styles, frame_width)

    doc.build(story)

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Wrote {OUTPUT.relative_to(ROOT)}  ({size_kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
