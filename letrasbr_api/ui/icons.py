"""Ícones da pasta assets/ com tint de cor conforme o tema."""

import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")


def load_tinted_icon(icon_name: str, color_hex: str, hover_hex: str = "#ffffff", size: int = 16) -> QIcon:
    """
    Carrega imagem da pasta assets e aplica tint de cor preservando a transparência (alpha mask).
    Retorna QIcon com estados Normal e Active (hover).
    """
    path = os.path.join(ASSETS_DIR, icon_name)
    if not os.path.exists(path):
        return QIcon()

    pix = QPixmap(path)
    if pix.isNull():
        return QIcon()

    qsize = QSize(size, size)
    scaled = pix.scaled(qsize, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _tint(base_pix: QPixmap, color: QColor) -> QPixmap:
        res = QPixmap(base_pix)
        p = QPainter(res)
        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p.fillRect(res.rect(), color)
        p.end()
        return res

    norm_pix = _tint(scaled, QColor(color_hex))
    hover_pix = _tint(scaled, QColor(hover_hex))

    icon = QIcon()
    icon.addPixmap(norm_pix, QIcon.Normal, QIcon.Off)
    icon.addPixmap(norm_pix, QIcon.Normal, QIcon.On)
    icon.addPixmap(hover_pix, QIcon.Active, QIcon.Off)
    icon.addPixmap(hover_pix, QIcon.Active, QIcon.On)
    return icon
