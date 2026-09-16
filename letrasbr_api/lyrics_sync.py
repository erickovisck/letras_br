import sys
import os
from typing import List, Optional

from ytmusicapi import YTMusic
from ytmusicapi.models.lyrics import LyricLine


def log(msg: str):
    try:
        print(f"[YTM] {msg}")
    except Exception:
        safe = str(msg).encode("ascii", "replace").decode("ascii")
        print(f"[YTM] {safe}")


class YTMManager:
    def __init__(self):
        log("Inicializando cliente YTMusic...")
        self.yt = YTMusic()
        log("Cliente YTMusic inicializado com sucesso.")

    def get_timed_lyrics(self, video_id: str, title: Optional[str] = None, artist: Optional[str] = None) -> Optional[List[LyricLine]]:
        """
        Obtém as letras temporizadas do YouTube Music usando ytmusicapi.
        Se o videoId direto não tiver letras, tenta buscar pelo título e artista
        para pegar a versão oficial da faixa de áudio.
        """
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
            query = f"{title} {artist or ''}".strip()
            log(f"Tentando busca alternativa no YouTube Music para: '{query}'...")
            try:
                search_results = self.yt.search(query, filter="songs")
                if search_results:
                    alt_video_id = search_results[0].get("videoId")
                    log(f"Versão de áudio alternativa encontrada: videoId='{alt_video_id}' (título: '{search_results[0].get('title')}')")
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


def find_active_line(lines: List[LyricLine], current_time_ms: int) -> Optional[LyricLine]:
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
