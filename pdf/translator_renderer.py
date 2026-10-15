"""Builds translation pages that preserve the original page's visuals.

Strategy per page:
1. Copy the original page untouched (images, vector graphics, line art).
2. Redact ONLY the text blocks that will be translated
   (images and line art are explicitly kept).
3. Draw translated text at the original coordinates with controlled
   font-size reduction so it never overflows the page.

If anything fails the page falls back to a pristine copy — stability first.
"""
from __future__ import annotations

import logging
import re

import pymupdf

from app.constants import (
    MAX_PAGE_EDGE_MARGIN,
    MIN_TRANSLATED_FONT_SIZE,
    REDACT_PAD_POINTS,
)
from pdf.extractor import PageModel, TextBlock
from pdf.renderer import (
    FONT_NAME_BOLD_ITALIC,
    FONT_NAME_BOLD,
    FONT_NAME_ITALIC,
    FONT_NAME_REGULAR,
    fit_text,
    get_font,
    resolve_font,
    srgb_to_rgb,
    wrap_text,
)

logger = logging.getLogger(__name__)
_WORD_RE = re.compile(r"\S+")

# page -> block index -> translated text
TranslationMap = dict[int, dict[int, str]]


def build_translation_document(
    orig_doc: pymupdf.Document,
    models: list[PageModel],
    translations: TranslationMap,
) -> pymupdf.Document:
    """Create a document whose page i mirrors original page i, translated."""
    trans_doc = pymupdf.open()
    for index, model in enumerate(models):
        if index >= orig_doc.page_count:
            break
        try:
            _render_page(orig_doc, trans_doc, index, model, translations.get(index, {}))
        except Exception:
            logger.exception("page %d translation render failed; using original copy", index + 1)
            if trans_doc.page_count == index:
                trans_doc.insert_pdf(orig_doc, from_page=index, to_page=index)
    # guarantee alignment for interleaving
    while trans_doc.page_count < len(models):
        i = trans_doc.page_count
        trans_doc.insert_pdf(orig_doc, from_page=i, to_page=i)
    return trans_doc


def _render_page(
    orig_doc: pymupdf.Document,
    trans_doc: pymupdf.Document,
    page_index: int,
    model: PageModel,
    page_translations: dict[int, str],
) -> None:
    blocks = [
        b for b in model.translatable_blocks
        if (page_translations.get(b.index) or "").strip()
    ]

    temp = pymupdf.open()
    try:
        temp.insert_pdf(orig_doc, from_page=page_index, to_page=page_index)
        page = temp[0]
        regular_path = resolve_font(regular=True)
        bold_path = resolve_font(regular=False)
        italic_path = resolve_font(regular=True, italic=True)
        bold_italic_path = resolve_font(regular=False, italic=True)
        if regular_path is None:
            logger.warning("no system TTF font found; Turkish glyphs may be lost")

        plans = [
            _plan_layout(page, model, block, page_translations[block.index],
                         regular_path, bold_path)
            for block in blocks
        ]
        if plans:
            _redact_blocks(page, blocks)
            for block, plan in zip(blocks, plans):
                font_path, font_name, size, lines, box, align, color, top_offset = plan
                _draw_styled_lines(
                    page, lines, box, size, block.line_ratio,
                    regular_path, bold_path, italic_path, bold_italic_path,
                    block, page_translations[block.index],
                    align, color, top_offset,
                )
    except Exception:
        logger.exception(
            "page %d translation render failed; using original copy", page_index + 1
        )
        # Discard the possibly-patched page and fall back to a pristine copy.
        temp.close()
        temp = pymupdf.open()
        temp.insert_pdf(orig_doc, from_page=page_index, to_page=page_index)
    trans_doc.insert_pdf(temp, from_page=0, to_page=0)
    temp.close()


