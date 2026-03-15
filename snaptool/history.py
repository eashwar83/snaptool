"""Screenshot history viewer."""

import os
from pathlib import Path
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QGridLayout, QSizePolicy, QApplication,
    QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QFont, QIcon

from .config import Config


class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = Config.instance()
        self.setWindowTitle("SnapTool - Screenshot History")
        self.setMinimumSize(700, 500)
        self._build_ui()
        self._apply_style()
        self._load_images()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Screenshot History")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        btn_folder = QPushButton("Open Folder")
        btn_folder.clicked.connect(self._open_folder)
        btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(btn_folder)

        btn_cleanup = QPushButton("Cleanup Old")
        btn_cleanup.clicked.connect(self._cleanup)
        btn_cleanup.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(btn_cleanup)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._load_images)
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(btn_refresh)

        layout.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3a3a3a;")
        layout.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(10)
        scroll.setWidget(self._grid_widget)
        layout.addWidget(scroll)

        self._status = QLabel("")
        self._status.setFont(QFont("Segoe UI", 9))
        self._status.setStyleSheet("color: #888;")
        layout.addWidget(self._status)

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog { background: #2b2b2b; color: #e0e0e0; }
            QPushButton {
                background: #3a3a3a; color: #e0e0e0;
                border: 1px solid #505050; border-radius: 4px;
                padding: 6px 14px; font-family: "Segoe UI"; font-size: 10pt;
            }
            QPushButton:hover { background: #4a4a4a; border-color: #0078d4; }
            QScrollArea { border: none; background: transparent; }
        """)

    def _load_images(self):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        folder = self.config.get("default_folder")
        if not os.path.isdir(folder):
            self._status.setText("No screenshots found.")
            return

        exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
        files = []
        for f in os.listdir(folder):
            if any(f.lower().endswith(e) for e in exts):
                full = os.path.join(folder, f)
                files.append((os.path.getmtime(full), full, f))

        files.sort(reverse=True)
        files = files[:100]

        cols = 4
        for i, (mtime, full_path, name) in enumerate(files):
            card = self._make_card(full_path, name, mtime)
            row, col = divmod(i, cols)
            self._grid_layout.addWidget(card, row, col)

        self._status.setText(f"{len(files)} screenshot(s) found")

    def _make_card(self, path, name, mtime):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #333; border: 1px solid #444; border-radius: 6px;
            }
            QFrame:hover { border-color: #0078d4; }
        """)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(card)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 6, 6, 6)

        thumb = QLabel()
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setFixedSize(150, 110)
        pm = QPixmap(path)
        if not pm.isNull():
            scaled = pm.scaled(
                140, 100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            thumb.setPixmap(scaled)
        else:
            thumb.setText("?")
        layout.addWidget(thumb)

        fn_label = QLabel(name)
        fn_label.setFont(QFont("Segoe UI", 8))
        fn_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fn_label.setStyleSheet("color: #aaa; border: none;")
        fn_label.setWordWrap(True)
        layout.addWidget(fn_label)

        dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        date_label = QLabel(dt)
        date_label.setFont(QFont("Segoe UI", 7))
        date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_label.setStyleSheet("color: #666; border: none;")
        layout.addWidget(date_label)

        actions = QHBoxLayout()
        actions.setSpacing(4)

        btn_copy = QPushButton("Copy")
        btn_copy.setFixedHeight(24)
        btn_copy.setFont(QFont("Segoe UI", 8))
        btn_copy.clicked.connect(lambda _, p=path: self._copy_image(p))
        actions.addWidget(btn_copy)

        btn_path = QPushButton("Path")
        btn_path.setFixedHeight(24)
        btn_path.setFont(QFont("Segoe UI", 8))
        btn_path.clicked.connect(lambda _, p=path: self._copy_path(p))
        actions.addWidget(btn_path)

        btn_del = QPushButton("Del")
        btn_del.setFixedHeight(24)
        btn_del.setFont(QFont("Segoe UI", 8))
        btn_del.setStyleSheet(
            "QPushButton { color: #cc4444; } QPushButton:hover { color: #ff5555; }"
        )
        btn_del.clicked.connect(lambda _, p=path: self._delete_image(p))
        actions.addWidget(btn_del)

        layout.addLayout(actions)
        return card

    def _copy_image(self, path):
        pm = QPixmap(path)
        if not pm.isNull():
            QApplication.clipboard().setPixmap(pm)

    def _copy_path(self, path):
        QApplication.clipboard().setText(os.path.abspath(path))

    def _delete_image(self, path):
        reply = QMessageBox.question(
            self, "Delete Screenshot",
            f"Delete {os.path.basename(path)}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(path)
                self._load_images()
            except OSError:
                pass

    def _open_folder(self):
        folder = self.config.get("default_folder")
        if os.path.isdir(folder):
            if os.name == "nt":
                os.startfile(folder)
            else:
                os.system(f'xdg-open "{folder}"')

    def _cleanup(self):
        days = self.config.get("auto_cleanup_days", 30)
        folder = self.config.get("default_folder")
        if not os.path.isdir(folder):
            return

        cutoff = datetime.now() - timedelta(days=days)
        exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
        removed = 0

        for f in os.listdir(folder):
            if any(f.lower().endswith(e) for e in exts):
                full = os.path.join(folder, f)
                if datetime.fromtimestamp(os.path.getmtime(full)) < cutoff:
                    try:
                        os.remove(full)
                        removed += 1
                    except OSError:
                        pass

        QMessageBox.information(
            self, "Cleanup",
            f"Removed {removed} screenshot(s) older than {days} days.",
        )
        self._load_images()
