"""
Paleta de cores da interface derivada do tema (fundo, texto original e tradução).
Substitui os cinzas fixos da interface, que ficavam ilegíveis em temas claros.
"""

from dataclasses import dataclass

from PySide6.QtGui import QColor


def blend(fg: str, bg: str, amount: float) -> str:
    """Mistura `amount` de fg sobre bg (0 = bg, 1 = fg)."""
    a, b = QColor(fg), QColor(bg)
    mix = lambda x, y: round(x * amount + y * (1 - amount))
    return QColor(mix(a.red(), b.red()), mix(a.green(), b.green()), mix(a.blue(), b.blue())).name()


def luminance(hex_color: str) -> float:
    c = QColor(hex_color)
    return (0.2126 * c.redF() + 0.7152 * c.greenF() + 0.0722 * c.blueF())


def rgba(hex_color: str, alpha: float) -> str:
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {round(alpha * 255)})"


@dataclass(frozen=True)
class Palette:
    bg: str          # Fundo do overlay
    text: str        # Texto principal (cor do original)
    accent: str      # Destaque (cor da tradução)
    muted: str       # Textos secundários (status, tempo)
    subtle: str      # Separadores, alça de redimensionamento
    surface: str     # Caixas/painéis sobre o fundo
    border: str      # Bordas de campos
    is_light: bool
    hover: str       # Fundo de botão em hover
    pressed: str     # Fundo de botão pressionado
    on_accent: str   # Texto sobre a cor de destaque

    @classmethod
    def from_config(cls, cfg: dict) -> "Palette":
        bg = cfg.get("bgColor", "#121216")
        text = cfg.get("origColor", "#cbd5e1")
        accent = cfg.get("transColor", "#38bdf8")
        is_light = luminance(bg) > 0.5
        ink = "#000000" if is_light else "#ffffff"
        return cls(
            bg=bg,
            text=text,
            accent=accent,
            muted=blend(text, bg, 0.62),
            subtle=blend(text, bg, 0.35),
            surface=blend(ink, bg, 0.05),
            border=blend(ink, bg, 0.18),
            is_light=is_light,
            hover=rgba(ink, 0.10 if is_light else 0.14),
            pressed=rgba(ink, 0.18 if is_light else 0.24),
            on_accent="#0f172a" if luminance(accent) > 0.45 else "#ffffff",
        )
