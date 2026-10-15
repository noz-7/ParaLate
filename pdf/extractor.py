"""Structured extraction of translatable content from PDF pages.

No OCR: if the PDF has no text layer the pipeline stops with a clear error.
Blocks are classified so code, math and pure URLs are never sent to a
translator.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import pymupdf

from app.constants import DEFAULT_LINE_RATIO

logger = logging.getLogger(__name__)


class BlockKind:
    HEADING = "heading"
    BODY = "body"
    CODE = "code"
    MATH = "math"
    SKIP = "skip"


class NoTextFoundError(Exception):
    """PDF has no usable text layer."""


class ExtractionCancelled(Exception):
    """Cooperative cancellation from the worker."""


_MONO_MARKERS = (
    "courier", "mono", "consolas", "menlo", "dejavu sans mono",
    "liberation mono", "inconsolata", "cascadia", "lucidasanstypewriter",
)
_MATH_CHARS = set("±×÷≤≥≈≠∞∑∏∫√∂∇∆∈∀∃∅⊕⊗→←↔′″⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉λμθπαβγδεφωΩρστχψ")
_FORMULA_RE = re.compile(r"\d\s*[=+*/^]\s*[\d(]|[=]{2,}|∑|∫|√")
_URL_RE = re.compile(r"^(?:https?://|www\.)\S+$", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HEADING_SIZE_RATIO = 1.18
_BOLD_HEADING_CHARS = 130
_MIN_LETTER_RATIO = 0.25
_MIN_MATH_RATIO = 0.06


@dataclass
class TextStyleRun:
    length: int
    color: int
    bold: bool
    italic: bool


@dataclass
class TextBlock:
    bbox: tuple[float, float, float, float]
    kind: str
    text: str
    font_size: float
    bold: bool
    color: int
    align: str
    line_count: int
    line_ratio: float
    index: int = 0
    style_runs: list[TextStyleRun] = field(default_factory=list)

    @property
    def rect(self) -> pymupdf.Rect:
        return pymupdf.Rect(self.bbox)

    @property
    def translatable(self) -> bool:
        return self.kind in (BlockKind.HEADING, BlockKind.BODY)


@dataclass
class PageModel:
    number: int
    width: float
    height: float
    blocks: list[TextBlock] = field(default_factory=list)

    @property
    def translatable_blocks(self) -> list[TextBlock]:
        return [b for b in self.blocks if b.translatable]

    @property
    def has_text(self) -> bool:
        return bool(self.blocks)


def extract_page_model(page: pymupdf.Page) -> PageModel:
    """One pass over page text; classification happens after body-size calc."""
    data = page.get_text("dict")
    raw_blocks: list[dict] = [
        b for b in data.get("blocks", []) if b.get("type", 0) == 0 and b.get("lines")
    ]
    model = PageModel(
        number=page.number,
        width=float(page.rect.width),
        height=float(page.rect.height),
    )
    if not raw_blocks:
        return model

    body_size = _page_body_size(raw_blocks)
    for index, raw in enumerate(raw_blocks):
        block = _build_block(raw, index, body_size)
        if block is not None:
            model.blocks.append(block)
    return model


def extract_models(doc: pymupdf.Document, should_cancel=None) -> list[PageModel]:
    models: list[PageModel] = []
    for page in doc:
        if should_cancel and should_cancel():
            raise ExtractionCancelled()
        models.append(extract_page_model(page))
    processable = any(
        block.kind != BlockKind.SKIP
        for model in models
        for block in model.blocks
    )
    if not processable:
        raise NoTextFoundError("no text layer")
    return models


def sample_text(models: list[PageModel], limit: int = 600) -> str:
    """First translatable characters, used for source language detection."""
    parts: list[str] = []
    total = 0
    for model in models:
        for block in model.translatable_blocks:
            parts.append(block.text)
            total += len(block.text)
            if total >= limit:
                return " ".join(parts)[:limit]
    return " ".join(parts)[:limit]


# --------------------------------------------------------------------------- #
# internals
# --------------------------------------------------------------------------- #

def _page_body_size(raw_blocks: list[dict]) -> float:
    """Character-weighted median span size: robust against headings."""
    weights: dict[float, int] = {}
    for raw in raw_blocks:
        for line in raw.get("lines", []):
            for span in line.get("spans", []):
                size = round(float(span.get("size", 10.0)), 1)
                text = span.get("text", "")
                weights[size] = weights.get(size, 0) + max(1, len(text))
    if not weights:
        return 10.0
    total = sum(weights.values())
    running = 0
    for size in sorted(weights):
        running += weights[size]
        if running >= total / 2:
            return size
    return max(weights)


def _build_block(raw: dict, index: int, body_size: float) -> TextBlock | None:
    spans = [s for line in raw.get("lines", []) for s in line.get("spans", []) if s.get("text")]
    if not spans:
        return None
    text = _block_text(raw)
    if not text.strip():
        return None

    bbox = tuple(float(v) for v in raw.get("bbox", (0, 0, 0, 0)))
    font_size = _dominant_size(spans, body_size)
    bold = any("bold" in str(s.get("font", "")).lower() for s in spans)
    color = int(spans[0].get("color", 0)) if isinstance(spans[0].get("color", 0), int) else 0
    style_runs = [
        TextStyleRun(
            length=len(str(span.get("text", ""))),
            color=int(span.get("color", 0))
            if isinstance(span.get("color", 0), int) else 0,
            bold=(
                "bold" in str(span.get("font", "")).lower()
                or bool(int(span.get("flags", 0)) & 16)
            ),
            italic=(
                "italic" in str(span.get("font", "")).lower()
                or bool(int(span.get("flags", 0)) & 2)
            ),
        )
        for span in spans
        if span.get("text")
    ]
    lines = raw.get("lines", [])
    align = _detect_align(bbox, lines)
    line_ratio = _line_ratio(bbox, len(lines), font_size)
    kind = _classify(text, spans, font_size, body_size, bold, len(lines))
    return TextBlock(
        bbox=bbox,  # type: ignore[arg-type]
        kind=kind,
        text=text,
        font_size=font_size,
        bold=bold,
        color=color,
        align=align,
        line_count=max(1, len(lines)),
        line_ratio=line_ratio,
        index=index,
        style_runs=style_runs,
    )


def _block_text(raw: dict) -> str:
    lines = ["".join(s.get("text", "") for s in line.get("spans", [])).strip()
             for line in raw.get("lines", [])]
    return " ".join(part for part in lines if part)


def _dominant_size(spans: list[dict], body_size: float) -> float:
    best = body_size
    for span in spans:
        size = float(span.get("size", body_size))
        if size > best:
            best = size
    return round(best, 1)


def _detect_align(bbox: tuple, lines: list[dict]) -> str:
    if len(lines) < 1:
        return "left"
    width = bbox[2] - bbox[0]
    if width < 24:
        return "left"
    left_gaps: list[float] = []
    right_gaps: list[float] = []
    for line in lines:
        lb = line.get("bbox")
        if not lb:
            continue
        left_gaps.append(lb[0] - bbox[0])
        right_gaps.append(bbox[2] - lb[2])
    if not left_gaps:
        return "left"
    left_gaps.sort()
    right_gaps.sort()
    med_left = left_gaps[len(left_gaps) // 2]
    med_right = right_gaps[len(right_gaps) // 2]
    if med_left > 0.12 * width and abs(med_left - med_right) <= 0.10 * width:
        return "center"
    if med_right > 0.30 * width and med_left <= 0.08 * width:
        return "left"
    return "left"


def _line_ratio(bbox: tuple, line_count: int, font_size: float) -> float:
    if line_count >= 2 and font_size > 0:
        height = bbox[3] - bbox[1]
        ratio = height / (line_count * font_size)
        if 1.0 <= ratio <= 2.0:
            return round(ratio, 2)
    return DEFAULT_LINE_RATIO


def _classify(
    text: str, spans: list[dict], font_size: float, body_size: float, bold: bool, line_count: int
) -> str:
    letters = sum(1 for ch in text if ch.isalpha())
    printable = sum(1 for ch in text if not ch.isspace())
    if printable == 0 or letters < max(2, _MIN_LETTER_RATIO * printable):
        return BlockKind.SKIP
    if _URL_RE.match(text.strip()) or _EMAIL_RE.match(text.strip()):
        return BlockKind.SKIP
    if _looks_like_code(text, spans):
        return BlockKind.CODE
    if _looks_like_math(text, spans, font_size):
        return BlockKind.MATH
    if font_size >= body_size * _HEADING_SIZE_RATIO or (bold and len(text) <= _BOLD_HEADING_CHARS):
        return BlockKind.HEADING
    return BlockKind.BODY


def _looks_like_code(text: str, spans: list[dict]) -> bool:
    fonts = " ".join(str(s.get("font", "")).lower() for s in spans)
    if any(marker in fonts for marker in _MONO_MARKERS):
        return True
    syntax = sum(text.count(ch) for ch in "{};<>|=()`")
    if syntax >= 6 and text.count("\n") + text.count("def ") + text.count("class ") >= 0:
        words = len(text.split())
        if words and syntax / max(1, words) > 0.35:
            return True
    return False


def _looks_like_math(text: str, spans: list[dict], font_size: float) -> bool:
    compact = "".join(ch for ch in text if not ch.isspace())
    if not compact:
        return False
    math_hits = sum(1 for ch in compact if ch in _MATH_CHARS)
    if math_hits / len(compact) >= _MIN_MATH_RATIO:
        return True
    small_spans = sum(
        1 for s in spans if float(s.get("size", font_size)) < 0.72 * font_size
    )
    if small_spans >= 2 and _FORMULA_RE.search(text):
        return True
    return False
