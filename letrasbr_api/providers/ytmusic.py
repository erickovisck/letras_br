from typing import List, Optional

from .base import MusicProviderAdapter, TimedLine, TrackInfo
from ..lyrics_sync import YTMManager


class YouTubeMusicAdapter(MusicProviderAdapter):
    """
    Adapter concreto para o YouTube Music.
    Encapsula o cliente YTMManager e converte as letras do formato LyricLine para TimedLine.
    """

    def __init__(self, ytm_manager: Optional[YTMManager] = None):
        self._ytm = ytm_manager or YTMManager()
        self._pending_command: Optional[str] = None

    @property
    def provider_id(self) -> str:
        return "ytmusic"

    def get_timed_lyrics(self, track: TrackInfo) -> Optional[List[TimedLine]]:
        raw_lines = self._ytm.get_timed_lyrics(
            video_id=track.track_id or "",
            title=track.title,
            artist=track.artist,
            duration=track.duration
        )
        if not raw_lines:
            return None

        timed_lines: List[TimedLine] = []
        for line in raw_lines:
            timed_lines.append(TimedLine(
                start_time=line.start_time,
                end_time=line.end_time,
                text=line.text
            ))
        return timed_lines

    def queue_command(self, action: str) -> None:
        self._pending_command = action

    def pop_pending_command(self) -> Optional[str]:
        cmd = self._pending_command
        self._pending_command = None
        return cmd
