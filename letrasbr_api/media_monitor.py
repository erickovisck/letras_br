"""
Módulo de Monitoramento Nativo de Mídia do Windows (GSMTC).
Captura sessões ativas do YouTube Music (no Chrome, Edge, Brave, etc.) ou Spotify
sem necessidade de extensões no navegador.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import QThread, Signal

try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as SessionManager,
        GlobalSystemMediaTransportControlsSession as MediaSession,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )
    WINRT_AVAILABLE = True
except ImportError:
    WINRT_AVAILABLE = False


class WindowsMediaMonitor(QThread):
    """
    Thread de monitoramento de mídia do Windows.
    Emite sinais para a interface gráfica PySide6:
    - track_changed: novo título, artista, álbum, duração em segundos
    - playback_tick: posição atual em segundos, duração, está pausado (bool)
    - status_message: mensagens de status para depuração/log
    """
    track_changed = Signal(str, str, str, float)  # title, artist, album, duration
    playback_tick = Signal(float, float, bool)     # current_seconds, duration, is_paused
    source_changed = Signal(str)                  # "spotify", "youtube", "idle"
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._manager: Optional[SessionManager] = None
        self._current_session: Optional[MediaSession] = None
        self._last_title = ""
        self._last_artist = ""
        self._last_source: Optional[str] = None
        self._last_is_paused: Optional[bool] = None

        # Fila de comandos assíncronos (play, pause, next, previous)
        self._command_queue = []

    def stop(self):
        self._running = False

    def send_command(self, action: str):
        """Enfileira um comando para ser executado na sessão ativa do Windows"""
        self._command_queue.append(action)

    def send_seek(self, seconds: float):
        """Enfileira um comando de seek para alterar a posição da música em segundos"""
        self._command_queue.append(("seek", max(0.0, float(seconds))))

    def run(self):
        if not WINRT_AVAILABLE:
            self.status_message.emit("Módulo winrt-Windows.Media.Control não disponível.")
            return

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._monitor_loop())
        finally:
            self._loop.close()

    async def _get_active_session(self) -> Optional[MediaSession]:
        """Obtém a melhor sessão de mídia ativa disponível."""
        if not self._manager:
            try:
                self._manager = await SessionManager.request_async()
            except Exception as e:
                self.status_message.emit(f"Erro ao inicializar SessionManager: {e}")
                return None

        current = self._manager.get_current_session()
        if current:
            return current

        # Fallback: se get_current_session for None, procura nas sessões abertas
        try:
            sessions = self._manager.get_sessions()
            for s in sessions:
                info = s.get_playback_info()
                if info and info.playback_status == PlaybackStatus.PLAYING:
                    return s
            if sessions:
                return sessions[0]
        except Exception:
            pass
        return None

    async def _execute_commands(self, session: MediaSession):
        while self._command_queue:
            cmd = self._command_queue.pop(0)
            try:
                if isinstance(cmd, tuple) and cmd[0] == "seek":
                    ticks = int(cmd[1] * 10_000_000)
                    await session.try_change_playback_position_async(ticks)
                elif cmd in ("play_pause", "toggle_play"):
                    await session.try_toggle_play_pause_async()
                elif cmd == "next":
                    await session.try_skip_next_async()
                elif cmd == "previous":
                    await session.try_skip_previous_async()
                elif cmd == "play":
                    await session.try_play_async()
                elif cmd == "pause":
                    await session.try_pause_async()
            except Exception as e:
                self.status_message.emit(f"Falha ao executar comando {cmd}: {e}")

    async def _monitor_loop(self):
        self.status_message.emit("Monitor de Mídia do Windows ativado.")
        poll_count = 0

        while self._running:
            try:
                # A cada ~500ms ou se não tiver sessão, atualiza sessão
                if poll_count % 5 == 0 or not self._current_session:
                    self._current_session = await self._get_active_session()

                if self._current_session:
                    # Detecta a origem da reprodução (Spotify vs YouTube Music)
                    app_id = (getattr(self._current_session, "source_app_user_model_id", "") or "").lower()
                    if "spotify" in app_id:
                        src = "spotify"
                    elif any(k in app_id for k in ("chrome", "edge", "brave", "opera", "firefox", "youtube", "cinhimbnkkghhklpknlkffjgod")):
                        src = "youtube"
                    else:
                        src = "spotify" if "spotify" in app_id else "youtube"

                    if src != self._last_source:
                        self._last_source = src
                        self.source_changed.emit(src)

                    # Executa comandos pendentes
                    await self._execute_commands(self._current_session)

                    # Propriedades de mídia (Título, Artista, Álbum)
                    props = await self._current_session.try_get_media_properties_async()
                    title = (props.title or "").strip() if props else ""
                    artist = (props.artist or "").strip() if props else ""
                    album = (props.album_title or "").strip() if props else ""

                    # Timeline e Status
                    timeline = self._current_session.get_timeline_properties()
                    info = self._current_session.get_playback_info()

                    is_paused = True
                    if info:
                        is_paused = (info.playback_status != PlaybackStatus.PLAYING)

                    duration = 0.0
                    current_seconds = 0.0

                    if timeline:
                        duration = timeline.end_time.total_seconds()
                        base_pos = timeline.position.total_seconds()
                        if not is_paused and timeline.last_updated_time:
                            now = datetime.now(timezone.utc)
                            elapsed = (now - timeline.last_updated_time).total_seconds()
                            current_seconds = max(0.0, base_pos + elapsed)
                        else:
                            current_seconds = max(0.0, base_pos)

                    # Detecção de mudança de faixa (autoplay ou pulo manual)
                    if title and (title != self._last_title or artist != self._last_artist):
                        self._last_title = title
                        self._last_artist = artist
                        self.track_changed.emit(title, artist, album, duration)

                    # Emite tick contínuo para o overlay sincronizar as letras
                    self.playback_tick.emit(current_seconds, duration, is_paused)

                else:
                    # Nenhuma sessão ativa no momento
                    if self._last_source != "idle":
                        self._last_source = "idle"
                        self.source_changed.emit("idle")

                    if self._last_title != "":
                        self._last_title = ""
                        self._last_artist = ""
                        self.track_changed.emit("", "", "", 0.0)

            except Exception as e:
                self._current_session = None

            poll_count += 1
            await asyncio.sleep(0.1)
