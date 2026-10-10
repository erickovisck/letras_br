"""
Janela principal do overlay flutuante: sem bordas, translúcida, arrastável e redimensionável,
com miniplayer integrado ao Windows (GSMTC) e sincronização das letras em tempo real.

- Barras de controle somem sozinhas quando o mouse sai (opção em Configurações > Sistema).
- Cadeado: o overlay passa a deixar os cliques passarem; destrava pela bandeja ou Ctrl+Alt+L.
- Ajuste de sincronia por música, painel com a letra completa e menu "Música errada?".
"""

import os
import webbrowser
from typing import Optional, List

from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QSize, QTimer, Signal, Slot
from PySide6.QtGui import QCursor, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu,
    QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget
)

from .. import track_prefs
from ..aligner import AlignedLine, find_active_index
from ..config import DYNAMIC_THEME_NAME, get_config, save_config
from ..lyrics_client import LyricsClient
from ..media_monitor import WindowsMediaMonitor
from ..pipeline import LyricsResult
from ..scraper import BASE_URL, clear_translation_cache, letras_path_from_url
from .cover_colors import theme_from_cover
from .hotkeys import MOD_ALT, MOD_CONTROL, GlobalHotkeys
from .icons import ASSETS_DIR, load_tinted_icon
from .lyric_view import LyricContainerWidget
from .lyrics_panel import LyricsPanel
from .palette import Palette, rgba
from .settings_dialog import SettingsDialogQt
from .tray import create_tray_icon


# Rótulos exibidos no status/tooltip para a origem da letra sincronizada e da tradução
TIMING_SOURCE_LABELS = {
    "ytmusic": "YouTube Music",
    "lrclib": "LRCLIB",
    "estimated": "estimativa pela duração",
}
TRANSLATION_SOURCE_LABELS = {
    "letras": "Letras.mus.br",
    "auto": "tradução automática",
    "mixed": "Letras.mus.br + automática",
    "original": "já no seu idioma",
    "none": "sem tradução",
}

OFFSET_STEP_MS = 250
PANEL_HEIGHT = 220
AUTO_HIDE_DELAY_MS = 1500


