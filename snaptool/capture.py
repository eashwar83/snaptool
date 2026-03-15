"""Screen capture engine and region selection overlay."""

import io
import sys

import mss
import mss.tools
from PIL import Image, ImageFilter

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QPixmap, QImage, QCursor, QFont, QBrush,
)


class ScreenCapture:
    """Handles all screen capture operations."""

    @staticmethod
    def full_screen():
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])
            return Image.frombytes("RGB", shot.size, shot.rgb)

    @staticmethod
    def monitor(index=1):
        with mss.mss() as sct:
            if index < len(sct.monitors):
                shot = sct.grab(sct.monitors[index])
                return Image.frombytes("RGB", shot.size, shot.rgb)
        return ScreenCapture.full_screen()

    @staticmethod
    def region(x, y, w, h):
        with mss.mss() as sct:
            area = {"left": x, "top": y, "width": w, "height": h}
            shot = sct.grab(area)
            return Image.frombytes("RGB", shot.size, shot.rgb)

    @staticmethod
    def active_window():
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                rect = wintypes.RECT()

                try:
                    dwmapi = ctypes.windll.dwmapi
                    dwmapi.DwmGetWindowAttribute(
                        hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)
                    )
                except Exception:
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))

                x, y = rect.left, rect.top
                w = rect.right - rect.left
                h = rect.bottom - rect.top

                if w > 0 and h > 0:
                    return ScreenCapture.region(x, y, w, h)
            except Exception:
                pass
        return ScreenCapture.full_screen()

    @staticmethod
    def pil_to_qpixmap(pil_image):
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        buf.seek(0)
        pm = QPixmap()
        pm.loadFromData(buf.read())
        return pm

    @staticmethod
    def qpixmap_to_pil(qpixmap):
        qimg = qpixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        bits = qimg.bits()
        bits.setsize(qimg.sizeInBytes())
        img = Image.frombytes(
            "RGBA", (qimg.width(), qimg.height()), bytes(bits), "raw", "RGBA"
        )
        return img.convert("RGB")

    @staticmethod
    def apply_effects(pil_image, config):
        img = pil_image

        if config.get("add_border"):
            bw = config.get("border_width", 2)
            bc = config.get("border_color", "#333333")
            bordered = Image.new("RGB", (img.width + 2 * bw, img.height + 2 * bw), bc)
            bordered.paste(img, (bw, bw))
            img = bordered

        if config.get("add_shadow"):
            pad = 12
            new_w, new_h = img.width + pad * 2, img.height + pad * 2
            shadow = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
            shadow_rect = Image.new("RGBA", (img.width, img.height), (0, 0, 0, 80))
            shadow.paste(shadow_rect, (pad + 4, pad + 4))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=pad))
            result = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
            result = Image.alpha_composite(result, shadow)
            result.paste(img.convert("RGBA"), (pad - 2, pad - 2))
            img = result.convert("RGB")

        return img

    @staticmethod
    def save_image(pil_image, path, config):
        fmt = config.get("image_format", "png").upper()
        save_kwargs = {}
        if fmt in ("JPG", "JPEG"):
            fmt = "JPEG"
            save_kwargs["quality"] = config.get("jpg_quality", 95)
        elif fmt == "WEBP":
            save_kwargs["quality"] = config.get("jpg_quality", 95)

        pil_image.save(path, format=fmt if fmt != "JPG" else "JPEG", **save_kwargs)


