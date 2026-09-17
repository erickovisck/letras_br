"""
Interface Gráfica PySide6 (Qt 6) para o Tradutor LetrasBR.
Substitui o Tkinter com design moderno translúcido, cantos arredondados,
animações de versos deslizando para cima com fade suave,
menu de configurações completo (cor de fundo, cor das letras, estilo de fonte)
e controle nativo de mídia via Windows GSMTC.
"""

import sys
import os
from typing import Optional, List

from PySide6.QtCore import (
    Qt, QPoint, QSize, QRect, QPropertyAnimation, QParallelAnimationGroup,
    QEasingCurve, Signal, Slot, QTimer, QVariantAnimation
)
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPen, QBrush, QIcon, QAction,
    QFontDatabase, QCursor, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QDialog, QFontComboBox, QSpinBox, QSlider, QComboBox,
    QColorDialog, QLineEdit, QCheckBox, QSystemTrayIcon, QMenu,
    QGraphicsOpacityEffect, QSizeGrip, QMessageBox, QInputDialog
)

# Adiciona diretório ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from config import get_config, save_config, add_config_listener, get_available_themes, save_custom_theme, THEMES_DIR
from aligner import find_active_aligned_line, AlignedLine
from lyrics_client import LyricsClient
from media_monitor import WindowsMediaMonitor


