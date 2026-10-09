"""
Pipeline único de letras: busca da letra sincronizada -> tradução -> alinhamento -> fallback automático.
Usado pelo overlay desktop (lyrics_client.py) e pela API (main.py).
"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from aligner import AlignedLine, align_lyrics, is_instrumental, normalize
from machine_translate import detect_language, translate_lines
from providers import ProviderFactory, TimedLine, TrackInfo
from providers.lrclib import fetch_lrclib_lyrics
from scraper import clean_song_title, fetch_translation, TranslationResult


@dataclass
class LyricsResult:
    aligned: List[AlignedLine]
    translation_url: Optional[str]
    lang: str                      # Idioma de destino pedido
    timing_source: str             # "ytmusic" | "lrclib" | "estimated" | "none"
    translation_source: str        # "letras" | "auto" | "mixed" | "original" | "none"
    timed_lyrics: List[TimedLine]  # Letra sincronizada bruta (reaproveitada ao trocar de idioma)


def log(msg: str):
    try:
        print(f"[PIPELINE] {msg}")
    except Exception:
        print(f"[PIPELINE] {str(msg).encode('ascii', 'replace').decode('ascii')}")


def fetch_timed_lyrics(track: TrackInfo, source: str) -> Tuple[List[TimedLine], str]:
    """
    Busca a letra sincronizada tentando as fontes na ordem mais provável para o player:
    Spotify -> LRCLIB, YouTube Music; YouTube/navegador -> YouTube Music, LRCLIB.
    """
    def from_ytmusic():
        return ProviderFactory.get_provider("ytmusic").get_timed_lyrics(track)

    def from_lrclib():
        return fetch_lrclib_lyrics(track.title, track.artist, track.album, track.duration)

    order = [("lrclib", from_lrclib), ("ytmusic", from_ytmusic)] if source == "spotify" \
        else [("ytmusic", from_ytmusic), ("lrclib", from_lrclib)]

    for name, fetch in order:
        try:
            lines = fetch()
        except Exception as e:
            log(f"Erro ao buscar letra sincronizada em {name}: {e}")
            lines = None
        if lines:
            return list(lines), name
    return [], "none"


def _estimate_timings(translation: TranslationResult, duration: float) -> List[AlignedLine]:
    """
    Sem letra sincronizada: distribui os versos do Letras ao longo da música,
    proporcionalmente ao tamanho do texto (entre 5% e 95% da duração).
    """
    verses = [v for v in translation.ordered_verses if v.get("originals")]
    if not verses or not duration:
        return []
    weights = [max(8, len(" ".join(v["originals"]))) for v in verses]
    start_ms = duration * 1000 * 0.05
    span_ms = duration * 1000 * 0.90
    total = sum(weights)
    aligned = []
    cursor = start_ms
    for verse, weight in zip(verses, weights):
        length = span_ms * weight / total
        aligned.append(AlignedLine(
            start_time=int(cursor),
            end_time=int(cursor + length),
            original=" / ".join(verse["originals"]),
            translation=verse["translation"],
            is_instrumental=False,
            source="letras",
        ))
        cursor += length
    return aligned


def _fill_with_machine_translation(aligned: List[AlignedLine], lang: str):
    """Completa com tradução automática os versos que ficaram sem tradução."""
    missing = [l for l in aligned if not l.is_instrumental and l.source == "none"]
    if not missing:
        return
    translations = translate_lines([l.original for l in missing], lang)
    for line in missing:
        trans = translations.get(line.original.strip())
        if not trans:
            continue
        if normalize(trans) == normalize(line.original):
            # O Google devolveu o próprio texto: o verso já está no idioma de destino
            line.source = "original"
        else:
            line.translation = trans
            line.source = "auto"


def _summarize_source(aligned: List[AlignedLine]) -> str:
    sources = {l.source for l in aligned if not l.is_instrumental}
    has_letras, has_auto = "letras" in sources, "auto" in sources
    if has_letras and has_auto:
        return "mixed"
    if has_letras:
        return "letras"
    if has_auto:
        return "auto"
    if sources == {"original"}:
        return "original"
    return "none"


def _log_untranslated(title: str, artist: str, lang: str, aligned: List[AlignedLine]):
    try:
        from translation_logger import log_untranslated_lyrics
        log_untranslated_lyrics(title, artist, lang, [l for l in aligned if l.source != "original"])
    except Exception:
        pass


def fetch_and_align(
    title: str,
    artist: str,
    album: Optional[str] = None,
    duration: Optional[float] = None,
    lang: str = "pt",
    source: str = "ytmusic",
    track_id: Optional[str] = None,
    auto_translate: bool = True,
    timed_lyrics: Optional[List[TimedLine]] = None,
    is_current: Optional[Callable[[], bool]] = None,
) -> Optional[LyricsResult]:
    """
    Executa o pipeline completo. Retorna None se `is_current()` indicar que a busca ficou obsoleta
    (ex: o usuário trocou de música no meio do caminho).
    `timed_lyrics` permite reaproveitar a letra sincronizada já obtida (ex: troca de idioma).
    """
    lang = (lang or "pt").lower().strip()
    duration = duration if duration and duration > 0 else None
    stale = lambda: is_current is not None and not is_current()

    # 1. Letra sincronizada
    timing_source = "cached" if timed_lyrics else "none"
    if not timed_lyrics:
        track = TrackInfo(title=title, artist=artist, album=album, track_id=track_id, duration=duration, source=source)
        timed_lyrics, timing_source = fetch_timed_lyrics(track, source)
        log(f"Letra sincronizada: {len(timed_lyrics)} linhas via {timing_source}.")
    if stale():
        return None

    # 2. Música já no idioma de destino: mostra só o original
    vocal_texts = [l.text for l in timed_lyrics if not is_instrumental(l.text)]
    detected = detect_language(vocal_texts) if vocal_texts else None
    if detected == lang:
        log(f"Letra detectada em '{detected}', igual ao idioma de destino: exibindo só o original.")
        aligned = align_lyrics(timed_lyrics, [])
        for line in aligned:
            if not line.is_instrumental:
                line.source = "original"
        return LyricsResult(aligned, None, lang, timing_source, "original", timed_lyrics)

    # 3. Tradução no Letras.mus.br (sem cair para PT quando o fallback automático está ligado)
    cleaned_title = clean_song_title(title)
    translation = fetch_translation(artist, cleaned_title, lang, allow_pt_fallback=not auto_translate)
    if not translation.song_found and ("-" in title or "(" in title):
        simple_title = title.split("-")[0].split("(")[0].strip()
        if simple_title and simple_title != cleaned_title:
            translation = fetch_translation(artist, simple_title, lang, allow_pt_fallback=not auto_translate)
    if stale():
        return None

    # 4. Alinhamento (ou sincronia estimada quando não há letra sincronizada)
    if timed_lyrics:
        aligned = align_lyrics(timed_lyrics, translation.ordered_verses)
    else:
        aligned = _estimate_timings(translation, duration or 0)
        if aligned:
            timing_source = "estimated"
            log("Sem letra sincronizada: usando sincronia estimada pela duração.")

    # 5. Fallback automático para os versos sem tradução
    if auto_translate and aligned:
        _fill_with_machine_translation(aligned, lang)
    if stale():
        return None

    _log_untranslated(title, artist, lang, aligned)
    return LyricsResult(
        aligned=aligned,
        translation_url=translation.url if translation.lang_used else None,
        lang=lang,
        timing_source=timing_source,
        translation_source=_summarize_source(aligned),
        timed_lyrics=timed_lyrics,
    )
