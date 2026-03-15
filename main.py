"""SnapTool - Professional Screenshot Application for Windows."""

import sys
import os

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("SnapTool")
    app.setOrganizationName("SnapTool")

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
