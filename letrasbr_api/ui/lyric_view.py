"""
Área central das letras, desenhada em QPainter.

- Mostra o verso atual em destaque e, se a altura do overlay permitir, versos anteriores/seguintes
  menores e esmaecidos (a quantidade é calculada automaticamente pelo espaço disponível).
- Transições configuráveis entre versos: 3D, rolagem (karaokê), deslizar, esmaecer ou sem animação.
- Efeito opcional no texto (sombra ou contorno) para legibilidade com fundo transparente.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

from PySide6.QtCore import Qt, QRect, QEasingCurve, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

from ..aligner import AlignedLine

TRANSITIONS = {
    "3d": "3D (estilo Stories)",
    "scroll": "Rolagem (karaokê)",
    "slide": "Deslizar",
    "fade": "Esmaecer",
    "none": "Sem animação",
}
TEXT_EFFECTS = {"none": "Nenhum", "shadow": "Sombra", "outline": "Contorno"}

MAX_CONTEXT_LINES = 4
MARGIN_X = 16
GAP = 6
CONTEXT_ALPHA = 0.42


@dataclass(frozen=True)
class Verse:
    original: str
    translation: str


@dataclass(frozen=True)
class _State:
    verses: Tuple[Verse, ...]
    active: int


def verse_from_line(line: AlignedLine) -> Verse:
    translation = line.translation
    if line.source == "auto" and translation:
        translation = f"≈ {translation}"  # Marca tradução automática
    return Verse(line.original, translation)


class LyricContainerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._config: dict = {}
        self._lyrics: Tuple[Verse, ...] = ()
        self._curr = _State((Verse("Aguardando reprodução no Windows...", ""),), 0)
        self._prev: Optional[_State] = None
        self._progress = 1.0
        self._height_cache: Dict[Tuple[Verse, int], int] = {}

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_tick)
        self._anim.finished.connect(self._on_anim_finished)

    # --- API pública ---

    def apply_style(self, config: dict):
        self._config = config.copy()
        self._anim.setDuration(int(self._config.get("transitionMs", 300)))
        self._height_cache.clear()
        self.update()

    def set_lines(self, lines: Sequence[AlignedLine]):
        """Define a letra da música atual (a exibição continua na mensagem até o primeiro verso ativo)."""
        self._lyrics = tuple(verse_from_line(l) for l in lines)

    def set_active_index(self, index: int):
        if 0 <= index < len(self._lyrics) and not (self._curr.verses is self._lyrics and self._curr.active == index):
            self._go_to(_State(self._lyrics, index))

    def set_message(self, original: str, translation: str = "", animated: bool = True):
        """Exibe uma mensagem no lugar da letra (carregando, aguardando, erro...)."""
        state = _State((Verse(original, translation),), 0)
        if state == self._curr:
            return
        if animated:
            self._go_to(state)
        else:
            self._anim.stop()
            self._prev, self._curr, self._progress = None, state, 1.0
            self.update()

    def active_index(self) -> int:
        return self._curr.active if self._curr.verses is self._lyrics else -1

    # --- Animação ---

    def _go_to(self, state: _State):
        self._anim.stop()
        self._prev, self._curr = self._curr, state
        if self._transition() == "none" or not self.isVisible():
            self._on_anim_finished()
            return
        self._progress = 0.0
        self._anim.start()

    def _on_anim_tick(self, value):
        self._progress = float(value)
        self.update()

    def _on_anim_finished(self):
        self._progress = 1.0
        self._prev = None
        self.update()

    def _transition(self) -> str:
        return self._config.get("transition", "3d")

    def resizeEvent(self, event):
        self._height_cache.clear()
        super().resizeEvent(event)

    # --- Medidas e tipografia ---

    def _fonts(self):
        family = self._config.get("fontFamily", "Segoe UI")
        size = self._config.get("fontSize", 15)
        bold = self._config.get("fontBold", True)
        italic = self._config.get("fontItalic", False)

        emphasized = QFont(family, max(10, int(size * 1.15)))
        emphasized.setBold(bold)
        emphasized.setItalic(italic)
        normal = QFont(family, max(9, int(size * 0.9)))
        normal.setItalic(italic)
        return emphasized, normal

    def _layout(self, verse: Verse):
        """Quais partes do verso aparecem e com que fonte, conforme o modo de exibição."""
        mode = self._config.get("displayMode", "both")
        emphasize_orig = mode == "orig" or not verse.translation
        show_orig = bool(verse.original) and (mode in ("both", "orig") or not verse.translation)
        show_trans = bool(verse.translation) and mode in ("both", "trans")
        return show_orig, show_trans, emphasize_orig

    def _text_width(self) -> int:
        return max(60, self.width() - MARGIN_X * 2)

    def _text_height(self, font: QFont, text: str) -> int:
        flags = Qt.AlignHCenter | Qt.TextWordWrap
        return QFontMetrics(font, self).boundingRect(0, 0, self._text_width(), 2000, flags, text).height()

    def _verse_height(self, verse: Verse) -> int:
        key = (verse, self.width())
        if key not in self._height_cache:
            emphasized, normal = self._fonts()
            show_orig, show_trans, emphasize_orig = self._layout(verse)
            height = 0
            if show_orig:
                height += self._text_height(emphasized if emphasize_orig else normal, verse.original)
            if show_trans:
                height += self._text_height(emphasized, verse.translation) + (2 if show_orig else 0)
            self._height_cache[key] = height
        return self._height_cache[key]

    def _context_scale(self) -> float:
        return 0.6 if self._transition() == "3d" else 0.8

    def _geometry(self, state: _State):
        """Distâncias entre versos e quantos versos de contexto cabem acima/abaixo do atual."""
        verses, active = state.verses, state.active
        current_h = self._verse_height(verses[active])
        neighbors = [verses[i] for i in (active - 1, active + 1) if 0 <= i < len(verses)]
        if not neighbors:
            context_h = current_h * self._context_scale()
        else:
            context_h = max(self._verse_height(v) for v in neighbors) * self._context_scale()
        first_step = (current_h + context_h) / 2 + GAP
        context_step = context_h + GAP
        free = (self.height() - current_h) / 2 - GAP
        count = int(max(0.0, free + GAP) // context_step) if context_step > 0 else 0
        return first_step, context_step, min(count, MAX_CONTEXT_LINES)

    # --- Desenho ---

    def paintEvent(self, event):
        if self.width() <= 0 or self.height() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        p, prev, curr = self._progress, self._prev, self._curr
        transition = self._transition()

        if prev is None or p >= 1.0:
            self._draw_frame(painter, curr, curr.active)
        elif prev.verses is curr.verses and abs(curr.active - prev.active) == 1 and transition in ("3d", "scroll"):
            # Avanço de um verso: a lista inteira rola continuamente
            center = curr.active - (1 - p) * (curr.active - prev.active)
            self._draw_frame(painter, curr, center)
        elif transition in ("3d", "scroll"):
            # Troca de lista (mensagem <-> letra) ou salto: o anterior sobe e some, o novo sobe do fundo
            self._draw_frame(painter, prev, prev.active + p, alpha=1 - p)
            self._draw_frame(painter, curr, curr.active - (1 - p), alpha=p)
        else:
            # Deslizar/esmaecer em sequência: o quadro antigo sai na 1ª metade e o novo entra na 2ª
            # (simultâneos, os versos de contexto dos dois quadros se sobrepõem e ficam ilegíveis)
            shift = self.width() * 0.25 if transition == "slide" else 0.0
            if p < 0.5:
                out = p * 2
                self._draw_frame(painter, prev, prev.active, alpha=1 - out, dx=-shift * out)
            else:
                into = (p - 0.5) * 2
                self._draw_frame(painter, curr, curr.active, alpha=into, dx=shift * (1 - into))
        painter.end()

    def _draw_frame(self, painter: QPainter, state: _State, center: float, alpha: float = 1.0, dx: float = 0.0):
        if alpha <= 0.01:
            return
        first_step, context_step, count = self._geometry(state)
        context_scale = self._context_scale()
        center_y = self.height() / 2.0

        for i, verse in enumerate(state.verses):
            rel = i - center
            distance = abs(rel)
            if distance >= count + 1:
                continue
            edge = 1.0 if distance <= count else (count + 1 - distance)   # some suavemente na borda
            emphasis = max(0.0, 1.0 - distance)                             # 1 no centro, 0 no contexto
            offset = min(distance, 1.0) * first_step + max(distance - 1.0, 0.0) * context_step
            y = center_y + (offset if rel > 0 else -offset)
            scale = context_scale + (1 - context_scale) * emphasis
            verse_alpha = (CONTEXT_ALPHA + (1 - CONTEXT_ALPHA) * emphasis) * edge * alpha
            self._draw_verse(painter, verse, y, scale, verse_alpha, dx)

    def _draw_verse(self, painter: QPainter, verse: Verse, center_y: float, scale: float, alpha: float, dx: float):
        if alpha <= 0.01 or scale <= 0.05:
            return
        emphasized, normal = self._fonts()
        show_orig, show_trans, emphasize_orig = self._layout(verse)
        orig_hex = self._config.get("origColor", "#cbd5e1")
        trans_hex = self._config.get("transColor", "#38bdf8")
        width = self._text_width()
        flags = Qt.AlignHCenter | Qt.TextWordWrap

        painter.save()
        center_x = self.width() / 2.0
        painter.translate(center_x + dx, center_y)
        painter.scale(scale, scale)
        painter.translate(-center_x, -center_y)

        top = center_y - self._verse_height(verse) / 2.0
        if show_orig:
            font = emphasized if emphasize_orig else normal
            painter.setFont(font)
            color = QColor(trans_hex if emphasize_orig else orig_hex)
            color.setAlphaF(min(1.0, alpha if emphasize_orig else alpha * 0.85))
            rect_h = self._text_height(font, verse.original)
            self._draw_text(painter, QRect(MARGIN_X, int(top), width, rect_h + 4), flags, verse.original, color)
            top += rect_h + 2
        if show_trans:
            painter.setFont(emphasized)
            color = QColor(trans_hex)
            color.setAlphaF(min(1.0, alpha))
            rect_h = self._text_height(emphasized, verse.translation)
            self._draw_text(painter, QRect(MARGIN_X, int(top), width, rect_h + 4), flags, verse.translation, color)
        painter.restore()

    def _draw_text(self, painter: QPainter, rect: QRect, flags, text: str, color: QColor):
        effect = self._config.get("textEffect", "none")
        if effect != "none":
            light_text = color.lightnessF() > 0.5
            fx = QColor("#000000" if light_text else "#ffffff")
            fx.setAlphaF(color.alphaF() * (0.85 if effect == "outline" else 0.55))
            painter.setPen(fx)
            offsets = [(1, 2)] if effect == "shadow" else [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
            for ox, oy in offsets:
                painter.drawText(rect.translated(ox, oy), flags, text)
        painter.setPen(color)
        painter.drawText(rect, flags, text)
