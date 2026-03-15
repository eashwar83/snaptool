"""Annotation editor with drawing tools."""

import io
import math
from enum import Enum, auto

from PIL import Image, ImageFilter

from PyQt6.QtWidgets import (
    QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsLineItem,
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPathItem,
    QGraphicsTextItem, QGraphicsPixmapItem, QToolBar,
    QColorDialog, QSpinBox, QLabel, QHBoxLayout,
    QWidget, QSizePolicy, QApplication, QInputDialog, QToolButton,
    QMenu, QFileDialog,
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QLineF, QEvent
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPixmap, QFont, QPainterPath,
    QPolygonF, QImage, QIcon, QTransform, QAction, QActionGroup,
)

from .config import Config
from .capture import ScreenCapture


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
        self._current_tool = Tool.ARROW
        self._pen_color = QColor(255, 50, 50)
        self._pen_width = 3
        self._drawing = False
        self._current_item = None
        self._start_pos = None
        self._path_points = []
        self._undo_stack = []
        self._redo_stack = []
        self._step_counter = 1

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
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        tool_group = QActionGroup(self)
        tools = [
            ("Arrow", Tool.ARROW),
            ("Rect", Tool.RECTANGLE),
            ("Ellipse", Tool.ELLIPSE),
            ("Line", Tool.LINE),
            ("Pen", Tool.FREEHAND),
            ("Text", Tool.TEXT),
            ("Blur", Tool.BLUR),
            ("Highlight", Tool.HIGHLIGHT),
            ("Step #", Tool.STEP_NUMBER),
        ]
        for name, tool in tools:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setData(tool)
            action.triggered.connect(lambda checked, t=tool: self._set_tool(t))
            tool_group.addAction(action)
            toolbar.addAction(action)
            if tool == Tool.ARROW:
                action.setChecked(True)

        toolbar.addSeparator()

        # Color button
        self._color_btn = QToolButton()
        self._color_btn.setText("Color")
        self._color_btn.setStyleSheet(
            f"background: {self._pen_color.name()}; min-width: 30px; min-height: 20px; border-radius: 3px;"
        )
        self._color_btn.clicked.connect(self._pick_color)
        toolbar.addWidget(self._color_btn)

        # Width spinner
        toolbar.addWidget(QLabel("  Width: "))
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 20)
        self._width_spin.setValue(self._pen_width)
        self._width_spin.valueChanged.connect(self._set_width)
        toolbar.addWidget(self._width_spin)

        toolbar.addSeparator()

        undo_action = QAction("Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self._undo)
        toolbar.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self._redo)
        toolbar.addAction(redo_action)

        toolbar.addSeparator()

        zoom_in = QAction("Zoom +", self)
        zoom_in.setShortcut("Ctrl+=")
        zoom_in.triggered.connect(lambda: self._view.scale(1.2, 1.2))
        toolbar.addAction(zoom_in)

        zoom_out = QAction("Zoom -", self)
        zoom_out.setShortcut("Ctrl+-")
        zoom_out.triggered.connect(lambda: self._view.scale(1 / 1.2, 1 / 1.2))
        toolbar.addAction(zoom_out)

        zoom_fit = QAction("Fit", self)
        zoom_fit.setShortcut("Ctrl+0")
        zoom_fit.triggered.connect(self._fit_view)
        toolbar.addAction(zoom_fit)

        toolbar.addSeparator()

        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save)
        toolbar.addAction(save_action)

        copy_action = QAction("Copy", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self._copy_to_clipboard)
        toolbar.addAction(copy_action)

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background: #1e1e1e; }
            QToolBar {
                background: #2b2b2b; border-bottom: 1px solid #3a3a3a;
                spacing: 4px; padding: 4px;
            }
            QToolBar QToolButton, QToolBar QPushButton {
                background: #3a3a3a; color: #e0e0e0;
                border: 1px solid #505050; border-radius: 4px;
                padding: 4px 10px; font-family: "Segoe UI"; font-size: 9pt;
            }
            QToolBar QToolButton:checked {
                background: #0078d4; border-color: #0078d4; color: white;
            }
            QToolBar QToolButton:hover { background: #4a4a4a; }
            QLabel { color: #ccc; font-family: "Segoe UI"; }
            QSpinBox {
                background: #333; color: #e0e0e0; border: 1px solid #505050;
                border-radius: 3px; padding: 2px 6px;
            }
            QGraphicsView { background: #1a1a1a; border: none; }
        """)

    def showEvent(self, event):
        super().showEvent(event)
        self._fit_view()

    def _fit_view(self):
        self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _set_tool(self, tool):
        self._current_tool = tool

    def _pick_color(self):
        color = QColorDialog.getColor(self._pen_color, self, "Pick Color")
        if color.isValid():
            self._pen_color = color
            self._color_btn.setStyleSheet(
                f"background: {color.name()}; min-width: 30px; min-height: 20px; border-radius: 3px;"
            )

    def _set_width(self, w):
        self._pen_width = w

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
            self._current_item = QGraphicsRectItem(QRectF(pos, pos))
            self._current_item.setPen(pen)
            self._current_item.setBrush(Qt.BrushStyle.NoBrush)
            self._scene.addItem(self._current_item)

        elif self._current_tool == Tool.ELLIPSE:
            self._current_item = QGraphicsEllipseItem(QRectF(pos, pos))
            self._current_item.setPen(pen)
            self._current_item.setBrush(Qt.BrushStyle.NoBrush)
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

        elif self._current_tool == Tool.BLUR:
            self._current_item = QGraphicsRectItem(QRectF(pos, pos))
            self._current_item.setPen(QPen(QColor(100, 100, 255, 150), 2, Qt.PenStyle.DashLine))
            self._current_item.setBrush(QBrush(QColor(100, 100, 255, 30)))
            self._scene.addItem(self._current_item)

        elif self._current_tool == Tool.HIGHLIGHT:
            self._current_item = QGraphicsRectItem(QRectF(pos, pos))
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

    def _on_move(self, pos):
        if not self._current_item:
            return

        if self._current_tool == Tool.ARROW:
            self._current_item.setLine(QLineF(self._start_pos, pos))
        elif self._current_tool == Tool.LINE:
            self._current_item.setLine(QLineF(self._start_pos, pos))
        elif self._current_tool in (Tool.RECTANGLE, Tool.BLUR, Tool.HIGHLIGHT):
            self._current_item.setRect(QRectF(self._start_pos, pos).normalized())
        elif self._current_tool == Tool.ELLIPSE:
            self._current_item.setRect(QRectF(self._start_pos, pos).normalized())
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
        self._current_item = None

    def _undo(self):
        if self._undo_stack:
            item = self._undo_stack.pop()
            self._scene.removeItem(item)
            self._redo_stack.append(item)

    def _redo(self):
        if self._redo_stack:
            item = self._redo_stack.pop()
            self._scene.addItem(item)
            self._undo_stack.append(item)

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

    def _copy_to_clipboard(self):
        pixmap = self._render_final()
        QApplication.clipboard().setPixmap(pixmap)
