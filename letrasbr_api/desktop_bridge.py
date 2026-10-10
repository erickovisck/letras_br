"""
Ponte entre o overlay desktop (thread do Qt) e a API FastAPI (thread do uvicorn), que rodam no mesmo processo.

O overlay publica aqui a faixa, a letra alinhada e a posição de reprodução; a API lê um retrato consistente
para o /mobile e devolve ao desktop os comandos de mídia e a troca de idioma pedidos pelo celular.
"""

import threading
import time
from typing import Callable, List, Optional, Sequence

from .aligner import AlignedLine

# A extensão/app Android (POST /api/sync) tem prioridade enquanto estiver enviando dados
REMOTE_CLIENT_TIMEOUT_S = 5.0

SOURCE_IDS = {"youtube": "ytmusic", "spotify": "spotify"}


class DesktopBridge:
    def __init__(self):
        self._lock = threading.Lock()
        self._on_command: Optional[Callable[[str], None]] = None
        self._on_language: Optional[Callable[[str], None]] = None
        self._reset_track()
        self._lang = ""
        self._source = "ytmusic"

    def _reset_track(self):
        self._title = ""
        self._artist = ""
        self._album = ""
        self._duration = 0.0
        self._lines: List[AlignedLine] = []
        self._loading = False
        self._translation_url: Optional[str] = None
        self._translation_source = "none"
        self._timing_source = "none"
        self._seconds = 0.0
        self._paused = True
        self._index = -1
        self._offset_ms = 0
        self._lyrics_version = 0

    # --- Lado do desktop (thread do Qt) ---

    def attach(self, on_command: Callable[[str], None], on_language: Callable[[str], None]):
        """on_command roda na thread da API (deve ser thread-safe); on_language deve só agendar a troca."""
        with self._lock:
            self._on_command, self._on_language = on_command, on_language

    def detach(self):
        with self._lock:
            self._on_command = self._on_language = None
            self._reset_track()

    @property
    def attached(self) -> bool:
        return self._on_command is not None

    def set_track(self, title: str, artist: str, album: str = "", duration: float = 0.0,
                  source: str = "", lang: str = "", offset_ms: int = 0):
        with self._lock:
            version = self._lyrics_version
            self._reset_track()
            self._lyrics_version = version + 1
            self._title, self._artist, self._album = title or "", artist or "", album or ""
            self._duration = duration or 0.0
            self._loading = bool(title)
            self._offset_ms = offset_ms
            if source:
                self._source = SOURCE_IDS.get(source, source)
            if lang:
                self._lang = lang

    def set_lyrics(self, lines: Sequence[AlignedLine], translation_url: Optional[str] = None,
                   translation_source: str = "none", timing_source: str = "none"):
        with self._lock:
            self._lines = list(lines)
            self._loading = False
            self._translation_url = translation_url
            self._translation_source = translation_source
            self._timing_source = timing_source
            self._index = -1
            self._lyrics_version += 1

    def set_position(self, seconds: float, duration: float, paused: bool, index: int, offset_ms: int = 0):
        with self._lock:
            self._seconds, self._paused, self._index, self._offset_ms = seconds, paused, index, offset_ms
            if duration > 0:
                self._duration = duration

    def set_lang(self, lang: str):
        with self._lock:
            self._lang = lang

    def set_source(self, source: str):
        with self._lock:
            self._source = SOURCE_IDS.get(source, source)

    # --- Lado da API (thread do uvicorn) ---

    def send_command(self, action: str) -> bool:
        handler = self._on_command
        if handler is None:
            return False
        handler(action)
        return True

    def request_language(self, lang: str) -> bool:
        handler = self._on_language
        if handler is None:
            return False
        handler(lang)
        return True

    def snapshot(self) -> dict:
        """Estado atual no mesmo formato de GET /api/current."""
        with self._lock:
            lines, index = self._lines, self._index
            active = lines[index] if 0 <= index < len(lines) else None
            upcoming = lines[index + 1] if 0 <= index + 1 < len(lines) else None
            if active is None and lines and index < 0:
                upcoming = lines[0]  # Antes do primeiro verso: mostra o que vem
            return {
                "title": self._title,
                "artist": self._artist,
                "album": self._album or None,
                "videoId": None,
                "trackId": None,
                "source": self._source,
                "lang": self._lang,
                "currentTimeMs": int(self._seconds * 1000),
                "currentSeconds": self._seconds,
                "durationSeconds": self._duration,
                "isPaused": self._paused,
                "isFetching": self._loading,
                "activeIndex": index,
                "activeOriginal": active.original if active else "",
                "activeTranslation": active.translation if active else "",
                "activeLineSource": active.source if active else "none",
                "nextOriginal": upcoming.original if upcoming else "",
                "nextTranslation": upcoming.translation if upcoming else "",
                "nextLineSource": upcoming.source if upcoming else "none",
                "translationUrl": self._translation_url,
                "hasTimedLyrics": self._timing_source not in ("none", "estimated") and bool(lines),
                "hasTranslation": self._translation_source in ("letras", "auto", "mixed"),
                "translationSource": self._translation_source,
                "timingSource": self._timing_source,
                "hasAlignedLyrics": bool(lines),
                "lyricsVersion": self._lyrics_version,
                "offsetMs": self._offset_ms,
                "origin": "desktop",
                "updatedAt": time.time(),
            }


bridge = DesktopBridge()
