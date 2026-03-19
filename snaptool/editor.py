"""Annotation editor with drawing tools."""

import io
import math
from enum import Enum, auto

from PIL import Image, ImageFilter

from PyQt6.QtWidgets import (
    QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsLineItem,
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPathItem,
    QGraphicsTextItem, QGraphicsPixmapItem, QToolBar,
    QColorDialog, QSpinBox, QLabel, QHBoxLayout, QVBoxLayout,
    QWidget, QSizePolicy, QApplication, QInputDialog, QToolButton,
    QMenu, QFileDialog, QMessageBox, QSlider, QFrame, QWidgetAction,
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QLineF, QEvent, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPixmap, QFont, QPainterPath,
    QPolygonF, QImage, QIcon, QTransform, QAction, QActionGroup,
    QCloseEvent,
)

from .config import Config
from .capture import ScreenCapture


# ── Icon factory ──────────────────────────────────────────────────────

_ICON_SIZE = 20
_ICON_COLOR = QColor(220, 220, 220)


def _new_pixmap():
    pm = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pm.fill(Qt.GlobalColor.transparent)
    return pm


def _icon_pen(width=1.6):
    pen = QPen(_ICON_COLOR, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _make_arrow_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = _icon_pen(1.8)
    p.setPen(pen)
    # Diagonal arrow from bottom-left to top-right
    p.drawLine(QPointF(4, 16), QPointF(16, 4))
    # Arrowhead
    p.setBrush(_ICON_COLOR)
    p.setPen(Qt.PenStyle.NoPen)
    poly = QPolygonF([QPointF(16, 4), QPointF(10, 5), QPointF(15, 10)])
    p.drawPolygon(poly)
    p.end()
    return QIcon(pm)


def _make_rect_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_icon_pen(1.6))
    p.drawRect(QRectF(3, 4, 14, 12))
    p.end()
    return QIcon(pm)


def _make_ellipse_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_icon_pen(1.6))
    p.drawEllipse(QRectF(2, 3, 16, 14))
    p.end()
    return QIcon(pm)


def _make_line_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_icon_pen(1.8))
    p.drawLine(QPointF(3, 17), QPointF(17, 3))
    p.end()
    return QIcon(pm)


def _make_pen_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Freehand wavy line representing pen drawing
    p.setPen(_icon_pen(2.0))
    path = QPainterPath()
    path.moveTo(2, 14)
    path.cubicTo(5, 6, 8, 16, 11, 10)
    path.cubicTo(13, 6, 15, 12, 18, 8)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def _make_text_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_ICON_COLOR)
    font = QFont("Segoe UI", 13, QFont.Weight.Bold)
    p.setFont(font)
    p.drawText(QRectF(0, 0, _ICON_SIZE, _ICON_SIZE), Qt.AlignmentFlag.AlignCenter, "T")
    p.end()
    return QIcon(pm)


def _make_blur_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = _icon_pen(1.2)
    p.setPen(pen)
    # Grid pattern representing blur/mosaic
    for x in range(3, 18, 4):
        p.drawLine(x, 3, x, 17)
    for y in range(3, 18, 4):
        p.drawLine(3, y, 17, y)
    p.end()
    return QIcon(pm)


def _make_highlight_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Highlighter body
    p.setPen(_icon_pen(1.4))
    p.drawLine(QPointF(5, 15), QPointF(12, 4))
    p.drawLine(QPointF(12, 4), QPointF(16, 7))
    p.drawLine(QPointF(16, 7), QPointF(9, 18))
    p.drawLine(QPointF(9, 18), QPointF(5, 15))
    # Highlight stroke at bottom
    highlight = QColor(255, 255, 0, 120)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(highlight)
    p.drawRect(QRectF(2, 16, 16, 3))
    p.end()
    return QIcon(pm)


