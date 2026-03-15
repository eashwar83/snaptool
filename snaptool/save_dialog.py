"""Post-capture dialog with save/action options."""

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QSizePolicy, QFrame, QApplication, QToolTip,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont, QIcon

from .config import Config
from .capture import ScreenCapture


class SaveDialog(QDialog):
    """Shows capture preview and save/action options."""

    edit_requested = pyqtSignal(object)    # PIL Image
    pin_requested = pyqtSignal(object)     # PIL Image

    def __init__(self, pil_image, parent=None):
        super().__init__(parent)
        self.pil_image = pil_image
        self.config = Config.instance()
        self.saved_path = None

        self.setWindowTitle("SnapTool - Screenshot Captured")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumWidth(420)
        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Preview
        preview_label = QLabel()
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setMinimumHeight(200)
        preview_label.setMaximumHeight(350)
        pixmap = ScreenCapture.pil_to_qpixmap(self.pil_image)
        scaled = pixmap.scaled(
            400, 300,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        preview_label.setPixmap(scaled)
        preview_label.setStyleSheet(
            "background: #1e1e1e; border: 1px solid #3a3a3a; border-radius: 6px; padding: 8px;"
        )
        layout.addWidget(preview_label)

        # Info
        w, h = self.pil_image.size
        fmt = self.config.get("image_format", "png").upper()
        info = QLabel(f"{w} x {h} px  |  Format: {fmt}")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setFont(QFont("Segoe UI", 9))
        info.setStyleSheet("color: #999;")
        layout.addWidget(info)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3a3a3a;")
        layout.addWidget(sep)

        # Action buttons - row 1
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        btn_quick = self._make_button(
            "Quick Save", "Save to default folder",
            self._on_quick_save, primary=True,
        )
        btn_saveas = self._make_button(
            "Save As...", "Choose save location",
            self._on_save_as,
        )
        row1.addWidget(btn_quick)
        row1.addWidget(btn_saveas)
        layout.addLayout(row1)

        # Row 2
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        btn_clip = self._make_button(
            "Copy to Clipboard", "Copy image to clipboard",
            self._on_clipboard,
        )
        btn_save_path = self._make_button(
            "Save + Copy Path", "Save and copy file path",
            self._on_save_copy_path,
        )
        row2.addWidget(btn_clip)
        row2.addWidget(btn_save_path)
        layout.addLayout(row2)

        # Row 3 (extras)
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        btn_edit = self._make_button(
            "Edit / Annotate", "Open annotation editor",
            self._on_edit,
        )
        btn_pin = self._make_button(
            "Pin on Screen", "Float as always-on-top window",
            self._on_pin,
        )
        btn_base64 = self._make_button(
            "Copy as Base64", "Copy base64 encoded image",
            self._on_copy_base64,
        )
        row3.addWidget(btn_edit)
        row3.addWidget(btn_pin)
        row3.addWidget(btn_base64)
        layout.addLayout(row3)

        # Discard
        btn_discard = QPushButton("Discard")
        btn_discard.setFont(QFont("Segoe UI", 9))
        btn_discard.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_discard.setStyleSheet(
            "QPushButton { color: #cc4444; background: transparent; border: none; padding: 6px; }"
            "QPushButton:hover { color: #ff5555; text-decoration: underline; }"
        )
        btn_discard.clicked.connect(self.reject)
        layout.addWidget(btn_discard, alignment=Qt.AlignmentFlag.AlignCenter)

    def _make_button(self, text, tooltip, callback, primary=False):
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFont(QFont("Segoe UI", 10))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(38)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.clicked.connect(callback)
        if primary:
            btn.setObjectName("primary")
        return btn

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #2b2b2b;
                color: #e0e0e0;
            }
            QPushButton {
                background: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #505050;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #4a4a4a;
                border-color: #0078d4;
            }
            QPushButton:pressed {
                background: #555555;
            }
            QPushButton#primary {
                background: #0078d4;
                border-color: #0078d4;
                color: white;
                font-weight: bold;
            }
            QPushButton#primary:hover {
                background: #1a8ae8;
            }
        """)

    def _save_to(self, path):
        img = ScreenCapture.apply_effects(self.pil_image, self.config)
        ScreenCapture.save_image(img, path, self.config)
        self.saved_path = path
        return path

    def _on_quick_save(self):
        path = self.config.get_default_save_path()
        self._save_to(path)
        self._show_status(f"Saved to {path}")
        self.accept()

    def _on_save_as(self):
        fmt = self.config.get("image_format", "png")
        filters = {
            "png": "PNG Images (*.png)",
            "jpg": "JPEG Images (*.jpg *.jpeg)",
            "bmp": "BMP Images (*.bmp)",
            "webp": "WebP Images (*.webp)",
        }
        file_filter = filters.get(fmt, "All Images (*.png *.jpg *.bmp *.webp)")
        all_filters = ";;".join(filters.values())

        last_dir = self.config.get("last_save_dir") or str(Path.home() / "Pictures")
        default_name = self.config.generate_filename()

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Screenshot", os.path.join(last_dir, default_name),
            all_filters, file_filter,
        )
        if path:
            self.config.set("last_save_dir", str(Path(path).parent))
            self._save_to(path)
            self._show_status(f"Saved to {path}")
            self.accept()

    def _on_clipboard(self):
        pixmap = ScreenCapture.pil_to_qpixmap(self.pil_image)
        QApplication.clipboard().setPixmap(pixmap)
        self._show_status("Copied to clipboard")
        self.accept()

    def _on_save_copy_path(self):
        path = self.config.get_default_save_path()
        self._save_to(path)
        QApplication.clipboard().setText(path)
        self._show_status(f"Saved & path copied: {path}")
        self.accept()

    def _on_edit(self):
        self.edit_requested.emit(self.pil_image)
        self.accept()

    def _on_pin(self):
        self.pin_requested.emit(self.pil_image)
        self.accept()

    def _on_copy_base64(self):
        import base64
        import io
        buf = io.BytesIO()
        fmt = self.config.get("image_format", "png")
        self.pil_image.save(buf, format=fmt.upper() if fmt != "jpg" else "JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        mime = f"image/{fmt}" if fmt != "jpg" else "image/jpeg"
        data_uri = f"data:{mime};base64,{b64}"
        QApplication.clipboard().setText(data_uri)
        self._show_status("Base64 copied to clipboard")
        self.accept()

    def _show_status(self, msg):
        if self.config.get("show_notification"):
            QToolTip.showText(
                self.mapToGlobal(self.rect().center()), msg, self, self.rect(), 2000,
            )
