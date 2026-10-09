"""Diálogo de configurações: tema, cores, fonte, modo de exibição e tradução."""

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QFontComboBox,
    QSlider, QComboBox, QColorDialog, QLineEdit, QCheckBox, QMessageBox, QInputDialog
)

from ..config import (
    DEFAULT_CONFIG, DEFAULT_THEME_NAME, THEME_KEYS, save_config, get_available_themes, save_custom_theme
)
from ..languages import LANGUAGES
from .color_inputs import HexColorLineEdit, SmartHtmlFilter


class SettingsDialogQt(QDialog):
    """
    Diálogo completo e moderno de configurações:
    - Cor de fundo e opacidade (alpha)
    - Cores de letras originais e traduzidas
    - Família da fonte, estilo (negrito, itálico) e tamanho
    - Idioma de tradução e tradução automática
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
        curr_theme = self.cfg.get("theme", DEFAULT_THEME_NAME)
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
        self.btn_bg_color.setFixedSize(26, 26)
        self.btn_bg_color.setCursor(Qt.PointingHandCursor)
        self.btn_bg_color.setToolTip("Clique para abrir a paleta de cores")
        self.edit_bg_color = HexColorLineEdit(self.cfg.get("bgColor", "#121216").upper())
        self.edit_bg_color.setFixedWidth(78)
        self.edit_bg_color.setToolTip("Código hexadecimal (ex: #121216). Cole com Ctrl+V!")
        self._update_color_btn(self.btn_bg_color, self.cfg.get("bgColor", "#121216"))
        self.btn_bg_color.clicked.connect(lambda: self._choose_color("bgColor", self.btn_bg_color, self.edit_bg_color))
        self.edit_bg_color.textEdited.connect(lambda text: self._on_hex_text_edited("bgColor", text, self.btn_bg_color))
        h_bg.addWidget(self.btn_bg_color)
        h_bg.addWidget(self.edit_bg_color)
        h_bg.addSpacing(15)

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
        self.btn_orig_color.setFixedSize(26, 26)
        self.btn_orig_color.setCursor(Qt.PointingHandCursor)
        self.btn_orig_color.setToolTip("Clique para abrir a paleta de cores")
        self.edit_orig_color = HexColorLineEdit(self.cfg.get("origColor", "#cbd5e1").upper())
        self.edit_orig_color.setFixedWidth(78)
        self.edit_orig_color.setToolTip("Código hexadecimal (ex: #CBD5E1). Cole com Ctrl+V!")
        self._update_color_btn(self.btn_orig_color, self.cfg.get("origColor", "#cbd5e1"))
        self.btn_orig_color.clicked.connect(lambda: self._choose_color("origColor", self.btn_orig_color, self.edit_orig_color))
        self.edit_orig_color.textEdited.connect(lambda text: self._on_hex_text_edited("origColor", text, self.btn_orig_color))
        h_text_colors.addWidget(self.btn_orig_color)
        h_text_colors.addWidget(self.edit_orig_color)
        h_text_colors.addSpacing(15)

        h_text_colors.addWidget(QLabel("Tradução:"))
        self.btn_trans_color = QPushButton()
        self.btn_trans_color.setFixedSize(26, 26)
        self.btn_trans_color.setCursor(Qt.PointingHandCursor)
        self.btn_trans_color.setToolTip("Clique para abrir a paleta de cores")
        self.edit_trans_color = HexColorLineEdit(self.cfg.get("transColor", "#38bdf8").upper())
        self.edit_trans_color.setFixedWidth(78)
        self.edit_trans_color.setToolTip("Código hexadecimal (ex: #38BDF8). Cole com Ctrl+V!")
        self._update_color_btn(self.btn_trans_color, self.cfg.get("transColor", "#38bdf8"))
        self.btn_trans_color.clicked.connect(lambda: self._choose_color("transColor", self.btn_trans_color, self.edit_trans_color))
        self.edit_trans_color.textEdited.connect(lambda text: self._on_hex_text_edited("transColor", text, self.btn_trans_color))
        h_text_colors.addWidget(self.btn_trans_color)
        h_text_colors.addWidget(self.edit_trans_color)
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

        # 3. Tradução
        box_net = QFrame(self)
        box_net.setStyleSheet("QFrame { background-color: #1f1f2e; border-radius: 8px; padding: 8px; }")
        l_net = QVBoxLayout(box_net)
        l_net.setSpacing(10)

        h_lang = QHBoxLayout()
        h_lang.addWidget(QLabel("Idioma de Tradução:"))
        self.cb_lang = QComboBox()
        for code, language in LANGUAGES.items():
            self.cb_lang.addItem(language.label, code)
        curr_lang = self.cfg.get("lang", "pt")
        for i in range(self.cb_lang.count()):
            if self.cb_lang.itemData(i) == curr_lang:
                self.cb_lang.setCurrentIndex(i)
        h_lang.addWidget(self.cb_lang)
        l_net.addLayout(h_lang)

        self.chk_auto_translate = QCheckBox("Completar com tradução automática (Google) quando o Letras não tiver")
        self.chk_auto_translate.setToolTip(
            "Usada quando a música ou alguns versos não têm tradução no Letras.mus.br.\n"
            "Versos traduzidos automaticamente aparecem marcados com ≈."
        )
        self.chk_auto_translate.setChecked(bool(self.cfg.get("autoTranslate", True)))
        l_net.addWidget(self.chk_auto_translate)

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
        btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid rgba(255, 255, 255, 0.45); border-radius: 4px;")
        btn.setText("")

    def _on_hex_text_edited(self, cfg_key: str, text: str, btn: QPushButton):
        clean = text.strip()
        if not clean.startswith("#"):
            clean = "#" + clean
        if re.match(r'^#[A-Fa-f0-9]{6}$', clean):
            self.cfg[cfg_key] = clean
            self._update_color_btn(btn, clean)

    def _choose_color(self, cfg_key: str, btn: QPushButton, line_edit: QLineEdit = None):
        initial = QColor(self.cfg.get(cfg_key, "#ffffff"))
        dlg = QColorDialog(initial, self)
        dlg.setWindowTitle("Escolher Cor")

        # Instala filtro inteligente no campo HTML para permitir colar qualquer formato hex
        for e in dlg.findChildren(QLineEdit):
            if e.text().startswith('#'):
                e.installEventFilter(SmartHtmlFilter(e, dlg))

        if dlg.exec():
            color = dlg.selectedColor()
            if color.isValid():
                hex_c = color.name()
                self.cfg[cfg_key] = hex_c
                self._update_color_btn(btn, hex_c)
                if line_edit:
                    line_edit.blockSignals(True)
                    line_edit.setText(hex_c.upper())
                    line_edit.blockSignals(False)

    def _on_theme_changed(self, index):
        theme_name = self.cb_theme.currentText()
        theme_data = self.available_themes.get(theme_name)
        if not theme_data:
            return

        for k in THEME_KEYS:
            if k in theme_data:
                self.cfg[k] = theme_data[k]

        bg = self.cfg.get("bgColor", "#121216")
        orig = self.cfg.get("origColor", "#cbd5e1")
        trans = self.cfg.get("transColor", "#38bdf8")

        self._update_color_btn(self.btn_bg_color, bg)
        self.edit_bg_color.setText(bg.upper())
        self._update_color_btn(self.btn_orig_color, orig)
        self.edit_orig_color.setText(orig.upper())
        self._update_color_btn(self.btn_trans_color, trans)
        self.edit_trans_color.setText(trans.upper())

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
        self.cfg["theme"] = DEFAULT_THEME_NAME
        idx = self.cb_theme.findText(DEFAULT_THEME_NAME)
        if idx >= 0:
            self.cb_theme.setCurrentIndex(idx)
        else:
            self.cfg.update({k: DEFAULT_CONFIG[k] for k in THEME_KEYS})

        self._update_color_btn(self.btn_bg_color, self.cfg["bgColor"])
        self.edit_bg_color.setText(self.cfg["bgColor"].upper())
        self._update_color_btn(self.btn_orig_color, self.cfg["origColor"])
        self.edit_orig_color.setText(self.cfg["origColor"].upper())
        self._update_color_btn(self.btn_trans_color, self.cfg["transColor"])
        self.edit_trans_color.setText(self.cfg["transColor"].upper())
        self.slider_opacity.setValue(int(self.cfg["opacity"] * 100))
        self.cb_font.setCurrentFont(QFont(self.cfg["fontFamily"]))
        self.slider_font_size.setValue(int(self.cfg["fontSize"]))
        self.lbl_font_size_val.setText(f"{int(self.cfg['fontSize'])} pt")
        self.chk_bold.setChecked(self.cfg["fontBold"])
        self.chk_italic.setChecked(self.cfg["fontItalic"])
        self.cb_mode.setCurrentIndex(0)

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
        self.cfg["autoTranslate"] = self.chk_auto_translate.isChecked()

        save_config(self.cfg)
        self.config_saved.emit(self.cfg)
        self.accept()
