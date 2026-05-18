"""Shared SnapTool icon helpers."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap


def create_app_icon():
    """Create the SnapTool camera icon used by windows and the tray."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setBrush(QColor(0, 122, 204))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 14, 56, 42, 8, 8)
    painter.drawRoundedRect(20, 6, 20, 12, 4, 4)

    painter.setBrush(QColor(240, 240, 240))
    painter.drawEllipse(18, 22, 28, 28)

    painter.setBrush(QColor(0, 90, 158))
    painter.drawEllipse(24, 28, 16, 16)

    painter.setBrush(QColor(255, 255, 255, 120))
    painter.drawEllipse(28, 30, 6, 6)

    painter.setBrush(QColor(255, 220, 50))
    painter.drawEllipse(46, 18, 8, 8)

    painter.end()
    return QIcon(pixmap)
