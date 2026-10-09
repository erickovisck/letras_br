from typing import List, Optional

from providers.base import MusicProviderAdapter, TimedLine, TrackInfo
from providers.lrclib import fetch_lrclib_lyrics


class SpotifyAdapter(MusicProviderAdapter):
    """
    Adapter concreto para o Spotify.
    Obtém letras temporizadas para faixas do Spotify via LRCLIB e gerencia comandos de player.
    """

    def __init__(self, api_token: Optional[str] = None):
        self._api_token = api_token
        self._pending_command: Optional[str] = None

    @property
    def provider_id(self) -> str:
        return "spotify"

    def get_timed_lyrics(self, track: TrackInfo) -> Optional[List[TimedLine]]:
        return fetch_lrclib_lyrics(track.title, track.artist, track.album, track.duration)

    def queue_command(self, action: str) -> None:
        self._pending_command = action

    def pop_pending_command(self) -> Optional[str]:
        cmd = self._pending_command
        self._pending_command = None
        return cmd