def _make_step_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_ICON_COLOR)
    p.drawEllipse(QRectF(2, 2, 16, 16))
    p.setPen(QColor(40, 40, 40))
    font = QFont("Segoe UI", 9, QFont.Weight.Bold)
    p.setFont(font)
    p.drawText(QRectF(2, 2, 16, 16), Qt.AlignmentFlag.AlignCenter, "1")
    p.end()
    return QIcon(pm)


def _make_undo_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_icon_pen(1.8))
    # Arc curving from right to left
    arc_rect = QRectF(4, 2, 14, 12)
    p.drawArc(arc_rect, 30 * 16, 130 * 16)  # start 30deg, span 130deg
    # Horizontal line at bottom
    p.drawLine(QPointF(5, 14), QPointF(16, 14))
    # Arrowhead at left end of arc
    p.setBrush(_ICON_COLOR)
    p.setPen(Qt.PenStyle.NoPen)
    poly = QPolygonF([QPointF(4, 8), QPointF(7, 4), QPointF(8, 9)])
    p.drawPolygon(poly)
    p.end()
    return QIcon(pm)


def _make_redo_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_icon_pen(1.8))
    # Arc curving from left to right
    arc_rect = QRectF(2, 2, 14, 12)
    p.drawArc(arc_rect, 20 * 16, 130 * 16)
    # Horizontal line at bottom
    p.drawLine(QPointF(4, 14), QPointF(15, 14))
    # Arrowhead at right end of arc
    p.setBrush(_ICON_COLOR)
    p.setPen(Qt.PenStyle.NoPen)
    poly = QPolygonF([QPointF(16, 8), QPointF(12, 4), QPointF(13, 9)])
    p.drawPolygon(poly)
    p.end()
    return QIcon(pm)


def _make_zoom_in_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_icon_pen(1.6))
    # Magnifying glass circle
    p.drawEllipse(QRectF(3, 2, 11, 11))
    # Handle
    p.drawLine(QPointF(13, 12), QPointF(18, 17))
    # Plus sign
    p.drawLine(QPointF(8.5, 5), QPointF(8.5, 10))
    p.drawLine(QPointF(6, 7.5), QPointF(11, 7.5))
    p.end()
    return QIcon(pm)


def _make_zoom_out_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_icon_pen(1.6))
    p.drawEllipse(QRectF(3, 2, 11, 11))
    p.drawLine(QPointF(13, 12), QPointF(18, 17))
    # Minus sign
    p.drawLine(QPointF(6, 7.5), QPointF(11, 7.5))
    p.end()
    return QIcon(pm)


def _make_fit_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_icon_pen(1.6))
    # Four corner arrows pointing outward
    # Top-left corner
    p.drawLine(QPointF(2, 7), QPointF(2, 2))
    p.drawLine(QPointF(2, 2), QPointF(7, 2))
    # Top-right corner
    p.drawLine(QPointF(13, 2), QPointF(18, 2))
    p.drawLine(QPointF(18, 2), QPointF(18, 7))
    # Bottom-left corner
    p.drawLine(QPointF(2, 13), QPointF(2, 18))
    p.drawLine(QPointF(2, 18), QPointF(7, 18))
    # Bottom-right corner
    p.drawLine(QPointF(13, 18), QPointF(18, 18))
    p.drawLine(QPointF(18, 18), QPointF(18, 13))
    p.end()
    return QIcon(pm)


def _make_save_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_icon_pen(1.6))
    # Floppy disk outline
    p.drawRect(QRectF(3, 2, 14, 16))
    # Label area at top
    p.drawRect(QRectF(6, 2, 8, 6))
    # Write slot
    p.drawRect(QRectF(5, 12, 10, 5))
    p.end()
    return QIcon(pm)


def _make_copy_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_icon_pen(1.4))
    # Back rectangle
    p.drawRect(QRectF(5, 1, 12, 13))
    # Front rectangle
    p.setBrush(QColor(43, 43, 43))
    p.drawRect(QRectF(2, 5, 12, 13))
    p.end()
    return QIcon(pm)


