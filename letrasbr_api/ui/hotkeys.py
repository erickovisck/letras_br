"""
Atalhos globais do Windows (funcionam mesmo com o overlay sem foco ou deixando os cliques passarem).
Usa RegisterHotKey e recebe WM_HOTKEY pelo filtro de eventos nativos do Qt.
"""

import sys
import ctypes
import logging
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000


class _NativeFilter(QAbstractNativeEventFilter):
    def __init__(self, on_hotkey):
        super().__init__()
        self._on_hotkey = on_hotkey

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                self._on_hotkey(int(msg.wParam))
                return True, 0
        return False, 0


class GlobalHotkeys(QObject):
    """Registra atalhos globais; emite `activated(nome)` quando um deles é pressionado."""
    activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._names = {}
        self._filter = None
        if sys.platform == "win32":
            self._filter = _NativeFilter(self._dispatch)
            QApplication.instance().installNativeEventFilter(self._filter)

    def register(self, name: str, modifiers: int, key: str) -> bool:
        """Ex: register("unlock", MOD_CONTROL | MOD_ALT, "L"). Retorna False se indisponível/em uso."""
        if self._filter is None:
            return False
        hotkey_id = 0xB000 + len(self._names)
        if not ctypes.windll.user32.RegisterHotKey(None, hotkey_id, modifiers | MOD_NOREPEAT, ord(key.upper())):
            logger.warning(f"Atalho global '{name}' indisponível (já usado por outro programa?).")
            return False
        self._names[hotkey_id] = name
        return True

    def unregister_all(self):
        for hotkey_id in list(self._names):
            ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
        self._names.clear()

    def _dispatch(self, hotkey_id: int):
        name = self._names.get(hotkey_id)
        if name:
            self.activated.emit(name)
