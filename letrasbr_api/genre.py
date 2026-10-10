"""
Gênero da música para o tema dinâmico (estilo da fonte).
Subgênero pelas tags do artista no MusicBrainz e gênero da faixa pelo iTunes Search (ambos sem chave de API).
O YouTube Music não informa gênero.
"""

import json
import logging
import os
import re
import threading
import time
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "LetrasBR/3.0 (github.com/erickovisck/letras_br)"}
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "genres.json")
TOP_TAGS = 6
MB_MIN_SCORE = 90
MB_MIN_INTERVAL = 1.1  # o MusicBrainz aceita 1 requisição por segundo

# (estilo, gêneros "pai", regex) em ordem de prioridade: subgêneros antes dos gêneros amplos.
# Cada tag recebe o primeiro estilo cuja regex casar.
RULES: List[Tuple[str, Tuple[str, ...], str]] = [
    ("extreme_metal", ("rock",), r"\b(black|death|grind|brutal|war|doom) metal\b|grindcore|deathcore"),
    ("synthwave", ("electronic",), r"synthwave|retrowave|outrun|darksynth|cyberpunk|vaporwave|dreamwave"),
    ("chiptune", ("electronic",), r"chiptune|bitpop|8-bit|glitch"),
    ("trap", ("hiphop",), r"\btrap\b|grime|drill|phonk"),
    ("boombap", ("hiphop",), r"boom bap|golden age hip hop"),
    ("hyperpop", ("pop",), r"hyperpop|alternative pop|art pop|electropop|pc music|bubblegum bass"),
    ("jrock", ("rock", "jpop"), r"j-rock|jrock|japanese rock|visual kei|vocaloid|anime|anison"),
    ("idol", ("jpop", "kpop", "pop"), r"\bidol\b"),
    ("kpop", ("pop",), r"k-pop|kpop|korean"),
    ("jpop", ("pop",), r"j-pop|jpop|japanese|city pop|yakousei"),
    ("sert_univ", ("country",), r"sertanejo universit|country pop|bro-country|feminejo|arrocha"),
    ("folk", ("country",), r"\bfolk\b|western|americana|bluegrass|sertanejo raiz|caipira|moda de viola|outlaw country"),
    ("indie", ("rock",), r"\bindie\b|alternative rock|^alternative$|garage|post-punk|shoegaze|grunge|\bemo\b|punk|britpop"),
    ("rock", (), r"\brock\b|metal|hardcore"),
    ("hiphop", (), r"hip hop|hip-hop|\brap\b"),
    ("classical", (), r"classical|orchestral|opera|baroque|symphon|choral|composer"),
    ("jazz", (), r"jazz|blues|swing|bossa nova"),
    ("electronic", (), r"electronic|electro|house|techno|trance|\bedm\b|(?<![\w-])dance(?![\w-])|dubstep|"
                       r"drum and bass|\bclub\b|ambient|downtempo|\bidm\b"),
    ("country", (), r"country|sertanejo"),
    ("pop", (), r"\bpop\b|r&b"),
]
PARENTS: Dict[str, Tuple[str, ...]] = {style: parents for style, parents, _ in RULES}
_COMPILED = [(style, re.compile(pattern)) for style, _, pattern in RULES]

_cache_lock = threading.Lock()
_mb_lock = threading.Lock()
_mb_last_request = 0.0
_cache: Optional[Dict[str, object]] = None  # "mb|artista" -> [tags], "it|artista|título" -> gênero


def style_for(tag: str) -> Optional[str]:
    """Estilo de um gênero/tag ('black metal' -> 'extreme_metal'). None se não reconhecido."""
    tag = (tag or "").strip().lower()
    for style, regex in _COMPILED:
        if regex.search(tag):
            return style
    return None


