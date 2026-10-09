import re
from typing import List, Optional

import httpx

from providers.base import TimedLine

LRCLIB_URL = "https://lrclib.net/api"
HEADERS = {"User-Agent": "LetrasBR/3.0 (github.com/erickovisck/letras_br)"}

# Tolerância de duração (segundos) para aceitar um resultado da busca aproximada
DURATION_TOLERANCE = 3.0


def log(msg: str):
    try:
        print(f"[LRCLIB] {msg}")
    except Exception:
        print(f"[LRCLIB] {str(msg).encode('ascii', 'replace').decode('ascii')}")


def parse_lrc(lrc_content: str) -> List[TimedLine]:
    """
    Converte conteúdo no formato LRC padrão ([mm:ss.xx] texto) em uma lista de TimedLine.
    Calcula end_time automaticamente com base no início do próximo verso.
    """
    lines = lrc_content.strip().split("\n")
    parsed: List[tuple[int, str]] = []

    pattern = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\](.*)$")
    # Linhas de crédito de quem sincronizou a letra (ex: "lrc by fulano")
    credit = re.compile(r"^(?:lrc|lyrics|synced|ripped|timing)\s+(?:made\s+)?by\b", re.IGNORECASE)

    for raw_line in lines:
        raw_line = raw_line.strip()
        match = pattern.match(raw_line)
        if match:
            minutes = int(match.group(1))
            seconds = float(match.group(2))
            text = match.group(3).strip()
            if credit.match(text):
                continue
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


def _pick_search_result(results: list, artist: str, duration: Optional[float]) -> Optional[dict]:
    """Escolhe o melhor resultado com letra sincronizada: duração mais próxima e artista compatível."""
    artist_low = (artist or "").lower()
    candidates = []
    for item in results:
        if not item.get("syncedLyrics"):
            continue
        item_artist = (item.get("artistName") or "").lower()
        artist_ok = not artist_low or artist_low in item_artist or item_artist in artist_low
        diff = abs(float(item.get("duration") or 0) - duration) if duration else 0.0
        if duration and diff > DURATION_TOLERANCE:
            continue
        # Artista compatível vem antes; depois menor diferença de duração
        candidates.append((0 if artist_ok else 1, diff, item))

    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][2]


def fetch_lrclib_lyrics(
    title: str,
    artist: str,
    album: Optional[str] = None,
    duration: Optional[float] = None
) -> Optional[List[TimedLine]]:
    """
    Busca letras sincronizadas no LRCLIB.
    1. /api/get com assinatura exata (título, artista, álbum, duração).
    2. Se não encontrar (404), /api/search filtrando por duração e artista.
    """
    if not title:
        return None
    duration = duration if duration and duration > 0 else None

    try:
        with httpx.Client(headers=HEADERS, timeout=6.0, follow_redirects=True) as client:
            params = {"track_name": title, "artist_name": artist}
            if album:
                params["album_name"] = album
            if duration:
                params["duration"] = int(round(duration))

            res = client.get(f"{LRCLIB_URL}/get", params=params)
            if res.status_code == 200:
                lines = parse_lrc(res.json().get("syncedLyrics") or "")
                if lines:
                    log(f"✅ {len(lines)} versos sincronizados (busca exata) para '{title}'.")
                    return lines

            search_params = {"track_name": title}
            if artist:
                search_params["artist_name"] = artist
            res = client.get(f"{LRCLIB_URL}/search", params=search_params)
            if res.status_code == 200 and isinstance(res.json(), list):
                best = _pick_search_result(res.json(), artist, duration)
                if best:
                    lines = parse_lrc(best["syncedLyrics"])
                    if lines:
                        log(f"✅ {len(lines)} versos sincronizados (busca aproximada) para '{title}'.")
                        return lines
    except Exception as e:
        log(f"⚠️ Erro ao consultar LRCLIB: {e}")

    log(f"Nenhuma letra sincronizada encontrada para '{title}'.")
    return None
