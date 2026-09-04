"""Tests for the Markdown -> PDF renderer.

The renderer builds a committed deliverable, so its failure modes (malformed
markup crashing the build, or silently dropping content) are worth pinning down.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "build_analysis_pdf", ROOT / "scripts" / "build_analysis_pdf.py"
)
builder = importlib.util.module_from_spec(spec)
sys.modules["build_analysis_pdf"] = builder
spec.loader.exec_module(builder)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("plain text", "plain text"),
        ("**bold**", "<b>bold</b>"),
        ("*italic*", "<i>italic</i>"),
        ("a < b & c", "a &lt; b &amp; c"),
    ],
)
def test_inline_basic_conversions(source, expected):
    assert builder.inline(source) == expected


def test_nested_emphasis_is_well_formed():
    """Regression: `**a *b* c**` used to emit `<b>a <i>b</b></i>`.

    ReportLab rejects that outright and the whole build died. Nesting must come
    out correctly ordered.
    """
    result = builder.inline("**open of *t+1* here**")
    assert builder._is_well_formed(result)
    assert result == "<b>open of <i>t+1</i> here</b>"


def test_unmatched_asterisks_do_not_break_the_render():
    for source in ("**unclosed bold", "*unclosed italic", "a ** b * c", "***"):
        assert builder._is_well_formed(builder.inline(source))


def test_code_spans_are_not_interpreted_as_markup():
    """Markup characters inside a code span must survive verbatim."""
    result = builder.inline("use `a**b` and `x<y`")
    assert "a**b" in result
    assert "x&lt;y" in result
    assert builder._is_well_formed(result)


def test_well_formed_detector_rejects_bad_nesting():
    assert not builder._is_well_formed("<b>a <i>b</b></i>")
    assert not builder._is_well_formed("<b>unclosed")
    assert builder._is_well_formed("<b>a <i>b</i></b>")


def test_malformed_markup_degrades_to_plain_text(monkeypatch):
    """If anything slips through, strip tags rather than fail the build."""
    monkeypatch.setattr(builder, "_emphasis", lambda t: "<b>broken<i></b></i>")
    result = builder.inline("anything")
    assert "<" not in result


def test_parse_handles_every_supported_block():
    styles = builder.build_styles()
    markdown = """# Title

## Heading

Body paragraph with **bold**.

- bullet one
- bullet two

1. numbered one
2. numbered two

> quoted line

| A | B |
|---|---|
| 1 | 2 |

```python
x = 1
```

---
"""
    flow = builder.parse(markdown, styles, 400.0)
    assert len(flow) >= 8


def test_table_columns_fit_their_longest_word():
    """A long identifier must not be wrapped mid-word by a greedy neighbour."""
    styles = builder.build_styles()
    rows = [
        ["Repository", "What it lacks"],
        ["KingZTheShadowz07", "A very long description " * 12],
    ]
    table = builder.make_table(rows, styles, 500.0)

    from reportlab.pdfbase.pdfmetrics import stringWidth

    needed = stringWidth("KingZTheShadowz07", "Helvetica-Bold", 8.2)
    assert table._argW[0] >= needed
    assert sum(table._argW) == pytest.approx(500.0)


def test_the_committed_pdf_is_current():
    """The checked-in PDF must match the checked-in Markdown.

    Guards against editing the analysis and forgetting `make report`.
    """
    pdf = ROOT / "docs" / "pdf" / "Roadmap_Analysis.pdf"
    assert pdf.exists(), "run `make report`"

    pypdf = pytest.importorskip("pypdf")
    text = "\n".join(p.extract_text() for p in pypdf.PdfReader(str(pdf)).pages)

    # Spot-check the load-bearing measurements from the analysis.
    for probe in ("0.985008", "0.000013", "0.5115", "Deflated Sharpe"):
        assert probe in text, f"{probe!r} missing from the PDF; regenerate it"
