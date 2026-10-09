import sys
import os
from typing import List, Optional

try:
    from ytmusicapi import YTMusic
    try:
        from ytmusicapi.models.lyrics import LyricLine
    except ImportError:
        LyricLine = None  # ytmusicapi antigo sem modelo LyricLine
    _YTMUSICAPI_AVAILABLE = True
except ImportError as _ytm_err:
    YTMusic = None
    LyricLine = None
    _YTMUSICAPI_AVAILABLE = False
    print(f"[YTM] AVISO: ytmusicapi nao instalado: {_ytm_err}")


def log(msg: str):
    try:
        print(f"[YTM] {msg}")
    except Exception:
        safe = str(msg).encode("ascii", "replace").decode("ascii")
        print(f"[YTM] {safe}")


class YTMManager:
    def __init__(self):
        self._available = False
        self.yt = None
        try:
            log("Inicializando cliente YTMusic...")
            self.yt = YTMusic()
            self._available = True
            log("Cliente YTMusic inicializado com sucesso.")
        except Exception as e:
            log(f"AVISO: Nao foi possivel inicializar YTMusic: {e}")
            log("Letras sincronizadas do YouTube Music nao estarao disponiveis.")

    def get_timed_lyrics(
        self,
        video_id: str,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        duration: Optional[float] = None
    ) -> Optional[List]:
        """
        Obtém as letras temporizadas do YouTube Music usando ytmusicapi.
        Se o videoId direto não tiver letras, tenta buscar pelo título e artista
        para pegar a versão oficial da faixa de áudio (a de duração mais próxima).
        """
        if not self._available:
            log("ytmusicapi indisponivel — retornando None.")
            return None

        lyrics_browse_id = None

        if video_id:
            try:
                log(f"Consultando get_watch_playlist para videoId='{video_id}'...")
                watch_data = self.yt.get_watch_playlist(videoId=video_id)
                lyrics_browse_id = watch_data.get("lyrics")
                log(f"Resultado do watch_playlist: lyrics_browse_id = '{lyrics_browse_id}'")
            except Exception as e:
                log(f"Erro ao obter watch_playlist para {video_id}: {e}")

        # Se não encontrou letras no video_id fornecido e temos título e artista, tenta buscar a música oficial
        if not lyrics_browse_id and title:
            try:
                from scraper import clean_song_title
                cleaned = clean_song_title(title)
            except Exception:
                try:
                    from letrasbr_api.scraper import clean_song_title
                    cleaned = clean_song_title(title)
                except Exception:
                    cleaned = title
            query = f"{cleaned or title} {artist or ''}".strip()
            log(f"Tentando busca alternativa no YouTube Music para: '{query}'...")
            try:
                search_results = self.yt.search(query, filter="songs")
                if search_results:
                    best = pick_closest_duration(search_results, duration)
                    alt_video_id = best.get("videoId")
                    log(f"Versão de áudio alternativa encontrada: videoId='{alt_video_id}' (título: '{best.get('title')}', duração: {best.get('duration_seconds')}s)")
                    if alt_video_id and alt_video_id != video_id:
                        watch_data = self.yt.get_watch_playlist(videoId=alt_video_id)
                        lyrics_browse_id = watch_data.get("lyrics")
                        log(f"Lyrics ID da versão alternativa: '{lyrics_browse_id}'")
            except Exception as e:
                log(f"Erro ao buscar versão alternativa no YTM: {e}")

        if not lyrics_browse_id:
            log("Nenhum lyrics_browse_id disponível para esta faixa no YouTube Music.")
            return None

        try:
            log(f"Requisitando get_lyrics com timestamps=True para browseId='{lyrics_browse_id}'...")
            lyrics_data = self.yt.get_lyrics(lyrics_browse_id, timestamps=True)
            if lyrics_data and lyrics_data.get("hasTimestamps"):
                lines = lyrics_data.get("lyrics", [])
                log(f"Sucesso! {len(lines)} linhas temporizadas carregadas do YouTube Music.")
                return lines
            else:
                has_ts = lyrics_data.get("hasTimestamps") if lyrics_data else None
                log(f"Letra encontrada, mas hasTimestamps={has_ts} (sem sincronização temporal no YouTube Music).")
                return None
        except Exception as e:
            log(f"Erro ao obter get_lyrics: {e}")
            return None


def pick_closest_duration(results: List[dict], duration: Optional[float], top_n: int = 5, tolerance: float = 5.0) -> dict:
    """
    Entre os primeiros resultados da busca, escolhe o de duração mais próxima da faixa tocando.
    Sem duração conhecida (ou nenhum dentro da tolerância), mantém o primeiro resultado.
    """
    if not duration or duration <= 0:
        return results[0]
    timed = [r for r in results[:top_n] if r.get("duration_seconds")]
    if not timed:
        return results[0]
    best = min(timed, key=lambda r: abs(r["duration_seconds"] - duration))
    if abs(best["duration_seconds"] - duration) > tolerance:
        return results[0]
    return best


def find_active_line(lines: List, current_time_ms: int) -> Optional[object]:
    """
    Localiza a linha ativa com base no timestamp atual em milissegundos.
    """
    if not lines:
        return None

    active_line = None
    for line in lines:
        if line.start_time <= current_time_ms <= line.end_time:
            return line
        if line.start_time <= current_time_ms:
            active_line = line

    return active_line
