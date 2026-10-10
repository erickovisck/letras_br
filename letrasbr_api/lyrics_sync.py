import logging
from typing import List, Optional

from .scraper import clean_song_title

logger = logging.getLogger(__name__)

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
    logger.warning(f"ytmusicapi nao instalado: {_ytm_err}")



class YTMManager:
    def __init__(self):
        self._available = False
        self.yt = None
        try:
            logger.info("Inicializando cliente YTMusic...")
            self.yt = YTMusic()
            self._available = True
            logger.info("Cliente YTMusic inicializado com sucesso.")
        except Exception as e:
            logger.warning(f"Nao foi possivel inicializar YTMusic: {e}")
            logger.info("Letras sincronizadas do YouTube Music nao estarao disponiveis.")

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
            logger.info("ytmusicapi indisponivel — retornando None.")
            return None

        lyrics_browse_id = None

        if video_id:
            try:
                logger.info(f"Consultando get_watch_playlist para videoId='{video_id}'...")
                watch_data = self.yt.get_watch_playlist(videoId=video_id)
                lyrics_browse_id = watch_data.get("lyrics")
                logger.info(f"Resultado do watch_playlist: lyrics_browse_id = '{lyrics_browse_id}'")
            except Exception as e:
                logger.warning(f"Erro ao obter watch_playlist para {video_id}: {e}")

        # Se não encontrou letras no video_id fornecido e temos título e artista, tenta buscar a música oficial
        if not lyrics_browse_id and title:
            cleaned = clean_song_title(title)
            query = f"{cleaned or title} {artist or ''}".strip()
            logger.info(f"Tentando busca alternativa no YouTube Music para: '{query}'...")
            try:
                search_results = self.yt.search(query, filter="songs")
                if search_results:
                    best = pick_closest_duration(search_results, duration)
                    alt_video_id = best.get("videoId")
                    logger.info(f"Versão de áudio alternativa encontrada: videoId='{alt_video_id}' (título: '{best.get('title')}', duração: {best.get('duration_seconds')}s)")
                    if alt_video_id and alt_video_id != video_id:
                        watch_data = self.yt.get_watch_playlist(videoId=alt_video_id)
                        lyrics_browse_id = watch_data.get("lyrics")
                        logger.info(f"Lyrics ID da versão alternativa: '{lyrics_browse_id}'")
            except Exception as e:
                logger.warning(f"Erro ao buscar versão alternativa no YTM: {e}")

        if not lyrics_browse_id:
            logger.warning("Nenhum lyrics_browse_id disponível para esta faixa no YouTube Music.")
            return None

        try:
            logger.info(f"Requisitando get_lyrics com timestamps=True para browseId='{lyrics_browse_id}'...")
            lyrics_data = self.yt.get_lyrics(lyrics_browse_id, timestamps=True)
            if lyrics_data and lyrics_data.get("hasTimestamps"):
                lines = lyrics_data.get("lyrics", [])
                logger.info(f"Sucesso! {len(lines)} linhas temporizadas carregadas do YouTube Music.")
                return lines
            else:
                has_ts = lyrics_data.get("hasTimestamps") if lyrics_data else None
                logger.info(f"Letra encontrada, mas hasTimestamps={has_ts} (sem sincronização temporal no YouTube Music).")
                return None
        except Exception as e:
            logger.warning(f"Erro ao obter get_lyrics: {e}")
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
