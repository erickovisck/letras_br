import os
import sys
import datetime
from typing import Optional, List, Dict, Any

# Configura codificação UTF-8 no Windows para evitar UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

# Garante acesso aos módulos internos
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

root_dir = os.path.abspath(os.path.join(current_dir, ".."))

from scraper import get_translation, clean_song_title
from aligner import align_lyrics, find_active_aligned_line, AlignedLine
from config import get_config, save_config
from providers import ProviderFactory, TrackInfo, TimedLine

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
    lang: Optional[str] = None  # 'pt', 'fr', 'en', 'es'
    source: Optional[str] = "ytmusic"  # 'ytmusic' ou 'spotify'


class LanguagePayload(BaseModel):
    lang: str  # 'pt', 'fr', 'en', 'es'


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
        self.lang: str = get_config().get("lang", "pt")  # Idioma padrão vindo da configuração
        self.timed_lyrics: List[TimedLine] = []
        self.ordered_verses: List[Dict[str, Any]] = []
        self.aligned_lyrics: List[AlignedLine] = []
        self.translation_dict: Dict[str, str] = {}
        self.translation_url: Optional[str] = None
        self.last_line_key: Optional[Any] = None
        self.current_time_ms: int = 0
        self.active_original: str = ""
        self.active_translation: str = ""
        self.last_sync_log_time: float = 0
        self.is_paused: bool = False
        self.current_seconds: float = 0.0
        self.duration_seconds: float = 0.0


state = PlaybackState()


def queue_command(action: str, source: Optional[str] = None):
    """Enfileira um comando para ser executado pelo player ativo através do seu Adapter."""
    target_source = source or state.source or "ytmusic"
    provider = ProviderFactory.get_provider(target_source)
    provider.queue_command(action)
    safe_print(f"[{now_str()}] 🎮 Comando enviado para o player [{provider.provider_id.upper()}]: {action.upper()}")


