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

# Garante acesso aos módulos internos e ao ytmusicapi local
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

root_dir = os.path.abspath(os.path.join(current_dir, ".."))
inner_ytm = os.path.join(root_dir, "ytmusicapi")
if os.path.exists(os.path.join(inner_ytm, "ytmusicapi", "__init__.py")):
    if inner_ytm not in sys.path:
        sys.path.insert(0, inner_ytm)

from scraper import get_translation, clean_song_title
from aligner import align_lyrics, find_active_aligned_line, AlignedLine
from lyrics_sync import YTMManager
from config import get_config, save_config

app = FastAPI(title="YouTube Music - LetrasBR Tradutor API", version="2.0.0")

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

ytm_manager = YTMManager()


class SyncPayload(BaseModel):
    title: str
    artist: str
    album: Optional[str] = None
    videoId: Optional[str] = None
    currentTime: float  # em segundos
    duration: Optional[float] = None
    isPaused: Optional[bool] = False
    lang: Optional[str] = None  # 'pt', 'fr', 'en', 'es'


class LanguagePayload(BaseModel):
    lang: str  # 'pt', 'fr', 'en', 'es'


class PlayerActionPayload(BaseModel):
    action: str  # 'play_pause', 'next'


class PlaybackState:
    def __init__(self):
        self.song_key: Optional[str] = None
        self.title: str = ""
        self.artist: str = ""
        self.video_id: Optional[str] = None
        self.lang: str = get_config().get("lang", "pt")  # Idioma padrão vindo da configuração
        self.timed_lyrics: List[Any] = []
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
        self.pending_command: Optional[str] = None


state = PlaybackState()


def queue_command(action: str):
    """Enfileira um comando para ser executado pelo YouTube Music."""
    state.pending_command = action
    safe_print(f"[{now_str()}] 🎮 Comando enviado para o player: {action.upper()}")


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


def update_current_track(title: str, artist: str, video_id: Optional[str], lang: Optional[str] = None):
    if lang:
        state.lang = lang.lower().strip()

    state.title = title
    state.artist = artist
    state.video_id = video_id
    state.last_line_key = None
    state.aligned_lyrics = []

    safe_print("\n" + "=" * 70)
    safe_print(f"[{now_str()}] 🎵 NOVA FAIXA DETECTADA: {artist} - {title}")
    if video_id:
        safe_print(f"[{now_str()}] 🔗 Video ID: {video_id}")
    safe_print(f"[{now_str()}] 🌐 Idioma selecionado: {state.lang.upper()}")
    safe_print("=" * 70)

    # 1. Busca letras sincronizadas no YouTube Music
    safe_print(f"[{now_str()}] [1/3] 🔍 Buscando letras sincronizadas no YouTube Music (ytmusicapi)...")
    state.timed_lyrics = ytm_manager.get_timed_lyrics(video_id=video_id or "", title=title, artist=artist) or []
    if state.timed_lyrics:
        safe_print(f"[{now_str()}] ✅ [YTM] {len(state.timed_lyrics)} versos com timestamps carregados!")
    else:
        safe_print(f"[{now_str()}] ⚠️ [YTM] Nenhuma letra sincronizada encontrada para esta faixa.")

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
    state.aligned_lyrics = align_lyrics(state.timed_lyrics, ordered_verses)
    safe_print(f"[{now_str()}] ✅ {len(state.aligned_lyrics)} versos alinhados e prontos com latência zero!")

    safe_print("-" * 70)
    safe_print(f"[{now_str()}] ⏳ Sincronização ao vivo ativada. Aguardando reprodução...\n")


@app.post("/api/sync")
def sync_playback(payload: SyncPayload, request: Request):
    req_lang = payload.lang.lower().strip() if payload.lang else state.lang
    new_key = f"{payload.artist.strip()}|||{payload.title.strip()}|||{req_lang}"
    if payload.videoId:
        new_key += f"|||{payload.videoId.strip()}"

    is_new_song = (new_key != state.song_key)

    # Mudança de música ou de idioma
    if is_new_song:
        state.song_key = new_key
        update_current_track(payload.title, payload.artist, payload.videoId, lang=req_lang)

    # Atualiza o timestamp atual e estado do player
    current_ms = int(payload.currentTime * 1000)
    state.current_time_ms = current_ms
    state.current_seconds = payload.currentTime
    state.is_paused = bool(payload.isPaused)
    if payload.duration:
        state.duration_seconds = payload.duration

    # Consome comando pendente se houver (para ser executado pelo YouTube Music)
    pending_cmd = state.pending_command
    state.pending_command = None

    # Se pausado, não busca nova linha mas ainda entrega comandos se houver
    if payload.isPaused:
        res = {"status": "paused", "title": state.title, "artist": state.artist, "lang": state.lang}
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
        state.song_key = None  # Força reprocessamento com o novo idioma
        update_current_track(state.title, state.artist, state.video_id, lang=new_lang)
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
    """Envia um comando para o YouTube Music (play_pause, next)."""
    action = payload.action.lower().strip()
    if action not in ["play_pause", "next", "toggle_play"]:
        return {"status": "error", "message": f"Ação '{action}' desconhecida. Use 'play_pause' ou 'next'."}
    queue_command(action)
    return {"status": "ok", "action": action}


@app.get("/api/current")
def get_current():
    return {
        "title": state.title,
        "artist": state.artist,
        "videoId": state.video_id,
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
    return {"status": "running", "service": "letrasbr_api", "lang": state.lang, "time": now_str()}


if __name__ == "__main__":
    import uvicorn
    safe_print(f"[{now_str()}] Iniciando servidor LetrasBR API na porta 8000...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, access_log=False)