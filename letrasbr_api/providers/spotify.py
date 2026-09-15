import re
import urllib.request
import urllib.parse
import json
from typing import List, Optional

from providers.base import MusicProviderAdapter, TimedLine, TrackInfo


def parse_lrc(lrc_content: str) -> List[TimedLine]:
    """
    Converte conteúdo no formato LRC padrão ([mm:ss.xx] texto) em uma lista de TimedLine.
    Calcula end_time automaticamente com base no início do próximo verso.
    """
    lines = lrc_content.strip().split("\n")
    parsed: List[tuple[int, str]] = []

    pattern = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\](.*)$")

    for raw_line in lines:
        raw_line = raw_line.strip()
        match = pattern.match(raw_line)
        if match:
            minutes = int(match.group(1))
            seconds = float(match.group(2))
            text = match.group(3).strip()
            total_ms = int((minutes * 60 + seconds) * 1000)
            parsed.append((total_ms, text))

    if not parsed:
        return []

    timed_lines: List[TimedLine] = []
    for i in range(len(parsed)):
        start_ms, text = parsed[i]
        if i + 1 < len(parsed):
            next_start_ms = parsed[i + 1][0]
            end_ms = max(start_ms + 500, next_start_ms)
        else:
            end_ms = start_ms + 4000  # Último verso padrão

        timed_lines.append(TimedLine(start_time=start_ms, end_time=end_ms, text=text))

    return timed_lines


class SpotifyAdapter(MusicProviderAdapter):
    """
    Adapter concreto para o Spotify.
    Obtém letras temporizadas para faixas do Spotify utilizando serviços de letras sincronizadas
    compatíveis com faixas do Spotify (ex: LRCLIB / SyncedLyrics) e gerencia comandos de player.
    """

    def __init__(self, api_token: Optional[str] = None):
        self._api_token = api_token
        self._pending_command: Optional[str] = None

    @property
    def provider_id(self) -> str:
        return "spotify"

    def get_timed_lyrics(self, track: TrackInfo) -> Optional[List[TimedLine]]:
        """
        Busca letras sincronizadas para a música do Spotify.
        Utiliza busca direta no LRCLIB (provedor público de letras sincronizadas com hashes do Spotify).
        """
        try:
            params = {
                "track_name": track.title,
                "artist_name": track.artist,
            }
            if track.album:
                params["album_name"] = track.album
            if track.duration:
                params["duration"] = int(track.duration)

            query_str = urllib.parse.urlencode(params)
            req_url = f"https://lrclib.net/api/get?{query_str}"

            req = urllib.request.Request(
                req_url,
                headers={"User-Agent": "LetrasBR-Adapter/2.0 (github.com/erickovisck/letras_br)"}
            )

            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    synced_lyrics = data.get("syncedLyrics")
                    if synced_lyrics:
                        lines = parse_lrc(synced_lyrics)
                        if lines:
                            print(f"[SPOTIFY] ✅ {len(lines)} versos sincronizados obtidos com sucesso para '{track.title}'.")
                            return lines

            # Se a busca exata falhar, tenta endpoint de busca aproximada
            search_query = urllib.parse.urlencode({"q": f"{track.title} {track.artist}".strip()})
            search_url = f"https://lrclib.net/api/search?{search_query}"
            search_req = urllib.request.Request(
                search_url,
                headers={"User-Agent": "LetrasBR-Adapter/2.0"}
            )
            with urllib.request.urlopen(search_req, timeout=5) as response:
                if response.status == 200:
                    results = json.loads(response.read().decode("utf-8"))
                    if isinstance(results, list) and len(results) > 0:
                        for item in results:
                            synced_lyrics = item.get("syncedLyrics")
                            if synced_lyrics:
                                lines = parse_lrc(synced_lyrics)
                                if lines:
                                    print(f"[SPOTIFY] ✅ {len(lines)} versos sincronizados obtidos via busca aproximada.")
                                    return lines
        except Exception as e:
            print(f"[SPOTIFY] ⚠️ Erro ao consultar letras sincronizadas: {e}")

        return None

    def queue_command(self, action: str) -> None:
        self._pending_command = action

    def pop_pending_command(self) -> Optional[str]:
        cmd = self._pending_command
        self._pending_command = None
        return cmd