def _make_save_copy_path_icon():
    pm = _new_pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_icon_pen(1.4))
    # Floppy disk (smaller)
    p.drawRect(QRectF(2, 1, 11, 12))
    p.drawRect(QRectF(5, 1, 5, 4))
    p.drawRect(QRectF(4, 8, 7, 4))
    # Link/path indicator
    pen2 = _icon_pen(1.6)
    pen2.setColor(QColor(100, 200, 255))
    p.setPen(pen2)
    p.drawLine(QPointF(14, 10), QPointF(14, 18))
    p.drawLine(QPointF(14, 18), QPointF(18, 18))
    # Small arrow on the path
    p.setBrush(QColor(100, 200, 255))
    p.setPen(Qt.PenStyle.NoPen)
    poly = QPolygonF([QPointF(18, 18), QPointF(16, 16), QPointF(16, 20)])
    p.drawPolygon(poly)
    p.end()
    return QIcon(pm)


# ── Tool enum ─────────────────────────────────────────────────────────

class Tool(Enum):
    ARROW = auto()
    RECTANGLE = auto()
    ELLIPSE = auto()
    LINE = auto()
    FREEHAND = auto()
    TEXT = auto()
    BLUR = auto()
    HIGHLIGHT = auto()
    STEP_NUMBER = auto()


# Map tool enum names for config persistence
_TOOL_NAMES = {t.name: t for t in Tool}


class ArrowItem(QGraphicsLineItem):
    """Line with arrowhead."""

    def __init__(self, line, pen):
        super().__init__(line)
        self.setPen(pen)
        self._arrow_size = 14

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(self.pen())

        line = self.line()
        if line.length() < 1:
            return

        painter.drawLine(line)

        angle = line.angle()
        rad = math.radians(angle)
        arrow_p1 = line.p2() - QPointF(
            self._arrow_size * math.cos(rad - math.pi / 6),
            -self._arrow_size * math.sin(rad - math.pi / 6),
        )
        arrow_p2 = line.p2() - QPointF(
            self._arrow_size * math.cos(rad + math.pi / 6),
            -self._arrow_size * math.sin(rad + math.pi / 6),
        )

        painter.setBrush(self.pen().color())
        painter.setPen(Qt.PenStyle.NoPen)
        poly = QPolygonF([line.p2(), arrow_p1, arrow_p2])
        painter.drawPolygon(poly)


class StepNumberItem(QGraphicsEllipseItem):
    """Numbered circle marker for step annotations."""

    def __init__(self, center, number, size, color):
        r = size / 2
        super().__init__(center.x() - r, center.y() - r, size, size)
        self._number = number
        self._color = color
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.PenStyle.NoPen))

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self.brush())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.rect())

        painter.setPen(QColor(255, 255, 255))
        font = QFont("Segoe UI", int(self.rect().width() * 0.4), QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(self._number))


