"""Utilitários de texto compartilhados: transliteração japonesa, detecção de instrumental e normalização."""

import re
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_kakasi():
    """Instância única do pykakasi (transliteração japonês -> hiragana/romaji), ou None se indisponível."""
    try:
        import pykakasi
        return pykakasi.kakasi()
    except Exception as e:
        logger.warning(f"pykakasi indisponível, sem transliteração japonesa: {e}")
        return None


def to_romaji(text: str) -> Optional[str]:
    kks = get_kakasi()
    if not kks:
        return None
    try:
        return " ".join(item["hepburn"] for item in kks.convert(text)).strip() or None
    except Exception:
        return None


def is_instrumental(text: str) -> bool:
    """Verifica se a linha é apenas instrumental / notas musicais (♪, ♫, etc.) ou vazia."""
    if not text:
        return True
    cleaned = re.sub(r"[\s\(\)\[\]♩-♯♪♫♪♩♬~〜\-–—.]+", "", text).strip().lower()
    return len(cleaned) == 0 or cleaned in (
        "instrumental", "solo", "sóinstrumental", "soinstrumental",
        "soloinstrumental", "instrumentalsolo"
    )


def normalize(text: str) -> str:
    """Normaliza o texto para comparação."""
    if not text:
        return ""
    text = re.sub(r"[♩-♯♪♫♪♩♬]", "", text).lower()
    text = re.sub(r"[^\w\s぀-ヿ㐀-䶿一-鿿豈-﫿가-힯]", "", text)
    return re.sub(r"[\s　]+", " ", text).strip()
