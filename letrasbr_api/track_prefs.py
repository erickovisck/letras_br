"""
Preferências por música, salvas em config/track_prefs.json:
- offsetMs: ajuste de sincronia (positivo = letra aparece mais cedo)
- letrasPath: página do Letras.mus.br escolhida manualmente ("Música errada?")
"""

import os
import json
import logging
import threading
from typing import Any, Dict, Optional

from .config import CONFIG_DIR

logger = logging.getLogger(__name__)

PREFS_FILE = os.path.join(CONFIG_DIR, "track_prefs.json")

_lock = threading.Lock()
_prefs: Optional[Dict[str, Dict[str, Any]]] = None


def track_key(artist: str, title: str) -> str:
    return f"{(artist or '').strip().lower()}|||{(title or '').strip().lower()}"


def _load() -> Dict[str, Dict[str, Any]]:
    global _prefs
    if _prefs is None:
        _prefs = {}
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as f:
                _prefs = json.load(f)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Preferências por música ilegíveis, ignorando: {e}")
    return _prefs


def _save():
    try:
        tmp = PREFS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_prefs, f, indent=2, ensure_ascii=False)
        os.replace(tmp, PREFS_FILE)
    except Exception as e:
        logger.warning(f"Erro ao salvar preferências por música: {e}")


def get_pref(artist: str, title: str, name: str, default=None):
    with _lock:
        return _load().get(track_key(artist, title), {}).get(name, default)


def set_pref(artist: str, title: str, name: str, value):
    """Define (ou remove, com value None/0/"") uma preferência da música e grava em disco."""
    key = track_key(artist, title)
    with _lock:
        prefs = _load()
        entry = prefs.setdefault(key, {})
        if value in (None, 0, ""):
            entry.pop(name, None)
        else:
            entry[name] = value
        if not entry:
            prefs.pop(key, None)
        _save()


def get_offset_ms(artist: str, title: str) -> int:
    return int(get_pref(artist, title, "offsetMs", 0) or 0)


def set_offset_ms(artist: str, title: str, offset_ms: int):
    set_pref(artist, title, "offsetMs", int(offset_ms))


def get_letras_path(artist: str, title: str) -> Optional[str]:
    return get_pref(artist, title, "letrasPath")


def set_letras_path(artist: str, title: str, path: Optional[str]):
    set_pref(artist, title, "letrasPath", path)
