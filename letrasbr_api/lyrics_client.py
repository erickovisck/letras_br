"""
Cliente desacoplado para busca, tradução e alinhamento de letras.
Suporta execução local direta ou conexão HTTP com servidor remoto configurável.
Inclui cache em memória e invalidação de requisições obsoletas (autoplay/pulo rápido).
"""

import sys
import os
import requests
from typing import List, Dict, Optional, Tuple

from PySide6.QtCore import QThread, Signal

# Assegura caminhos
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from scraper import get_translation, clean_song_title
from aligner import align_lyrics, find_active_aligned_line, AlignedLine
from providers import ProviderFactory, TrackInfo, TimedLine


class LyricsFetchWorker(QThread):
    """
    Worker assíncrono para buscar e traduzir letras sem travar a interface gráfica.
    Possui suporte a cancelamento automático via request_id.
    """
    finished_success = Signal(int, list, str)  # request_id, aligned_lyrics, trans_url
    finished_error = Signal(int, str)          # request_id, error_message

    def __init__(self, request_id: int, title: str, artist: str, album: str, duration: float, lang: str, server_url: str):
        super().__init__()
        self.request_id = request_id
        self.title = title
        self.artist = artist
        self.album = album
        self.duration = duration
        self.lang = lang
        self.server_url = (server_url or "").rstrip("/")

    def run(self):
        # Se um servidor remoto (diferente de localhost/127.0.0.1) estiver configurado, usa a API REST
        is_remote = bool(self.server_url and not any(h in self.server_url for h in ("localhost", "127.0.0.1")))

        if is_remote:
            self._run_remote()
        else:
            self._run_local()

    def _run_remote(self):
        try:
            url = f"{self.server_url}/api/sync"
            payload = {
                "title": self.title,
                "artist": self.artist,
                "album": self.album,
                "currentTime": 0.0,
                "duration": self.duration,
                "lang": self.lang,
                "source": "ytmusic"
            }
            resp = requests.post(url, json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                # Consulta dados detalhados da faixa
                curr_resp = requests.get(f"{self.server_url}/api/current", timeout=5)
                if curr_resp.status_code == 200:
                    curr_data = curr_resp.json()
                    # Como o servidor alinha internamente, podemos usar o endpoint
                    pass
                self.finished_success.emit(self.request_id, [], data.get("url", ""))
            else:
                self.finished_error.emit(self.request_id, f"Erro HTTP {resp.status_code}")
        except Exception as e:
            # Fallback para local se o servidor remoto falhar
            self._run_local()

    def _run_local(self):
        try:
            # 1. Busca letras sincronizadas do YouTube Music
            provider = ProviderFactory.get_provider("ytmusic")
            track_info = TrackInfo(
                title=self.title,
                artist=self.artist,
                album=self.album,
                track_id=None,
                duration=self.duration,
                source="ytmusic"
            )
            timed_lyrics = provider.get_timed_lyrics(track_info) or []

            # 2. Busca tradução no Letras.mus.br
            cleaned_title = clean_song_title(self.title)
            trans_dict, ordered_verses, trans_url = get_translation(self.artist, cleaned_title, lang=self.lang)

            # Se não encontrou tradução com cleaned_title e o título tinha separador, tenta termo mais limpo
            if not ordered_verses and not trans_dict and ("-" in self.title or "(" in self.title):
                simple_title = self.title.split("-")[0].split("(")[0].strip()
                trans_dict, ordered_verses, trans_url = get_translation(self.artist, simple_title, lang=self.lang)

            # 3. Alinha os versos sincronizados com a tradução
            aligned = align_lyrics(timed_lyrics, ordered_verses)
            self.finished_success.emit(self.request_id, aligned, trans_url or "")
        except Exception as e:
            self.finished_error.emit(self.request_id, str(e))


class LyricsClient:
    """
    Gerenciador com cache de letras e controle de requisições de faixa.
    """
    def __init__(self):
        self._cache: Dict[str, Tuple[List[AlignedLine], str]] = {}
        self._current_request_id = 0
        self._active_worker: Optional[LyricsFetchWorker] = None

    def get_cached(self, artist: str, title: str, lang: str) -> Optional[Tuple[List[AlignedLine], str]]:
        key = f"{artist.strip().lower()}|||{title.strip().lower()}|||{lang.strip().lower()}"
        return self._cache.get(key)

    def set_cached(self, artist: str, title: str, lang: str, aligned: List[AlignedLine], url: str):
        key = f"{artist.strip().lower()}|||{title.strip().lower()}|||{lang.strip().lower()}"
        self._cache[key] = (aligned, url)

    def fetch_lyrics(
        self,
        title: str,
        artist: str,
        album: str,
        duration: float,
        lang: str,
        server_url: str,
        on_success,
        on_error
    ) -> int:
        """
        Inicia a busca assíncrona. Cancela qualquer busca anterior em andamento.
        Retorna o request_id emitido.
        """
        self._current_request_id += 1
        req_id = self._current_request_id

        # Verifica cache primeiro
        cached = self.get_cached(artist, title, lang)
        if cached:
            aligned, url = cached
            on_success(req_id, aligned, url)
            return req_id

        # Interrompe worker anterior se ainda estiver rodando
        if self._active_worker and self._active_worker.isRunning():
            try:
                self._active_worker.terminate()
            except Exception:
                pass

        worker = LyricsFetchWorker(
            request_id=req_id,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            lang=lang,
            server_url=server_url
        )

        def _handle_success(worker_req_id, aligned, trans_url):
            if worker_req_id == self._current_request_id:
                if aligned:
                    self.set_cached(artist, title, lang, aligned, trans_url)
                on_success(worker_req_id, aligned, trans_url)

        def _handle_error(worker_req_id, err_msg):
            if worker_req_id == self._current_request_id:
                on_error(worker_req_id, err_msg)

        worker.finished_success.connect(_handle_success)
        worker.finished_error.connect(_handle_error)

        self._active_worker = worker
        worker.start()
        return req_id