def classify(artist_tags: List[str], track_genre: str) -> Optional[str]:
    """
    Escolhe o estilo: se a principal tag do artista já é um subgênero, usa ela; senão o gênero da faixa
    (iTunes) define a família e as tags do artista refinam para um subgênero dela.
    """
    tag_styles = [s for s in (style_for(t) for t in artist_tags) if s]
    if tag_styles and PARENTS.get(tag_styles[0]):
        return tag_styles[0]
    family = style_for(track_genre) or (tag_styles[0] if tag_styles else None)
    if family is None:
        return None
    for style in tag_styles:
        if family in PARENTS.get(style, ()):
            return style
    return family


def _load_cache() -> Dict[str, object]:
    global _cache
    if _cache is None:
        _cache = {}
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.info(f"Cache de gêneros ilegível, recriando: {e}")
    return _cache


def _save_cache():
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
        os.replace(tmp, CACHE_FILE)
    except Exception as e:
        logger.warning(f"Erro ao salvar cache de gêneros: {e}")


def _cached(key: str, fetch):
    """Busca com cache em disco. Falhas de rede (exceção) não são guardadas."""
    with _cache_lock:
        cache = _load_cache()
        if key in cache:
            return cache[key]
    value = fetch()
    with _cache_lock:
        _load_cache()[key] = value
        _save_cache()
    return value


def _musicbrainz_tags(client: httpx.Client, artist: str) -> List[str]:
    global _mb_last_request
    with _mb_lock:
        wait = MB_MIN_INTERVAL - (time.monotonic() - _mb_last_request)
        if wait > 0:
            time.sleep(wait)
        _mb_last_request = time.monotonic()
        response = client.get("https://musicbrainz.org/ws/2/artist",
                              params={"query": f'artist:"{artist.replace(chr(34), "")}"', "limit": 1, "fmt": "json"})
    response.raise_for_status()
    artists = response.json().get("artists", [])
    if not artists or int(artists[0].get("score", 0)) < MB_MIN_SCORE:
        return []
    tags = sorted(artists[0].get("tags", []), key=lambda t: -t.get("count", 0))
    return [t["name"] for t in tags[:TOP_TAGS]]


def _itunes_genre(client: httpx.Client, artist: str, title: str) -> str:
    response = client.get("https://itunes.apple.com/search",
                          params={"term": f"{artist} {title}", "entity": "song", "limit": 5, "country": "US"})
    response.raise_for_status()
    wanted = artist.casefold()
    for result in response.json().get("results", []):
        found = (result.get("artistName") or "").casefold()
        # Aceita variações do nome ("Tião Carreiro e Pardinho" x "Tião Carreiro & Pardinho")
        if found and (found in wanted or wanted in found or found.split()[:2] == wanted.split()[:2]):
            return result.get("primaryGenreName") or ""
    return ""


def _artist_candidates(artist: str) -> List[str]:
    """Nome completo primeiro ('Jorge & Mateus'), depois o artista principal ('A, B feat. C' -> 'A')."""
    main = re.split(r",|;| feat\.? | ft\.? | x | & ", artist, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    return [artist] if main == artist or not main else [artist, main]


def resolve_style(artist: str, title: str) -> Optional[str]:
    """Estilo de fonte da música (chave de RULES) ou None se o gênero não for reconhecido / sem rede."""
    artist, title = (artist or "").strip(), (title or "").strip()
    if not artist:
        return None
    try:
        with httpx.Client(headers=HEADERS, timeout=6.0, follow_redirects=True) as client:
            tags: List[str] = []
            for name in _artist_candidates(artist):
                tags = _cached(f"mb|{name.lower()}", lambda: _musicbrainz_tags(client, name))
                if tags:
                    break
            style = classify(tags, "")
            if not style or not PARENTS.get(style):
                track_genre = _cached(f"it|{artist.lower()}|{title.lower()}", lambda: _itunes_genre(client, artist, title))
                style = classify(tags, track_genre)
    except Exception as e:
        logger.info(f"Não foi possível obter o gênero de {artist} - {title}: {e}")
        return None
    logger.info(f"Gênero de {artist} - {title}: {style or 'desconhecido'} (tags: {', '.join(tags) or '-'})")
    return style
