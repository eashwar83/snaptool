"""SnapTool - Professional Screenshot Application for Windows."""

import sys

from PyQt6.QtWidgets import QApplication


def _set_windows_app_id():
    if sys.platform != "win32":
        return

    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "SnapTool.ScreenshotTool"
        )
    except Exception:
        pass


def main():
    _set_windows_app_id()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("SnapTool")
    app.setOrganizationName("SnapTool")

    from snaptool.icons import create_app_icon
    app.setWindowIcon(create_app_icon())

    # Prevent multiple instances
    from PyQt6.QtCore import QSharedMemory
    shared = QSharedMemory("SnapTool_SingleInstance")
    if not shared.create(1):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(None, "SnapTool", "SnapTool is already running.\nCheck the system tray.")
        sys.exit(0)

    from snaptool.app import SnapToolApp
    snap = SnapToolApp()
    snap.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
