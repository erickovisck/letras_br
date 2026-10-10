"""
Cliente do overlay para busca, tradução e alinhamento de letras em segundo plano.
Inclui cache em memória e invalidação de requisições obsoletas (autoplay/pulo rápido).
"""

from typing import Dict, Optional, Set

from PySide6.QtCore import QThread, Signal

from .pipeline import fetch_and_align, LyricsResult


class LyricsFetchWorker(QThread):
    """
    Worker assíncrono para buscar e traduzir letras sem travar a interface gráfica.
    Resultados de requisições antigas são descartados pelo request_id.
    """
    finished_success = Signal(int, object)  # request_id, LyricsResult
    finished_error = Signal(int, str)       # request_id, error_message

    def __init__(self, request_id: int, title: str, artist: str, album: str, duration: float,
                 lang: str, source: str, auto_translate: bool, track_id: Optional[str] = None):
        super().__init__()
        self.request_id = request_id
        self.title = title
        self.artist = artist
        self.album = album
        self.duration = duration
        self.lang = lang
        self.source = source
        self.auto_translate = auto_translate
        self.track_id = track_id

    def run(self):
        try:
            result = fetch_and_align(
                title=self.title,
                artist=self.artist,
                album=self.album,
                duration=self.duration,
                lang=self.lang,
                source=self.source,
                track_id=self.track_id,
                auto_translate=self.auto_translate,
            )
            self.finished_success.emit(self.request_id, result)
        except Exception as e:
            self.finished_error.emit(self.request_id, str(e))


class LyricsClient:
    """
    Gerenciador com cache de letras e controle de requisições de faixa.
    """
    def __init__(self):
        self._cache: Dict[str, LyricsResult] = {}
        self._current_request_id = 0
        # Mantém referência aos workers em execução até terminarem (um QThread não pode ser
        # destruído rodando). Workers obsoletos terminam normalmente e têm o resultado ignorado.
        self._workers: Set[LyricsFetchWorker] = set()

    @staticmethod
    def _key(artist: str, title: str, lang: str, auto_translate: bool) -> str:
        return f"{artist.strip().lower()}|||{title.strip().lower()}|||{lang.strip().lower()}|||{int(auto_translate)}"

    def invalidate(self, artist: str, title: str):
        """Descarta do cache todas as versões (idiomas) desta música."""
        prefix = f"{artist.strip().lower()}|||{title.strip().lower()}|||"
        for key in [k for k in self._cache if k.startswith(prefix)]:
            del self._cache[key]

    def fetch_lyrics(
        self,
        title: str,
        artist: str,
        album: str,
        duration: float,
        lang: str,
        on_success,
        on_error,
        source: str = "youtube",
        auto_translate: bool = True,
        track_id: Optional[str] = None
    ) -> int:
        """
        Inicia a busca assíncrona; qualquer busca anterior em andamento passa a ser ignorada.
        on_success(request_id, LyricsResult) / on_error(request_id, mensagem).
        Retorna o request_id emitido.
        """
        self._current_request_id += 1
        req_id = self._current_request_id

        key = self._key(artist, title, lang, auto_translate)
        cached = self._cache.get(key)
        if cached:
            on_success(req_id, cached)
            return req_id

        worker = LyricsFetchWorker(
            request_id=req_id,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            lang=lang,
            source=source,
            auto_translate=auto_translate,
            track_id=track_id
        )

        def _handle_success(worker_req_id, result):
            if result and result.aligned:
                self._cache[key] = result
            if worker_req_id == self._current_request_id:
                on_success(worker_req_id, result)

        def _handle_error(worker_req_id, err_msg):
            if worker_req_id == self._current_request_id:
                on_error(worker_req_id, err_msg)

        worker.finished_success.connect(_handle_success)
        worker.finished_error.connect(_handle_error)
        worker.finished.connect(lambda: self._workers.discard(worker))

        self._workers.add(worker)
        worker.start()
        return req_id
