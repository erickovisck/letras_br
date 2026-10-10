"""
Tela de configurações em abas (Aparência, Letras, Tradução, Sistema).
Cada alteração é pré-visualizada no overlay na hora (sinal preview_changed); Cancelar desfaz.
As cores da própria tela seguem o tema escolhido.
"""

import re
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFontComboBox, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSlider, QTabWidget, QVBoxLayout, QWidget
)

from ..config import (
    DEFAULT_CONFIG, DEFAULT_THEME_NAME, DYNAMIC_THEME_NAME, THEME_KEYS, save_config, get_available_themes,
    save_custom_theme
)
from ..languages import LANGUAGES
from .color_inputs import HexColorLineEdit, SmartHtmlFilter
from .lyric_view import TEXT_EFFECTS, TRANSITIONS
from .palette import Palette

DISPLAY_MODES = {"both": "Ambos (Original + Tradução)", "trans": "Apenas Tradução", "orig": "Apenas Original"}
COLOR_FIELDS = (("bgColor", "Fundo"), ("origColor", "Texto original"), ("transColor", "Tradução"))


def _combo(options: dict, current: str) -> QComboBox:
    combo = QComboBox()
    for key, label in options.items():
        combo.addItem(label, key)
    index = combo.findData(current)
    combo.setCurrentIndex(max(0, index))
    return combo


