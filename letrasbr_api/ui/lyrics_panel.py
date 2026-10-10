"""Painel expansível com a letra completa; clicar em um verso pula a música para ele."""

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from ..aligner import AlignedLine
from .palette import Palette, rgba


def _format_ms(ms: int) -> str:
    seconds = max(0, ms // 1000)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class LyricsPanel(QListWidget):
    seek_requested = Signal(int)  # início do verso clicado, em ms

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Clique em um verso para pular até ele")
        self.itemClicked.connect(lambda item: self.seek_requested.emit(item.data(Qt.UserRole)))
        self._active = -1

    def set_lines(self, lines: List[AlignedLine]):
        self.clear()
        self._active = -1
        for line in lines:
            translation = f"≈ {line.translation}" if line.source == "auto" and line.translation else line.translation
            text = f"{_format_ms(line.start_time)}   {line.original}"
            if translation and translation != "(♪)":
                text += f"\n          {translation}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, line.start_time)
            self.addItem(item)

    def set_active(self, index: int):
        if index == self._active or not (0 <= index < self.count()):
            return
        self._active = index
        self.setCurrentRow(index)
        self.scrollToItem(self.item(index), QAbstractItemView.PositionAtCenter)

    def apply_palette(self, palette: Palette, font_family: str):
        self.setStyleSheet(f"""
            QListWidget {{
                background: {rgba(palette.bg, 0.0)};
                border: none;
                border-top: 1px solid {palette.subtle};
                color: {palette.muted};
                font-family: '{font_family}';
                font-size: 12px;
                outline: none;
            }}
            QListWidget::item {{ padding: 4px 6px; border-radius: 6px; }}
            QListWidget::item:hover {{ background: {palette.hover}; color: {palette.text}; }}
            QListWidget::item:selected {{ background: {palette.pressed}; color: {palette.accent}; }}
            QScrollBar:vertical {{ width: 6px; background: transparent; }}
            QScrollBar::handle:vertical {{ background: {palette.subtle}; border-radius: 3px; min-height: 24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
