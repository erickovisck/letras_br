"""Área central das letras: desenho em QPainter e animação de transição entre versos."""

from PySide6.QtCore import Qt, QRect, QEasingCurve, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget


class LyricContainerWidget(QWidget):
    """
    Widget de letras com animação estilo Instagram:
    - O verso anterior sobe encolhendo em perspectiva 3D (indo para trás e para cima).
    - O novo verso surge de baixo aumentando de escala (vindo de trás para a frente).
    - Renderização direta em QPainter (zero glitches ou caixas sólidas de opacidade do Windows).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # Textos dos versos
        self._curr_orig = "Aguardando reprodução no Windows..."
        self._curr_trans = ""
        self._prev_orig = ""
        self._prev_trans = ""

        # Animação suave (300ms OutCubic)
        self._anim_progress = 1.0  # 1.0 = estático, 0.0 -> 1.0 = transição ativa
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_tick)
        self._anim.finished.connect(self._on_anim_finished)

        self._config = {}

    def apply_style(self, config: dict):
        self._config = config.copy()
        self.update()

    def set_texts_animated(self, original: str, translation: str):
        if original == self._curr_orig and translation == self._curr_trans:
            return

        # Guarda o verso atual como anterior para fazer a transição para trás
        self._prev_orig = self._curr_orig
        self._prev_trans = self._curr_trans
        self._curr_orig = original
        self._curr_trans = translation

        if self._anim.state() == QVariantAnimation.Running:
            self._anim.stop()

        self._anim_progress = 0.0
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def set_texts_instant(self, original: str, translation: str):
        self._anim.stop()
        self._anim_progress = 1.0
        self._curr_orig = original
        self._curr_trans = translation
        self._prev_orig = ""
        self._prev_trans = ""
        self.update()

    def _on_anim_tick(self, val):
        self._anim_progress = float(val)
        self.update()

    def _on_anim_finished(self):
        self._anim_progress = 1.0
        self._prev_orig = ""
        self._prev_trans = ""
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        # Configurações tipográficas
        font_family = self._config.get("fontFamily", "Segoe UI")
        font_size = self._config.get("fontSize", 15)
        is_bold = self._config.get("fontBold", True)
        is_italic = self._config.get("fontItalic", False)
        orig_hex = self._config.get("origColor", "#cbd5e1")
        trans_hex = self._config.get("transColor", "#38bdf8")
        display_mode = self._config.get("displayMode", "both")

        # Original em destaque (mesmo estilo da tradução): modo "Apenas Original"
        # ou versos sem tradução (música no idioma de destino, verso sem correspondência)
        font_orig_emph = QFont(font_family, max(10, int(font_size * 1.15)))
        font_orig_emph.setBold(is_bold)
        font_orig_emph.setItalic(is_italic)

        font_orig_normal = QFont(font_family, max(9, int(font_size * 0.9)))
        font_orig_normal.setItalic(is_italic)

        font_trans = QFont(font_family, max(10, int(font_size * 1.15)))
        font_trans.setBold(is_bold)
        font_trans.setItalic(is_italic)

        c_trans = QColor(trans_hex)

        def draw_verse(orig_text: str, trans_text: str, center_y: float, scale: float, alpha: float):
            if alpha <= 0.01 or scale <= 0.05:
                return

            painter.save()

            # Ponto central para escala em perspectiva (efeito de ir para trás)
            center_x = w / 2.0
            painter.translate(center_x, center_y)
            painter.scale(scale, scale)
            painter.translate(-center_x, -center_y)

            emphasize_orig = display_mode == "orig" or not trans_text
            show_orig = bool(orig_text) and (display_mode in ("both", "orig") or not trans_text)
            show_trans = bool(trans_text) and display_mode in ("both", "trans")
            font_orig = font_orig_emph if emphasize_orig else font_orig_normal

            # Aplica opacidade diretamente na cor do pincel (sem QGraphicsOpacityEffect)
            color_o = QColor(trans_hex if emphasize_orig else orig_hex)
            color_o.setAlphaF(max(0.0, min(1.0, alpha if emphasize_orig else alpha * 0.85)))

            color_t = QColor(c_trans)
            color_t.setAlphaF(max(0.0, min(1.0, alpha)))

            margin_x = 16
            max_w = max(60, w - margin_x * 2)

            painter.setFont(font_orig)
            rect_o = painter.fontMetrics().boundingRect(0, 0, max_w, 200, Qt.AlignHCenter | Qt.TextWordWrap, orig_text) if show_orig else QRect(0,0,0,0)


            painter.setFont(font_trans)
            rect_t = painter.fontMetrics().boundingRect(0, 0, max_w, 200, Qt.AlignHCenter | Qt.TextWordWrap, trans_text) if show_trans else QRect(0,0,0,0)

            spacing = 2 if (rect_o.height() > 0 and rect_t.height() > 0) else 0
            total_h = rect_o.height() + spacing + rect_t.height()
            top_y = center_y - (total_h / 2.0)

            # Desenha verso original
            if show_orig:
                painter.setFont(font_orig)
                painter.setPen(color_o)
                target_o = QRect(margin_x, int(top_y), max_w, rect_o.height() + 4)
                painter.drawText(target_o, Qt.AlignHCenter | Qt.TextWordWrap, orig_text)
                top_y += rect_o.height() + spacing

            # Desenha verso traduzido
            if show_trans:
                painter.setFont(font_trans)
                painter.setPen(color_t)
                target_t = QRect(margin_x, int(top_y), max_w, rect_t.height() + 4)
                painter.drawText(target_t, Qt.AlignHCenter | Qt.TextWordWrap, trans_text)

            painter.restore()

        center_y = h / 2.0
        travel_distance = h * 0.55

        if self._anim_progress >= 1.0 or not self._prev_orig:
            # Estado estático: verso atual no centro em escala 1.0
            draw_verse(self._curr_orig, self._curr_trans, center_y, scale=1.0, alpha=1.0)
        else:
            p = self._anim_progress

            # 1. Verso anterior: SOBE E ENCOLHE (vai para trás e para cima, estilo Instagram)
            prev_scale = 1.0 - (0.40 * p)                     # Escala: 1.0 -> 0.60 (perspectiva 3D para trás)
            prev_y = center_y - (travel_distance * p)         # Y: sobe
            prev_alpha = max(0.0, 1.0 - p * 1.1)             # Desvanece naturalmente
            draw_verse(self._prev_orig, self._prev_trans, prev_y, scale=prev_scale, alpha=prev_alpha)

            # 2. Novo verso: SOBE E CRESCE (vem de trás para a frente)
            curr_scale = 0.65 + (0.35 * p)                    # Escala: 0.65 -> 1.0
            curr_y = center_y + (travel_distance * (1.0 - p)) # Y: sobe de baixo para o centro
            curr_alpha = min(1.0, p * 1.2)                    # Aparece em destaque
            draw_verse(self._curr_orig, self._curr_trans, curr_y, scale=curr_scale, alpha=curr_alpha)
