"""Two-page viewer over the interleaved PDF: ONE document, ONE scroll.

Physical pages: (1) original, (2) translation, (3) original, (4) translation...
Spread k pairs pages (2k, 2k+1) and renders [original | translation].
Both panes live in a single scroll surface, so wheel scrolling is
synchronized by construction.
"""
from __future__ import annotations

import logging
from collections import OrderedDict

import pymupdf
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.constants import (
    SPREAD_GAP_PX,
    SPREAD_MARGIN_PX,
    VIEWER_CACHE_SPREADS,
    VIEWER_MAX_ZOOM,
    VIEWER_MIN_ZOOM,
)
from localization import tr
from ui.ad_banner import AdBanner
from ui.dialogs.premium_dialog import PremiumDialog
from ui.style import COLORS

logger = logging.getLogger(__name__)

_SAFE_SCHEMES = ("http", "https", "mailto")


def clamp_zoom(value: float) -> float:
    return max(VIEWER_MIN_ZOOM, min(VIEWER_MAX_ZOOM, value))


class SpreadCanvas(QWidget):
    spread_changed = pyqtSignal(int, int)   # current spread, total spreads
    link_activated = pyqtSignal(str)        # validated external url

    def __init__(self, doc: pymupdf.Document, zoom: float = 1.0, parent=None) -> None:
        super().__init__(parent)
        self._doc = doc
        self._zoom = clamp_zoom(zoom)
        self._page_count = doc.page_count  # cached: safe after doc.close()
        self._sizes: list[tuple[float, float]] = []
        for page in doc:
            rect = page.rect
            self._sizes.append((float(rect.width), float(rect.height)))
        self._cell_w = max((w for w, _ in self._sizes), default=595.0)
        self._cell_h = max((h for _, h in self._sizes), default=842.0)
        self._pixmaps: "OrderedDict[tuple[int, int], QPixmap]" = OrderedDict()
        self._links: dict[int, list[dict]] = {}
        self._highlights: list[tuple[int, pymupdf.Rect]] = []
        self._words: dict[int, list[tuple]] = {}
        self._selection_anchor: tuple[int, int] | None = None
        self._selection_end: tuple[int, int] | None = None
        self._selection_dragging = False
        self._selection_moved = False
        self._active_hit = -1
        self._hover_url: str | None = None
        self._hover_goto: int | None = None
        self._closed = False
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def begin_shutdown(self) -> None:
        """Stop all doc access before the document is closed."""
        self._closed = True
        self._pixmaps.clear()
        self._highlights = []
        self._words.clear()
        self._selection_anchor = None
        self._selection_end = None
        self._links.clear()
        self.update()

    # ------------------------------------------------------------------ #
    # geometry
    # ------------------------------------------------------------------ #
    @property
    def zoom(self) -> float:
        return self._zoom

    @property
    def page_count(self) -> int:
        return self._page_count

    @property
    def spread_count(self) -> int:
        return (self.page_count + 1) // 2

    @property
    def stride(self) -> float:
        return self._cell_h * self._zoom + SPREAD_GAP_PX

    def page_spread(self, page_number: int) -> int:
        return page_number // 2

    def spread_pages(self, spread: int) -> tuple[int, int]:
        """(left physical page, right physical page), 0-based."""
        left = spread * 2
        right = left + 1
        if right >= self.page_count:
            right = left  # degenerate last spread (should not happen: 2n pages)
        return left, right

    def sizeHint(self):  # noqa: N802
        width = int(2 * SPREAD_MARGIN_PX + 2 * self._cell_w * self._zoom + SPREAD_GAP_PX)
        height = int(2 * SPREAD_MARGIN_PX + self.spread_count * self.stride)
        from PyQt6.QtCore import QSize

        return QSize(width, height)

    def _column_x(self, column: int) -> float:
        col_w = self._cell_w * self._zoom
        return SPREAD_MARGIN_PX + column * (col_w + SPREAD_GAP_PX)

    def _spread_y(self, spread: int) -> float:
        return SPREAD_MARGIN_PX + spread * self.stride

    def _page_rect_on_canvas(self, page_no: int) -> QRectF:
        """Canvas-logical rect where page *page_no* is drawn."""
        spread = page_no // 2
        left_page, right_page = self.spread_pages(spread)
        column = 0 if page_no == left_page else 1
        width, height = self._sizes[page_no]
        x = self._column_x(column) + (self._cell_w - width) * 0.5 * self._zoom
        y = self._spread_y(spread) + (self._cell_h - height) * 0.5 * self._zoom
        return QRectF(x, y, width * self._zoom, height * self._zoom)

    # ------------------------------------------------------------------ #
    # zoom
    # ------------------------------------------------------------------ #
    def set_zoom(self, zoom: float) -> None:
        new_zoom = clamp_zoom(zoom)
        if abs(new_zoom - self._zoom) < 1e-6:
            return
        self._zoom = new_zoom
        self._pixmaps.clear()
        self.updateGeometry()
        self.resize(self.sizeHint())

    def fit_width(self, viewport_width: int) -> None:
        usable = viewport_width - 2 * SPREAD_MARGIN_PX - SPREAD_GAP_PX
        if usable <= 40:
            return
        self.set_zoom(usable / (2 * self._cell_w))

    # ------------------------------------------------------------------ #
    # rendering
    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:  # noqa: N802
        if self._closed:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(COLORS["canvas"]))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        scrollbar = self._vertical_scrollbar()
        view_top = scrollbar.value() if scrollbar else 0
        view_height = self.height()
        first = max(0, int((view_top - SPREAD_MARGIN_PX) // self.stride) - 1)
        last = min(self.spread_count - 1, int((view_top + view_height) // self.stride) + 1)
        for spread in range(first, last + 1):
            self._paint_spread(painter, spread)
        painter.end()

    def _paint_spread(self, painter: QPainter, spread: int) -> None:
        left_page, right_page = self.spread_pages(spread)
        for column, page_no in enumerate((left_page, right_page)):
            if page_no >= self.page_count:
                continue
            target = self._page_rect_on_canvas(page_no)
            pixmap = self._pixmap(page_no)
            if pixmap is not None:
                painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
            pen = QPen(QColor(COLORS["page_border"]))
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(target.adjusted(-0.5, -0.5, 0.5, 0.5))
            self._paint_highlights(painter, page_no, target)
            self._paint_selection(painter, page_no, target)

    def _paint_selection(self, painter: QPainter, page_no: int, target: QRectF) -> None:
        for rect in self._selection_rects(page_no):
            box = QRectF(
                target.x() + rect.x0 * self._zoom,
                target.y() + rect.y0 * self._zoom,
                rect.width * self._zoom,
                rect.height * self._zoom,
            )
            color = QColor(COLORS["accent"])
            color.setAlpha(105)
            painter.fillRect(box, color)

    def _paint_highlights(self, painter: QPainter, page_no: int, target: QRectF) -> None:
        if not self._highlights:
            return
        zoom = self._zoom
        for index, (hit_page, rect) in enumerate(self._highlights):
            if hit_page != page_no:
                continue
            x = target.x() + rect.x0 * zoom
            y = target.y() + rect.y0 * zoom
            w = (rect.x1 - rect.x0) * zoom
            h = (rect.y1 - rect.y0) * zoom
            box = QRectF(x, y, w, h)
            color = QColor(COLORS["accent"])
            color.setAlpha(160 if index == self._active_hit else 60)
            painter.fillRect(box, color)
            if index == self._active_hit:
                pen = QPen(QColor(COLORS["accent"]))
                pen.setWidthF(1.5)
                painter.setPen(pen)
                painter.drawRect(box)

    def _pixmap(self, page_no: int) -> QPixmap | None:
        if self._closed:
            return None
        dpr = int(self.devicePixelRatioF() * 100)
        # Limit device pixel ratio to avoid excessively large pixmaps during scrolling
        dpr = min(dpr, 150)  # max 1.5x
        key = (page_no, int(self._zoom * 1000), dpr)
        cached = self._pixmaps.get(key)
        if cached is not None:
            self._pixmaps.move_to_end(key)
            return cached
        try:
            page = self._doc[page_no]
            scale = self._zoom * (dpr / 100.0)
            matrix = pymupdf.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            data = pix.tobytes("png")
            pixmap = QPixmap()
            if not pixmap.loadFromData(data):
                return None
            pixmap.setDevicePixelRatio(dpr / 100.0)
        except Exception:
            logger.exception("page %d render failed", page_no + 1)
            return None
        self._pixmaps[key] = pixmap
        while len(self._pixmaps) > VIEWER_CACHE_SPREADS * 2:
            self._pixmaps.popitem(last=False)
        return pixmap

    # ------------------------------------------------------------------ #
    # links
    # ------------------------------------------------------------------ #
    def _page_links(self, page_no: int) -> list[dict]:
        if self._closed:
            return []
        if page_no in self._links:
            return self._links[page_no]
        try:
            links = self._doc[page_no].get_links()
        except Exception:
            links = []
        self._links[page_no] = links
        return links

    def _hit_test(self, pos) -> tuple[str | None, int | None]:
        if self._closed:
            return None, None
        for page_no in range(self.page_count):
            target = self._page_rect_on_canvas(page_no)
            if not target.contains(pos):
                continue
            local = QPointF(pos.x() - target.x(), pos.y() - target.y())
            doc_point = pymupdf.Point(local.x() / self._zoom, local.y() / self._zoom)
            for link in self._page_links(page_no):
                rect = link.get("from")
                if rect is None:
                    continue
                if not (rect.x0 <= doc_point.x <= rect.x1 and rect.y0 <= doc_point.y <= rect.y1):
                    continue
                kind = link.get("kind")
                if kind == pymupdf.LINK_URI:
                    uri = str(link.get("uri", ""))
                    if uri.split(":", 1)[0].lower() in _SAFE_SCHEMES:
                        return uri, None
                elif kind in (pymupdf.LINK_GOTO, pymupdf.LINK_NAMED):
                    to_page = link.get("page", -1)
                    if isinstance(to_page, int) and 0 <= to_page < self.page_count:
                        return None, to_page
            return None, None
        return None, None

    def _page_point(self, pos) -> tuple[int, pymupdf.Point] | None:
        for page_no in range(self.page_count):
            target = self._page_rect_on_canvas(page_no)
            if target.contains(pos):
                return page_no, pymupdf.Point(
                    (pos.x() - target.x()) / self._zoom,
                    (pos.y() - target.y()) / self._zoom,
                )
        return None

    def _page_words(self, page_no: int) -> list[tuple]:
        if page_no not in self._words:
            try:
                self._words[page_no] = self._doc[page_no].get_text("words", sort=True)
            except Exception:
                logger.exception("page %d word extraction failed", page_no + 1)
                self._words[page_no] = []
        return self._words[page_no]

    def _word_at(
        self, page_no: int, point: pymupdf.Point, require_near: bool = False
    ) -> int | None:
        words = self._page_words(page_no)
        nearest: tuple[float, int] | None = None
        for index, word in enumerate(words):
            x0, y0, x1, y1 = map(float, word[:4])
            dx = max(x0 - point.x, 0.0, point.x - x1)
            dy = max(y0 - point.y, 0.0, point.y - y1)
            distance = dx * dx + dy * dy
            if distance == 0:
                return index
            if nearest is None or distance < nearest[0]:
                nearest = (distance, index)
        if nearest is not None and (not require_near or nearest[0] <= 9.0):
            return nearest[1]
        return None

    def _selection_ranges(self) -> dict[int, tuple[int, int]]:
        if self._selection_anchor is None or self._selection_end is None:
            return {}
        start, end = sorted((self._selection_anchor, self._selection_end))
        ranges: dict[int, tuple[int, int]] = {}
        for page_no in range(start[0], end[0] + 1):
            words = self._page_words(page_no)
            if not words:
                continue
            first = start[1] if page_no == start[0] else 0
            last = end[1] if page_no == end[0] else len(words) - 1
            ranges[page_no] = (max(0, first), min(len(words) - 1, last))
        return ranges

    def _selection_rects(self, page_no: int) -> list[pymupdf.Rect]:
        bounds = self._selection_ranges().get(page_no)
        if bounds is None:
            return []
        words = self._page_words(page_no)
        return [pymupdf.Rect(word[:4]) for word in words[bounds[0]:bounds[1] + 1]]

    @property
    def selected_text(self) -> str:
        selected: list[str] = []
        for page_no, (first, last) in self._selection_ranges().items():
            words = self._page_words(page_no)[first:last + 1]
            line: list[str] = []
            previous_line: tuple | None = None
            for word in words:
                line_key = (word[5], word[6])
                if previous_line is not None and line_key != previous_line:
                    selected.append(" ".join(line))
                    line = []
                line.append(str(word[4]))
                previous_line = line_key
            if line:
                selected.append(" ".join(line))
        return "\n".join(selected)

    def _update_selection_end(self, pos) -> None:
        if self._selection_anchor is None:
            return
        page_point = self._page_point(pos)
        if page_point is None:
            return
        page_no, point = page_point
        word_index = self._word_at(page_no, point)
        if word_index is None:
            return
        end = (page_no, word_index)
        if end != self._selection_end:
            self._selection_end = end
            self._selection_moved = self._selection_moved or end != self._selection_anchor
            self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._closed:
            super().mousePressEvent(event)
            return
        page_point = self._page_point(event.position())
        if page_point is None:
            self._selection_anchor = None
            self._selection_end = None
            self._selection_moved = False
            self.update()
            super().mousePressEvent(event)
            return
        page_no, point = page_point
        word_index = self._word_at(page_no, point, require_near=True)
        if word_index is None:
            self._selection_anchor = None
            self._selection_end = None
            self._selection_moved = False
            self.update()
            super().mousePressEvent(event)
            return
        self._selection_anchor = (page_no, word_index)
        self._selection_end = self._selection_anchor
        self._selection_dragging = True
        self._selection_moved = False
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        page_point = self._page_point(event.position())
        if page_point is None:
            return
        page_no, point = page_point
        word_index = self._word_at(page_no, point, require_near=True)
        if word_index is not None:
            self._selection_anchor = (page_no, word_index)
            self._selection_end = self._selection_anchor
            self._selection_dragging = False
            self._selection_moved = True
            self.update()
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._selection_dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self._update_selection_end(event.position())
            self.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
            event.accept()
            return
        url, goto = self._hit_test(event.position())
        self._hover_url = url
        self._hover_goto = goto
        page_point = self._page_point(event.position())
        on_text = (
            page_point is not None
            and self._word_at(page_point[0], page_point[1], require_near=True) is not None
        )
        cursor = (
            Qt.CursorShape.PointingHandCursor if (url or goto is not None)
            else Qt.CursorShape.IBeamCursor if on_text
            else Qt.CursorShape.ArrowCursor
        )
        self.setCursor(QCursor(cursor))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._selection_dragging:
            self._update_selection_end(event.position())
            self._selection_dragging = False
            if not self._selection_moved:
                url, goto = self._hit_test(event.position())
                if url:
                    self.link_activated.emit(url)
                elif goto is not None:
                    self.center_page(goto)
            event.accept()
            return
        if self._selection_moved:
            event.accept()
            return
        url, goto = self._hit_test(event.position())
        if url:
            self.link_activated.emit(url)
        elif goto is not None:
            self.center_page(goto)

    # ------------------------------------------------------------------ #
    # search / navigation
    # ------------------------------------------------------------------ #
    def search(self, text: str) -> int:
        self._highlights = []
        self._active_hit = -1
        if self._closed:
            return 0
        needle = text.strip()
        if not needle:
            self.update()
            return 0
        for page_no in range(self.page_count):
            try:
                rects = self._doc[page_no].search_for(needle)
            except Exception:
                rects = []
            for rect in rects:
                self._highlights.append((page_no, pymupdf.Rect(rect)))
        self.update()
        return len(self._highlights)

    @property
    def hit_count(self) -> int:
        return len(self._highlights)

    def goto_hit(self, step: int) -> int:
        if not self._highlights:
            return -1
        self._active_hit = (self._active_hit + step) % len(self._highlights)
        page_no, rect = self._highlights[self._active_hit]
        self.center_page(page_no, rect)
        self.update()
        return self._active_hit

    def clear_search(self) -> None:
        self._highlights = []
        self._active_hit = -1
        self.update()

    def center_page(self, page_no: int, rect: pymupdf.Rect | None = None) -> None:
        target = self._page_rect_on_canvas(page_no)
        area = self._scroll_area()
        if area is None:
            return
        h_bar = area.horizontalScrollBar()
        v_bar = area.verticalScrollBar()
        view_w = area.viewport().width()
        view_h = area.viewport().height()
        if rect is not None:
            focus_y = target.y() + (rect.y0 + rect.y1) * 0.5 * self._zoom
            focus_x = target.x() + (rect.x0 + rect.x1) * 0.5 * self._zoom
        else:
            focus_y = target.y() + target.height() * 0.5
            focus_x = target.x() + target.width() * 0.5
        v_bar.setValue(max(0, int(focus_y - view_h * 0.5)))
        if target.width() > view_w:
            h_bar.setValue(max(0, int(focus_x - view_w * 0.5)))
        self.spread_changed.emit(self.current_spread(), self.spread_count)

    def current_spread(self) -> int:
        area = self._scroll_area()
        if area is None or self.spread_count == 0:
            return 0
        top = area.verticalScrollBar().value()
        spread = int((top - SPREAD_MARGIN_PX + self.stride * 0.35) // self.stride)
        return max(0, min(self.spread_count - 1, spread))

    # ------------------------------------------------------------------ #
    # parent lookups
    # ------------------------------------------------------------------ #
    def _scroll_area(self) -> QScrollArea | None:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                return parent
            parent = parent.parentWidget()
        return None

    def _vertical_scrollbar(self):
        area = self._scroll_area()
        return area.verticalScrollBar() if area else None


# --------------------------------------------------------------------------- #
class _ZoomScrollArea(QScrollArea):
    """Scroll area owning Ctrl+wheel zoom and the first-fit resize hook.

    Implemented as overrides instead of an event filter: a Python event filter
    on a widget being destroyed can crash natively during teardown.
    """

    ctrl_wheel = pyqtSignal(int, int)   # wheel delta, cursor y
    first_resize = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._fit_emitted = False

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.ctrl_wheel.emit(int(delta), int(event.position().y()))
                event.accept()
                return
        super().wheelEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not self._fit_emitted:
            self._fit_emitted = True
            self.first_resize.emit()


class ViewerWindow(QMainWindow):
    """Toolbar + Ctrl+F search + two-page canvas + reserved ad strip."""

    def __init__(self, services, document_id: str, title: str, pdf_bytes: bytes, parent=None) -> None:
        super().__init__(parent)
        from pdf.loader import open_pdf_bytes

        self._services = services
        self._document_id = document_id
        self._title = title
        self._pdf_bytes = pdf_bytes
        self._doc = open_pdf_bytes(pdf_bytes)  # raises PdfOpenError to caller
        self._fitted = False

        self.setObjectName("root")
        self.setWindowTitle(f"{title} — ParaLate")
        self.resize(1280, 860)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        central = QWidget()
        central.setObjectName("root")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_search_bar())

        self._scroll = _ZoomScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.canvas = SpreadCanvas(self._doc, zoom=1.0)
        self._scroll.setWidget(self.canvas)
        layout.addWidget(self._scroll, 1)

        self._banner = AdBanner(services.ads, "viewer")
        banner_wrap = QWidget()
        banner_wrap.setObjectName("root")
        banner_layout = QVBoxLayout(banner_wrap)
        banner_layout.setContentsMargins(10, 6, 10, 8)
        banner_layout.addWidget(self._banner)
        layout.addWidget(banner_wrap)

        self.setCentralWidget(central)
        self._promo_cover = QWidget(central)
        self._promo_cover.setObjectName("premiumPromoCover")
        self._promo_cover.setStyleSheet(
            f"QWidget#premiumPromoCover {{ background: {COLORS['window']}; }}"
        )
        cover_layout = QVBoxLayout(self._promo_cover)
        cover_message = QLabel(tr("premium.promo_blocked"))
        cover_message.setObjectName("section")
        cover_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_layout.addWidget(cover_message)
        self._promo_cover.hide()
        self._build_toolbar()
        self._build_shortcuts()

        self.canvas.spread_changed.connect(self._on_spread_changed)
        self.canvas.link_activated.connect(self._on_link)
        self._scroll.verticalScrollBar().valueChanged.connect(lambda _: self._update_page_label())
        self._scroll.ctrl_wheel.connect(self._on_ctrl_wheel)
        self._scroll.first_resize.connect(self._on_first_resize)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._run_search)

        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self._fit_width)

        self._pending_restore = None
        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self._run_pending_restore)

        self._update_badge()
        self._update_page_label()

    # ------------------------------------------------------------------ #
    # toolbar / search bar construction
    # ------------------------------------------------------------------ #
    def _build_toolbar(self) -> None:
        bar = QToolBar()
        bar.setMovable(False)
        bar.setFloatable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(bar)

        app_label = QLabel("ParaLate")
        app_label.setObjectName("section")
        bar.addWidget(app_label)
        title_label = QLabel(f"   {self._title}")
        title_label.setObjectName("dim")
        bar.addWidget(title_label)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        bar.addWidget(spacer)

        self._page_label = QLabel("1 / 1")
        self._page_label.setObjectName("dim")
        bar.addWidget(self._page_label)
        bar.addSeparator()

        self._zoom_out = self._tool_button("−", self._zoom_out_clicked)
        bar.addWidget(self._zoom_out)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setObjectName("dim")
        bar.addWidget(self._zoom_label)
        self._zoom_in = self._tool_button("+", self._zoom_in_clicked)
        bar.addWidget(self._zoom_in)

        self._fs_button = self._tool_button(tr("viewer.fullscreen"), self._toggle_fullscreen)
        bar.addWidget(self._fs_button)
        self._download_button = QPushButton("")
        self._download_button.setObjectName("toolbar")
        self._download_button.clicked.connect(self._on_download)
        bar.addWidget(self._download_button)

        self._badge = QLabel("")
        bar.addWidget(self._badge)

    @staticmethod
    def _tool_button(text: str, slot) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("toolbar")
        button.clicked.connect(slot)
        return button

    def _build_search_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("root")
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 8, 10, 4)
        row.setSpacing(6)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(tr("viewer.search_placeholder"))
        self._search_edit.textChanged.connect(self._on_search_text)
        self._search_edit.returnPressed.connect(self._search_next)
        row.addWidget(self._search_edit, 1)
        self._search_count = QLabel("")
        self._search_count.setObjectName("dim")
        row.addWidget(self._search_count)
        prev = self._tool_button("↑", self._search_prev)
        nxt = self._tool_button("↓", self._search_next)
        close = self._tool_button("✕", self._hide_search)
        row.addWidget(prev)
        row.addWidget(nxt)
        row.addWidget(close)
        frame.hide()
        self._search_bar = frame
        return frame

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence.StandardKey.Find, self, self._show_search)
        QShortcut(
            QKeySequence.StandardKey.Copy,
            self.canvas,
            lambda: QApplication.clipboard().setText(self.canvas.selected_text)
            if self.canvas.selected_text else None,
        )
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in_clicked)
        QShortcut(QKeySequence.StandardKey.ZoomIn, self, self._zoom_in_clicked)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out_clicked)
        QShortcut(QKeySequence.StandardKey.ZoomOut, self, self._zoom_out_clicked)
        QShortcut(QKeySequence("Ctrl+0"), self, self._fit_width)
        QShortcut(QKeySequence("F11"), self, self._toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self, self._on_escape)

    # ------------------------------------------------------------------ #
    # zoom / layout
    # ------------------------------------------------------------------ #
    def _on_ctrl_wheel(self, delta: int, anchor_y: int) -> None:
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._zoom_to(self.canvas.zoom * factor, anchor_y=anchor_y)

    def _on_first_resize(self) -> None:
        if not self._fitted:
            self._fitted = True
            self._fit_timer.start(0)

    def _run_pending_restore(self) -> None:
        restore = self._pending_restore
        self._pending_restore = None
        if restore is not None:
            restore()

    def _zoom_in_clicked(self) -> None:
        self._zoom_to(self.canvas.zoom * 1.15)

    def _zoom_out_clicked(self) -> None:
        self._zoom_to(self.canvas.zoom / 1.15)

    def _fit_width(self) -> None:
        self._zoom_to(None)

    def _zoom_to(self, new_zoom: float | None, anchor_y: int | None = None) -> None:
        old_zoom = self.canvas.zoom
        if new_zoom is None:
            viewport_w = self._scroll.viewport().width()
            usable = viewport_w - 2 * SPREAD_MARGIN_PX - SPREAD_GAP_PX
            if usable <= 40:
                return
            new_zoom = clamp_zoom(usable / (2 * self.canvas._cell_w))
        new_zoom = clamp_zoom(new_zoom)
        if abs(new_zoom - old_zoom) < 1e-6:
            return
        v_bar = self._scroll.verticalScrollBar()
        h_bar = self._scroll.horizontalScrollBar()
        if anchor_y is None:
            anchor_y = self._scroll.viewport().height() // 2
            anchor_x = self._scroll.viewport().width() // 2
            content_x = h_bar.value() + anchor_x
        else:
            content_x = None
        content_y = v_bar.value() + anchor_y
        ratio = new_zoom / old_zoom

        self.canvas.set_zoom(new_zoom)
        self._zoom_label.setText(f"{round(new_zoom * 100)}%")

        def restore() -> None:
            try:
                v_bar.setValue(int(content_y * ratio - anchor_y))
                if content_x is not None:
                    h_bar.setValue(int(content_x * ratio - anchor_x))
                self.canvas.update()
            except RuntimeError:
                # window was closed before the deferred restore fired
                logger.debug("zoom restore skipped: window closed")

        self._pending_restore = restore
        self._restore_timer.start(0)

    # ------------------------------------------------------------------ #
    # page label / spread
    # ------------------------------------------------------------------ #
    def _update_page_label(self) -> None:
        spread = self.canvas.current_spread()
        left, right = self.canvas.spread_pages(spread)
        total = self.canvas.page_count
        self._page_label.setText(f"{left + 1}–{right + 1} / {total}")

    def set_premium_promo_blocked(self, blocked: bool) -> None:
        self._promo_cover.setGeometry(self.centralWidget().rect())
        self._promo_cover.setVisible(blocked)
        self._promo_cover.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_promo_cover") and self.centralWidget() is not None:
            self._promo_cover.setGeometry(self.centralWidget().rect())

    def _on_spread_changed(self, spread: int, total: int) -> None:
        left, right = self.canvas.spread_pages(spread)
        self._page_label.setText(f"{left + 1}–{right + 1} / {self.canvas.page_count}")

    # ------------------------------------------------------------------ #
    # search
    # ------------------------------------------------------------------ #
    def _show_search(self) -> None:
        self._search_bar.show()
        self._search_edit.setFocus()
        self._search_edit.selectAll()

    def _hide_search(self) -> None:
        self._search_bar.hide()
        self.canvas.clear_search()
        self._search_count.setText("")
        self.canvas.setFocus()

    def _on_search_text(self, text: str) -> None:
        self._search_timer.start()

    def _run_search(self) -> None:
        text = self._search_edit.text().strip()
        if not text:
            self.canvas.clear_search()
            self._search_count.setText("")
            return
        hits = self.canvas.search(text)
        if hits:
            self.canvas.goto_hit(1)  # active was -1 -> first hit
            self._search_count.setText(f"1/{hits}")
        else:
            self._search_count.setText(tr("viewer.search_none"))

    def _search_next(self) -> None:
        if not self.canvas.hit_count:
            self._run_search()
            return
        self.canvas.goto_hit(1)
        self._search_count.setText(f"{self.canvas._active_hit + 1}/{self.canvas.hit_count}")

    def _search_prev(self) -> None:
        if not self.canvas.hit_count:
            return
        self.canvas.goto_hit(-1)
        self._search_count.setText(f"{self.canvas._active_hit + 1}/{self.canvas.hit_count}")

    # ------------------------------------------------------------------ #
    # fullscreen / links / download
    # ------------------------------------------------------------------ #
    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.findChild(QToolBar).show()
            if self._services.ads.enabled:
                self._banner.show()
        else:
            self.showFullScreen()
            self.findChild(QToolBar).hide()
            self._banner.hide()

    def _on_escape(self) -> None:
        if self.isFullScreen():
            self._toggle_fullscreen()
        elif self._search_bar.isVisible():
            self._hide_search()

    def _on_link(self, url: str) -> None:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        parsed = QUrl(url)
        if parsed.scheme() in ("http", "https", "mailto") and parsed.host():
            QDesktopServices.openUrl(parsed)

    def _on_download(self) -> None:
        if not self._services.license.allows("download"):
            dialog = PremiumDialog(self._services.license, self)
            dialog.exec()
            self._update_badge()
            self._banner.refresh()
            return
        suggested = self._title
        if not suggested.lower().endswith(".pdf"):
            suggested += ".pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, tr("viewer.save_as"), suggested, "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            from pathlib import Path

            Path(path).write_bytes(self._pdf_bytes)
        except OSError:
            QMessageBox.critical(self, tr("error.title"), tr("error.disk"))
            logger.exception("download failed")
        else:
            QMessageBox.information(self, tr("viewer.saved"), tr("viewer.saved_body", path=path))

    def _update_badge(self) -> None:
        premium = self._services.license.is_premium
        self._badge.setText("👑 PREMIUM" if premium else "FREE")
        self._badge.setObjectName("badgePremium" if premium else "badge")
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)
        self._download_button.setText(tr("viewer.download") + ("" if premium else " 👑"))

    # ------------------------------------------------------------------ #
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._banner.refresh()

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            self._search_timer.stop()
            self._fit_timer.stop()
            self._restore_timer.stop()
            self._promo_cover.hide()
            self.canvas.begin_shutdown()
            self._doc.close()
        except RuntimeError:
            logger.debug("viewer teardown: objects already gone")
        except Exception:
            logger.debug("doc close failed", exc_info=True)
        super().closeEvent(event)