class SettingsDialogQt(QDialog):
    config_saved = Signal(dict)
    preview_changed = Signal(dict)

    def __init__(self, current_cfg: dict, parent=None, cover_theme: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Configurações - LetrasBR")
        self.resize(500, 440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.cfg = current_cfg.copy()
        self.cover_theme = cover_theme
        self.available_themes = get_available_themes()
        self._loading = False  # evita pré-visualizações enquanto os campos são preenchidos

        self._build_ui()
        self._apply_dialog_style()

    # ------------------------------------------------------------ Montagem

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.title = QLabel("⚙️ Configurações")
        self.title.setObjectName("title")
        layout.addWidget(self.title)

        tabs = QTabWidget()
        tabs.addTab(self._build_appearance_tab(), "Aparência")
        tabs.addTab(self._build_lyrics_tab(), "Letras")
        tabs.addTab(self._build_translation_tab(), "Tradução")
        tabs.addTab(self._build_system_tab(), "Sistema")
        layout.addWidget(tabs, 1)

        actions = QHBoxLayout()
        btn_defaults = QPushButton("Restaurar Padrões")
        btn_defaults.clicked.connect(self._restore_defaults)
        actions.addWidget(btn_defaults)
        actions.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        actions.addWidget(btn_cancel)
        btn_save = QPushButton("Salvar")
        btn_save.setObjectName("primary")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._save_and_apply)
        actions.addWidget(btn_save)
        layout.addLayout(actions)

        self._fill_fields()

    def _build_appearance_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(10)

        theme_row = QHBoxLayout()
        self.cb_theme = QComboBox()
        self._reload_theme_combo()
        self.cb_theme.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.cb_theme, 1)
        btn_save_theme = QPushButton("💾 Salvar como novo")
        btn_save_theme.setToolTip("Salva cores e fonte atuais como um tema em config/themes/")
        btn_save_theme.clicked.connect(self._save_new_theme)
        theme_row.addWidget(btn_save_theme)
        form.addRow("Tema:", theme_row)

        self.lbl_dynamic_hint = QLabel("Cores extraídas automaticamente da capa da música que está tocando.")
        self.lbl_dynamic_hint.setObjectName("hint")
        self.lbl_dynamic_hint.setWordWrap(True)
        form.addRow("", self.lbl_dynamic_hint)

        self.color_buttons = {}
        self.color_edits = {}
        for key, label in COLOR_FIELDS:
            row = QHBoxLayout()
            btn = QPushButton()
            btn.setFixedSize(26, 26)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip("Clique para abrir a paleta de cores")
            btn.clicked.connect(lambda _=False, k=key: self._choose_color(k))
            edit = HexColorLineEdit()
            edit.setFixedWidth(84)
            edit.setToolTip("Código hexadecimal (ex: #121216). Cole com Ctrl+V!")
            edit.textEdited.connect(lambda text, k=key: self._on_hex_text_edited(k, text))
            row.addWidget(btn)
            row.addWidget(edit)
            row.addStretch()
            self.color_buttons[key], self.color_edits[key] = btn, edit
            form.addRow(f"{label}:", row)

        opacity_row = QHBoxLayout()
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(20, 100)
        self.lbl_opacity_val = QLabel()
        self.slider_opacity.valueChanged.connect(lambda v: (self.lbl_opacity_val.setText(f"{v}%"), self._preview()))
        opacity_row.addWidget(self.slider_opacity, 1)
        opacity_row.addWidget(self.lbl_opacity_val)
        form.addRow("Opacidade:", opacity_row)

        self.cb_text_effect = _combo(TEXT_EFFECTS, "none")
        self.cb_text_effect.setToolTip("Melhora a leitura com fundo muito transparente")
        self.cb_text_effect.currentIndexChanged.connect(self._preview)
        form.addRow("Efeito no texto:", self.cb_text_effect)
        return tab

    def _build_lyrics_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(10)

        self.cb_font = QFontComboBox()
        self.cb_font.currentFontChanged.connect(self._preview)
        form.addRow("Fonte:", self.cb_font)

        size_row = QHBoxLayout()
        btn_dec = QPushButton("−")
        btn_dec.setFixedWidth(32)
        btn_inc = QPushButton("+")
        btn_inc.setFixedWidth(32)
        self.slider_font_size = QSlider(Qt.Horizontal)
        self.slider_font_size.setRange(10, 36)
        self.lbl_font_size_val = QLabel()
        self.lbl_font_size_val.setFixedWidth(44)
        btn_dec.clicked.connect(lambda: self.slider_font_size.setValue(self.slider_font_size.value() - 1))
        btn_inc.clicked.connect(lambda: self.slider_font_size.setValue(self.slider_font_size.value() + 1))
        self.slider_font_size.valueChanged.connect(lambda v: (self.lbl_font_size_val.setText(f"{v} pt"), self._preview()))
        for w in (btn_dec, self.lbl_font_size_val, btn_inc):
            size_row.addWidget(w)
        size_row.addWidget(self.slider_font_size, 1)
        form.addRow("Tamanho:", size_row)

        style_row = QHBoxLayout()
        self.chk_bold = QCheckBox("Negrito")
        self.chk_italic = QCheckBox("Itálico")
        self.chk_upper = QCheckBox("Maiúsculas")
        for chk in (self.chk_bold, self.chk_italic, self.chk_upper):
            chk.toggled.connect(self._preview)
            style_row.addWidget(chk)
        style_row.addStretch()
        form.addRow("Estilo:", style_row)

        self.cb_mode = _combo(DISPLAY_MODES, "both")
        self.cb_mode.currentIndexChanged.connect(self._preview)
        form.addRow("Exibir:", self.cb_mode)

        self.cb_transition = _combo(TRANSITIONS, "3d")
        self.cb_transition.currentIndexChanged.connect(self._preview)
        form.addRow("Transição:", self.cb_transition)

        duration_row = QHBoxLayout()
        self.slider_transition_ms = QSlider(Qt.Horizontal)
        self.slider_transition_ms.setRange(100, 1000)
        self.slider_transition_ms.setSingleStep(50)
        self.lbl_transition_ms = QLabel()
        self.lbl_transition_ms.setFixedWidth(52)
        self.slider_transition_ms.valueChanged.connect(
            lambda v: (self.lbl_transition_ms.setText(f"{v} ms"), self._preview()))
        duration_row.addWidget(self.slider_transition_ms, 1)
        duration_row.addWidget(self.lbl_transition_ms)
        form.addRow("Duração:", duration_row)

        hint = QLabel("A quantidade de versos exibidos acompanha a altura do overlay: aumente a janela "
                      "para ver também os versos anteriores e seguintes.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return tab

    def _build_translation_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(10)
        self.cb_lang = _combo({code: lang.label for code, lang in LANGUAGES.items()}, "pt")
        form.addRow("Idioma:", self.cb_lang)
        self.chk_auto_translate = QCheckBox("Completar com tradução automática (Google) quando o Letras não tiver")
        self.chk_auto_translate.setToolTip("Versos traduzidos automaticamente aparecem marcados com ≈.")
        form.addRow("", self.chk_auto_translate)
        hint = QLabel("Música errada ou sincronia fora do tempo? Clique no nome da música no overlay "
                      "para corrigir a página do Letras.mus.br ou ajustar a sincronia.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return tab

    def _build_system_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(10)
        self.chk_auto_hide = QCheckBox("Esconder os controles quando o mouse sair do overlay")
        self.chk_auto_hide.toggled.connect(self._preview)
        form.addRow("", self.chk_auto_hide)
        shortcuts = QLabel(
            "<b>Ctrl+Alt+L</b> — travar/destravar o overlay (travado, os cliques passam por ele)<br>"
            "<b>]</b> / <b>[</b> — adiantar/atrasar a letra 0,25 s (com o overlay em foco)<br>"
            "<b>0</b> — zerar o ajuste de sincronia da música"
        )
        shortcuts.setObjectName("hint")
        shortcuts.setWordWrap(True)
        form.addRow("Atalhos:", shortcuts)
        return tab

    # --------------------------------------------------------- Estado

    def _reload_theme_combo(self):
        self.cb_theme.blockSignals(True)
        self.cb_theme.clear()
        self.cb_theme.addItem(DYNAMIC_THEME_NAME)
        for name in self.available_themes:
            self.cb_theme.addItem(name)
        current = self.cfg.get("theme", DEFAULT_THEME_NAME)
        if self.cb_theme.findText(current) < 0:
            self.cb_theme.addItem(current)
        self.cb_theme.setCurrentText(current)
        self.cb_theme.blockSignals(False)

    def _fill_fields(self):
        """Preenche todos os campos a partir de self.cfg (sem disparar pré-visualizações)."""
        self._loading = True
        cfg = self.cfg
        for key, _ in COLOR_FIELDS:
            self._show_color(key, cfg.get(key, DEFAULT_CONFIG[key]))
        self.slider_opacity.setValue(int(float(cfg.get("opacity", 0.88)) * 100))
        self.lbl_opacity_val.setText(f"{self.slider_opacity.value()}%")
        self.cb_text_effect.setCurrentIndex(max(0, self.cb_text_effect.findData(cfg.get("textEffect", "none"))))
        self.cb_font.setCurrentFont(QFont(cfg.get("fontFamily", "Segoe UI")))
        self.slider_font_size.setValue(int(cfg.get("fontSize", 15)))
        self.lbl_font_size_val.setText(f"{self.slider_font_size.value()} pt")
        self.chk_bold.setChecked(bool(cfg.get("fontBold", True)))
        self.chk_italic.setChecked(bool(cfg.get("fontItalic", False)))
        self.chk_upper.setChecked(bool(cfg.get("fontUppercase", False)))
        self.cb_mode.setCurrentIndex(max(0, self.cb_mode.findData(cfg.get("displayMode", "both"))))
        self.cb_transition.setCurrentIndex(max(0, self.cb_transition.findData(cfg.get("transition", "3d"))))
        self.slider_transition_ms.setValue(int(cfg.get("transitionMs", 300)))
        self.lbl_transition_ms.setText(f"{self.slider_transition_ms.value()} ms")
        self.cb_lang.setCurrentIndex(max(0, self.cb_lang.findData(cfg.get("lang", "pt"))))
        self.chk_auto_translate.setChecked(bool(cfg.get("autoTranslate", True)))
        self.chk_auto_hide.setChecked(bool(cfg.get("autoHideControls", True)))
        self.lbl_dynamic_hint.setVisible(cfg.get("theme") == DYNAMIC_THEME_NAME)
        self._loading = False

    def _collect(self):
        """Copia os valores dos campos para self.cfg (as cores já são atualizadas ao escolher)."""
        self.cfg["theme"] = self.cb_theme.currentText()
        self.cfg["opacity"] = self.slider_opacity.value() / 100.0
        self.cfg["textEffect"] = self.cb_text_effect.currentData()
        self.cfg["fontFamily"] = self.cb_font.currentFont().family()
        self.cfg["fontSize"] = self.slider_font_size.value()
        self.cfg["fontBold"] = self.chk_bold.isChecked()
        self.cfg["fontItalic"] = self.chk_italic.isChecked()
        self.cfg["fontUppercase"] = self.chk_upper.isChecked()
        self.cfg["displayMode"] = self.cb_mode.currentData()
        self.cfg["transition"] = self.cb_transition.currentData()
        self.cfg["transitionMs"] = self.slider_transition_ms.value()
        self.cfg["lang"] = self.cb_lang.currentData()
        self.cfg["autoTranslate"] = self.chk_auto_translate.isChecked()
        self.cfg["autoHideControls"] = self.chk_auto_hide.isChecked()

    def _preview(self, *_):
        if self._loading:
            return
        self._collect()
        self._apply_dialog_style()
        self.preview_changed.emit(dict(self.cfg))

    # --------------------------------------------------------- Cores

    def _show_color(self, key: str, hex_color: str):
        self.color_buttons[key].setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid rgba(128, 128, 128, 0.6); border-radius: 4px;")
        edit = self.color_edits[key]
        if edit.text().upper() != hex_color.upper():
            edit.setText(hex_color.upper())

    def _set_color(self, key: str, hex_color: str):
        self.cfg[key] = hex_color
        self._show_color(key, hex_color)
        self._preview()

    def _on_hex_text_edited(self, key: str, text: str):
        clean = text.strip()
        if not clean.startswith("#"):
            clean = "#" + clean
        if re.match(r'^#[A-Fa-f0-9]{6}$', clean):
            self._set_color(key, clean)

    def _choose_color(self, key: str):
        dlg = QColorDialog(QColor(self.cfg.get(key, "#ffffff")), self)
        dlg.setWindowTitle("Escolher Cor")
        # Instala filtro inteligente no campo HTML para permitir colar qualquer formato hex
        for e in dlg.findChildren(QLineEdit):
            if e.text().startswith('#'):
                e.installEventFilter(SmartHtmlFilter(e, dlg))
        if dlg.exec() and dlg.selectedColor().isValid():
            self._set_color(key, dlg.selectedColor().name())

    # --------------------------------------------------------- Temas

    def _on_theme_changed(self, _index):
        name = self.cb_theme.currentText()
        if name == DYNAMIC_THEME_NAME:
            theme = self.cover_theme or {}
        else:
            theme = self.available_themes.get(name, {})
        self._collect()
        self.cfg.update({k: v for k, v in theme.items() if k in THEME_KEYS})
        self._fill_fields()
        self._preview()

    def _save_new_theme(self):
        name, ok = QInputDialog.getText(self, "Salvar Novo Tema", "Nome do novo tema:", QLineEdit.Normal, "")
        if not ok or not name.strip():
            return
        self._collect()
        try:
            saved_path = save_custom_theme(name.strip(), {k: self.cfg[k] for k in THEME_KEYS if k in self.cfg})
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Salvar Tema", f"Ocorreu um erro ao salvar o tema:\n{e}")
            return
        self.available_themes = get_available_themes()
        self.cfg["theme"] = name.strip()
        self._reload_theme_combo()
        QMessageBox.information(self, "Tema Salvo", f"Tema '{name.strip()}' salvo em:\n{saved_path}")

    def _restore_defaults(self):
        keys = THEME_KEYS + ("displayMode", "transition", "transitionMs", "textEffect", "autoHideControls", "fontUppercase")
        self.cfg.update({k: DEFAULT_CONFIG[k] for k in keys})
        theme = self.available_themes.get(DEFAULT_THEME_NAME)
        if theme:
            self.cfg.update({k: v for k, v in theme.items() if k in THEME_KEYS})
        self.cfg["theme"] = DEFAULT_THEME_NAME
        self._reload_theme_combo()
        self._fill_fields()
        self._preview()

    # --------------------------------------------------------- Salvar

    def _save_and_apply(self):
        self._collect()
        save_config(self.cfg)
        self.config_saved.emit(self.cfg)
        self.accept()

    def _apply_dialog_style(self):
        pal = Palette.from_config(self.cfg)
        self.setStyleSheet(f"""
            QDialog, QTabWidget::pane, QTabWidget > QWidget > QWidget {{
                background-color: {pal.bg}; color: {pal.text}; font-family: 'Segoe UI', sans-serif;
            }}
            QLabel {{ color: {pal.text}; font-size: 12px; }}
            QLabel#title {{ font-size: 16px; font-weight: bold; color: {pal.accent}; }}
            QLabel#hint {{ color: {pal.muted}; font-size: 11px; }}
            QTabWidget::pane {{ border: 1px solid {pal.border}; border-radius: 8px; padding: 10px; }}
            QTabBar::tab {{
                background: {pal.surface}; color: {pal.muted}; padding: 6px 14px; margin-right: 2px;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected {{ background: {pal.border}; color: {pal.accent}; font-weight: bold; }}
            QPushButton {{
                background-color: {pal.surface}; color: {pal.text}; border: 1px solid {pal.border};
                border-radius: 6px; padding: 5px 12px; font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {pal.accent}; color: {pal.on_accent}; }}
            QPushButton#primary {{ background-color: {pal.accent}; color: {pal.on_accent}; }}
            QComboBox, QFontComboBox, QLineEdit {{
                background-color: {pal.surface}; color: {pal.text}; border: 1px solid {pal.border};
                border-radius: 6px; padding: 4px 6px; font-size: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {pal.bg}; color: {pal.text}; selection-background-color: {pal.accent};
                selection-color: {pal.on_accent};
            }}
            QLineEdit#hexColor {{ font-family: 'Consolas', monospace; font-weight: bold; }}
            QLineEdit:focus {{ border-color: {pal.accent}; }}
            QCheckBox {{ color: {pal.text}; font-size: 12px; }}
            QSlider::groove:horizontal {{ height: 6px; background: {pal.border}; border-radius: 3px; }}
            QSlider::sub-page:horizontal {{ background: {pal.accent}; border-radius: 3px; }}
            QSlider::handle:horizontal {{
                background: {pal.text}; width: 14px; margin: -4px 0; border-radius: 7px;
            }}
        """)
