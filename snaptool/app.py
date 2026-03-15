"""Main application - system tray, hotkeys, and coordination."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtWidgets import (
    QSystemTrayIcon, QMenu, QApplication, QWidget,
    QLabel, QVBoxLayout, QSizePolicy, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QIcon, QCursor, QAction,
)

from .config import Config
from .capture import ScreenCapture, RegionSelector
from .save_dialog import SaveDialog
from .editor import AnnotationEditor
from .settings_dialog import SettingsDialog
from .history import HistoryDialog


class HotkeySignals(QObject):
    """Thread-safe signal bridge for global hotkeys."""
    fullscreen = pyqtSignal()
    region = pyqtSignal()
    window = pyqtSignal()
    delayed = pyqtSignal()


class PinWindow(QWidget):
    """Floating always-on-top screenshot window."""

    def __init__(self, pil_image, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        pixmap = ScreenCapture.pil_to_qpixmap(pil_image)
        max_w, max_h = 500, 400
        if pixmap.width() > max_w or pixmap.height() > max_h:
            pixmap = pixmap.scaled(
                max_w, max_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._pixmap = pixmap

        self._label = QLabel(self)
        self._label.setPixmap(pixmap)
        self._label.adjustSize()
        self.resize(pixmap.size())
        self._drag_pos = None

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

    def _show_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #2b2b2b; color: #e0e0e0; border: 1px solid #3a3a3a; }
            QMenu::item:selected { background: #0078d4; }
        """)
        close_action = menu.addAction("Close Pin")
        close_action.triggered.connect(self.close)
        copy_action = menu.addAction("Copy Image")
        copy_action.triggered.connect(
            lambda: QApplication.clipboard().setPixmap(self._pixmap)
        )
        menu.exec(self.mapToGlobal(pos))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class SnapToolApp(QObject):
    """Main application controller."""

    def __init__(self):
        super().__init__()
        self.config = Config.instance()
        self._region_selector = RegionSelector()
        self._region_selector.region_selected.connect(self._on_capture)
        self._region_selector.selection_cancelled.connect(self._on_cancel)
        self._hotkey_signals = HotkeySignals()
        self._pin_windows = []
        self._editors = []
        self._tray = None
        self._countdown_timer = None
        self._countdown_remaining = 0
        self._countdown_window = None

    def start(self):
        self._setup_tray()
        self._setup_hotkeys()
        self._auto_cleanup()
        self._show_welcome()

    def _create_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setBrush(QColor(0, 122, 204))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(4, 14, 56, 42, 8, 8)
        p.drawRoundedRect(20, 6, 20, 12, 4, 4)

        p.setBrush(QColor(240, 240, 240))
        p.drawEllipse(18, 22, 28, 28)

        p.setBrush(QColor(0, 90, 158))
        p.drawEllipse(24, 28, 16, 16)

        p.setBrush(QColor(255, 255, 255, 120))
        p.drawEllipse(28, 30, 6, 6)

        p.setBrush(QColor(255, 220, 50))
        p.drawEllipse(46, 18, 8, 8)

        p.end()
        return QIcon(pixmap)

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self._create_icon())
        self._tray.setToolTip("SnapTool - Screenshot Tool")

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #2b2b2b; color: #e0e0e0;
                border: 1px solid #3a3a3a; padding: 4px;
                font-family: "Segoe UI"; font-size: 10pt;
            }
            QMenu::item { padding: 6px 24px 6px 12px; }
            QMenu::item:selected { background: #0078d4; border-radius: 3px; }
            QMenu::separator { height: 1px; background: #3a3a3a; margin: 4px 8px; }
        """)

        hotkeys = self.config.get("hotkeys", {})

        a_full = menu.addAction("Full Screen")
        a_full.setShortcut(hotkeys.get("fullscreen", ""))
        a_full.triggered.connect(self._capture_fullscreen)

        a_region = menu.addAction("Region Select")
        a_region.setShortcut(hotkeys.get("region", ""))
        a_region.triggered.connect(self._capture_region)

        a_window = menu.addAction("Active Window")
        a_window.setShortcut(hotkeys.get("window", ""))
        a_window.triggered.connect(self._capture_window)

        a_delayed = menu.addAction("Delayed Capture...")
        a_delayed.setShortcut(hotkeys.get("delayed", ""))
        a_delayed.triggered.connect(self._capture_delayed)

        menu.addSeparator()

        a_history = menu.addAction("History")
        a_history.triggered.connect(self._show_history)

        a_settings = menu.addAction("Settings")
        a_settings.triggered.connect(self._show_settings)

        menu.addSeparator()

        a_about = menu.addAction("About SnapTool")
        a_about.triggered.connect(self._show_about)

        a_quit = menu.addAction("Quit")
        a_quit.triggered.connect(self._quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _setup_hotkeys(self):
        try:
            import keyboard
        except ImportError:
            print("Warning: 'keyboard' package not installed. Global hotkeys disabled.")
            return

        self._hotkey_signals.fullscreen.connect(self._capture_fullscreen)
        self._hotkey_signals.region.connect(self._capture_region)
        self._hotkey_signals.window.connect(self._capture_window)
        self._hotkey_signals.delayed.connect(self._capture_delayed)

        hotkeys = self.config.get("hotkeys", {})
        bindings = {
            "fullscreen": self._hotkey_signals.fullscreen,
            "region": self._hotkey_signals.region,
            "window": self._hotkey_signals.window,
            "delayed": self._hotkey_signals.delayed,
        }

        for action, signal in bindings.items():
            combo = hotkeys.get(action, "")
            if combo:
                try:
                    keyboard.add_hotkey(combo, signal.emit, suppress=False)
                except Exception as e:
                    print(f"Warning: Could not register hotkey '{combo}' for {action}: {e}")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._capture_region()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._capture_fullscreen()

    def _capture_fullscreen(self):
        QTimer.singleShot(200, self._do_fullscreen)

    def _do_fullscreen(self):
        img = ScreenCapture.full_screen()
        self._on_capture(img)

    def _capture_region(self):
        QTimer.singleShot(150, self._region_selector.start_selection)

    def _capture_window(self):
        QTimer.singleShot(200, self._do_window)

    def _do_window(self):
        img = ScreenCapture.active_window()
        self._on_capture(img)

    def _capture_delayed(self):
        delay = self.config.get("delay_seconds", 3)
        self._countdown_remaining = delay
        self._show_countdown()

    def _show_countdown(self):
        if self._countdown_window:
            self._countdown_window.close()

        self._countdown_window = QWidget()
        self._countdown_window.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self._countdown_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        label = QLabel(str(self._countdown_remaining), self._countdown_window)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Segoe UI", 48, QFont.Weight.Bold))
        label.setStyleSheet("""
            color: white;
            background: rgba(0, 122, 204, 200);
            border-radius: 40px;
            min-width: 80px;
            min-height: 80px;
        """)
        label.setFixedSize(80, 80)
        self._countdown_label = label

        self._countdown_window.resize(80, 80)
        screen = QApplication.primaryScreen().geometry()
        self._countdown_window.move(
            (screen.width() - 80) // 2,
            (screen.height() - 80) // 2,
        )
        self._countdown_window.show()

        self._countdown_timer = QTimer()
        self._countdown_timer.timeout.connect(self._countdown_tick)
        self._countdown_timer.start(1000)

    def _countdown_tick(self):
        self._countdown_remaining -= 1
        if self._countdown_remaining <= 0:
            self._countdown_timer.stop()
            if self._countdown_window:
                self._countdown_window.close()
                self._countdown_window = None
            QTimer.singleShot(200, self._do_fullscreen)
        else:
            self._countdown_label.setText(str(self._countdown_remaining))

    def _on_capture(self, pil_image):
        config = self.config
        pil_image = ScreenCapture.apply_effects(pil_image, config)

        if config.get("auto_copy_to_clipboard"):
            pixmap = ScreenCapture.pil_to_qpixmap(pil_image)
            QApplication.clipboard().setPixmap(pixmap)

        dialog = SaveDialog(pil_image)
        dialog.edit_requested.connect(self._open_editor)
        dialog.pin_requested.connect(self._pin_image)
        dialog.exec()

    def _on_cancel(self):
        pass

    def _open_editor(self, pil_image):
        editor = AnnotationEditor(pil_image)
        self._editors.append(editor)
        editor.show()

    def _pin_image(self, pil_image):
        pin = PinWindow(pil_image)
        self._pin_windows.append(pin)
        cursor = QCursor.pos()
        pin.move(cursor.x() + 20, cursor.y() + 20)
        pin.show()

    def _show_history(self):
        dialog = HistoryDialog()
        dialog.exec()

    def _show_settings(self):
        dialog = SettingsDialog()
        if dialog.exec():
            # Re-register hotkeys
            try:
                import keyboard
                keyboard.unhook_all()
            except Exception:
                pass
            self._setup_hotkeys()
            # Rebuild tray menu to reflect new shortcuts
            self._setup_tray()

    def _show_about(self):
        from . import __version__
        QMessageBox.about(
            None, "About SnapTool",
            f"<h2>SnapTool v{__version__}</h2>"
            f"<p>Professional Screenshot Tool for Windows</p>"
            f"<p>Features:</p>"
            f"<ul>"
            f"<li>Full screen, region, and window capture</li>"
            f"<li>Annotation editor with arrows, shapes, blur, and more</li>"
            f"<li>Pin screenshots as floating windows</li>"
            f"<li>Global hotkeys</li>"
            f"<li>Screenshot history</li>"
            f"<li>Copy as Base64 for embedding</li>"
            f"<li>Border and shadow effects</li>"
            f"<li>Auto-cleanup old screenshots</li>"
            f"</ul>"
        )

    def _show_welcome(self):
        self._tray.showMessage(
            "SnapTool",
            "SnapTool is running. Right-click the tray icon for options.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    def _auto_cleanup(self):
        if not self.config.get("auto_cleanup_enabled"):
            return

        days = self.config.get("auto_cleanup_days", 30)
        folder = self.config.get("default_folder")
        if not Path(folder).is_dir():
            return

        cutoff = datetime.now() - timedelta(days=days)
        exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

        for f in os.listdir(folder):
            if any(f.lower().endswith(e) for e in exts):
                full = os.path.join(folder, f)
                try:
                    if datetime.fromtimestamp(os.path.getmtime(full)) < cutoff:
                        os.remove(full)
                except OSError:
                    pass

    def _quit(self):
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass

        for pin in self._pin_windows:
            pin.close()
        for editor in self._editors:
            editor.close()

        self._tray.hide()
        QApplication.quit()
