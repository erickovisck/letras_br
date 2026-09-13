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

app = FastAPI(title="YouTube Music - LetrasBR Tradutor API", version="2.0.0")

# Permitir requisições de qualquer origem (extensões, páginas locais, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ytm_manager = YTMManager()


class SyncPayload(BaseModel):
    title: str
    artist: str
    album: Optional[str] = None
    videoId: Optional[str] = None
    currentTime: float  # em segundos
    duration: Optional[float] = None
    isPaused: Optional[bool] = False


class PlaybackState:
    def __init__(self):
        self.song_key: Optional[str] = None
        self.title: str = ""
        self.artist: str = ""
        self.video_id: Optional[str] = None
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


state = PlaybackState()


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


def update_current_track(title: str, artist: str, video_id: Optional[str]):
    state.title = title
    state.artist = artist
    state.video_id = video_id
    state.last_line_key = None
    state.aligned_lyrics = []

    safe_print("\n" + "=" * 70)
    safe_print(f"[{now_str()}] 🎵 NOVA FAIXA DETECTADA: {artist} - {title}")
    if video_id:
        safe_print(f"[{now_str()}] 🔗 Video ID: {video_id}")
    safe_print("=" * 70)

    # 1. Busca letras sincronizadas no YouTube Music
    safe_print(f"[{now_str()}] [1/3] 🔍 Buscando letras sincronizadas no YouTube Music (ytmusicapi)...")
    state.timed_lyrics = ytm_manager.get_timed_lyrics(video_id=video_id or "", title=title, artist=artist) or []
    if state.timed_lyrics:
        safe_print(f"[{now_str()}] ✅ [YTM] {len(state.timed_lyrics)} versos com timestamps carregados!")
    else:
        safe_print(f"[{now_str()}] ⚠️ [YTM] Nenhuma letra sincronizada encontrada para esta faixa.")

    # 2. Busca tradução no Letras.mus.br
    safe_print(f"[{now_str()}] [2/3] 🌐 Buscando tradução verso a verso no Letras.mus.br...")
    cleaned_title = clean_song_title(title)
    trans_dict, ordered_verses, trans_url = get_translation(artist, cleaned_title)
    state.translation_dict = trans_dict
    state.ordered_verses = ordered_verses
    state.translation_url = trans_url

    if ordered_verses or trans_dict:
        safe_print(f"[{now_str()}] ✅ [LETRAS] {len(trans_dict)} versos traduzidos carregados com sucesso!")
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
    new_key = f"{payload.artist.strip()}|||{payload.title.strip()}"
    if payload.videoId:
        new_key += f"|||{payload.videoId.strip()}"

    is_new_song = (new_key != state.song_key)

    # Mudança de música
    if is_new_song:
        state.song_key = new_key
        update_current_track(payload.title, payload.artist, payload.videoId)

    # Atualiza o timestamp atual
    current_ms = int(payload.currentTime * 1000)
    state.current_time_ms = current_ms

    # Se pausado, não busca nova linha
    if payload.isPaused:
        return {"status": "paused", "title": state.title, "artist": state.artist}

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

    return {
        "status": "ok",
        "title": state.title,
        "artist": state.artist,
        "currentTime": payload.currentTime,
        "activeOriginal": state.active_original,
        "activeTranslation": state.active_translation,
    }


@app.get("/api/current")
def get_current():
    return {
        "title": state.title,
        "artist": state.artist,
        "videoId": state.video_id,
        "currentTimeMs": state.current_time_ms,
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
    return {"status": "running", "service": "letrasbr_api", "time": now_str()}


if __name__ == "__main__":
    import uvicorn
    safe_print(f"[{now_str()}] Iniciando servidor LetrasBR API na porta 8000...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, access_log=False)