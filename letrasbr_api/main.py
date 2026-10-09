import os
import asyncio
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .aligner import find_active_aligned_line, AlignedLine
from .config import get_config, save_config
from .languages import DEFAULT_LANGUAGE, is_supported, normalize_lang, supported_codes_text
from .pipeline import fetch_and_align, LyricsResult
from .providers import ProviderFactory, TimedLine

logger = logging.getLogger(__name__)

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_lyrics_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="lyrics_fetch")

app = FastAPI(title="LetrasBR Tradutor API (Universal)", version="2.1.0")

# Permitir requisições de qualquer origem (extensões, páginas locais, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mobile_dir = os.path.join(root_dir, "mobile")
if os.path.exists(mobile_dir):
    app.mount("/mobile", StaticFiles(directory=mobile_dir, html=True), name="mobile")


@app.get("/")
def root_index():
    if os.path.exists(mobile_dir):
        return RedirectResponse(url="/mobile")
    return {"service": "LetrasBR API", "status": "running"}


class SyncPayload(BaseModel):
    title: str
    artist: str
    album: Optional[str] = None
    trackId: Optional[str] = None
    videoId: Optional[str] = None  # Mantido para 100% de retrocompatibilidade com extensões existentes
    currentTime: float  # em segundos
    duration: Optional[float] = None
    isPaused: Optional[bool] = False
    lang: Optional[str] = None  # ver languages.LANGUAGES
    source: Optional[str] = "ytmusic"  # 'ytmusic' ou 'spotify'


class LanguagePayload(BaseModel):
    lang: str  # ver languages.LANGUAGES


class PlayerActionPayload(BaseModel):
    action: str  # 'play_pause', 'next', 'previous', 'toggle_play'
    source: Optional[str] = None  # Se omitido, usa o provedor ativo


class PlaybackState:
    def __init__(self):
        self.song_key: Optional[str] = None
        self.title: str = ""
        self.artist: str = ""
        self.album: Optional[str] = None
        self.track_id: Optional[str] = None
        self.video_id: Optional[str] = None  # Alias para compatibilidade retroativa
        self.source: str = "ytmusic"
        self.lang: str = normalize_lang(get_config().get("lang", DEFAULT_LANGUAGE))  # Idioma padrão vindo da configuração
        self.timed_lyrics: List[TimedLine] = []
        self.aligned_lyrics: List[AlignedLine] = []
        self.translation_url: Optional[str] = None
        self.translation_source: str = "none"  # letras | auto | mixed | original | none
        self.timing_source: str = "none"       # ytmusic | lrclib | estimated | none
        self.last_line_key: Optional[Any] = None
        self.current_time_ms: int = 0
        self.active_original: str = ""
        self.active_translation: str = ""
        self.last_sync_log_time: float = 0
        self.is_paused: bool = False
        self.current_seconds: float = 0.0
        self.duration_seconds: float = 0.0
        self.is_fetching: bool = False
        self.fetch_generation: int = 0  # Incrementa a cada nova faixa para cancelar fetches anteriores


state = PlaybackState()


def queue_command(action: str, source: Optional[str] = None):
    """Enfileira um comando para ser executado pelo player ativo através do seu Adapter."""
    target_source = source or state.source or "ytmusic"
    provider = ProviderFactory.get_provider(target_source)
    provider.queue_command(action)
    logger.info(f"🎮 Comando enviado para o player [{provider.provider_id.upper()}]: {action.upper()}")


