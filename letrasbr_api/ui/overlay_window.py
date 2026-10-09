"""
Janela principal do overlay flutuante: sem bordas, translúcida, arrastável e redimensionável,
com miniplayer integrado ao Windows (GSMTC) e sincronização das letras em tempo real.
"""

import os
from typing import Optional, List

from PySide6.QtCore import Qt, QPoint, QSize, QTimer, Slot
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QSlider

from ..aligner import find_active_aligned_line, AlignedLine
from ..config import get_config, save_config
from ..lyrics_client import LyricsClient
from ..media_monitor import WindowsMediaMonitor
from ..pipeline import LyricsResult
from .icons import ASSETS_DIR, load_tinted_icon
from .lyric_view import LyricContainerWidget
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
            self.window.schedule_config_save()
            event.accept()


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

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(lambda: save_config(self.config))

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

        # Ícone e menu da bandeja do sistema
        self.tray_icon = create_tray_icon(self)

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
        self.btn_prev.clicked.connect(lambda: self.send_media_cmd("previous"))
        top_layout.addWidget(self.btn_prev)

        self.btn_play = QPushButton(self.top_bar)
        self.btn_play.setFixedSize(22, 22)
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(lambda: self.send_media_cmd("play_pause"))
        top_layout.addWidget(self.btn_play)

        self.btn_next = QPushButton(self.top_bar)
        self.btn_next.setFixedSize(22, 22)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.clicked.connect(lambda: self.send_media_cmd("next"))
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

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def exit_application(self):
        if self._save_timer.isActive():  # Grava posição/tamanho pendentes antes de sair
            self._save_timer.stop()
            save_config(self.config)
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
        if source == "spotify":
            icon_file = os.path.join(ASSETS_DIR, "spotify.png")
            if os.path.exists(icon_file):
                self.lbl_source_icon.setPixmap(QPixmap(icon_file).scaled(14, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.lbl_source_icon.setToolTip("Sincronizado via Spotify")
        elif source == "youtube":
            icon_file = os.path.join(ASSETS_DIR, "youtube.png")
            if not os.path.exists(icon_file):
                icon_file = os.path.join(ASSETS_DIR, "app.png")
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

    def send_media_cmd(self, action: str):
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

        # Dispara busca desacoplada assíncrona
        self.lyrics_client.fetch_lyrics(
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            lang=self.config.get("lang", "pt"),
            source=getattr(self, "_current_source", "youtube"),
            auto_translate=bool(self.config.get("autoTranslate", True)),
            on_success=self._on_lyrics_loaded,
            on_error=self._on_lyrics_error
        )

    def _on_lyrics_loaded(self, req_id: int, result: LyricsResult):
        self.aligned_lyrics = result.aligned if result else []
        if self.aligned_lyrics:
            # O ícone do player ativo substitui o antigo texto "🟢 Sincronizado"
            self._update_source_icon_display(getattr(self, "_current_source", "youtube"))
            self.lbl_source_icon.setVisible(True)

            notes = []
            if result.timing_source == "estimated":
                notes.append("sincronia estimada")
            notes.append(TRANSLATION_SOURCE_LABELS.get(result.translation_source, ""))
            suffix = " · ".join(n for n in notes if n)
            self.lbl_status.setText(f"{self.current_artist} - {self.current_title}" + (f"  ·  {suffix}" if suffix else ""))

            versos = len(self.aligned_lyrics)
            timing_name = TIMING_SOURCE_LABELS.get(result.timing_source, result.timing_source)
            tooltip = f"Sincronizado ({versos} versos) via {timing_name}"
            if suffix:
                tooltip += f"\nTradução: {suffix}"
            if result.translation_url:
                tooltip += f"\n{result.translation_url}"
            self.lbl_source_icon.setToolTip(tooltip)
            self.lbl_status.setToolTip(tooltip)
        else:
            self.lbl_source_icon.setVisible(False)
            self.lbl_status.setText(f"⚠️ {self.current_artist} - {self.current_title} (sem sincronização)")
            self.lyric_widget.set_texts_instant("Letra sincronizada não disponível no momento.", "")

    def _on_lyrics_error(self, req_id: int, err_msg: str):
        self.lbl_source_icon.setVisible(False)
        self.lbl_status.setText("⚠️ Tradução não encontrada")
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
                translation = active_line.translation
                if active_line.source == "auto" and translation:
                    translation = f"≈ {translation}"  # Marca tradução automática
                self.lyric_widget.set_texts_animated(active_line.original, translation)

    def open_settings(self):
        dlg = SettingsDialogQt(self.config, self)
        dlg.config_saved.connect(self._on_config_updated)
        dlg.exec()

    def _on_config_updated(self, new_cfg: dict):
        old_cfg = self.config
        self.config = new_cfg
        self._apply_current_style()

        # Só recarrega a música atual se mudou algo que afeta a tradução (idioma ou fallback automático)
        translation_changed = any(old_cfg.get(k) != new_cfg.get(k) for k in ("lang", "autoTranslate"))
        if translation_changed and self.current_title and self.current_artist:
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
            self.schedule_config_save()
            event.accept()

    def schedule_config_save(self):
        """Agrupa gravações seguidas (arraste/redimensionamento) numa única escrita em disco."""
        self._save_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.is_compact:
            self.config["width"] = self.width()
            self.config["height"] = self.height()
            self.schedule_config_save()
