"""
Tradução automática (fallback) via Google Tradutor gratuito (endpoint gtx, sem chave de API)
e detecção de idioma das letras.
Usado quando o Letras.mus.br não tem a música, não tem o idioma pedido ou deixa versos sem tradução.
"""

import os
import json
import time
import threading
from typing import Dict, List, Optional

import httpx

MAX_CHUNK_CHARS = 4000
# Tempo (s) que um endpoint fica de fora após ser bloqueado pelo Google (HTTP 429 / captcha)
BLOCK_COOLDOWN = 15 * 60
MAX_CACHE_ENTRIES = 20000

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "auto_translations.json")

_cache_lock = threading.Lock()
_cache: Optional[Dict[str, str]] = None  # "lang|||linha original" -> tradução

try:
    from langdetect import DetectorFactory, detect_langs
    DetectorFactory.seed = 0  # Resultados determinísticos
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False


def log(msg: str):
    try:
        print(f"[AUTO-TRAD] {msg}")
    except Exception:
        print(f"[AUTO-TRAD] {str(msg).encode('ascii', 'replace').decode('ascii')}")


def detect_language(lines: List[str], min_probability: float = 0.90) -> Optional[str]:
    """
    Detecta o idioma predominante das linhas ('pt', 'en', 'ja', ...).
    Retorna None se a detecção não for confiável (ex: músicas que misturam idiomas).
    """
    if not _LANGDETECT_AVAILABLE:
        return None
    text = "\n".join(l for l in lines if l and l.strip())
    if len(text) < 20:
        return None
    try:
        best = detect_langs(text)[0]
    except Exception:
        return None
    if best.prob < min_probability:
        return None
    return best.lang.split("-")[0].lower()


def _load_cache() -> Dict[str, str]:
    global _cache
    if _cache is None:
        _cache = {}
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except FileNotFoundError:
            pass
        except Exception as e:
            log(f"Cache de traduções automáticas ilegível, recriando: {e}")
    return _cache


def _save_cache():
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        # Mantém só as entradas mais recentes (dict preserva a ordem de inserção)
        while len(_cache) > MAX_CACHE_ENTRIES:
            _cache.pop(next(iter(_cache)))
        tmp = CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
        os.replace(tmp, CACHE_FILE)
    except Exception as e:
        log(f"Erro ao salvar cache de traduções automáticas: {e}")


def _chunk_lines(lines: List[str]) -> List[List[str]]:
    chunks: List[List[str]] = []
    current: List[str] = []
    size = 0
    for line in lines:
        if current and size + len(line) + 1 > MAX_CHUNK_CHARS:
            chunks.append(current)
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append(current)
    return chunks


def _parse_dict_chrome_ex(data) -> str:
    # Formato: [["texto traduzido", "idioma de origem"]] (ou ["texto traduzido"])
    item = data[0]
    return item[0] if isinstance(item, list) else item


def _parse_gtx(data) -> str:
    # Formato: [[["trecho traduzido", "trecho original", ...], ...], None, "idioma de origem", ...]
    return "".join(seg[0] for seg in (data[0] or []) if seg and seg[0])


# Endpoints gratuitos do Google Tradutor, tentados em ordem. Ambos aceitam POST e preservam quebras de linha.
ENDPOINTS = [
    ("clients5", "https://clients5.google.com/translate_a/t", {"client": "dict-chrome-ex"}, _parse_dict_chrome_ex),
    ("gtx", "https://translate.googleapis.com/translate_a/single", {"client": "gtx", "dt": "t"}, _parse_gtx),
]
_blocked_until: Dict[str, float] = {}


def _translate_chunk(client: httpx.Client, lines: List[str], target: str) -> Optional[List[str]]:
    """Traduz um bloco de linhas numa única requisição, preservando a quantidade de linhas."""
    translated = None
    for name, url, params, parse in ENDPOINTS:
        if _blocked_until.get(name, 0) > time.time():
            continue
        try:
            res = client.post(url, params={**params, "sl": "auto", "tl": target}, data={"q": "\n".join(lines)})
        except httpx.HTTPError as e:
            log(f"Endpoint '{name}' falhou: {e}")
            continue
        if res.status_code == 429:
            log(f"Endpoint '{name}' bloqueado pelo Google (HTTP 429); pausado por {BLOCK_COOLDOWN // 60} min.")
            _blocked_until[name] = time.time() + BLOCK_COOLDOWN
            continue
        if res.status_code != 200:
            log(f"Endpoint '{name}' retornou HTTP {res.status_code}.")
            continue
        try:
            translated = parse(res.json())
            break
        except Exception as e:
            log(f"Resposta inesperada do endpoint '{name}': {e}")

    if translated is None:
        return None
    out = translated.split("\n")
    if len(out) != len(lines):
        log(f"Quantidade de linhas divergente ({len(out)} != {len(lines)}); bloco descartado.")
        return None
    return [o.strip() for o in out]


def translate_lines(lines: List[str], target: str) -> Dict[str, str]:
    """
    Traduz as linhas para o idioma alvo. Retorna {linha original: tradução} apenas para
    as linhas traduzidas com sucesso (falhas são omitidas, nunca lançam exceção).
    Linhas repetidas (refrões) são enviadas uma única vez e o resultado fica em cache no disco.
    """
    target = (target or "pt").lower().strip()
    unique = list(dict.fromkeys(l.strip() for l in lines if l and l.strip()))
    if not unique:
        return {}

    result: Dict[str, str] = {}
    with _cache_lock:
        cache = _load_cache()
        missing = []
        for line in unique:
            cached = cache.get(f"{target}|||{line}")
            if cached is not None:
                result[line] = cached
            else:
                missing.append(line)

    if not missing:
        return result

    log(f"Traduzindo automaticamente {len(missing)} linha(s) para '{target}'...")
    fresh: Dict[str, str] = {}
    try:
        with httpx.Client(timeout=10.0) as client:
            for chunk in _chunk_lines(missing):
                translated = _translate_chunk(client, chunk, target)
                if translated:
                    fresh.update(zip(chunk, translated))
    except Exception as e:
        log(f"Falha na tradução automática: {e}")

    if fresh:
        with _cache_lock:
            cache = _load_cache()
            for line, trans in fresh.items():
                cache[f"{target}|||{line}"] = trans
            _save_cache()
        log(f"✅ {len(fresh)} linha(s) traduzidas automaticamente.")

    result.update(fresh)
    return result
