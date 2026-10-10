"""Campos de cor hexadecimal com colagem robusta (Ctrl+V, Shift+Insert, menu de contexto)."""

import re

from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import QLineEdit


class SmartHtmlFilter(QObject):
    """
    Filtro de evento para o campo HTML do QColorDialog.
    Garante que colar codigos hexadecimais (com ou sem '#', com espacos, maiusculos/minusculos)
    via Ctrl+V, Shift+Insert ou menu de contexto funcione perfeitamente.
    """
    def __init__(self, edit, dlg):
        super().__init__(edit)
        self.edit = edit
        self.dlg = dlg

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            is_paste = (
                (event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_V) or
                (event.modifiers() & Qt.ShiftModifier and event.key() == Qt.Key_Insert)
            )
            if is_paste:
                if self._do_paste():
                    return True
        elif event.type() == QEvent.ContextMenu:
            menu = self.edit.createStandardContextMenu()
            for act in menu.actions():
                txt = act.text().lower()
                if "paste" in txt or "colar" in txt:
                    act.triggered.disconnect()
                    act.triggered.connect(self._do_paste)
            menu.exec(event.globalPos())
            return True
        return super().eventFilter(obj, event)

    def _do_paste(self):
        clip = QGuiApplication.clipboard().text().strip()
        m = re.search(r'#?([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})', clip)
        if m:
            val = m.group(1)
            if len(val) == 3:
                val = ''.join([c*2 for c in val])
            clean_hex = '#' + val.upper()
            self.edit.setText(clean_hex)
            self.edit.textEdited.emit(clean_hex)
            self.dlg.setCurrentColor(QColor(clean_hex))
            return True
        return False


class HexColorLineEdit(QLineEdit):
    """
    Campo de texto para codigos hexadecimais com suporte robusto a colagem
    (Ctrl+V, Shift+Insert, menu de contexto) mesmo com espacos ou sem '#'.
    """
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMaxLength(7)
        # Cores vêm do estilo da tela de configurações (seguem o tema); aqui só a tipografia
        self.setObjectName("hexColor")

    def keyPressEvent(self, event):
        if (event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_V) or \
           (event.modifiers() & Qt.ShiftModifier and event.key() == Qt.Key_Insert):
            self.paste()
            return
        super().keyPressEvent(event)

    def paste(self):
        clip = QGuiApplication.clipboard().text().strip()
        m = re.search(r'#?([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})', clip)
        if m:
            val = m.group(1)
            if len(val) == 3:
                val = ''.join([c*2 for c in val])
            clean = '#' + val.upper()
            self.setText(clean)
            self.textEdited.emit(clean)
        else:
            super().paste()
