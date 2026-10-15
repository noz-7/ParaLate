"""Font resolution and text fitting for translated pages.

Base-14 fonts (helv) cannot render Turkish glyphs correctly, so a system
TTF covering the target script is resolved at runtime.
"""
from __future__ import annotations

import logging
import sys
from functools import lru_cache

import pymupdf

from app.constants import FONT_SIZE_STEP, MIN_TRANSLATED_FONT_SIZE

logger = logging.getLogger(__name__)

_REGULAR_CANDIDATES = (
    # Windows
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
)
_BOLD_CANDIDATES = (
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\tahomabd.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)
_ITALIC_CANDIDATES = (
    r"C:\Windows\Fonts\segoeuii.ttf",
    r"C:\Windows\Fonts\tahomai.ttf",
    r"C:\Windows\Fonts\ariali.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Italic.ttf",
)
_BOLD_ITALIC_CANDIDATES = (
    r"C:\Windows\Fonts\segoeuiz.ttf",
    r"C:\Windows\Fonts\tahomabi.ttf",
    r"C:\Windows\Fonts\arialbi.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-BoldItalic.ttf",
)

FONT_NAME_REGULAR = "plt"
FONT_NAME_BOLD = "pltb"
FONT_NAME_ITALIC = "plti"
FONT_NAME_BOLD_ITALIC = "pltbi"


@lru_cache(maxsize=4)
def resolve_font(regular: bool = True, italic: bool = False) -> str | None:
    """First existing font file that covers Turkish and similar scripts."""
    candidates = (
        _REGULAR_CANDIDATES if regular else _BOLD_CANDIDATES
    ) if not italic else (
        _ITALIC_CANDIDATES if regular else _BOLD_ITALIC_CANDIDATES
    )
    for path in candidates:
        try:
            if os_path_exists(path):
                pymupdf.Font(fontfile=path)  # validate parseability
                return path
        except Exception:
            logger.debug("font candidate failed: %s", path)
    return None


def os_path_exists(path: str) -> bool:
    import os

    return os.path.exists(path)


@lru_cache(maxsize=4)
def _font(font_path: str) -> pymupdf.Font:
    return pymupdf.Font(fontfile=font_path)


def get_font(font_path: str | None) -> pymupdf.Font:
    """Metrics font: system TTF when available, base-14 fallback otherwise."""
    if font_path:
        return _font(font_path)
    return pymupdf.Font("helv")


def srgb_to_rgb(color_int: int) -> tuple[float, float, float]:
    r = ((color_int >> 16) & 255) / 255.0
    g = ((color_int >> 8) & 255) / 255.0
    b = (color_int & 255) / 255.0
    # avoid invisible text on dark-on-dark exports
    if r + g + b < 0.15:
        return (0.0, 0.0, 0.0)
    return (r, g, b)


def wrap_text(font: pymupdf.Font, text: str, width: float, size: float) -> list[str]:
    """Greedy word wrap measured with the actual font metrics."""
    if width <= 1:
        return [text]
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip() if current else word
            if font.text_length(candidate, fontsize=size) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            if font.text_length(word, fontsize=size) <= width:
                current = word
            else:
                piece = ""
                for char in word:
                    if font.text_length(piece + char, fontsize=size) <= width:
                        piece += char
                    else:
                        if piece:
                            lines.append(piece)
                        piece = char
                current = piece
        if current:
            lines.append(current)
    return lines or [""]


def fit_text(
    font: pymupdf.Font,
    text: str,
    box_width: float,
    box_height: float,
    preferred_size: float,
    line_ratio: float,
    min_size: float = MIN_TRANSLATED_FONT_SIZE,
) -> tuple[float, list[str]] | None:
    """Shrink font size until the wrapped text fits the box; None if impossible."""
    size = max(min_size, preferred_size)
    while size >= min_size:
        lines = wrap_text(font, text, box_width, size)
        needed = len(lines) * size * line_ratio
        if needed <= box_height + 0.5:
            return size, lines
        size = round(size - FONT_SIZE_STEP, 2)
    return None


def draw_lines(
    page: pymupdf.Page,
    lines: list[str],
    box: pymupdf.Rect,
    size: float,
    line_ratio: float,
    font_path: str | None,
    font_name: str,
    align: str = "left",
    color: tuple[float, float, float] = (0, 0, 0),
    top_offset: float = 0.0,
) -> None:
    """Draw pre-wrapped lines inside *box* (top-left anchored)."""
    font = get_font(font_path)
    step = size * line_ratio
    baseline = box.y0 + top_offset + step * 0.5 + size * 0.32
    for line in lines:
        line_width = font.text_length(line, fontsize=size)
        if align == "center":
            x = box.x0 + max(0.0, (box.width - line_width) / 2)
        elif align == "right":
            x = box.x1 - line_width
        else:
            x = box.x0
        try:
            kwargs: dict = {"fontname": font_name}
            if font_path:
                kwargs["fontfile"] = font_path
            else:
                kwargs["fontname"] = "helv"
            page.insert_text(
                pymupdf.Point(x, baseline),
                line,
                fontsize=size,
                color=color,
                overlay=True,
                **kwargs,
            )
        except Exception:
            logger.warning("failed to draw a text line", exc_info=True)
            return
        baseline += step