class RegionSelector(QWidget):
    """Fullscreen overlay for selecting a screen region."""

    region_selected = pyqtSignal(object)  # PIL Image
    selection_cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(False)

        self._start = None
        self._end = None
        self._selecting = False
        self._background = None
        self._bg_pil = None
        self._dark_bg = None
        self._dpr = 1.0

    def start_selection(self):
        # Ensure widget is hidden before capturing
        self.hide()
        QApplication.processEvents()

        screen = QApplication.primaryScreen()
        self._dpr = screen.devicePixelRatio()

        # Capture clean screen with mss BEFORE showing overlay
        self._bg_pil = ScreenCapture.full_screen()
        self._background = ScreenCapture.pil_to_qpixmap(self._bg_pil)
        # Set DPR so Qt scales it correctly for display (no zoom)
        self._background.setDevicePixelRatio(self._dpr)

        # Pre-render darkened version
        self._dark_bg = self._background.copy()
        self._dark_bg.setDevicePixelRatio(self._dpr)
        p = QPainter(self._dark_bg)
        p.fillRect(self._dark_bg.rect(), QColor(0, 0, 0, 100))
        p.end()

        geom = screen.virtualGeometry()
        self.setGeometry(geom)
        self._start = None
        self._end = None
        self._selecting = False
        self.showFullScreen()
        self.activateWindow()
        self.setFocus()

    def paintEvent(self, event):
        if not self._background:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw darkened background (Qt handles DPI scaling automatically)
        painter.drawPixmap(0, 0, self._dark_bg)

        cursor_pos = self.mapFromGlobal(QCursor.pos())

        if self._start and self._end:
            rect = self._get_selection_rect()

            # Draw selected region at full brightness
            # Source rect must be in physical pixels (pixmap's native coords)
            src_rect = QRect(
                int(rect.x() * self._dpr), int(rect.y() * self._dpr),
                int(rect.width() * self._dpr), int(rect.height() * self._dpr),
            )
            painter.drawPixmap(rect, self._background, src_rect)

            # Selection border
            painter.setPen(QPen(QColor(0, 174, 255), 2, Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            # Corner handles
            handle = 4
            painter.setBrush(QColor(0, 174, 255))
            painter.setPen(Qt.PenStyle.NoPen)
            for c in [rect.topLeft(), rect.topRight(),
                       rect.bottomLeft(), rect.bottomRight()]:
                painter.drawRect(c.x() - handle, c.y() - handle, handle * 2, handle * 2)

            # Dimension label (show physical pixel dimensions)
            pw = int(rect.width() * self._dpr)
            ph = int(rect.height() * self._dpr)
            label = f"{pw} x {ph}"
            font = QFont("Segoe UI", 10, QFont.Weight.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(label) + 16
            th = fm.height() + 8
            lx = rect.x()
            ly = rect.y() - th - 4
            if ly < 0:
                ly = rect.bottom() + 4
            bg_rect = QRect(lx, ly, tw, th)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 174, 255))
            painter.drawRoundedRect(bg_rect, 3, 3)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, label)

        # Crosshair lines - only while dragging
        if self._selecting:
            painter.setPen(QPen(QColor(0, 174, 255, 100), 1, Qt.PenStyle.DashLine))
            painter.drawLine(cursor_pos.x(), 0, cursor_pos.x(), self.height())
            painter.drawLine(0, cursor_pos.y(), self.width(), cursor_pos.y())

        # Instructions
        if not self._selecting and not self._start:
            painter.setFont(QFont("Segoe UI", 14))
            painter.setPen(QColor(255, 255, 255, 200))
            hint = "Click and drag to select a region  |  ESC to cancel"
            fm = painter.fontMetrics()
            tx = (self.width() - fm.horizontalAdvance(hint)) // 2
            ty = self.height() // 2
            painter.drawText(tx, ty, hint)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.pos()
            self._end = event.pos()
            self._selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        self._end = event.pos()
        if self._selecting:
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._selecting:
            self._end = event.pos()
            self._selecting = False
            rect = self._get_selection_rect()

            if rect.width() > 5 and rect.height() > 5:
                self.hide()
                # Crop from the ORIGINAL PIL image (guaranteed clean, no overlay)
                dpr = self._dpr
                x = int(rect.x() * dpr)
                y = int(rect.y() * dpr)
                w = int(rect.width() * dpr)
                h = int(rect.height() * dpr)
                pil_image = self._bg_pil.crop((x, y, x + w, y + h))
                self.region_selected.emit(pil_image)
            else:
                self.hide()
                self.selection_cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.selection_cancelled.emit()

    def _get_selection_rect(self):
        if self._start and self._end:
            x1 = min(self._start.x(), self._end.x())
            y1 = min(self._start.y(), self._end.y())
            x2 = max(self._start.x(), self._end.x())
            y2 = max(self._start.y(), self._end.y())
            return QRect(x1, y1, x2 - x1, y2 - y1)
        return QRect()