def now_str() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def format_timestamp(ms: int) -> str:
    total_seconds = int(ms / 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"[{minutes:02d}:{seconds:02d}]"


def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        cleaned_args = [str(a).encode("ascii", "replace").decode("ascii") for a in args]
        print(*cleaned_args, **kwargs)


def update_current_track(
    title: str,
    artist: str,
    track_id: Optional[str],
    lang: Optional[str] = None,
    source: str = "ytmusic",
    album: Optional[str] = None,
    duration: Optional[float] = None
):
    if lang:
        state.lang = lang.lower().strip()

    state.title = title
    state.artist = artist
    state.album = album
    state.track_id = track_id
    state.video_id = track_id  # Mantém compatibilidade com clientes que consultam videoId
    state.source = source
    state.last_line_key = None
    state.aligned_lyrics = []

    provider = ProviderFactory.get_provider(source)

    song_id = f"{provider.provider_id}|||{artist.strip()}|||{title.strip()}"
    if track_id:
        song_id += f"|||{track_id.strip()}"
    state.song_key = f"{song_id}|||{state.lang.strip()}"

    safe_print("\n" + "=" * 70)
    safe_print(f"[{now_str()}] 🎵 NOVA FAIXA DETECTADA [{provider.provider_id.upper()}]: {artist} - {title}")
    if track_id:
        safe_print(f"[{now_str()}] 🔗 Track ID: {track_id}")
    safe_print(f"[{now_str()}] 🌐 Idioma selecionado: {state.lang.upper()}")
    safe_print("=" * 70)

    # 1. Busca letras sincronizadas através do Provider Adapter
    safe_print(f"[{now_str()}] [1/3] 🔍 Buscando letras sincronizadas no provedor '{provider.provider_id.upper()}'...")
    track_info = TrackInfo(
        title=title,
        artist=artist,
        album=album,
        track_id=track_id,
        duration=duration,
        source=provider.provider_id
    )
    state.timed_lyrics = provider.get_timed_lyrics(track_info) or []
    if state.timed_lyrics:
        safe_print(f"[{now_str()}] ✅ [{provider.provider_id.upper()}] {len(state.timed_lyrics)} versos com timestamps carregados!")
    else:
        safe_print(f"[{now_str()}] ⚠️ [{provider.provider_id.upper()}] Nenhuma letra sincronizada encontrada para esta faixa.")

    # 2. Busca tradução no Letras.mus.br no idioma configurado
    safe_print(f"[{now_str()}] [2/3] 🌐 Buscando tradução ({state.lang.upper()}) verso a verso no Letras.mus.br...")
    cleaned_title = clean_song_title(title)
    trans_dict, ordered_verses, trans_url = get_translation(artist, cleaned_title, lang=state.lang)
    state.translation_dict = trans_dict
    state.ordered_verses = ordered_verses
    state.translation_url = trans_url

    if ordered_verses or trans_dict:
        safe_print(f"[{now_str()}] ✅ [LETRAS] {len(trans_dict)} versos traduzidos ({state.lang.upper()}) carregados com sucesso!")
        safe_print(f"[{now_str()}] 🌐 Link: {trans_url}")
    else:
        safe_print(f"[{now_str()}] ⚠️ [LETRAS] Não foi possível carregar a tradução de '{cleaned_title}'.")

    # 3. Pré-alinhamento global de todos os versos (atribuição antecipada e preenchimento de lacunas)
    safe_print(f"[{now_str()}] [3/3] ⚙️ Executando pré-alinhamento global e preenchimento de lacunas...")
    state.aligned_lyrics = align_lyrics(state.timed_lyrics, ordered_verses, title=title, artist=artist, lang=state.lang)
    safe_print(f"[{now_str()}] ✅ {len(state.aligned_lyrics)} versos alinhados e prontos com latência zero!")

    safe_print("-" * 70)
    safe_print(f"[{now_str()}] ⏳ Sincronização ao vivo ativada. Aguardando reprodução...\n")


@app.post("/api/sync")
def sync_playback(payload: SyncPayload, request: Request):
    effective_track_id = payload.trackId or payload.videoId
    effective_source = payload.source or "ytmusic"
    provider = ProviderFactory.get_provider(effective_source)

    song_id = f"{provider.provider_id}|||{payload.artist.strip()}|||{payload.title.strip()}"
    if effective_track_id:
        song_id += f"|||{effective_track_id.strip()}"

    active_lang = state.lang
    new_key = f"{song_id}|||{active_lang}"
    is_new_song = (new_key != state.song_key)

    # Mudança de faixa
    if is_new_song:
        update_current_track(
            title=payload.title,
            artist=payload.artist,
            track_id=effective_track_id,
            lang=active_lang,
            source=effective_source,
            album=payload.album,
            duration=payload.duration
        )

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
            safe_print(f"[{now_str()}] {ts} {active_line.original} => {active_line.translation}")

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
    new_lang = new_lang.lower().strip()
    if new_lang not in ["pt", "fr", "en", "es"]:
        return False

    old_lang = state.lang
    state.lang = new_lang
    save_config({"lang": new_lang})
    safe_print(f"\n[{now_str()}] 🔄 Alterando idioma de '{old_lang.upper()}' para '{new_lang.upper()}'...")

    if state.title and state.artist:
        provider = ProviderFactory.get_provider(state.source)
        song_id = f"{provider.provider_id}|||{state.artist.strip()}|||{state.title.strip()}"
        effective_id = state.track_id or state.video_id
        if effective_id:
            song_id += f"|||{effective_id.strip()}"
        state.song_key = f"{song_id}|||{new_lang}"

        # 1. Se ainda não temos letras com timestamps, busca pelo adapter do provedor
        if not state.timed_lyrics:
            safe_print(f"[{now_str()}] [1/2] 🔍 Buscando letras sincronizadas no provedor '{provider.provider_id.upper()}'...")
            track_info = TrackInfo(
                title=state.title,
                artist=state.artist,
                album=state.album,
                track_id=effective_id,
                duration=state.duration_seconds,
                source=provider.provider_id
            )
            state.timed_lyrics = provider.get_timed_lyrics(track_info) or []

        # 2. Busca tradução no novo idioma
        safe_print(f"[{now_str()}] [1/2] 🌐 Buscando tradução ({new_lang.upper()}) verso a verso no Letras.mus.br...")
        cleaned_title = clean_song_title(state.title)
        trans_dict, ordered_verses, trans_url = get_translation(state.artist, cleaned_title, lang=new_lang)
        state.translation_dict = trans_dict
        state.ordered_verses = ordered_verses
        state.translation_url = trans_url

        if ordered_verses or trans_dict:
            safe_print(f"[{now_str()}] ✅ [LETRAS] {len(trans_dict)} versos traduzidos ({new_lang.upper()}) carregados com sucesso!")
            safe_print(f"[{now_str()}] 🌐 Link: {trans_url}")
        else:
            safe_print(f"[{now_str()}] ⚠️ [LETRAS] Não foi possível carregar a tradução de '{cleaned_title}'.")

        # 3. Re-alinha os versos
        safe_print(f"[{now_str()}] [2/2] ⚙️ Re-alinhando versos no idioma {new_lang.upper()}...")
        state.aligned_lyrics = align_lyrics(state.timed_lyrics, ordered_verses, title=state.title, artist=state.artist, lang=new_lang)
        state.last_line_key = None

        # Reencontra a linha ativa no tempo atual para atualização imediata
        active_line = find_active_aligned_line(state.aligned_lyrics, state.current_time_ms)
        if active_line:
            state.active_original = active_line.original
            state.active_translation = active_line.translation
            ts = format_timestamp(active_line.start_time)
            safe_print(f"[{now_str()}] ✅ Tradução atualizada ({new_lang.upper()}): {ts} {active_line.original} => {active_line.translation}")

    return True


@app.post("/api/language")
def change_language(payload: LanguagePayload):
    """Altera o idioma de busca da tradução ('pt', 'fr', 'en', 'es') e re-sincroniza a música atual."""
    new_lang = payload.lang.lower().strip()
    if not change_language_internal(new_lang):
        return {"status": "error", "message": f"Idioma '{new_lang}' não suportado. Opções válidas: pt, fr, en, es."}

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
        new_lang = str(cfg["lang"]).lower().strip()
        if new_lang in ["pt", "fr", "en", "es"] and new_lang != state.lang:
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
    state.ordered_verses = []
    state.aligned_lyrics = []
    state.translation_dict = {}
    state.translation_url = None
    state.last_line_key = None
    state.current_time_ms = 0
    state.active_original = ""
    state.active_translation = ""
    state.is_paused = True
    state.current_seconds = 0.0
    state.duration_seconds = 0.0
    safe_print(f"[{now_str()}] ⏹️ Sessão de reprodução encerrada pelo cliente. Estado resetado.")


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
        "hasTranslation": len(state.translation_dict) > 0,
        "hasAlignedLyrics": len(state.aligned_lyrics) > 0,
    }


@app.get("/api/health")
def health():
    safe_print(f"[{now_str()}] [HEALTH] Verificação de saúde recebida (API OK).")
    return {
        "status": "running",
        "service": "letrasbr_api",
        "source": state.source,
        "lang": state.lang,
        "time": now_str()
    }


if __name__ == "__main__":
    import uvicorn
    safe_print(f"[{now_str()}] Iniciando servidor LetrasBR API na porta 8000...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, access_log=False)