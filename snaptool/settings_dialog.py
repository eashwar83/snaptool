"""Settings configuration dialog."""

import os
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QSlider, QCheckBox,
    QSpinBox, QGroupBox, QFileDialog, QColorDialog, QTabWidget,
    QWidget, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from .config import Config


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = Config.instance()
        self.setWindowTitle("SnapTool - Settings")
        self.setMinimumWidth(500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self._build_ui()
        self._load_values()
        self._apply_style()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_capture_tab(), "Capture")
        tabs.addTab(self._build_effects_tab(), "Effects")
        tabs.addTab(self._build_hotkeys_tab(), "Hotkeys")
        tabs.addTab(self._build_system_tab(), "System")
        layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._save_and_close)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(btn_cancel)

        btn_apply = QPushButton("Apply")
        btn_apply.clicked.connect(self._save_values)
        btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(btn_apply)

        layout.addLayout(btn_layout)

    def _build_general_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setMinimumWidth(250)
        folder_row.addWidget(self._folder_edit)
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_folder)
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        folder_row.addWidget(btn_browse)
        layout.addRow("Default Folder:", folder_row)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["png", "jpg", "bmp", "webp"])
        layout.addRow("Image Format:", self._format_combo)

        quality_row = QHBoxLayout()
        self._quality_slider = QSlider(Qt.Orientation.Horizontal)
        self._quality_slider.setRange(10, 100)
        self._quality_slider.setTickInterval(10)
        self._quality_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._quality_label = QLabel("95")
        self._quality_slider.valueChanged.connect(
            lambda v: self._quality_label.setText(str(v))
        )
        quality_row.addWidget(self._quality_slider)
        quality_row.addWidget(self._quality_label)
        layout.addRow("JPG/WebP Quality:", quality_row)

        self._pattern_edit = QLineEdit()
        self._pattern_edit.setPlaceholderText("snap_{timestamp}")
        layout.addRow("Filename Pattern:", self._pattern_edit)

        hint = QLabel("Use {timestamp} for date/time. Example: snap_{timestamp}")
        hint.setStyleSheet("color: #888; font-size: 8pt;")
        layout.addRow("", hint)

        return widget

    def _build_capture_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        self._cursor_check = QCheckBox("Include mouse cursor in screenshots")
        layout.addWidget(self._cursor_check)

        self._auto_clip_check = QCheckBox("Auto-copy screenshot to clipboard after capture")
        layout.addWidget(self._auto_clip_check)

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Timed capture delay:"))
        self._delay_spin = QSpinBox()
        self._delay_spin.setRange(1, 30)
        self._delay_spin.setSuffix(" seconds")
        delay_row.addWidget(self._delay_spin)
        delay_row.addStretch()
        layout.addLayout(delay_row)

        layout.addStretch()
        return widget

    def _build_effects_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        self._border_check = QCheckBox("Add border to screenshots")
        layout.addWidget(self._border_check)

        border_opts = QHBoxLayout()
        border_opts.addWidget(QLabel("  Border color:"))
        self._border_color_btn = QPushButton()
        self._border_color_btn.setFixedSize(30, 24)
        self._border_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._border_color_btn.clicked.connect(self._pick_border_color)
        border_opts.addWidget(self._border_color_btn)

        border_opts.addWidget(QLabel("  Width:"))
        self._border_width_spin = QSpinBox()
        self._border_width_spin.setRange(1, 10)
        border_opts.addWidget(self._border_width_spin)
        border_opts.addStretch()
        layout.addLayout(border_opts)

        self._shadow_check = QCheckBox("Add drop shadow to screenshots")
        layout.addWidget(self._shadow_check)

        layout.addStretch()
        return widget

    def _build_hotkeys_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        self._hk_fullscreen = QLineEdit()
        layout.addRow("Full Screen:", self._hk_fullscreen)

        self._hk_region = QLineEdit()
        layout.addRow("Region Select:", self._hk_region)

        self._hk_window = QLineEdit()
        layout.addRow("Active Window:", self._hk_window)

        self._hk_delayed = QLineEdit()
        layout.addRow("Delayed Capture:", self._hk_delayed)

        hint = QLabel(
            "Format: ctrl+shift+s, alt+print screen, etc.\n"
            "Restart required for hotkey changes to take effect."
        )
        hint.setStyleSheet("color: #888; font-size: 8pt;")
        layout.addRow("", hint)

        return widget

    def _build_system_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        self._startup_check = QCheckBox("Start SnapTool with Windows")
        layout.addWidget(self._startup_check)

        self._notify_check = QCheckBox("Show notifications after save")
        layout.addWidget(self._notify_check)

        cleanup_row = QHBoxLayout()
        self._cleanup_check = QCheckBox("Auto-delete screenshots older than")
        cleanup_row.addWidget(self._cleanup_check)
        self._cleanup_days_spin = QSpinBox()
        self._cleanup_days_spin.setRange(1, 365)
        self._cleanup_days_spin.setSuffix(" days")
        cleanup_row.addWidget(self._cleanup_days_spin)
        cleanup_row.addStretch()
        layout.addLayout(cleanup_row)

        layout.addStretch()

        from . import __version__
        ver = QLabel(f"SnapTool v{__version__}")
        ver.setStyleSheet("color: #666; font-size: 8pt;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver)

        return widget

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog { background: #2b2b2b; color: #e0e0e0; }
            QTabWidget::pane { border: 1px solid #3a3a3a; background: #2b2b2b; }
            QTabBar::tab {
                background: #333; color: #aaa; padding: 8px 16px;
                border: 1px solid #3a3a3a; border-bottom: none;
                font-family: "Segoe UI"; font-size: 10pt;
            }
            QTabBar::tab:selected { background: #2b2b2b; color: #e0e0e0; }
            QTabBar::tab:hover { background: #3a3a3a; }
            QLabel { color: #ccc; font-family: "Segoe UI"; font-size: 10pt; }
            QLineEdit, QComboBox, QSpinBox {
                background: #333; color: #e0e0e0; border: 1px solid #505050;
                border-radius: 4px; padding: 5px 8px;
                font-family: "Segoe UI"; font-size: 10pt;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #0078d4; }
            QCheckBox { color: #ccc; font-family: "Segoe UI"; font-size: 10pt; spacing: 8px; }
            QCheckBox::indicator {
                width: 16px; height: 16px; border: 1px solid #555;
                border-radius: 3px; background: #333;
            }
            QCheckBox::indicator:checked { background: #0078d4; border-color: #0078d4; }
            QPushButton {
                background: #3a3a3a; color: #e0e0e0; border: 1px solid #505050;
                border-radius: 4px; padding: 6px 16px;
                font-family: "Segoe UI"; font-size: 10pt;
            }
            QPushButton:hover { background: #4a4a4a; border-color: #0078d4; }
            QPushButton:default { background: #0078d4; border-color: #0078d4; color: white; }
            QSlider::groove:horizontal {
                height: 6px; background: #444; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px; height: 16px; margin: -5px 0;
                background: #0078d4; border-radius: 8px;
            }
            QSlider::sub-page:horizontal { background: #0078d4; border-radius: 3px; }
        """)

    def _load_values(self):
        c = self.config
        self._folder_edit.setText(c.get("default_folder"))
        idx = self._format_combo.findText(c.get("image_format", "png"))
        if idx >= 0:
            self._format_combo.setCurrentIndex(idx)
        self._quality_slider.setValue(c.get("jpg_quality", 95))
        self._pattern_edit.setText(c.get("filename_pattern", "snap_{timestamp}"))
        self._cursor_check.setChecked(c.get("capture_cursor", False))
        self._auto_clip_check.setChecked(c.get("auto_copy_to_clipboard", False))
        self._delay_spin.setValue(c.get("delay_seconds", 3))
        self._border_check.setChecked(c.get("add_border", False))
        bc = c.get("border_color", "#333333")
        self._border_color_btn.setStyleSheet(
            f"background: {bc}; border: 1px solid #666; border-radius: 3px;"
        )
        self._border_color_btn.setProperty("color", bc)
        self._border_width_spin.setValue(c.get("border_width", 2))
        self._shadow_check.setChecked(c.get("add_shadow", False))
        hotkeys = c.get("hotkeys", {})
        self._hk_fullscreen.setText(hotkeys.get("fullscreen", ""))
        self._hk_region.setText(hotkeys.get("region", ""))
        self._hk_window.setText(hotkeys.get("window", ""))
        self._hk_delayed.setText(hotkeys.get("delayed", ""))
        self._startup_check.setChecked(c.get("startup_with_windows", False))
        self._notify_check.setChecked(c.get("show_notification", True))
        self._cleanup_check.setChecked(c.get("auto_cleanup_enabled", False))
        self._cleanup_days_spin.setValue(c.get("auto_cleanup_days", 30))

    def _save_values(self):
        c = self.config
        c.set("default_folder", self._folder_edit.text())
        c.set("image_format", self._format_combo.currentText())
        c.set("jpg_quality", self._quality_slider.value())
        c.set("filename_pattern", self._pattern_edit.text() or "snap_{timestamp}")
        c.set("capture_cursor", self._cursor_check.isChecked())
        c.set("auto_copy_to_clipboard", self._auto_clip_check.isChecked())
        c.set("delay_seconds", self._delay_spin.value())
        c.set("add_border", self._border_check.isChecked())
        c.set("border_color", self._border_color_btn.property("color") or "#333333")
        c.set("border_width", self._border_width_spin.value())
        c.set("add_shadow", self._shadow_check.isChecked())
        c.set("hotkeys", {
            "fullscreen": self._hk_fullscreen.text(),
            "region": self._hk_region.text(),
            "window": self._hk_window.text(),
            "delayed": self._hk_delayed.text(),
        })
        c.set("show_notification", self._notify_check.isChecked())
        c.set("auto_cleanup_enabled", self._cleanup_check.isChecked())
        c.set("auto_cleanup_days", self._cleanup_days_spin.value())

        startup = self._startup_check.isChecked()
        c.set("startup_with_windows", startup)
        self._set_startup(startup)

    def _save_and_close(self):
        self._save_values()
        self.accept()

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Default Folder", self._folder_edit.text(),
        )
        if folder:
            self._folder_edit.setText(folder)

    def _pick_border_color(self):
        current = QColor(self._border_color_btn.property("color") or "#333333")
        color = QColorDialog.getColor(current, self, "Border Color")
        if color.isValid():
            self._border_color_btn.setStyleSheet(
                f"background: {color.name()}; border: 1px solid #666; border-radius: 3px;"
            )
            self._border_color_btn.setProperty("color", color.name())

    def _set_startup(self, enable):
        if sys.platform != "win32":
            return
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            if enable:
                if getattr(sys, "frozen", False):
                    # Running as PyInstaller exe
                    cmd = f'"{sys.executable}"'
                else:
                    # Running as script - launch via python
                    script = os.path.abspath(
                        os.path.join(os.path.dirname(__file__), "..", "main.py")
                    )
                    cmd = f'"{sys.executable}" "{script}"'
                winreg.SetValueEx(key, "SnapTool", 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, "SnapTool")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass
