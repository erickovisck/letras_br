"""Idiomas de tradução suportados (fonte única para API, scraper e interface)."""

from typing import Dict, NamedTuple


class Language(NamedTuple):
    label: str           # Nome exibido na interface
    letras_suffix: str   # Sufixo da página de tradução no Letras.mus.br


LANGUAGES: Dict[str, Language] = {
    "pt": Language("Português (PT)", "traducao.html"),
    "en": Language("English (EN)", "english.html"),
    "es": Language("Español (ES)", "traduccion.html"),
    "fr": Language("Français (FR)", "traduction-francaise.html"),
}

DEFAULT_LANGUAGE = "pt"


def normalize_lang(lang: str) -> str:
    """'PT-BR ' -> 'pt'. Retorna o código base em minúsculas (sem validar)."""
    return (lang or "").lower().strip().split("-")[0]


def is_supported(lang: str) -> bool:
    return normalize_lang(lang) in LANGUAGES


def supported_codes_text() -> str:
    return ", ".join(LANGUAGES)