def _plan_layout(
    page: pymupdf.Page,
    model: PageModel,
    block: TextBlock,
    translated: str,
    regular_path: str | None,
    bold_path: str | None,
) -> tuple:
    """Pre-compute everything so drawing can never half-fail."""
    font_path = (bold_path if (block.bold and bold_path) else regular_path) or regular_path
    font_name = FONT_NAME_BOLD if (block.bold and bold_path and font_path == bold_path) else FONT_NAME_REGULAR
    font = get_font(font_path)

    box = pymupdf.Rect(block.bbox)
    box.x0 = max(0.0, box.x0 - 1.0)
    box.x1 = min(model.width, box.x1 + 1.0)
    box.y0 = max(0.0, box.y0 - 1.0)
    box.y1 = min(model.height, box.y1 + 1.0)

    preferred = block.font_size
    line_ratio = block.line_ratio
    result = fit_text(font, translated, box.width, box.height, preferred, line_ratio)
    top_offset = 0.0

    if result is None:
        limit_y = _expansion_limit(page, model, block)
        if limit_y > box.y1 + 2.0:
            grown = pymupdf.Rect(box.x0, box.y0, box.x1, min(limit_y, model.height - 2.0))
            result = fit_text(font, translated, grown.width, grown.height, preferred, line_ratio)
            if result is not None:
                box = grown

    if result is None:
        # Controlled degradation: keep as much readable text as possible.
        size = MIN_TRANSLATED_FONT_SIZE
        lines = wrap_text(font, translated, box.width, size)
        max_lines = max(1, int(box.height / (size * line_ratio)))
        lines = lines[:max_lines]
        logger.warning(
            "block at %s could not fully fit; truncating translated text", tuple(block.bbox)
        )
    else:
        size, lines = result
        needed = len(lines) * size * line_ratio
        if needed < box.height:
            top_offset = (box.height - needed) / 2

    return (
        font_path or "",
        font_name,
        size,
        lines,
        box,
        block.align,
        srgb_to_rgb(block.color),
        top_offset,
    )


def _draw_styled_lines(
    page: pymupdf.Page,
    lines: list[str],
    box: pymupdf.Rect,
    size: float,
    line_ratio: float,
    regular_path: str | None,
    bold_path: str | None,
    italic_path: str | None,
    bold_italic_path: str | None,
    block: TextBlock,
    translated: str,
    align: str,
    default_color: tuple[float, float, float],
    top_offset: float,
) -> None:
    """Draw translated words using the source spans' colors and font styles."""
    source_tokens = list(_WORD_RE.finditer(translated))
    if not source_tokens:
        return
    style_ranges = _translated_style_ranges(block, len(translated))
    style_cursor = [0, 0]
    font_paths = {
        (False, False): regular_path,
        (True, False): bold_path or regular_path,
        (False, True): italic_path or regular_path,
        (True, True): bold_italic_path or bold_path or regular_path,
    }
    font_names = {
        (False, False): FONT_NAME_REGULAR,
        (True, False): FONT_NAME_BOLD if bold_path else FONT_NAME_REGULAR,
        (False, True): FONT_NAME_ITALIC if italic_path else FONT_NAME_REGULAR,
        (True, True): (
            FONT_NAME_BOLD_ITALIC if bold_italic_path
            else FONT_NAME_BOLD if bold_path else FONT_NAME_REGULAR
        ),
    }
    fonts = {style: get_font(path) for style, path in font_paths.items()}
    baseline = box.y0 + top_offset + size * line_ratio * 0.5 + size * 0.32

    for line in lines:
        segments = _styled_line_segments(
            line, source_tokens, style_cursor, style_ranges, block.color, block.bold
        )
        line_width = sum(
            fonts[(bold, italic)].text_length(text, fontsize=size)
            for text, _color, bold, italic in segments
        )
        if align == "center":
            x = box.x0 + max(0.0, (box.width - line_width) / 2)
        elif align == "right":
            x = box.x1 - line_width
        else:
            x = box.x0

        for text, color_int, bold, italic in segments:
            style = (bold, italic)
            font_path = font_paths[style]
            kwargs: dict = {"fontname": font_names[style]}
            if font_path:
                kwargs["fontfile"] = font_path
            else:
                kwargs["fontname"] = (
                    "hebi" if bold and italic else "heit" if italic
                    else "hebo" if bold else "helv"
                )
            rgb = srgb_to_rgb(color_int) if color_int is not None else default_color
            try:
                page.insert_text(
                    pymupdf.Point(x, baseline),
                    text,
                    fontsize=size,
                    color=rgb,
                    overlay=True,
                    **kwargs,
                )
            except Exception:
                logger.warning("failed to draw a styled text run", exc_info=True)
                return
            x += fonts[style].text_length(text, fontsize=size)
        baseline += size * line_ratio


