"""Tipografia do tema dinâmico por gênero, só com fontes do Windows (e do Office, quando instalado)."""

from typing import Dict, NamedTuple, Optional, Tuple

from PySide6.QtGui import QFontDatabase


class GenreStyle(NamedTuple):
    label: str
    fonts: Tuple[str, ...]  # preferidas primeiro; usa a primeira instalada
    bold: bool = True
    caps: str = ""          # "upper", "lower" ou "" (como na letra)
    spacing: int = 0        # espaçamento extra entre letras, em % do tamanho


GENRE_STYLES: Dict[str, GenreStyle] = {
    "rock": GenreStyle("Rock/Metal", ("Impact", "Bahnschrift Condensed"), bold=False, caps="upper", spacing=3),
    "extreme_metal": GenreStyle("Metal extremo", ("Old English Text MT", "Impact"), bold=False),
    "indie": GenreStyle("Indie/Rock alternativo", ("Franklin Gothic Medium Cond", "Bahnschrift SemiCondensed", "Arial Narrow"),
                        bold=False, caps="upper", spacing=2),
    "hiphop": GenreStyle("Hip-Hop/Rap", ("Arial Black", "Segoe UI Black"), bold=False, caps="upper", spacing=2),
    "trap": GenreStyle("Trap/Grime", ("Franklin Gothic Heavy", "Segoe UI Black"), bold=False, caps="upper", spacing=6),
    "boombap": GenreStyle("Boom Bap", ("Ink Free", "Segoe Print"), caps="upper", spacing=2),
    "pop": GenreStyle("Pop", ("Century Gothic", "Segoe UI Variable Display", "Segoe UI")),
    "hyperpop": GenreStyle("Hyperpop/Pop alternativo", ("Bahnschrift", "Segoe UI"), caps="lower", spacing=4),
    "jazz": GenreStyle("Jazz/Blues", ("Bodoni MT", "Georgia"), spacing=2),
    "classical": GenreStyle("Clássica/Orquestral", ("Perpetua Titling MT", "Castellar", "Palatino Linotype"),
                            bold=False, caps="upper", spacing=8),
    "electronic": GenreStyle("Eletrônica", ("Bahnschrift", "Segoe UI"), caps="upper", spacing=10),
    "synthwave": GenreStyle("Synthwave/Cyberpunk", ("Agency FB", "Bahnschrift Condensed"), caps="upper", spacing=15),
    "chiptune": GenreStyle("Chiptune/Glitch", ("Cascadia Mono", "Consolas"), caps="upper"),
    "jpop": GenreStyle("J-Pop", ("Yu Gothic UI", "Yu Gothic", "Meiryo")),
    "kpop": GenreStyle("K-Pop", ("Malgun Gothic",)),
    "jrock": GenreStyle("J-Rock/Vocaloid/Anime", ("Yu Gothic", "Meiryo"), caps="upper", spacing=3),
    "idol": GenreStyle("Idol", ("Yu Gothic UI", "Meiryo"), bold=False, spacing=6),
    "country": GenreStyle("Sertanejo/Country", ("Rockwell", "Cambria")),
    "folk": GenreStyle("Folk/Western", ("Playbill", "Rockwell Extra Bold", "Georgia"), bold=False, caps="upper", spacing=5),
    "sert_univ": GenreStyle("Sertanejo universitário/Country pop", ("Rockwell", "Cambria"), bold=False, spacing=2),
}


def genre_font_config(style_key: Optional[str]) -> Optional[dict]:
    """Chaves de fonte (fontFamily, fontBold, fontCaps, fontSpacing) do estilo, ou None se desconhecido."""
    style = GENRE_STYLES.get(style_key or "")
    if style is None:
        return None
    installed = set(QFontDatabase.families())
    family = next((f for f in style.fonts if f in installed), None)
    if family is None:
        return None
    return {"fontFamily": family, "fontBold": style.bold, "fontCaps": style.caps, "fontSpacing": style.spacing,
            "genreLabel": style.label}