class AnnotationEditor(QMainWindow):
    """Screenshot annotation editor window."""

    def __init__(self, pil_image, parent=None):
        super().__init__(parent)
        self.config = Config.instance()
        self.pil_image = pil_image
        self._drawing = False
        self._current_item = None
        self._start_pos = None
        self._path_points = []
        self._undo_stack = []
        self._redo_stack = []
        self._step_counter = 1
        self._saved = False
        self._has_annotations = False

        # Restore persisted editor settings
        saved_tool = self.config.get("editor_tool", "ARROW")
        self._current_tool = _TOOL_NAMES.get(saved_tool, Tool.ARROW)

        saved_color = self.config.get("editor_color", "#ff3232")
        self._pen_color = QColor(saved_color)
        if not self._pen_color.isValid():
            self._pen_color = QColor(255, 50, 50)

        self._pen_width = self.config.get("editor_width", 3)

        self.setWindowTitle("SnapTool - Editor")
        self.setMinimumSize(800, 600)
        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._view.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self._view.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.FullViewportUpdate
        )

        self._bg_pixmap = ScreenCapture.pil_to_qpixmap(self.pil_image)
        self._bg_item = self._scene.addPixmap(self._bg_pixmap)
        self._scene.setSceneRect(QRectF(self._bg_pixmap.rect()))

        self.setCentralWidget(self._view)
        self._view.viewport().installEventFilter(self)

        # Toolbar
        toolbar = QToolBar("Tools")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # Tool icons
        _tool_icons = {
            Tool.ARROW: _make_arrow_icon(),
            Tool.RECTANGLE: _make_rect_icon(),
            Tool.ELLIPSE: _make_ellipse_icon(),
            Tool.LINE: _make_line_icon(),
            Tool.FREEHAND: _make_pen_icon(),
            Tool.TEXT: _make_text_icon(),
            Tool.BLUR: _make_blur_icon(),
            Tool.HIGHLIGHT: _make_highlight_icon(),
            Tool.STEP_NUMBER: _make_step_icon(),
        }

        tool_group = QActionGroup(self)
        tools = [
            ("Arrow", Tool.ARROW),
            ("Rectangle", Tool.RECTANGLE),
            ("Ellipse", Tool.ELLIPSE),
            ("Line", Tool.LINE),
            ("Pen", Tool.FREEHAND),
            ("Text", Tool.TEXT),
            ("Blur", Tool.BLUR),
            ("Highlight", Tool.HIGHLIGHT),
            ("Step #", Tool.STEP_NUMBER),
        ]
        for name, tool in tools:
            action = QAction(_tool_icons[tool], name, self)
            action.setToolTip(name)
            action.setCheckable(True)
            action.setData(tool)
            action.triggered.connect(lambda checked, t=tool: self._set_tool(t))
            tool_group.addAction(action)
            toolbar.addAction(action)
            if tool == self._current_tool:
                action.setChecked(True)

        toolbar.addSeparator()

        # Color button
        self._color_btn = QToolButton()
        self._color_btn.setToolTip("Color")
        self._color_btn.setStyleSheet(
            f"background: {self._pen_color.name()}; min-width: 24px; min-height: 24px; border-radius: 3px; border: 2px solid #666;"
        )
        self._color_btn.clicked.connect(self._pick_color)
        toolbar.addWidget(self._color_btn)

        # Width slider button (Snipping Tool style popup)
        self._width_btn = QToolButton()
        self._width_btn.setText(str(self._pen_width))
        self._width_btn.setToolTip("Size")
        self._width_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        width_menu = QMenu(self._width_btn)
        width_menu.setStyleSheet("""
            QMenu {
                background: #2b2b2b; border: 1px solid #3a3a3a;
                padding: 12px; border-radius: 6px;
            }
            QLabel { color: #e0e0e0; font-family: "Segoe UI"; font-size: 9pt; }
            QSlider::groove:horizontal {
                height: 4px; background: #505050; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 14px; height: 14px; margin: -5px 0;
                background: #0078d4; border-radius: 7px;
            }
            QSlider::sub-page:horizontal { background: #0078d4; border-radius: 2px; }
        """)

        slider_widget = QWidget()
        slider_layout = QVBoxLayout(slider_widget)
        slider_layout.setContentsMargins(4, 4, 4, 4)
        slider_layout.setSpacing(6)

        size_label = QLabel("Size")
        size_label.setStyleSheet("font-weight: bold;")
        slider_layout.addWidget(size_label)

        self._width_preview = QLabel()
        self._width_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._width_preview.setMinimumHeight(30)
        self._update_width_preview()
        slider_layout.addWidget(self._width_preview)

        self._width_slider = QSlider(Qt.Orientation.Horizontal)
        self._width_slider.setRange(1, 20)
        self._width_slider.setValue(self._pen_width)
        self._width_slider.setMinimumWidth(160)
        self._width_slider.valueChanged.connect(self._on_width_slider_changed)
        slider_layout.addWidget(self._width_slider)

        slider_action = QWidgetAction(width_menu)
        slider_action.setDefaultWidget(slider_widget)
        width_menu.addAction(slider_action)

        self._width_btn.setMenu(width_menu)
        toolbar.addWidget(self._width_btn)

        toolbar.addSeparator()

        undo_action = QAction(_make_undo_icon(), "Undo", self)
        undo_action.setToolTip("Undo (Ctrl+Z)")
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self._undo)
        toolbar.addAction(undo_action)

        redo_action = QAction(_make_redo_icon(), "Redo", self)
        redo_action.setToolTip("Redo (Ctrl+Y)")
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self._redo)
        toolbar.addAction(redo_action)

        toolbar.addSeparator()

        zoom_in = QAction(_make_zoom_in_icon(), "Zoom In", self)
        zoom_in.setToolTip("Zoom In (Ctrl+=)")
        zoom_in.setShortcut("Ctrl+=")
        zoom_in.triggered.connect(lambda: self._view.scale(1.2, 1.2))
        toolbar.addAction(zoom_in)

        zoom_out = QAction(_make_zoom_out_icon(), "Zoom Out", self)
        zoom_out.setToolTip("Zoom Out (Ctrl+-)")
        zoom_out.setShortcut("Ctrl+-")
        zoom_out.triggered.connect(lambda: self._view.scale(1 / 1.2, 1 / 1.2))
        toolbar.addAction(zoom_out)

        zoom_fit = QAction(_make_fit_icon(), "Fit", self)
        zoom_fit.setToolTip("Fit to Window (Ctrl+0)")
        zoom_fit.setShortcut("Ctrl+0")
        zoom_fit.triggered.connect(self._fit_view)
        toolbar.addAction(zoom_fit)

        toolbar.addSeparator()

        save_action = QAction(_make_save_icon(), "Save", self)
        save_action.setToolTip("Save (Ctrl+S)")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save)
        toolbar.addAction(save_action)

        save_copy_path_action = QAction(_make_save_copy_path_icon(), "Save + Copy Path", self)
        save_copy_path_action.setToolTip("Save + Copy Path")
        save_copy_path_action.triggered.connect(self._save_copy_path)
        toolbar.addAction(save_copy_path_action)

        copy_action = QAction(_make_copy_icon(), "Copy", self)
        copy_action.setToolTip("Copy to Clipboard (Ctrl+C)")
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self._copy_to_clipboard)
        toolbar.addAction(copy_action)

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background: #1e1e1e; }
            QToolBar {
                background: #2b2b2b; border-bottom: 1px solid #3a3a3a;
                spacing: 2px; padding: 4px;
            }
            QToolBar QToolButton, QToolBar QPushButton {
                background: #3a3a3a; color: #e0e0e0;
                border: 1px solid #505050; border-radius: 4px;
                padding: 4px 4px 2px 4px; font-family: "Segoe UI"; font-size: 7pt;
            }
            QToolBar QToolButton:checked {
                background: #0078d4; border-color: #0078d4; color: white;
            }
            QToolBar QToolButton:hover { background: #4a4a4a; }
            QToolBar QToolButton::menu-indicator { image: none; }
            QLabel { color: #ccc; font-family: "Segoe UI"; }
            QGraphicsView { background: #1a1a1a; border: none; }
        """)

    def showEvent(self, event):
        super().showEvent(event)
        self._fit_view()

    def closeEvent(self, event: QCloseEvent):
        if self._has_annotations and not self._saved:
            reply = QMessageBox.question(
                self,
                "Unsaved Annotations",
                "You have unsaved annotations. Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        # Persist editor settings for next session
        self._persist_settings()
        super().closeEvent(event)

    def _persist_settings(self):
        self.config.set_all({
            **self.config.get_all(),
            "editor_tool": self._current_tool.name,
            "editor_color": self._pen_color.name(),
            "editor_width": self._pen_width,
        })

    def _fit_view(self):
        self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _set_tool(self, tool):
        self._current_tool = tool

    def _pick_color(self):
        color = QColorDialog.getColor(self._pen_color, self, "Pick Color")
        if color.isValid():
            self._pen_color = color
            self._color_btn.setStyleSheet(
                f"background: {color.name()}; min-width: 24px; min-height: 24px; border-radius: 3px; border: 2px solid #666;"
            )
            self._update_width_preview()

    def _set_width(self, w):
        self._pen_width = w

    def _on_width_slider_changed(self, value):
        self._pen_width = value
        self._width_btn.setText(str(value))
        self._update_width_preview()

    def _update_width_preview(self):
        pm = QPixmap(160, 30)
        pm.fill(QColor(43, 43, 43))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._pen_color, self._pen_width,
                   Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(20, 15), QPointF(140, 15))
        p.end()
        self._width_preview.setPixmap(pm)

    def _make_pen(self):
        return QPen(
            self._pen_color, self._pen_width,
            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin,
        )

    def eventFilter(self, obj, event):
        if obj is self._view.viewport():
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._on_press(self._view.mapToScene(event.pos()))
                return True
            elif event.type() == QEvent.Type.MouseMove and self._drawing:
                self._on_move(self._view.mapToScene(event.pos()))
                return True
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self._on_release(self._view.mapToScene(event.pos()))
                return True
        return super().eventFilter(obj, event)

    def _on_press(self, pos):
        self._drawing = True
        self._start_pos = pos
        pen = self._make_pen()

        if self._current_tool == Tool.ARROW:
            self._current_item = ArrowItem(QLineF(pos, pos), pen)
            self._scene.addItem(self._current_item)

        elif self._current_tool == Tool.RECTANGLE:
            self._current_item = QGraphicsRectItem(pos.x(), pos.y(), 0, 0)
            self._current_item.setPen(pen)
            self._current_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            self._scene.addItem(self._current_item)

        elif self._current_tool == Tool.ELLIPSE:
            self._current_item = QGraphicsEllipseItem(pos.x(), pos.y(), 0, 0)
            self._current_item.setPen(pen)
            self._current_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            self._scene.addItem(self._current_item)

        elif self._current_tool == Tool.LINE:
            self._current_item = QGraphicsLineItem(QLineF(pos, pos))
            self._current_item.setPen(pen)
            self._scene.addItem(self._current_item)

        elif self._current_tool == Tool.FREEHAND:
            path = QPainterPath()
            path.moveTo(pos)
            self._current_item = QGraphicsPathItem(path)
            self._current_item.setPen(pen)
            self._path_points = [pos]
            self._scene.addItem(self._current_item)

        elif self._current_tool == Tool.TEXT:
            self._drawing = False
            text, ok = QInputDialog.getText(self, "Add Text", "Enter text:")
            if ok and text:
                item = QGraphicsTextItem(text)
                item.setPos(pos)
                item.setDefaultTextColor(self._pen_color)
                item.setFont(QFont("Segoe UI", self._pen_width * 4))
                self._scene.addItem(item)
                self._undo_stack.append(item)
                self._redo_stack.clear()
                self._has_annotations = True

        elif self._current_tool == Tool.BLUR:
            self._current_item = QGraphicsRectItem(pos.x(), pos.y(), 0, 0)
            self._current_item.setPen(QPen(QColor(100, 100, 255, 150), 2, Qt.PenStyle.DashLine))
            self._current_item.setBrush(QBrush(QColor(100, 100, 255, 30)))
            self._scene.addItem(self._current_item)

        elif self._current_tool == Tool.HIGHLIGHT:
            self._current_item = QGraphicsRectItem(pos.x(), pos.y(), 0, 0)
            highlight_color = QColor(self._pen_color)
            highlight_color.setAlpha(60)
            self._current_item.setPen(QPen(Qt.PenStyle.NoPen))
            self._current_item.setBrush(QBrush(highlight_color))
            self._scene.addItem(self._current_item)

        elif self._current_tool == Tool.STEP_NUMBER:
            self._drawing = False
            item = StepNumberItem(pos, self._step_counter, 32, self._pen_color)
            self._scene.addItem(item)
            self._undo_stack.append(item)
            self._redo_stack.clear()
            self._step_counter += 1
            self._has_annotations = True

    def _on_move(self, pos):
        if not self._current_item:
            return

        if self._current_tool == Tool.ARROW:
            self._current_item.setLine(QLineF(self._start_pos, pos))
        elif self._current_tool == Tool.LINE:
            self._current_item.setLine(QLineF(self._start_pos, pos))
        elif self._current_tool in (Tool.RECTANGLE, Tool.BLUR, Tool.HIGHLIGHT, Tool.ELLIPSE):
            x1, y1 = self._start_pos.x(), self._start_pos.y()
            x2, y2 = pos.x(), pos.y()
            self._current_item.setRect(QRectF(
                min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)
            ))
        elif self._current_tool == Tool.FREEHAND:
            self._path_points.append(pos)
            path = QPainterPath()
            path.moveTo(self._path_points[0])
            for pt in self._path_points[1:]:
                path.lineTo(pt)
            self._current_item.setPath(path)

    def _on_release(self, pos):
        if not self._drawing:
            return
        self._drawing = False

        if self._current_tool == Tool.BLUR and self._current_item:
            rect = self._current_item.rect().toRect()
            self._scene.removeItem(self._current_item)

            if rect.width() > 2 and rect.height() > 2:
                source = self._bg_pixmap.copy(rect)
                qimg = source.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
                ba = qimg.bits()
                ba.setsize(qimg.sizeInBytes())
                pil_region = Image.frombytes(
                    "RGBA", (qimg.width(), qimg.height()), bytes(ba)
                )
                blurred = pil_region.filter(ImageFilter.GaussianBlur(radius=12))

                buf = io.BytesIO()
                blurred.save(buf, format="PNG")
                buf.seek(0)
                blur_pm = QPixmap()
                blur_pm.loadFromData(buf.read())

                blur_item = QGraphicsPixmapItem(blur_pm)
                blur_item.setPos(rect.x(), rect.y())
                self._scene.addItem(blur_item)
                self._current_item = blur_item
            else:
                self._current_item = None

        if self._current_item:
            self._undo_stack.append(self._current_item)
            self._redo_stack.clear()
            self._has_annotations = True
        self._current_item = None

    def _undo(self):
        if self._undo_stack:
            item = self._undo_stack.pop()
            self._scene.removeItem(item)
            self._redo_stack.append(item)
            if not self._undo_stack:
                self._has_annotations = False

    def _redo(self):
        if self._redo_stack:
            item = self._redo_stack.pop()
            self._scene.addItem(item)
            self._undo_stack.append(item)
            self._has_annotations = True

    def _render_final(self):
        rect = self._scene.sceneRect()
        pixmap = QPixmap(int(rect.width()), int(rect.height()))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._scene.render(painter)
        painter.end()
        return pixmap

    def _save(self):
        filters = {
            "png": "PNG Images (*.png)",
            "jpg": "JPEG Images (*.jpg *.jpeg)",
            "bmp": "BMP Images (*.bmp)",
            "webp": "WebP Images (*.webp)",
        }
        all_filters = ";;".join(filters.values())
        default_name = self.config.generate_filename()
        folder = self.config.get("default_folder")

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Annotated Screenshot",
            f"{folder}/{default_name}", all_filters,
        )
        if path:
            pixmap = self._render_final()
            pil_img = ScreenCapture.qpixmap_to_pil(pixmap)
            ScreenCapture.save_image(pil_img, path, self.config)
            self._saved = True

    def _save_copy_path(self):
        path = self.config.get_default_save_path()
        pixmap = self._render_final()
        pil_img = ScreenCapture.qpixmap_to_pil(pixmap)
        ScreenCapture.save_image(pil_img, path, self.config)
        QApplication.clipboard().setText(path)
        self._saved = True
        self.statusBar().showMessage(f"Saved & path copied: {path}", 4000)

    def _copy_to_clipboard(self):
        pixmap = self._render_final()
        QApplication.clipboard().setPixmap(pixmap)
