"""Ícone e menu da bandeja do sistema (ao lado do relógio do Windows)."""

import os

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .icons import ASSETS_DIR


def load_app_icon() -> QIcon:
    """Ícone do app em assets/, ou um 'L' desenhado via QPainter como fallback."""
    icon_path = os.path.join(ASSETS_DIR, "app_icon.png")
    if os.path.exists(icon_path):
        return QIcon(icon_path)

    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QBrush(QColor("#38bdf8")))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(2, 2, 28, 28, 8, 8)
    painter.setPen(QPen(QColor("#0f172a")))
    painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
    painter.drawText(QRect(0, 0, 32, 32), Qt.AlignCenter, "L")
    painter.end()
    return QIcon(pixmap)


def create_tray_icon(window) -> QSystemTrayIcon:
    """
    Cria o ícone da bandeja ligado à janela do overlay.
    A janela precisa expor: toggle_visibility, toggle_lock, open_settings, send_media_cmd e exit_application.
    """
    app_icon = load_app_icon()
    window.setWindowIcon(app_icon)

    tray_icon = QSystemTrayIcon(app_icon, window)
    menu = QMenu(window)

    def add_action(text, callback):
        action = QAction(text, window)
        action.triggered.connect(callback)
        menu.addAction(action)
        return action

    add_action("Mostrar / Ocultar Overlay", window.toggle_visibility)
    # Única forma (além do atalho) de destravar quando o overlay deixa os cliques passarem
    tray_icon.lock_action = add_action("Travar / Destravar overlay (Ctrl+Alt+L)", window.toggle_lock)
    add_action("Configurações", window.open_settings)
    menu.addSeparator()
    add_action("Play / Pause", lambda: window.send_media_cmd("play_pause"))
    add_action("Próxima Música", lambda: window.send_media_cmd("next"))
    menu.addSeparator()
    add_action("Sair do LetrasBR", window.exit_application)

    tray_icon.setContextMenu(menu)
    tray_icon.activated.connect(
        lambda reason: window.toggle_visibility() if reason == QSystemTrayIcon.Trigger else None
    )
    tray_icon.show()
    return tray_icon