def format_time_str(seconds: float) -> str:
    """Converte segundos em string de tempo MM:SS"""
    s = int(max(0, seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def format_offset(offset_ms: int) -> str:
    return f"{offset_ms / 1000:+.2f}s".replace(".", ",")


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()


class ResizeGripLabel(QLabel):
    """Ícone no canto inferior direito para redimensionar largura e altura."""
    def __init__(self, window, parent=None):
        super().__init__("⇲", parent)
        self.window = window
        self.setToolTip("Arraste para redimensionar largura e altura")
        self.setCursor(Qt.SizeFDiagCursor)
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
            event.accept()


class LyricsOverlayQt(QWidget):
    """Janela principal do overlay flutuante."""

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
        self._current_source = "youtube"
        self._result: Optional[LyricsResult] = None
        self._offset_ms = 0
        self._cover_theme: Optional[dict] = None

        self.aligned_lyrics: List[AlignedLine] = []
        self.is_locked = bool(self.config.get("locked", False))
        self.is_compact = False

        # Variáveis de arraste da janela
        self._drag_position = QPoint()
        self._is_dragging = False

        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow
        if self.is_locked:
            flags |= Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(lambda: save_config(self.config))

        self._build_ui()
        self._init_auto_hide()
        self._apply_current_style()

        x = self.config.get("x", 100)
        y = self.config.get("y", 100)
        w = max(400, self.config.get("width", 650))
        h = max(90, self.config.get("height", 115))
        self.setGeometry(x, y, w, h)

        if self.media_monitor:
            self.media_monitor.track_changed.connect(self._on_track_changed)
            self.media_monitor.playback_tick.connect(self._on_playback_tick)
            self.media_monitor.source_changed.connect(self._on_source_changed)
            self.media_monitor.cover_changed.connect(self._on_cover_changed)

        self.tray_icon = create_tray_icon(self)

        self.hotkeys = GlobalHotkeys(self)
        self.hotkeys.activated.connect(self._on_hotkey)
        self.hotkeys.register("lock", MOD_CONTROL | MOD_ALT, "L")

        # Atalhos com o overlay em foco: ajuste de sincronia
        QShortcut(QKeySequence("]"), self, activated=lambda: self.adjust_offset(OFFSET_STEP_MS))
        QShortcut(QKeySequence("["), self, activated=lambda: self.adjust_offset(-OFFSET_STEP_MS))
        QShortcut(QKeySequence("0"), self, activated=lambda: self.adjust_offset(None))

        if self.is_locked:
            self._set_controls_visible(False, animated=False)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.container = QFrame(self)
        self.container.setObjectName("container")
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(8, 4, 8, 4)
        container_layout.setSpacing(2)

        # --- BARRA SUPERIOR ---
        self.top_bar = QWidget(self.container)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(4, 2, 4, 2)
        top_layout.setSpacing(6)

        self.lbl_grip = QLabel("⠿ LetrasBR", self.top_bar)
        top_layout.addWidget(self.lbl_grip)

        self.btn_prev = self._icon_button(lambda: self.send_media_cmd("previous"))
        self.btn_play = self._icon_button(lambda: self.send_media_cmd("play_pause"))
        self.btn_next = self._icon_button(lambda: self.send_media_cmd("next"))
        for btn in (self.btn_prev, self.btn_play, self.btn_next):
            top_layout.addWidget(btn)

        self._is_user_seeking = False
        self.timeline_slider = QSlider(Qt.Horizontal, self.top_bar)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setFixedWidth(100)
        self.timeline_slider.setCursor(Qt.PointingHandCursor)
        self.timeline_slider.setToolTip("Arraste para avançar ou voltar a música")
        self.timeline_slider.sliderPressed.connect(lambda: setattr(self, "_is_user_seeking", True))
        self.timeline_slider.sliderReleased.connect(self._on_slider_released)
        self.timeline_slider.sliderMoved.connect(self._on_slider_moved)
        top_layout.addWidget(self.timeline_slider)

        self.lbl_time = QLabel("00:00", self.top_bar)
        top_layout.addWidget(self.lbl_time)

        # Ajuste de sincronia (por música)
        self.btn_offset_minus = self._text_button("−", lambda: self.adjust_offset(-OFFSET_STEP_MS),
                                                  "Atrasar a letra 0,25 s  ( [ )")
        self.lbl_offset = ClickableLabel("", self.top_bar)
        self.lbl_offset.setToolTip("Ajuste de sincronia desta música (clique para zerar)")
        self.lbl_offset.setCursor(Qt.PointingHandCursor)
        self.lbl_offset.clicked.connect(lambda: self.adjust_offset(None))
        self.btn_offset_plus = self._text_button("+", lambda: self.adjust_offset(OFFSET_STEP_MS),
                                                 "Adiantar a letra 0,25 s  ( ] )")
        for widget in (self.btn_offset_minus, self.lbl_offset, self.btn_offset_plus):
            top_layout.addWidget(widget)

        self.sep = QLabel("|", self.top_bar)
        top_layout.addWidget(self.sep)

        # Status da faixa: clicar abre o menu da música ("Música errada?", sincronia, recarregar)
        self.status_container = QWidget(self.top_bar)
        status_layout = QHBoxLayout(self.status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(5)
        self.lbl_source_icon = QLabel(self.status_container)
        self.lbl_source_icon.setFixedSize(14, 14)
        self.lbl_source_icon.setScaledContents(True)
        self.lbl_source_icon.setVisible(False)
        status_layout.addWidget(self.lbl_source_icon)
        self.lbl_status = ClickableLabel("Aguardando reprodução no Windows (YouTube Music / Spotify)...", self.status_container)
        self.lbl_status.setCursor(Qt.PointingHandCursor)
        self.lbl_status.clicked.connect(self._show_song_menu)
        status_layout.addWidget(self.lbl_status, 1)
        top_layout.addWidget(self.status_container, 1)

        self.btn_panel = self._text_button("≡", self.toggle_lyrics_panel, "Mostrar a letra completa")
        self.btn_lock = self._icon_button(self.toggle_lock)
        self.btn_settings = self._icon_button(self.open_settings)
        self.btn_minimize = self._text_button("—", self._toggle_compact, "Modo compacto")
        self.btn_close = self._text_button("✕", self.hide, "Ocultar (continua na bandeja)")
        for btn in (self.btn_panel, self.btn_lock, self.btn_settings, self.btn_minimize, self.btn_close):
            top_layout.addWidget(btn)

        container_layout.addWidget(self.top_bar)

        # --- LETRAS ---
        self.lyric_widget = LyricContainerWidget(self.container)
        container_layout.addWidget(self.lyric_widget, 1)

        self.lyrics_panel = LyricsPanel(self.container)
        self.lyrics_panel.setFixedHeight(PANEL_HEIGHT)
        self.lyrics_panel.setVisible(False)
        self.lyrics_panel.seek_requested.connect(self._seek_to_line)
        container_layout.addWidget(self.lyrics_panel)

        # --- BARRA INFERIOR ---
        self.bottom_bar = QWidget(self.container)
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(4, 0, 4, 1)
        bottom_layout.setSpacing(0)
        bottom_layout.addStretch()
        self.resize_grip = ResizeGripLabel(self, self.bottom_bar)
        bottom_layout.addWidget(self.resize_grip)
        container_layout.addWidget(self.bottom_bar)

        main_layout.addWidget(self.container)
        self._update_offset_label()

    def _icon_button(self, callback) -> QPushButton:
        btn = QPushButton(self.top_bar)
        btn.setFixedSize(22, 22)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(callback)
        return btn

    def _text_button(self, text: str, callback, tooltip: str) -> QPushButton:
        btn = self._icon_button(callback)
        btn.setText(text)
        btn.setToolTip(tooltip)
        return btn

    def _apply_current_style(self, cfg: Optional[dict] = None):
        """Aplica tema/cores. `cfg` permite pré-visualizar sem alterar a configuração (tela de configurações)."""
        cfg = cfg or self.config
        pal = Palette.from_config(cfg)
        opacity = float(cfg.get("opacity", 0.88))
        ink = "#000000" if pal.is_light else "#ffffff"

        self.container.setStyleSheet(f"""
            #container {{
                background-color: {rgba(pal.bg, opacity)};
                border: 1px solid {rgba(ink, 0.12)};
                border-radius: 12px;
            }}
        """)
        self.lyric_widget.apply_style(cfg)
        self.lyrics_panel.apply_palette(pal, cfg.get("fontFamily", "Segoe UI"))

        self.lbl_grip.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {pal.muted};")
        self.lbl_time.setStyleSheet(f"font-size: 9px; color: {pal.muted}; min-width: 58px;")
        self.lbl_offset.setStyleSheet(f"font-size: 9px; color: {pal.accent};")
        self.sep.setStyleSheet(f"color: {pal.subtle};")
        self.lbl_status.setStyleSheet(f"font-size: 10px; color: {pal.muted};")
        self.resize_grip.setStyleSheet(f"""
            QLabel {{ color: {pal.subtle}; font-size: 13px; font-weight: bold; padding: 0 2px 2px 0; background: transparent; }}
            QLabel:hover {{ color: {pal.accent}; }}
        """)

        self.timeline_slider.setStyleSheet(f"""
            QSlider {{ background: transparent; }}
            QSlider::groove:horizontal {{ height: 2px; background: {rgba(pal.text, 0.25)}; border-radius: 1px; }}
            QSlider::sub-page:horizontal {{ background: {pal.accent}; height: 2px; border-radius: 1px; }}
            QSlider::handle:horizontal {{
                background: {pal.text}; width: 6px; height: 6px; margin: -2px 0; border-radius: 3px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {pal.accent}; width: 8px; height: 8px; margin: -3px 0; border-radius: 4px;
            }}
        """)

        btn_style = f"""
            QPushButton {{
                background: transparent; border: none; border-radius: 4px; padding: 2px;
                color: {pal.muted}; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {pal.hover}; color: {pal.text}; }}
            QPushButton:pressed {{ background: {pal.pressed}; }}
        """
        for btn in (self.btn_prev, self.btn_play, self.btn_next, self.btn_lock, self.btn_settings,
                    self.btn_minimize, self.btn_panel, self.btn_offset_minus, self.btn_offset_plus):
            btn.setStyleSheet(btn_style)
        self.btn_close.setStyleSheet(btn_style + "QPushButton:hover { background: #ef4444; color: #ffffff; }")

        hover_icon = "#000000" if pal.is_light else "#ffffff"
        self._icon_play = load_tinted_icon("play-button.png", pal.accent, hover_icon, 14)
        self._icon_pause = load_tinted_icon("pause.png", pal.accent, hover_icon, 14)
        self._icon_lock = load_tinted_icon("lock.png", pal.muted, hover_icon, 13)
        self._icon_unlock = load_tinted_icon("unlock.png", pal.muted, hover_icon, 13)
        self.btn_prev.setIcon(load_tinted_icon("back.png", pal.muted, hover_icon, 14))
        self.btn_next.setIcon(load_tinted_icon("next.png", pal.muted, hover_icon, 14))
        self.btn_settings.setIcon(load_tinted_icon("settings.png", pal.muted, hover_icon, 13))
        for btn, size in ((self.btn_prev, 14), (self.btn_play, 14), (self.btn_next, 14),
                          (self.btn_lock, 13), (self.btn_settings, 13)):
            btn.setIconSize(QSize(size, size))
        self.btn_prev.setToolTip("Voltar música")
        self.btn_next.setToolTip("Próxima música")
        self.btn_settings.setToolTip("Configurações e Temas")
        self._update_play_button()
        self._update_lock_button()

    def _update_play_button(self):
        self.btn_play.setIcon(self._icon_play if self.is_paused else self._icon_pause)
        self.btn_play.setToolTip("Reproduzir" if self.is_paused else "Pausar")

    def _update_lock_button(self):
        self.btn_lock.setIcon(self._icon_lock if self.is_locked else self._icon_unlock)
        self.btn_lock.setToolTip(
            "Travado: cliques passam pelo overlay. Destrave pela bandeja ou Ctrl+Alt+L" if self.is_locked
            else "Travar: o overlay deixa os cliques passarem (destrave pela bandeja ou Ctrl+Alt+L)"
        )

    # ------------------------------------------------------- Auto-ocultar

    def _init_auto_hide(self):
        self._bar_effects = []
        self._bar_anims = []
        for bar in (self.top_bar, self.bottom_bar):
            effect = QGraphicsOpacityEffect(bar)
            effect.setOpacity(1.0)
            bar.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity", self)
            self._bar_effects.append(effect)
            self._bar_anims.append(anim)
        self._controls_visible = True
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(AUTO_HIDE_DELAY_MS)
        self._hide_timer.timeout.connect(self._auto_hide_controls)

    def _set_controls_visible(self, visible: bool, animated: bool = True):
        if visible == self._controls_visible:
            return
        self._controls_visible = visible
        for effect, anim in zip(self._bar_effects, self._bar_anims):
            anim.stop()
            if animated:
                anim.setDuration(150 if visible else 400)
                anim.setStartValue(effect.opacity())
                anim.setEndValue(1.0 if visible else 0.0)
                anim.start()
            else:
                effect.setOpacity(1.0 if visible else 0.0)

    def _auto_hide_controls(self):
        if not self.config.get("autoHideControls", True) or self.lyrics_panel.isVisible():
            return
        busy = (self._is_user_seeking or QApplication.activePopupWidget() is not None
                or self.geometry().contains(QCursor.pos()))
        if busy:
            self._hide_timer.start()  # tenta de novo depois (menu aberto, mouse ainda em cima...)
            return
        self._set_controls_visible(False)

    def enterEvent(self, event):
        self._hide_timer.stop()
        self._set_controls_visible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.config.get("autoHideControls", True):
            self._hide_timer.start()
        super().leaveEvent(event)

    # ------------------------------------------------- Janela / bandeja

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def toggle_lock(self):
        self.set_locked(not self.is_locked)

    def set_locked(self, locked: bool):
        """Travado = cliques passam pelo overlay (não dá para arrastar nem clicar nos botões)."""
        self.is_locked = locked
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowTransparentForInput, locked)
        if was_visible:
            self.show()  # trocar flags de janela a esconde
        self._set_controls_visible(not locked, animated=False)
        if not locked and self.config.get("autoHideControls", True):
            self._hide_timer.start()
        self._update_lock_button()
        self.config["locked"] = locked
        self.schedule_config_save()
        if locked:
            self.tray_icon.showMessage(
                "LetrasBR travado", "Os cliques agora passam pelo overlay. Destrave pela bandeja ou com Ctrl+Alt+L.",
                self.windowIcon(), 4000
            )

    def _on_hotkey(self, name: str):
        if name == "lock":
            self.toggle_lock()

    def exit_application(self):
        if self._save_timer.isActive():  # Grava posição/tamanho pendentes antes de sair
            self._save_timer.stop()
            save_config(self.config)
        self.hotkeys.unregister_all()
        self.tray_icon.hide()
        if self.media_monitor:
            self.media_monitor.stop()
        QApplication.quit()

    def _toggle_compact(self):
        self.is_compact = not self.is_compact
        if self.is_compact and self.lyrics_panel.isVisible():
            self.toggle_lyrics_panel()
        self.lyric_widget.setVisible(not self.is_compact)
        self.bottom_bar.setVisible(not self.is_compact)
        self.resize(self.width(), 36 if self.is_compact else self.config.get("height", 115))

    def toggle_lyrics_panel(self):
        opening = not self.lyrics_panel.isVisible()
        if opening and self.is_compact:
            self._toggle_compact()
        self.lyrics_panel.setVisible(opening)
        self.btn_panel.setToolTip("Esconder a letra completa" if opening else "Mostrar a letra completa")
        self.resize(self.width(), self.height() + (PANEL_HEIGHT if opening else -PANEL_HEIGHT))
        if opening:
            self.lyrics_panel.set_active(self.lyric_widget.active_index())

    def send_media_cmd(self, action: str):
        if self.media_monitor:
            self.media_monitor.send_command(action)

    # -------------------------------------------------------- Timeline

    def _on_slider_released(self):
        if self.current_duration > 0 and self.media_monitor:
            self.media_monitor.send_seek((self.timeline_slider.value() / 1000.0) * self.current_duration)
        self._is_user_seeking = False

    def _on_slider_moved(self, value: int):
        if self.current_duration > 0:
            cur = (value / 1000.0) * self.current_duration
            self.lbl_time.setText(f"{format_time_str(cur)} / {format_time_str(self.current_duration)}")

    def _seek_to_line(self, start_ms: int):
        if self.media_monitor:
            # Compensa o ajuste de sincronia para o verso aparecer exatamente ao pular
            self.media_monitor.send_seek(max(0.0, (start_ms - self._offset_ms) / 1000.0))

    # ------------------------------------------------- Sincronia por música

    def adjust_offset(self, delta_ms: Optional[int]):
        """Soma delta_ms ao ajuste da música atual (None zera). Positivo = letra aparece mais cedo."""
        if not self.current_title:
            return
        self._offset_ms = 0 if delta_ms is None else self._offset_ms + delta_ms
        track_prefs.set_offset_ms(self.current_artist, self.current_title, self._offset_ms)
        self._update_offset_label()
        self._update_active_line()

    def _update_offset_label(self):
        self.lbl_offset.setText(format_offset(self._offset_ms) if self._offset_ms else "")
        self.lbl_offset.setVisible(bool(self._offset_ms))

    # ------------------------------------------------------ Menu da música

    def _show_song_menu(self):
        if not self.current_title:
            return
        menu = QMenu(self)
        if self._result and self._result.translation_url:
            url = self._result.translation_url
            menu.addAction("Abrir tradução no Letras.mus.br", lambda: webbrowser.open(url))
        menu.addAction("Música errada? Colar link do Letras.mus.br...", self._fix_letras_page)
        if track_prefs.get_letras_path(self.current_artist, self.current_title):
            menu.addAction("Desfazer correção (buscar automaticamente)", lambda: self._set_letras_path(None))
        menu.addAction("Recarregar letra e tradução", self._reload_lyrics)
        menu.addSeparator()
        menu.addAction("Adiantar letra 0,25 s   ]", lambda: self.adjust_offset(OFFSET_STEP_MS))
        menu.addAction("Atrasar letra 0,25 s   [", lambda: self.adjust_offset(-OFFSET_STEP_MS))
        if self._offset_ms:
            menu.addAction(f"Zerar ajuste de sincronia ({format_offset(self._offset_ms)})", lambda: self.adjust_offset(None))
        menu.exec(QCursor.pos())

    def _fix_letras_page(self):
        text, ok = QInputDialog.getText(
            self, "Música errada?",
            f"Cole o link da música correta no Letras.mus.br\n(ex: {BASE_URL}/artista/musica/)",
            QLineEdit.Normal, "",
        )
        if not ok or not text.strip():
            return
        path = letras_path_from_url(text)
        if not path:
            QMessageBox.warning(self, "Link inválido", "Não reconheci um link de música do Letras.mus.br.")
            return
        self._set_letras_path(path)

    def _set_letras_path(self, path: Optional[str]):
        track_prefs.set_letras_path(self.current_artist, self.current_title, path)
        self._reload_lyrics()

    def _reload_lyrics(self):
        self.lyrics_client.invalidate(self.current_artist, self.current_title)
        clear_translation_cache()
        self._on_track_changed(self.current_title, self.current_artist, self.current_album, self.current_duration)

    # ------------------------------------------------------ Eventos de mídia

    @Slot(str)
    def _on_source_changed(self, source: str):
        self._current_source = source
        self._update_source_icon_display(source)

    def _update_source_icon_display(self, source: str):
        names = {"spotify": ("spotify.png", "Spotify"), "youtube": ("youtube.png", "YouTube Music")}
        if source not in names:
            return
        file_name, label = names[source]
        icon_file = os.path.join(ASSETS_DIR, file_name)
        if not os.path.exists(icon_file):
            icon_file = os.path.join(ASSETS_DIR, "app.png")
        if os.path.exists(icon_file):
            self.lbl_source_icon.setPixmap(QPixmap(icon_file).scaled(14, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.lbl_source_icon.setToolTip(f"Sincronizado via {label}")

    @Slot(bytes)
    def _on_cover_changed(self, image_bytes: bytes):
        self._cover_theme = theme_from_cover(image_bytes) if image_bytes else None
        if self._cover_theme and self.config.get("theme") == DYNAMIC_THEME_NAME:
            self.config.update(self._cover_theme)
            self._apply_current_style()

    @Slot(str, str, str, float)
    def _on_track_changed(self, title: str, artist: str, album: str, duration: float):
        """Música mudou (autoplay ou pulo manual): feedback imediato e busca da letra em segundo plano."""
        self.current_title = title
        self.current_artist = artist
        self.current_album = album
        self.current_duration = duration
        self.aligned_lyrics = []
        self._result = None
        self.lyric_widget.set_lines([])
        self.lyrics_panel.set_lines([])
        self._offset_ms = track_prefs.get_offset_ms(artist, title) if title else 0
        self._update_offset_label()

        if not title:
            self.lbl_source_icon.setVisible(False)
            self.lbl_status.setText("Aguardando reprodução no Windows (YouTube Music / Spotify)...")
            self.lyric_widget.set_message("Aguardando reprodução no Windows...", animated=False)
            return

        self.lbl_source_icon.setVisible(False)
        self.lbl_status.setText(f"{artist} - {title}")
        self.lyric_widget.set_message("Carregando tradução...", f"{artist} - {title}")

        self.lyrics_client.fetch_lyrics(
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            lang=self.config.get("lang", "pt"),
            source=self._current_source,
            auto_translate=bool(self.config.get("autoTranslate", True)),
            on_success=self._on_lyrics_loaded,
            on_error=self._on_lyrics_error
        )

    def _on_lyrics_loaded(self, req_id: int, result: LyricsResult):
        self._result = result
        self.aligned_lyrics = result.aligned if result else []
        self.lyric_widget.set_lines(self.aligned_lyrics)
        self.lyrics_panel.set_lines(self.aligned_lyrics)
        if not self.aligned_lyrics:
            self.lbl_source_icon.setVisible(False)
            self.lbl_status.setText(f"⚠️ {self.current_artist} - {self.current_title} (sem sincronização)")
            self.lyric_widget.set_message("Letra sincronizada não disponível no momento.", animated=False)
            return

        self._update_source_icon_display(self._current_source)
        self.lbl_source_icon.setVisible(True)

        notes = []
        if result.timing_source == "estimated":
            notes.append("sincronia estimada")
        notes.append(TRANSLATION_SOURCE_LABELS.get(result.translation_source, ""))
        suffix = " · ".join(n for n in notes if n)
        self.lbl_status.setText(f"{self.current_artist} - {self.current_title}" + (f"  ·  {suffix}" if suffix else ""))

        timing_name = TIMING_SOURCE_LABELS.get(result.timing_source, result.timing_source)
        tooltip = f"Sincronizado ({len(self.aligned_lyrics)} versos) via {timing_name}"
        if suffix:
            tooltip += f"\nTradução: {suffix}"
        if result.translation_url:
            tooltip += f"\n{result.translation_url}"
        tooltip += "\n\nClique para: música errada?, ajuste de sincronia, recarregar"
        self.lbl_source_icon.setToolTip(tooltip)
        self.lbl_status.setToolTip(tooltip)
        self._update_active_line()

    def _on_lyrics_error(self, req_id: int, err_msg: str):
        self.lbl_source_icon.setVisible(False)
        self.lbl_status.setText("⚠️ Tradução não encontrada")
        self.lyric_widget.set_message("Tradução não disponível para esta faixa.", animated=False)

    @Slot(float, float, bool)
    def _on_playback_tick(self, current_seconds: float, duration: float, is_paused: bool):
        """Atualização de alta precisão a cada ~100ms"""
        self.current_time_seconds = current_seconds
        if is_paused != self.is_paused:
            self.is_paused = is_paused
            self._update_play_button()

        if not self._is_user_seeking:
            if duration > 0:
                self.timeline_slider.setValue(int(min(1.0, max(0.0, current_seconds / duration)) * 1000))
                self.lbl_time.setText(f"{format_time_str(current_seconds)} / {format_time_str(duration)}")
            else:
                self.timeline_slider.setValue(0)
                self.lbl_time.setText(format_time_str(current_seconds))

        self._update_active_line()

    def _update_active_line(self):
        if not self.aligned_lyrics:
            return
        index = find_active_index(self.aligned_lyrics, int(self.current_time_seconds * 1000) + self._offset_ms)
        if index >= 0:
            self.lyric_widget.set_active_index(index)
            if self.lyrics_panel.isVisible():
                self.lyrics_panel.set_active(index)

    # ------------------------------------------------------ Configurações

    def open_settings(self):
        original = dict(self.config)
        dlg = SettingsDialogQt(self.config, self, cover_theme=self._cover_theme)
        dlg.preview_changed.connect(self._apply_current_style)
        dlg.config_saved.connect(self._on_config_updated)
        if not dlg.exec():
            self._apply_current_style(original)  # Cancelar desfaz a pré-visualização

    def _on_config_updated(self, new_cfg: dict):
        old_cfg = self.config
        self.config = new_cfg
        if new_cfg.get("theme") == DYNAMIC_THEME_NAME and self._cover_theme:
            self.config.update(self._cover_theme)
        self._apply_current_style()

        # Só recarrega a música atual se mudou algo que afeta a tradução (idioma ou fallback automático)
        translation_changed = any(old_cfg.get(k) != new_cfg.get(k) for k in ("lang", "autoTranslate"))
        if translation_changed and self.current_title and self.current_artist:
            self._on_track_changed(self.current_title, self.current_artist, self.current_album, self.current_duration)

    # ------------------------------------------------- Arraste e tamanho

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.is_locked:
            self._is_dragging = True
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and not self.is_locked:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._is_dragging:
            self._is_dragging = False
            self.config["x"] = self.x()
            self.config["y"] = self.y()
            self.schedule_config_save()
            event.accept()

    def schedule_config_save(self):
        """Agrupa gravações seguidas (arraste/redimensionamento) numa única escrita em disco."""
        self._save_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Modo compacto e painel da letra completa são temporários: não alteram o tamanho salvo
        if not self.is_compact and not self.lyrics_panel.isVisible():
            self.config["width"] = self.width()
            self.config["height"] = self.height()
            self.schedule_config_save()