def now_str() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def format_timestamp(ms: int) -> str:
    total_seconds = int(ms / 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"[{minutes:02d}:{seconds:02d}]"


def _apply_result(result: LyricsResult):
    state.timed_lyrics = result.timed_lyrics
    state.aligned_lyrics = result.aligned
    state.translation_url = result.translation_url
    state.translation_source = result.translation_source
    state.timing_source = result.timing_source


def _do_fetch_lyrics_sync(
    title: str,
    artist: str,
    track_id: Optional[str],
    lang: Optional[str] = None,
    source: str = "ytmusic",
    album: Optional[str] = None,
    duration: Optional[float] = None,
    generation: int = 0
):
    is_current = lambda: state.fetch_generation == generation
    if not is_current():
        logger.info(f"⏹️ Fetch obsoleto antes do início (geração {generation} vs atual {state.fetch_generation}). Descartando.")
        return

    provider = ProviderFactory.get_provider(source)
    active_lang = normalize_lang(lang or state.lang or DEFAULT_LANGUAGE)
    logger.info(f"🌐 Idioma: {active_lang.upper()} | Track ID: {track_id or 'n/a'} (gen={generation})")

    result = fetch_and_align(
        title=title,
        artist=artist,
        album=album,
        duration=duration,
        lang=active_lang,
        source="spotify" if provider.provider_id == "spotify" else "ytmusic",
        track_id=track_id,
        auto_translate=bool(get_config().get("autoTranslate", True)),
        is_current=is_current,
    )

    # Atribui ao estado apenas se ainda somos a geração atual
    if result is None or not is_current():
        logger.info(f"⏹️ Fetch obsoleto (geração {generation} vs atual {state.fetch_generation}). Descartando.")
        return

    _apply_result(result)
    logger.info(f"✅ {len(result.aligned)} versos alinhados (letra: {result.timing_source}, tradução: {result.translation_source}).")
    logger.info("⏳ Sincronização ao vivo ativada. Aguardando reprodução...")


def _reset_state_for_new_track(
    title: str, artist: str, track_id: Optional[str],
    lang: Optional[str], source: str, album: Optional[str],
    duration: Optional[float]
):
    """Reseta o estado imediatamente quando uma nova faixa é detectada (sem bloquear)."""
    if lang:
        state.lang = normalize_lang(lang)
    state.title = title
    state.artist = artist
    state.album = album
    state.track_id = track_id
    state.video_id = track_id
    state.source = source
    state.last_line_key = None
    state.aligned_lyrics = []
    state.timed_lyrics = []
    state.translation_url = None
    state.translation_source = "none"
    state.timing_source = "none"
    state.active_original = ""
    state.active_translation = ""
    state.is_fetching = True
    state.fetch_generation += 1

    provider = ProviderFactory.get_provider(source)
    song_id = f"{provider.provider_id}|||{artist.strip()}|||{title.strip()}"
    if track_id:
        song_id += f"|||{track_id.strip()}"
    state.song_key = f"{song_id}|||{state.lang.strip()}"

    logger.info(f"NOVA FAIXA [{provider.provider_id.upper()}]: {artist} - {title}")
    logger.info("Buscando letras em background... (não bloqueante)")


async def _fetch_lyrics_background(
    title: str, artist: str, track_id: Optional[str],
    lang: str, source: str, album: Optional[str],
    duration: Optional[float], generation: int
):
    """Executa a busca de letras em thread separada sem bloquear o event loop."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            _lyrics_executor,
            lambda: _do_fetch_lyrics_sync(
                title, artist, track_id, lang, source, album, duration, generation
            )
        )
    except Exception as e:
        logger.warning(f"ERRO no fetch de letras em background: {e}")
    finally:
        # Só marca como concluído se ainda somos a geração atual
        if state.fetch_generation == generation:
            state.is_fetching = False
            logger.info(f"Letras carregadas! {len(state.aligned_lyrics)} versos alinhados.")


@app.post("/api/sync")
async def sync_playback(payload: SyncPayload, request: Request):
    effective_track_id = payload.trackId or payload.videoId
    effective_source = payload.source or "ytmusic"
    provider = ProviderFactory.get_provider(effective_source)

    song_id = f"{provider.provider_id}|||{payload.artist.strip()}|||{payload.title.strip()}"
    if effective_track_id:
        song_id += f"|||{effective_track_id.strip()}"

    active_lang = normalize_lang(payload.lang or state.lang or DEFAULT_LANGUAGE)
    new_key = f"{song_id}|||{active_lang}"
    is_new_song = (new_key != state.song_key)

    # Mudança de faixa — reseta imediatamente e busca em background
    if is_new_song:
        _reset_state_for_new_track(
            title=payload.title,
            artist=payload.artist,
            track_id=effective_track_id,
            lang=active_lang,
            source=effective_source,
            album=payload.album,
            duration=payload.duration
        )
        # Inicia busca não-bloqueante
        asyncio.create_task(_fetch_lyrics_background(
            title=payload.title,
            artist=payload.artist,
            track_id=effective_track_id,
            lang=active_lang,
            source=effective_source,
            album=payload.album,
            duration=payload.duration,
            generation=state.fetch_generation
        ))

    # Atualiza o timestamp atual e estado do player
    current_ms = int(payload.currentTime * 1000)
    state.current_time_ms = current_ms
    state.current_seconds = payload.currentTime
    state.is_paused = bool(payload.isPaused)
    if payload.duration:
        state.duration_seconds = payload.duration

    # Consome comando pendente do adapter se houver (para ser executado pelo player)
    pending_cmd = provider.pop_pending_command()

    # Se pausado, não busca nova linha mas ainda entrega comandos se houver
    if payload.isPaused:
        res = {
            "status": "paused",
            "title": state.title,
            "artist": state.artist,
            "lang": state.lang,
            "source": provider.provider_id
        }
        if pending_cmd:
            res["command"] = pending_cmd
        return res

    # Se ainda buscando letras, retorna status de carregando
    if state.is_fetching and not state.aligned_lyrics:
        res = {
            "status": "loading",
            "title": state.title,
            "artist": state.artist,
            "lang": state.lang,
            "source": provider.provider_id,
            "activeOriginal": state.title,
            "activeTranslation": "Buscando letras...",
        }
        if pending_cmd:
            res["command"] = pending_cmd
        return res

    # Busca em tempo real O(1) diretamente na lista pré-alinhada
    active_line = find_active_aligned_line(state.aligned_lyrics, current_ms)
    if active_line:
        line_key = (active_line.start_time, active_line.original)
        if line_key != state.last_line_key:
            state.last_line_key = line_key
            state.active_original = active_line.original
            state.active_translation = active_line.translation

            # Exibe no terminal formatado conforme solicitado
            ts = format_timestamp(active_line.start_time)
            logger.info(f"{ts} {active_line.original} => {active_line.translation}")

    res = {
        "status": "ok",
        "title": state.title,
        "artist": state.artist,
        "lang": state.lang,
        "source": provider.provider_id,
        "currentTime": payload.currentTime,
        "activeOriginal": state.active_original,
        "activeTranslation": state.active_translation,
    }
    if pending_cmd:
        res["command"] = pending_cmd
    return res


def change_language_internal(new_lang: str):
    """Altera o idioma de tradução, salva na configuração e re-sincroniza a música atual."""
    new_lang = normalize_lang(new_lang)
    if not is_supported(new_lang):
        return False

    old_lang = state.lang
    state.lang = new_lang
    save_config({"lang": new_lang})
    logger.info(f"🔄 Alterando idioma de '{old_lang.upper()}' para '{new_lang.upper()}'...")

    if state.title and state.artist:
        provider = ProviderFactory.get_provider(state.source)
        song_id = f"{provider.provider_id}|||{state.artist.strip()}|||{state.title.strip()}"
        effective_id = state.track_id or state.video_id
        if effective_id:
            song_id += f"|||{effective_id.strip()}"
        state.song_key = f"{song_id}|||{new_lang}"

        # Reaproveita a letra sincronizada já carregada; só refaz tradução e alinhamento
        result = fetch_and_align(
            title=state.title,
            artist=state.artist,
            album=state.album,
            duration=state.duration_seconds,
            lang=new_lang,
            source="spotify" if provider.provider_id == "spotify" else "ytmusic",
            track_id=effective_id,
            auto_translate=bool(get_config().get("autoTranslate", True)),
            timed_lyrics=state.timed_lyrics or None,
        )
        _apply_result(result)
        state.last_line_key = None

        # Reencontra a linha ativa no tempo atual para atualização imediata
        active_line = find_active_aligned_line(state.aligned_lyrics, state.current_time_ms)
        if active_line:
            state.active_original = active_line.original
            state.active_translation = active_line.translation
            ts = format_timestamp(active_line.start_time)
            logger.info(f"✅ Tradução atualizada ({new_lang.upper()}): {ts} {active_line.original} => {active_line.translation}")

    return True


@app.post("/api/language")
def change_language(payload: LanguagePayload):
    """Altera o idioma de busca da tradução ('pt', 'fr', 'en', 'es') e re-sincroniza a música atual."""
    new_lang = normalize_lang(payload.lang)
    if not change_language_internal(new_lang):
        return {"status": "error", "message": f"Idioma '{new_lang}' não suportado. Opções válidas: {supported_codes_text()}."}

    return {
        "status": "ok",
        "language": state.lang,
        "url": state.translation_url,
        "verses": len(state.aligned_lyrics)
    }


@app.get("/api/config")
def api_get_config():
    """Retorna a configuração atual do overlay e preferências."""
    return get_config()


@app.post("/api/config")
def api_set_config(cfg: Dict[str, Any]):
    """Atualiza as configurações (opacidade, tamanho da fonte, idioma, modo, etc.)."""
    if "lang" in cfg and cfg["lang"]:
        new_lang = normalize_lang(str(cfg["lang"]))
        if is_supported(new_lang) and new_lang != state.lang:
            change_language_internal(new_lang)

    save_config(cfg)
    return {"status": "ok", "config": get_config()}


@app.post("/api/player/action")
def api_player_action(payload: PlayerActionPayload):
    """Envia um comando para o player ativo (play_pause, next, toggle_play)."""
    action = payload.action.lower().strip()
    if action not in ["play_pause", "next", "previous", "toggle_play"]:
        return {"status": "error", "message": f"Ação '{action}' desconhecida. Use 'play_pause', 'next' ou 'previous'."}
    queue_command(action, source=payload.source)
    return {"status": "ok", "action": action, "source": payload.source or state.source}


def reset_playback_state():
    """Reseta o estado da reprodução quando uma sessão é encerrada pelo cliente."""
    state.song_key = None
    state.title = ""
    state.artist = ""
    state.album = None
    state.track_id = None
    state.video_id = None
    state.timed_lyrics = []
    state.aligned_lyrics = []
    state.translation_url = None
    state.translation_source = "none"
    state.timing_source = "none"
    state.last_line_key = None
    state.current_time_ms = 0
    state.active_original = ""
    state.active_translation = ""
    state.is_paused = True
    state.current_seconds = 0.0
    state.duration_seconds = 0.0
    state.is_fetching = False
    state.fetch_generation += 1
    logger.info("⏹️ Sessão de reprodução encerrada pelo cliente. Estado resetado.")


@app.post("/api/playback/clear")
@app.post("/api/playback/stop")
@app.post("/api/reset")
def api_playback_clear():
    """Limpa o estado atual de reprodução no servidor (chamado ao fechar o app/overlay)."""
    reset_playback_state()
    return {"status": "ok", "message": "Playback state cleared successfully"}


@app.get("/api/current")
def get_current():
    return {
        "title": state.title,
        "artist": state.artist,
        "album": state.album,
        "videoId": state.video_id,
        "trackId": state.track_id,
        "source": state.source,
        "lang": state.lang,
        "currentTimeMs": state.current_time_ms,
        "currentSeconds": state.current_seconds,
        "durationSeconds": state.duration_seconds,
        "isPaused": state.is_paused,
        "activeOriginal": state.active_original,
        "activeTranslation": state.active_translation,
        "translationUrl": state.translation_url,
        "hasTimedLyrics": len(state.timed_lyrics) > 0,
        "hasTranslation": state.translation_source in ("letras", "auto", "mixed"),
        "translationSource": state.translation_source,
        "timingSource": state.timing_source,
        "hasAlignedLyrics": len(state.aligned_lyrics) > 0,
    }


@app.get("/api/health")
def health():
    logger.debug("Verificação de saúde recebida (API OK).")
    return {
        "status": "running",
        "service": "letrasbr_api",
        "source": state.source,
        "lang": state.lang,
        "time": now_str()
    }