def load_tinted_icon(icon_name: str, color_hex: str, hover_hex: str = "#ffffff", size: int = 16) -> QIcon:
    """
    Carrega imagem da pasta assets e aplica tint de cor preservando a transparência (alpha mask).
    Retorna QIcon com estados Normal e Active (hover).
    """
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    path = os.path.join(assets_dir, icon_name)
    if not os.path.exists(path):
        return QIcon()

    pix = QPixmap(path)
    if pix.isNull():
        return QIcon()

    qsize = QSize(size, size)
    scaled = pix.scaled(qsize, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _tint(base_pix: QPixmap, color: QColor) -> QPixmap:
        res = QPixmap(base_pix)
        p = QPainter(res)
        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p.fillRect(res.rect(), color)
        p.end()
        return res

    norm_pix = _tint(scaled, QColor(color_hex))
    hover_pix = _tint(scaled, QColor(hover_hex))

    icon = QIcon()
    icon.addPixmap(norm_pix, QIcon.Normal, QIcon.Off)
    icon.addPixmap(norm_pix, QIcon.Normal, QIcon.On)
    icon.addPixmap(hover_pix, QIcon.Active, QIcon.Off)
    icon.addPixmap(hover_pix, QIcon.Active, QIcon.On)
    return icon


def format_time_str(seconds: float) -> str:
    """Converte segundos em string de tempo MM:SS"""
    s = int(max(0, seconds))
    m = s // 60
    s = s % 60
    return f"{m:02d}:{s:02d}"


class ResizeGripLabel(QLabel):
    """
    Ícone estilizado no canto inferior direito para redimensionar largura e altura.
    """
    def __init__(self, window, parent=None):
        super().__init__("⇲", parent)
        self.window = window
        self.setToolTip("Arraste para redimensionar largura e altura")
        self.setCursor(Qt.SizeFDiagCursor)
        self.setStyleSheet("""
            QLabel {
                color: #64748b;
                font-size: 13px;
                font-weight: bold;
                padding-right: 2px;
                padding-bottom: 2px;
                background: transparent;
            }
            QLabel:hover {
                color: #38bdf8;
            }
        """)
        self._dragging = False
        self._start_pos = QPoint()
        self._start_size = QSize()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._start_pos = event.globalPosition().toPoint()
            self._start_size = self.window.size()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.globalPosition().toPoint() - self._start_pos
            new_w = max(380, self._start_size.width() + delta.x())
            new_h = max(80, self._start_size.height() + delta.y())
            self.window.resize(new_w, new_h)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            self.window.config["width"] = self.window.width()
            self.window.config["height"] = self.window.height()
            save_config(self.window.config)
            event.accept()


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
        from PySide6.QtCore import QVariantAnimation
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

        font_orig = QFont(font_family, max(9, int(font_size * 0.9)))
        font_orig.setItalic(is_italic)

        font_trans = QFont(font_family, max(10, int(font_size * 1.15)))
        font_trans.setBold(is_bold)
        font_trans.setItalic(is_italic)

        c_orig = QColor(orig_hex)
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

            # Aplica opacidade diretamente na cor do pincel (sem QGraphicsOpacityEffect)
            color_o = QColor(c_orig)
            color_o.setAlphaF(max(0.0, min(1.0, alpha * 0.85)))

            color_t = QColor(c_trans)
            color_t.setAlphaF(max(0.0, min(1.0, alpha)))

            margin_x = 16
            max_w = max(60, w - margin_x * 2)

            painter.setFont(font_orig)
            rect_o = painter.fontMetrics().boundingRect(0, 0, max_w, 200, Qt.AlignHCenter | Qt.TextWordWrap, orig_text) if (display_mode in ("both", "orig") and orig_text) else QRect(0,0,0,0)


            painter.setFont(font_trans)
            rect_t = painter.fontMetrics().boundingRect(0, 0, max_w, 200, Qt.AlignHCenter | Qt.TextWordWrap, trans_text) if (display_mode in ("both", "trans") and trans_text) else QRect(0,0,0,0)

            spacing = 2 if (rect_o.height() > 0 and rect_t.height() > 0) else 0
            total_h = rect_o.height() + spacing + rect_t.height()
            top_y = center_y - (total_h / 2.0)

            # Desenha verso original
            if display_mode in ("both", "orig") and orig_text:
                painter.setFont(font_orig)
                painter.setPen(color_o)
                target_o = QRect(margin_x, int(top_y), max_w, rect_o.height() + 4)
                painter.drawText(target_o, Qt.AlignHCenter | Qt.TextWordWrap, orig_text)
                top_y += rect_o.height() + spacing

            # Desenha verso traduzido
            if display_mode in ("both", "trans") and trans_text:
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



class SettingsDialogQt(QDialog):
    """
    Diálogo completo e moderno de configurações:
    - Cor de fundo e opacidade (alpha)
    - Cores de letras originais e traduzidas
    - Família da fonte, estilo (negrito, itálico) e tamanho
    - Idioma e Servidor Remoto
    """
    config_saved = Signal(dict)

    def __init__(self, current_cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações do Tradutor - LetrasBR")
        self.resize(460, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.cfg = current_cfg.copy()

        # Estilo escuro moderno para a janela de configurações
        self.setStyleSheet("""
            QDialog {
                background-color: #181824;
                color: #f1f5f9;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 12px;
            }
            QPushButton {
                background-color: #27273a;
                color: #f8fafc;
                border: 1px solid #3f3f5a;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38bdf8;
                color: #0f172a;
            }
            QComboBox, QFontComboBox, QSpinBox, QLineEdit {
                background-color: #212130;
                color: #f8fafc;
                border: 1px solid #3f3f5a;
                border-radius: 6px;
                padding: 5px;
                font-size: 12px;
            }
            QCheckBox {
                color: #cbd5e1;
                font-size: 12px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #27273a;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #38bdf8;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
        """)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("⚙️ Configurações Visuais e Sistema", self)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8; margin-bottom: 6px;")
        layout.addWidget(title)

        # 0. Tema da Interface
        box_theme = QFrame(self)
        box_theme.setStyleSheet("QFrame { background-color: #1f1f2e; border-radius: 8px; padding: 10px; }")
        l_theme = QHBoxLayout(box_theme)
        l_theme.setSpacing(10)

        lbl_theme = QLabel("🎨 Tema Visual:")
        lbl_theme.setStyleSheet("font-size: 12px; font-weight: bold; color: #f8fafc;")
        l_theme.addWidget(lbl_theme)

        self.cb_theme = QComboBox()
        self.cb_theme.setStyleSheet("""
            QComboBox {
                background-color: #27273a;
                color: #f8fafc;
                border: 1px solid #3f3f5a;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                min-width: 170px;
            }
        """)
        self.available_themes = get_available_themes()
        curr_theme = self.cfg.get("theme", "Escuro (Padrão)")
        for t_name in self.available_themes.keys():
            self.cb_theme.addItem(t_name)

        idx = self.cb_theme.findText(curr_theme)
        if idx >= 0:
            self.cb_theme.setCurrentIndex(idx)
        else:
            self.cb_theme.addItem(curr_theme)
            self.cb_theme.setCurrentText(curr_theme)

        self.cb_theme.currentIndexChanged.connect(self._on_theme_changed)
        l_theme.addWidget(self.cb_theme, 1)

        self.btn_save_theme = QPushButton("💾 Salvar como Novo Tema")
        self.btn_save_theme.setCursor(Qt.PointingHandCursor)
        self.btn_save_theme.setStyleSheet("""
            QPushButton {
                background-color: #27273a;
                color: #38bdf8;
                border: 1px solid #38bdf8;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38bdf8;
                color: #0f172a;
            }
        """)
        self.btn_save_theme.setToolTip("Salva a configuração atual de cores, fonte e estilo como um novo tema em config/themes/")
        self.btn_save_theme.clicked.connect(self._save_new_theme)
        l_theme.addWidget(self.btn_save_theme)

        lbl_theme_hint = QLabel("📁 config/themes/")
        lbl_theme_hint.setToolTip("Pasta onde os temas (.json) ficam armazenados")
        lbl_theme_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        l_theme.addWidget(lbl_theme_hint)

        layout.addWidget(box_theme)

        # 1. Cores e Fundo
        box_colors = QFrame(self)
        box_colors.setStyleSheet("QFrame { background-color: #1f1f2e; border-radius: 8px; padding: 8px; }")
        l_colors = QVBoxLayout(box_colors)
        l_colors.setSpacing(10)

        # Cor do Fundo
        h_bg = QHBoxLayout()
        h_bg.addWidget(QLabel("Cor do Fundo:"))
        self.btn_bg_color = QPushButton()
        self.btn_bg_color.setFixedWidth(70)
        self._update_color_btn(self.btn_bg_color, self.cfg.get("bgColor", "#121216"))
        self.btn_bg_color.clicked.connect(lambda: self._choose_color("bgColor", self.btn_bg_color))
        h_bg.addWidget(self.btn_bg_color)

        h_bg.addWidget(QLabel("Opacidade:"))
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(20, 100)
        self.slider_opacity.setValue(int(self.cfg.get("opacity", 0.88) * 100))
        self.lbl_opacity_val = QLabel(f"{self.slider_opacity.value()}%")
        self.slider_opacity.valueChanged.connect(lambda v: self.lbl_opacity_val.setText(f"{v}%"))
        h_bg.addWidget(self.slider_opacity)
        h_bg.addWidget(self.lbl_opacity_val)
        l_colors.addLayout(h_bg)

        # Cor do Texto Original e Traduzido
        h_text_colors = QHBoxLayout()
        h_text_colors.addWidget(QLabel("Texto Original:"))
        self.btn_orig_color = QPushButton()
        self.btn_orig_color.setFixedWidth(70)
        self._update_color_btn(self.btn_orig_color, self.cfg.get("origColor", "#cbd5e1"))
        self.btn_orig_color.clicked.connect(lambda: self._choose_color("origColor", self.btn_orig_color))
        h_text_colors.addWidget(self.btn_orig_color)

        h_text_colors.addWidget(QLabel("Tradução:"))
        self.btn_trans_color = QPushButton()
        self.btn_trans_color.setFixedWidth(70)
        self._update_color_btn(self.btn_trans_color, self.cfg.get("transColor", "#38bdf8"))
        self.btn_trans_color.clicked.connect(lambda: self._choose_color("transColor", self.btn_trans_color))
        h_text_colors.addWidget(self.btn_trans_color)
        l_colors.addLayout(h_text_colors)

        layout.addWidget(box_colors)

        # 2. Fonte e Tipografia
        box_font = QFrame(self)
        box_font.setStyleSheet("QFrame { background-color: #1f1f2e; border-radius: 8px; padding: 10px; }")
        l_font = QVBoxLayout(box_font)
        l_font.setSpacing(10)

        # Família da Fonte (linha inteira dedicada)
        h_font_fam = QHBoxLayout()
        h_font_fam.addWidget(QLabel("Família da Fonte:"))
        self.cb_font = QFontComboBox()
        self.cb_font.setCurrentFont(QFont(self.cfg.get("fontFamily", "Segoe UI")))
        h_font_fam.addWidget(self.cb_font, 1)
        l_font.addLayout(h_font_fam)

        # Tamanho da Fonte com botões [-] e [+] grandes e slider
        h_font_size = QHBoxLayout()
        h_font_size.addWidget(QLabel("Tamanho:"))

        self.btn_dec_font = QPushButton("−")
        self.btn_dec_font.setFixedSize(32, 28)
        self.btn_dec_font.setCursor(Qt.PointingHandCursor)
        self.btn_dec_font.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #27273a; color: #f8fafc; border: 1px solid #3f3f5a; border-radius: 6px;")

        self.lbl_font_size_val = QLabel(f"{int(self.cfg.get('fontSize', 15))} pt")
        self.lbl_font_size_val.setFixedWidth(52)
        self.lbl_font_size_val.setAlignment(Qt.AlignCenter)
        self.lbl_font_size_val.setStyleSheet("font-size: 13px; font-weight: bold; color: #38bdf8;")

        self.btn_inc_font = QPushButton("+")
        self.btn_inc_font.setFixedSize(32, 28)
        self.btn_inc_font.setCursor(Qt.PointingHandCursor)
        self.btn_inc_font.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #27273a; color: #f8fafc; border: 1px solid #3f3f5a; border-radius: 6px;")

        self.slider_font_size = QSlider(Qt.Horizontal)
        self.slider_font_size.setRange(10, 36)
        self.slider_font_size.setValue(int(self.cfg.get("fontSize", 15)))

        def set_font_size_val(v):
            clamped = max(10, min(36, int(v)))
            self.slider_font_size.setValue(clamped)
            self.lbl_font_size_val.setText(f"{clamped} pt")

        self.btn_dec_font.clicked.connect(lambda: set_font_size_val(self.slider_font_size.value() - 1))
        self.btn_inc_font.clicked.connect(lambda: set_font_size_val(self.slider_font_size.value() + 1))
        self.slider_font_size.valueChanged.connect(lambda v: self.lbl_font_size_val.setText(f"{v} pt"))

        h_font_size.addWidget(self.btn_dec_font)
        h_font_size.addWidget(self.lbl_font_size_val)
        h_font_size.addWidget(self.btn_inc_font)
        h_font_size.addWidget(self.slider_font_size, 1)
        l_font.addLayout(h_font_size)

        h_font_styles = QHBoxLayout()
        self.chk_bold = QCheckBox("Negrito")
        self.chk_bold.setChecked(bool(self.cfg.get("fontBold", True)))
        self.chk_italic = QCheckBox("Itálico")
        self.chk_italic.setChecked(bool(self.cfg.get("fontItalic", False)))
        h_font_styles.addWidget(self.chk_bold)
        h_font_styles.addWidget(self.chk_italic)

        h_font_styles.addWidget(QLabel("Modo:"))
        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["Ambos (Original + Tradução)", "Apenas Tradução", "Apenas Original"])
        mode_map = {"both": 0, "trans": 1, "orig": 2}
        self.cb_mode.setCurrentIndex(mode_map.get(self.cfg.get("displayMode", "both"), 0))
        h_font_styles.addWidget(self.cb_mode, 1)
        l_font.addLayout(h_font_styles)

        layout.addWidget(box_font)

        # 3. Idioma e Servidor Desacoplado
        box_net = QFrame(self)
        box_net.setStyleSheet("QFrame { background-color: #1f1f2e; border-radius: 8px; padding: 8px; }")
        l_net = QVBoxLayout(box_net)
        l_net.setSpacing(10)

        h_lang = QHBoxLayout()
        h_lang.addWidget(QLabel("Idioma de Tradução:"))
        self.cb_lang = QComboBox()
        self.cb_lang.addItem("Português (PT)", "pt")
        self.cb_lang.addItem("English (EN)", "en")
        self.cb_lang.addItem("Español (ES)", "es")
        self.cb_lang.addItem("Français (FR)", "fr")
        curr_lang = self.cfg.get("lang", "pt")
        for i in range(self.cb_lang.count()):
            if self.cb_lang.itemData(i) == curr_lang:
                self.cb_lang.setCurrentIndex(i)
        h_lang.addWidget(self.cb_lang)
        l_net.addLayout(h_lang)

        h_server = QHBoxLayout()
        h_server.addWidget(QLabel("Servidor API:"))
        self.txt_server = QLineEdit(self.cfg.get("serverUrl", "http://127.0.0.1:8000"))
        self.txt_server.setPlaceholderText("http://127.0.0.1:8000 ou IP remoto")
        h_server.addWidget(self.txt_server)
        l_net.addLayout(h_server)

        layout.addWidget(box_net)

        # Botões de Ação
        h_actions = QHBoxLayout()
        btn_defaults = QPushButton("Restaurar Padrões")
        btn_defaults.clicked.connect(self._restore_defaults)
        h_actions.addWidget(btn_defaults)

        h_actions.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        h_actions.addWidget(btn_cancel)

        btn_save = QPushButton("Salvar Alterações")
        btn_save.setStyleSheet("background-color: #38bdf8; color: #0f172a;")
        btn_save.clicked.connect(self._save_and_apply)
        h_actions.addWidget(btn_save)

        layout.addLayout(h_actions)

    def _update_color_btn(self, btn: QPushButton, hex_color: str):
        btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #ffffff; border-radius: 4px;")
        btn.setText(hex_color.upper())

    def _choose_color(self, cfg_key: str, btn: QPushButton):
        initial = QColor(self.cfg.get(cfg_key, "#ffffff"))
        color = QColorDialog.getColor(initial, self, "Escolher Cor")
        if color.isValid():
            hex_c = color.name()
            self.cfg[cfg_key] = hex_c
            self._update_color_btn(btn, hex_c)

    def _on_theme_changed(self, index):
        theme_name = self.cb_theme.currentText()
        theme_data = self.available_themes.get(theme_name)
        if not theme_data:
            return

        for k in ["bgColor", "opacity", "origColor", "transColor", "fontFamily", "fontSize", "fontBold", "fontItalic"]:
            if k in theme_data:
                self.cfg[k] = theme_data[k]

        self._update_color_btn(self.btn_bg_color, self.cfg.get("bgColor", "#121216"))
        self._update_color_btn(self.btn_orig_color, self.cfg.get("origColor", "#cbd5e1"))
        self._update_color_btn(self.btn_trans_color, self.cfg.get("transColor", "#38bdf8"))
        self.slider_opacity.setValue(int(self.cfg.get("opacity", 0.88) * 100))
        self.lbl_opacity_val.setText(f"{self.slider_opacity.value()}%")
        self.cb_font.setCurrentFont(QFont(self.cfg.get("fontFamily", "Segoe UI")))
        self.slider_font_size.setValue(int(self.cfg.get("fontSize", 15)))
        self.lbl_font_size_val.setText(f"{int(self.cfg.get('fontSize', 15))} pt")
        self.chk_bold.setChecked(bool(self.cfg.get("fontBold", True)))
        self.chk_italic.setChecked(bool(self.cfg.get("fontItalic", False)))

    def _save_new_theme(self):
        name, ok = QInputDialog.getText(
            self,
            "Salvar Novo Tema",
            "Digite o nome do novo tema:",
            QLineEdit.Normal,
            ""
        )
        if not ok or not name.strip():
            return

        clean_name = name.strip()
        theme_data = {
            "bgColor": self.cfg.get("bgColor", "#121216"),
            "opacity": round(self.slider_opacity.value() / 100.0, 2),
            "origColor": self.cfg.get("origColor", "#cbd5e1"),
            "transColor": self.cfg.get("transColor", "#38bdf8"),
            "fontFamily": self.cb_font.currentFont().family(),
            "fontSize": self.slider_font_size.value(),
            "fontBold": self.chk_bold.isChecked(),
            "fontItalic": self.chk_italic.isChecked()
        }

        try:
            saved_path = save_custom_theme(clean_name, theme_data)
            self.available_themes = get_available_themes()

            self.cb_theme.blockSignals(True)
            self.cb_theme.clear()
            for t_name in self.available_themes.keys():
                self.cb_theme.addItem(t_name)

            idx = self.cb_theme.findText(clean_name)
            if idx >= 0:
                self.cb_theme.setCurrentIndex(idx)
            self.cb_theme.blockSignals(False)

            self.cfg["theme"] = clean_name
            QMessageBox.information(
                self,
                "Tema Salvo",
                f"Tema '{clean_name}' salvo com sucesso!\n\nArquivo salvo em:\n{saved_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro ao Salvar Tema",
                f"Ocorreu um erro ao salvar o tema:\n{e}"
            )

    def _restore_defaults(self):
        self.cfg["theme"] = "Escuro (Padrão)"
        idx = self.cb_theme.findText("Escuro (Padrão)")
        if idx >= 0:
            self.cb_theme.setCurrentIndex(idx)
        else:
            self.cfg["bgColor"] = "#121216"
            self.cfg["opacity"] = 0.88
            self.cfg["origColor"] = "#cbd5e1"
            self.cfg["transColor"] = "#38bdf8"
            self.cfg["fontFamily"] = "Segoe UI"
            self.cfg["fontSize"] = 15
            self.cfg["fontBold"] = True
            self.cfg["fontItalic"] = False

        self._update_color_btn(self.btn_bg_color, self.cfg["bgColor"])
        self._update_color_btn(self.btn_orig_color, self.cfg["origColor"])
        self._update_color_btn(self.btn_trans_color, self.cfg["transColor"])
        self.slider_opacity.setValue(int(self.cfg["opacity"] * 100))
        self.cb_font.setCurrentFont(QFont(self.cfg["fontFamily"]))
        self.slider_font_size.setValue(int(self.cfg["fontSize"]))
        self.lbl_font_size_val.setText(f"{int(self.cfg['fontSize'])} pt")
        self.chk_bold.setChecked(self.cfg["fontBold"])
        self.chk_italic.setChecked(self.cfg["fontItalic"])
        self.cb_mode.setCurrentIndex(0)
        self.txt_server.setText(self.cfg.get("serverUrl", "http://127.0.0.1:8000"))

    def _save_and_apply(self):
        self.cfg["theme"] = self.cb_theme.currentText()
        self.cfg["opacity"] = self.slider_opacity.value() / 100.0
        self.cfg["fontSize"] = self.slider_font_size.value()
        self.cfg["fontFamily"] = self.cb_font.currentFont().family()
        self.cfg["fontBold"] = self.chk_bold.isChecked()
        self.cfg["fontItalic"] = self.chk_italic.isChecked()

        idx_mode = self.cb_mode.currentIndex()
        rev_mode = {0: "both", 1: "trans", 2: "orig"}
        self.cfg["displayMode"] = rev_mode.get(idx_mode, "both")

        self.cfg["lang"] = self.cb_lang.currentData()
        self.cfg["serverUrl"] = self.txt_server.text().strip() or "http://127.0.0.1:8000"

        save_config(self.cfg)
        self.config_saved.emit(self.cfg)
        self.accept()


class LyricsOverlayQt(QWidget):
    """
    Janela Principal do Overlay Flutuante PySide6:
    - Sem bordas com cantos arredondados translúcidos
    - Arraste livre e redimensionamento por borda/alça
    - Controles de mídia nativos integrados ao Windows
    - Sincronização em tempo real de alta precisão
    """
    def __init__(self, media_monitor: Optional[WindowsMediaMonitor] = None, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.media_monitor = media_monitor
        self.lyrics_client = LyricsClient()

        # Estado atual de reprodução
        self.current_title = ""
        self.current_artist = ""
        self.current_album = ""
        self.current_duration = 0.0
        self.current_time_seconds = 0.0
        self.is_paused = False

        self.aligned_lyrics: List[AlignedLine] = []
        self.last_active_line_key = None
        self.is_locked = bool(self.config.get("locked", False))
        self.is_compact = False

        # Variáveis de arraste da janela
        self._drag_position = QPoint()
        self._is_dragging = False

        # Configurações de janela flutuante
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.SubWindow
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._build_ui()
        self._apply_current_style()

        # Posicionamento e dimensões
        x = self.config.get("x", 100)
        y = self.config.get("y", 100)
        w = max(400, self.config.get("width", 650))
        h = max(90, self.config.get("height", 115))
        self.setGeometry(x, y, w, h)

        # Conecta eventos do media monitor
        if self.media_monitor:
            self.media_monitor.track_changed.connect(self._on_track_changed)
            self.media_monitor.playback_tick.connect(self._on_playback_tick)
            self.media_monitor.source_changed.connect(self._on_source_changed)

        # Cria System Tray Icon
        self._init_tray_icon()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Container interno para desenhar cantos arredondados e borda
        self.container = QFrame(self)
        self.container.setObjectName("container")
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(8, 4, 8, 4)
        container_layout.setSpacing(2)

        # --- BARRA SUPERIOR DE CONTROLE ---
        self.top_bar = QWidget(self.container)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(4, 2, 4, 2)
        top_layout.setSpacing(6)

        # Grip / Título do App
        self.lbl_grip = QLabel("⠿ LetrasBR", self.top_bar)
        self.lbl_grip.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8;")
        top_layout.addWidget(self.lbl_grip)

        # Miniplayer: Anterior, Play/Pause, Próxima
        self.btn_prev = QPushButton(self.top_bar)
        self.btn_prev.setFixedSize(22, 22)
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        self.btn_prev.clicked.connect(lambda: self._send_media_cmd("previous"))
        top_layout.addWidget(self.btn_prev)

        self.btn_play = QPushButton(self.top_bar)
        self.btn_play.setFixedSize(22, 22)
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(lambda: self._send_media_cmd("play_pause"))
        top_layout.addWidget(self.btn_play)

        self.btn_next = QPushButton(self.top_bar)
        self.btn_next.setFixedSize(22, 22)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.clicked.connect(lambda: self._send_media_cmd("next"))
        top_layout.addWidget(self.btn_next)

        # Scroll / Timeline Seek Slider
        self._is_user_seeking = False
        self.timeline_slider = QSlider(Qt.Horizontal, self.top_bar)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.setFixedWidth(100)
        self.timeline_slider.setCursor(Qt.PointingHandCursor)
        self.timeline_slider.setToolTip("Arraste para avançar ou voltar a música")

        self.lbl_time = QLabel("00:00", self.top_bar)
        self.lbl_time.setStyleSheet("font-size: 9px; color: #94a3b8; min-width: 58px;")

        def on_slider_pressed():
            self._is_user_seeking = True

        def on_slider_released():
            if self.current_duration > 0 and self.media_monitor:
                target_sec = (self.timeline_slider.value() / 1000.0) * self.current_duration
                self.media_monitor.send_seek(target_sec)
            self._is_user_seeking = False

        def on_slider_moved(val):
            if self.current_duration > 0:
                cur = (val / 1000.0) * self.current_duration
                self.lbl_time.setText(f"{format_time_str(cur)} / {format_time_str(self.current_duration)}")

        self.timeline_slider.sliderPressed.connect(on_slider_pressed)
        self.timeline_slider.sliderReleased.connect(on_slider_released)
        self.timeline_slider.sliderMoved.connect(on_slider_moved)

        top_layout.addWidget(self.timeline_slider)
        top_layout.addWidget(self.lbl_time)

        # Separador vertical
        sep = QLabel("|", self.top_bar)
        sep.setStyleSheet("color: #334155;")
        top_layout.addWidget(sep)

        # Status / Faixa atual com ícone do app no lugar de "Sincronizado"
        self.status_container = QWidget(self.top_bar)
        status_layout = QHBoxLayout(self.status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(5)

        self.lbl_source_icon = QLabel(self.status_container)
        self.lbl_source_icon.setFixedSize(14, 14)
        self.lbl_source_icon.setScaledContents(True)
        self.lbl_source_icon.setVisible(False)
        status_layout.addWidget(self.lbl_source_icon)

        self.lbl_status = QLabel("Aguardando reprodução no Windows (YouTube Music / Spotify)...", self.status_container)
        self.lbl_status.setStyleSheet("font-size: 10px; color: #64748b;")
        status_layout.addWidget(self.lbl_status, 1)

        top_layout.addWidget(self.status_container, 1)

        # Botões de controle da janela (direita)
        self.btn_lock = QPushButton(self.top_bar)
        self.btn_lock.setFixedSize(22, 22)
        self.btn_lock.setCursor(Qt.PointingHandCursor)
        self.btn_lock.clicked.connect(self._toggle_lock)
        top_layout.addWidget(self.btn_lock)

        self.btn_settings = QPushButton(self.top_bar)
        self.btn_settings.setFixedSize(22, 22)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.open_settings)
        top_layout.addWidget(self.btn_settings)

        self.btn_minimize = QPushButton("—", self.top_bar)
        self.btn_minimize.setFixedSize(22, 22)
        self.btn_minimize.setCursor(Qt.PointingHandCursor)
        self.btn_minimize.clicked.connect(self._toggle_compact)
        top_layout.addWidget(self.btn_minimize)

        self.btn_close = QPushButton("✕", self.top_bar)
        self.btn_close.setObjectName("btn_close")
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.hide)  # Oculta para o tray
        top_layout.addWidget(self.btn_close)

        container_layout.addWidget(self.top_bar)

        # --- ÁREA CENTRAL DAS LETRAS ---
        self.lyric_widget = LyricContainerWidget(self.container)
        container_layout.addWidget(self.lyric_widget, 1)

        # --- BARRA INFERIOR COM ÍCONE DE REDIMENSIONAMENTO ---
        self.bottom_bar = QWidget(self.container)
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(4, 0, 4, 1)
        bottom_layout.setSpacing(0)
        bottom_layout.addStretch()

        # Ícone visual no canto inferior direito simbolizando largura e altura
        self.resize_grip = ResizeGripLabel(self, self.bottom_bar)
        bottom_layout.addWidget(self.resize_grip)

        container_layout.addWidget(self.bottom_bar)
        main_layout.addWidget(self.container)

    def _init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        # Carrega icone de assets/ ou gera via QPainter como fallback
        icon_path = os.path.join(os.path.dirname(current_dir), "assets", "app_icon.png")
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
        else:
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QBrush(QColor("#38bdf8")))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(2, 2, 28, 28, 8, 8)
            painter.setPen(QPen(QColor("#0f172a")))
            font = QFont("Segoe UI", 12, QFont.Bold)
            painter.setFont(font)
            painter.drawText(QRect(0, 0, 32, 32), Qt.AlignCenter, "L")
            painter.end()
            app_icon = QIcon(pixmap)

        self.tray_icon.setIcon(app_icon)
        self.setWindowIcon(app_icon)

        tray_menu = QMenu()

        act_toggle = QAction("Mostrar / Ocultar Overlay", self)
        act_toggle.triggered.connect(self._toggle_visibility)
        tray_menu.addAction(act_toggle)

        act_settings = QAction("Configurações", self)
        act_settings.triggered.connect(self.open_settings)
        tray_menu.addAction(act_settings)

        tray_menu.addSeparator()

        act_play = QAction("Play / Pause", self)
        act_play.triggered.connect(lambda: self._send_media_cmd("play_pause"))
        tray_menu.addAction(act_play)

        act_next = QAction("Próxima Música", self)
        act_next.triggered.connect(lambda: self._send_media_cmd("next"))
        tray_menu.addAction(act_next)

        tray_menu.addSeparator()

        act_exit = QAction("Sair do LetrasBR", self)
        act_exit.triggered.connect(self._exit_application)
        tray_menu.addAction(act_exit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(lambda reason: self._toggle_visibility() if reason == QSystemTrayIcon.Trigger else None)
        self.tray_icon.show()

    def _toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def _exit_application(self):
        self.tray_icon.hide()
        if self.media_monitor:
            self.media_monitor.stop()
        QApplication.quit()

    def _apply_current_style(self):
        bg_hex = self.config.get("bgColor", "#121216")
        opacity = float(self.config.get("opacity", 0.88))
        color = QColor(bg_hex)
        r, g, b = color.red(), color.green(), color.blue()
        alpha = int(opacity * 255)

        self.container.setStyleSheet(f"""
            #container {{
                background-color: rgba({r}, {g}, {b}, {alpha});
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
            }}
        """)
        self.lyric_widget.apply_style(self.config)

        accent_color = self.config.get("transColor", "#38bdf8")
        nav_color = self.config.get("origColor", "#cbd5e1")

        # Scroll / Timeline Seek Slider ultra fino e elegante (2px)
        self.timeline_slider.setStyleSheet(f"""
            QSlider {{
                background: transparent;
            }}
            QSlider::groove:horizontal {{
                height: 2px;
                background: rgba(148, 163, 184, 0.25);
                border-radius: 1px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent_color};
                height: 2px;
                border-radius: 1px;
            }}
            QSlider::handle:horizontal {{
                background: #f8fafc;
                width: 6px;
                height: 6px;
                margin-top: -2px;
                margin-bottom: -2px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {accent_color};
                width: 8px;
                height: 8px;
                margin-top: -3px;
                margin-bottom: -3px;
                border-radius: 4px;
            }}
        """)

        btn_base_style = """
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 2px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.14);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.24);
            }
        """
        self.btn_prev.setStyleSheet(btn_base_style)
        self.btn_play.setStyleSheet(btn_base_style)
        self.btn_next.setStyleSheet(btn_base_style)
        self.btn_lock.setStyleSheet(btn_base_style)
        self.btn_settings.setStyleSheet(btn_base_style)
        self.btn_minimize.setStyleSheet(btn_base_style + "QPushButton { color: #94a3b8; font-size: 11px; font-weight: bold; }")
        self.btn_close.setStyleSheet(btn_base_style + "QPushButton { color: #94a3b8; font-size: 11px; } QPushButton:hover { background: #ef4444; color: #ffffff; }")

        # Ícones dos botões com tinting de acordo com o tema
        self._icon_play = load_tinted_icon("play-button.png", accent_color, "#ffffff", 14)
        self._icon_pause = load_tinted_icon("pause.png", accent_color, "#ffffff", 14)
        self._icon_prev = load_tinted_icon("back.png", nav_color, "#ffffff", 14)
        self._icon_next = load_tinted_icon("next.png", nav_color, "#ffffff", 14)
        self._icon_lock = load_tinted_icon("lock.png", nav_color, "#ffffff", 13)
        self._icon_unlock = load_tinted_icon("unlock.png", nav_color, "#ffffff", 13)
        self._icon_settings = load_tinted_icon("settings.png", nav_color, "#ffffff", 13)

        self.btn_prev.setIcon(self._icon_prev)
        self.btn_prev.setIconSize(QSize(14, 14))
        self.btn_prev.setToolTip("Voltar música")

        self.btn_next.setIcon(self._icon_next)
        self.btn_next.setIconSize(QSize(14, 14))
        self.btn_next.setToolTip("Próxima música")

        self.btn_play.setIcon(self._icon_play if self.is_paused else self._icon_pause)
        self.btn_play.setIconSize(QSize(14, 14))
        self.btn_play.setToolTip("Reproduzir" if self.is_paused else "Pausar")

        self.btn_lock.setIcon(self._icon_lock if self.is_locked else self._icon_unlock)
        self.btn_lock.setIconSize(QSize(13, 13))
        self.btn_lock.setToolTip("Bloqueado (ignora arrasto)" if self.is_locked else "Desbloqueado (clique para travar)")

        self.btn_settings.setIcon(self._icon_settings)
        self.btn_settings.setIconSize(QSize(13, 13))
        self.btn_settings.setToolTip("Configurações e Temas")

    @Slot(str)
    def _on_source_changed(self, source: str):
        self._current_source = source
        self._update_source_icon_display(source)

    def _update_source_icon_display(self, source: str):
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
        if source == "spotify":
            icon_file = os.path.join(assets_dir, "spotify.png")
            if os.path.exists(icon_file):
                self.lbl_source_icon.setPixmap(QPixmap(icon_file).scaled(14, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.lbl_source_icon.setToolTip("Sincronizado via Spotify")
        elif source == "youtube":
            icon_file = os.path.join(assets_dir, "youtube.png")
            if not os.path.exists(icon_file):
                icon_file = os.path.join(assets_dir, "app.png")
            if os.path.exists(icon_file):
                self.lbl_source_icon.setPixmap(QPixmap(icon_file).scaled(14, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.lbl_source_icon.setToolTip("Sincronizado via YouTube Music")

    def _toggle_lock(self):
        self.is_locked = not self.is_locked
        if hasattr(self, "_icon_lock") and hasattr(self, "_icon_unlock"):
            self.btn_lock.setIcon(self._icon_lock if self.is_locked else self._icon_unlock)
        self.btn_lock.setToolTip("Bloqueado (ignora arrasto)" if self.is_locked else "Desbloqueado (clique para travar)")
        self.config["locked"] = self.is_locked
        save_config(self.config)

    def _toggle_compact(self):
        self.is_compact = not self.is_compact
        self.lyric_widget.setVisible(not self.is_compact)
        self.bottom_bar.setVisible(not self.is_compact)
        if self.is_compact:
            self.resize(self.width(), 36)
        else:
            self.resize(self.width(), self.config.get("height", 115))

    def _send_media_cmd(self, action: str):
        if self.media_monitor:
            self.media_monitor.send_command(action)

    @Slot(str, str, str, float)
    def _on_track_changed(self, title: str, artist: str, album: str, duration: float):
        """
        Chamado quando a música muda (autoplay ou pulo manual de faixa).
        Exibe feedback visual imediato e busca letras com cancelamento prévio.
        """
        self.current_title = title
        self.current_artist = artist
        self.current_album = album
        self.current_duration = duration
        self.last_active_line_key = None
        self.aligned_lyrics = []

        if not title:
            self.lbl_source_icon.setVisible(False)
            self.lbl_status.setText("Aguardando reprodução no Windows (YouTube Music / Spotify)...")
            self.lyric_widget.set_texts_instant("Aguardando reprodução no Windows...", "")
            return

        self.lbl_source_icon.setVisible(False)
        self.lbl_status.setText(f"{artist} - {title}")
        self.lyric_widget.set_texts_animated("Carregando tradução...", f"{artist} - {title}")

        lang = self.config.get("lang", "pt")
        server_url = self.config.get("serverUrl", "http://127.0.0.1:8000")

        # Dispara busca desacoplada assíncrona
        self.lyrics_client.fetch_lyrics(
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            lang=lang,
            server_url=server_url,
            on_success=self._on_lyrics_loaded,
            on_error=self._on_lyrics_error
        )

    def _on_lyrics_loaded(self, req_id: int, aligned: List[AlignedLine], trans_url: str):
        self.aligned_lyrics = aligned or []
        if self.aligned_lyrics:
            # O ícone do player ativo substitui o antigo texto "🟢 Sincronizado"
            self._update_source_icon_display(getattr(self, "_current_source", "youtube"))
            self.lbl_source_icon.setVisible(True)
            self.lbl_status.setText(f"{self.current_artist} - {self.current_title}")
            versos = len(self.aligned_lyrics)
            src_name = "Spotify" if getattr(self, "_current_source", "") == "spotify" else "YouTube Music"
            tooltip = f"Sincronizado ({versos} versos) via {src_name}"
            self.lbl_source_icon.setToolTip(tooltip)
            self.lbl_status.setToolTip(tooltip)
        else:
            self.lbl_source_icon.setVisible(False)
            self.lbl_status.setText(f"⚠️ {self.current_artist} - {self.current_title} (sem sincronização)")
            self.lyric_widget.set_texts_instant("Letra sincronizada não disponível no momento.", "")

    def _on_lyrics_error(self, req_id: int, err_msg: str):
        self.lbl_source_icon.setVisible(False)
        self.lbl_status.setText(f"⚠️ Tradução não encontrada")
        self.lyric_widget.set_texts_instant("Tradução não disponível para esta faixa.", "")

    @Slot(float, float, bool)
    def _on_playback_tick(self, current_seconds: float, duration: float, is_paused: bool):
        """Atualização de alta precisão a cada ~100ms"""
        self.current_time_seconds = current_seconds
        self.is_paused = is_paused

        # Atualiza ícone do botão play/pause se o estado mudou
        if is_paused != getattr(self, "_last_paused_state", None):
            self._last_paused_state = is_paused
            if hasattr(self, "_icon_play") and hasattr(self, "_icon_pause"):
                self.btn_play.setIcon(self._icon_play if is_paused else self._icon_pause)
                self.btn_play.setToolTip("Reproduzir" if is_paused else "Pausar")

        # Atualiza timeline slider e label de tempo
        if not getattr(self, "_is_user_seeking", False):
            if duration > 0:
                ratio = min(1.0, max(0.0, current_seconds / duration))
                self.timeline_slider.setValue(int(ratio * 1000))
                self.lbl_time.setText(f"{format_time_str(current_seconds)} / {format_time_str(duration)}")
            else:
                self.timeline_slider.setValue(0)
                self.lbl_time.setText(format_time_str(current_seconds))

        if not self.aligned_lyrics:
            return

        current_ms = int(current_seconds * 1000)
        active_line = find_active_aligned_line(self.aligned_lyrics, current_ms)

        if active_line:
            line_key = (active_line.start_time, active_line.original)
            if line_key != self.last_active_line_key:
                self.last_active_line_key = line_key
                self.lyric_widget.set_texts_animated(active_line.original, active_line.translation)

    def open_settings(self):
        dlg = SettingsDialogQt(self.config, self)
        dlg.config_saved.connect(self._on_config_updated)
        dlg.exec()

    def _on_config_updated(self, new_cfg: dict):
        self.config = new_cfg
        self._apply_current_style()

        # Se mudou o idioma, recarrega a música atual
        if self.current_title and self.current_artist:
            self._on_track_changed(
                self.current_title,
                self.current_artist,
                self.current_album,
                self.current_duration
            )

    # --- EVENTOS DE ARRASTE DA JANELA ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.is_locked:
            self._is_dragging = True
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and not self.is_locked:
            new_pos = event.globalPosition().toPoint() - self._drag_position
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._is_dragging:
            self._is_dragging = False
            # Salva nova posição
            self.config["x"] = self.x()
            self.config["y"] = self.y()
            save_config(self.config)
            event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.is_compact:
            self.config["width"] = self.width()
            self.config["height"] = self.height()
            save_config(self.config)