def _translated_style_ranges(
    block: TextBlock, translated_length: int
) -> list[tuple[int, int, bool, bool]]:
    runs = block.style_runs
    if translated_length == 0 or not runs:
        return [(translated_length, block.color, block.bold, False)]
    total_source_length = sum(max(0, run.length) for run in runs)
    if total_source_length == 0:
        return [(translated_length, block.color, block.bold, False)]

    ranges: list[tuple[int, int, bool, bool]] = []
    consumed_source = 0
    previous_end = 0
    for run in runs:
        consumed_source += max(0, run.length)
        end = round(translated_length * consumed_source / total_source_length)
        end = max(previous_end, min(translated_length, end))
        if end > previous_end:
            ranges.append((end, run.color, run.bold, run.italic))
        previous_end = end
    if not ranges:
        ranges.append((translated_length, block.color, block.bold, False))
    elif ranges[-1][0] < translated_length:
        ranges[-1] = (translated_length, *ranges[-1][1:])
    return ranges


def _styled_line_segments(
    line: str,
    source_tokens: list[re.Match],
    cursor: list[int],
    style_ranges: list[tuple[int, int, bool, bool]],
    default_color: int,
    default_bold: bool,
) -> list[tuple[str, int | None, bool, bool]]:
    segments: list[tuple[str, int | None, bool, bool]] = []
    words = line.split()
    for word_index, word in enumerate(words):
        if cursor[0] >= len(source_tokens):
            color, bold, italic = default_color, default_bold, False
            token_start = 0
        else:
            token = source_tokens[cursor[0]]
            token_start = token.start() + cursor[1]
            color, bold, italic = default_color, default_bold, False
            for end, run_color, run_bold, run_italic in style_ranges:
                if token_start < end:
                    color, bold, italic = run_color, run_bold, run_italic
                    break

        remaining = word
        while remaining:
            if cursor[0] >= len(source_tokens):
                color, bold, italic = default_color, default_bold, False
                take = len(remaining)
            else:
                token = source_tokens[cursor[0]]
                token_start = token.start() + cursor[1]
                run_end = len(token.group())
                for end, run_color, run_bold, run_italic in style_ranges:
                    if token_start < end:
                        color, bold, italic = run_color, run_bold, run_italic
                        run_end = min(run_end, end - token.start())
                        break
                take = max(1, min(len(remaining), run_end - cursor[1]))

            chunk = remaining[:take]
            if word_index > 0 and cursor[1] == 0 and len(remaining) == len(word):
                chunk = " " + chunk
            if segments and segments[-1][1:] == (color, bold, italic):
                previous, previous_color, previous_bold, previous_italic = segments[-1]
                segments[-1] = (
                    previous + chunk, previous_color, previous_bold, previous_italic
                )
            else:
                segments.append((chunk, color, bold, italic))
            remaining = remaining[take:]
            if cursor[0] < len(source_tokens):
                cursor[1] += take
                if cursor[1] >= len(source_tokens[cursor[0]].group()):
                    cursor[0] += 1
                    cursor[1] = 0
    return segments


def _expansion_limit(page: pymupdf.Page, model: PageModel, block: TextBlock) -> float:
    """Nearest obstacle below this block (other blocks, images, page edge)."""
    limit = model.height - MAX_PAGE_EDGE_MARGIN
    for other in model.blocks:
        if other is block:
            continue
        top = other.bbox[1]
        if top >= block.bbox[3] - 1.0 and top - block.bbox[3] > 0:
            limit = min(limit, top - 3.0)
    try:
        for info in page.get_image_info():
            top = float(info["bbox"][1])
            if top >= block.bbox[3] - 1.0:
                limit = min(limit, top - 3.0)
    except Exception:
        logger.debug("image info failed during expansion check", exc_info=True)
    return limit


def _redact_blocks(page: pymupdf.Page, blocks: list[TextBlock]) -> None:
    if not blocks:
        return
    page_rect = page.rect
    for block in blocks:
        rect = pymupdf.Rect(block.bbox)
        rect.x0 -= REDACT_PAD_POINTS
        rect.x1 += REDACT_PAD_POINTS
        rect.y0 -= REDACT_PAD_POINTS * 0.6
        rect.y1 += REDACT_PAD_POINTS * 0.6
        rect &= page_rect
        if rect.is_empty:
            continue
        page.add_redact_annot(rect, fill=None, cross_out=False)
    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
        text=pymupdf.PDF_REDACT_TEXT_REMOVE,
    )
