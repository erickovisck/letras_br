import sys
import os
import tkinter as tk
from tkinter import ttk
from typing import Optional

# Configurações e estado compartilhado
from config import get_config, save_config, add_config_listener


class LyricsOverlay:
    def __init__(self, playback_state=None, on_language_change=None, on_player_action=None):
        self.state = playback_state
        self.on_language_change = on_language_change
        self.on_player_action = on_player_action
        self.config = get_config()

        self.root = tk.Tk()
        self.root.title("LetrasBR Overlay")

        # Configurações de janela flutuante
        self.root.overrideredirect(True)  # Sem bordas do Windows
        self.root.attributes("-topmost", True)  # Sempre no topo
        self.root.configure(bg="#121216")

        # Variáveis de arraste (mover)
        self.drag_data = {"x": 0, "y": 0, "win_x": 0, "win_y": 0}
        self.is_dragging = False

        # Variáveis de redimensionamento (largura e altura)
        self.resize_data = {"start_x": 0, "start_y": 0, "start_w": 650, "start_h": 110}
        self.is_resizing = False

        # Variáveis de conteúdo
        self.last_orig = ""
        self.last_trans = ""
        self.last_title = ""
        self.last_paused = None
        self.settings_window = None

        # Monta a interface
        self._build_ui()
        self._apply_config(self.config)

        # Registra ouvinte para alterações de configuração vindas da API/Extensão
        add_config_listener(self._on_external_config_change)

        # Inicia loop de atualização da letra e player (100ms)
        self.root.after(100, self._tick)

    def _build_ui(self):
        # Container principal com borda sutil
        self.main_frame = tk.Frame(self.root, bg="#121216", highlightbackground="#2d3748", highlightthickness=1)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Barra de controle superior (Grip, Miniplayer, Título/Status, Botões de controle)
        self.top_bar = tk.Frame(self.main_frame, bg="#1a1a24", height=26)
        self.top_bar.pack(side=tk.TOP, fill=tk.X)
        self.top_bar.pack_propagate(False)

        # Grip / Indicador de arraste
        self.grip_label = tk.Label(
            self.top_bar,
            text=" ⠿ LetrasBR",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg="#1a1a24",
            cursor="fleur"
        )
        self.grip_label.pack(side=tk.LEFT, padx=(4, 2))

        # Separador
        sep_player = tk.Label(self.top_bar, text="|", font=("Segoe UI", 8), fg="#334155", bg="#1a1a24")
        sep_player.pack(side=tk.LEFT, padx=1)

        # ----------------------------------------------------
        # Miniplayer Integrado: Pausar / Continuar e Pular Música
        # ----------------------------------------------------
        self.btn_play_pause = tk.Label(
            self.top_bar,
            text="⏸",
            font=("Segoe UI", 9, "bold"),
            fg="#f8fafc",
            bg="#1a1a24",
            cursor="hand2",
            padx=4
        )
        self.btn_play_pause.pack(side=tk.LEFT)
        self.btn_play_pause.bind("<Button-1>", lambda e: self.send_player_action("play_pause"))
        self.btn_play_pause.bind("<Enter>", lambda e: self.btn_play_pause.configure(fg="#38bdf8"))
        self.btn_play_pause.bind("<Leave>", lambda e: self._refresh_play_pause_color())

        self.btn_next = tk.Label(
            self.top_bar,
            text="⏭",
            font=("Segoe UI", 9, "bold"),
            fg="#cbd5e1",
            bg="#1a1a24",
            cursor="hand2",
            padx=4
        )
        self.btn_next.pack(side=tk.LEFT)
        self.btn_next.bind("<Button-1>", lambda e: self.send_player_action("next"))
        self.btn_next.bind("<Enter>", lambda e: self.btn_next.configure(fg="#38bdf8"))
        self.btn_next.bind("<Leave>", lambda e: self.btn_next.configure(fg="#cbd5e1"))

        # Separador pós miniplayer
        sep_after = tk.Label(self.top_bar, text="|", font=("Segoe UI", 8), fg="#334155", bg="#1a1a24")
        sep_after.pack(side=tk.LEFT, padx=1)

        # Status / Título curto da música
        self.title_bar_label = tk.Label(
            self.top_bar,
            text="",
            font=("Segoe UI", 8),
            fg="#64748b",
            bg="#1a1a24",
            anchor="w"
        )
        self.title_bar_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # Botão de Configurações ⚙️
        self.btn_settings = tk.Label(
            self.top_bar,
            text="⚙",
            font=("Segoe UI", 10),
            fg="#cbd5e1",
            bg="#1a1a24",
            cursor="hand2",
            padx=5
        )
        self.btn_settings.pack(side=tk.RIGHT)
        self.btn_settings.bind("<Button-1>", lambda e: self.open_settings())
        self.btn_settings.bind("<Enter>", lambda e: self.btn_settings.configure(fg="#38bdf8"))
        self.btn_settings.bind("<Leave>", lambda e: self.btn_settings.configure(fg="#cbd5e1"))

        # Botão Travar/Destravar Posição e Redimensionamento 🔓/🔒
        self.btn_lock = tk.Label(
            self.top_bar,
            text="🔓",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#1a1a24",
            cursor="hand2",
            padx=4
        )
        self.btn_lock.pack(side=tk.RIGHT)
        self.btn_lock.bind("<Button-1>", lambda e: self._toggle_lock())

        # Botão Minimizar/Ocultar 🗕
        self.btn_min = tk.Label(
            self.top_bar,
            text="—",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg="#1a1a24",
            cursor="hand2",
            padx=4
        )
        self.btn_min.pack(side=tk.RIGHT)
        self.btn_min.bind("<Button-1>", lambda e: self._toggle_compact_mode())

        # Botão Fechar ✕
        self.btn_close = tk.Label(
            self.top_bar,
            text="✕",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#1a1a24",
            cursor="hand2",
            padx=5
        )
        self.btn_close.pack(side=tk.RIGHT)
        self.btn_close.bind("<Button-1>", lambda e: self.quit())
        self.btn_close.bind("<Enter>", lambda e: self.btn_close.configure(fg="#ef4444"))
        self.btn_close.bind("<Leave>", lambda e: self.btn_close.configure(fg="#94a3b8"))

        # Configura eventos de mouse para arrastar a janela
        for widget in (self.top_bar, self.grip_label, self.title_bar_label):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)
            widget.bind("<ButtonRelease-1>", self._stop_drag)

        # Barra inferior com Alça de Redimensionamento (Height + Width)
        self.bottom_bar = tk.Frame(self.main_frame, bg="#121216", height=14)
        self.bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.bottom_bar.pack_propagate(False)

        # Alça de redimensionamento no canto inferior direito
        self.resize_grip = tk.Label(
            self.bottom_bar,
            text="⇲",
            font=("Segoe UI", 8),
            fg="#475569",
            bg="#121216",
            cursor="size_nw_se",
            padx=3
        )
        self.resize_grip.pack(side=tk.RIGHT)
        self.resize_grip.bind("<Button-1>", self._start_resize)
        self.resize_grip.bind("<B1-Motion>", self._on_resize)
        self.resize_grip.bind("<ButtonRelease-1>", self._stop_resize)
        self.resize_grip.bind("<Enter>", lambda e: self.resize_grip.configure(fg="#38bdf8"))
        self.resize_grip.bind("<Leave>", lambda e: self.resize_grip.configure(fg="#475569"))

        # A barra inferior também permite redimensionar altura arrastando
        self.bottom_bar.bind("<Button-1>", self._start_resize)
        self.bottom_bar.bind("<B1-Motion>", self._on_resize)
        self.bottom_bar.bind("<ButtonRelease-1>", self._stop_resize)

        # Área de exibição das letras
        self.lyrics_frame = tk.Frame(self.main_frame, bg="#121216")
        self.lyrics_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # Label da Linha Original
        self.lbl_original = tk.Label(
            self.lyrics_frame,
            text="Aguardando reprodução no YouTube Music...",
            font=("Segoe UI", self.config.get("fontSize", 15)),
            fg="#cbd5e1",
            bg="#121216",
            wraplength=self.config.get("width", 650) - 24,
            justify="center",
            anchor="center"
        )
        self.lbl_original.pack(fill=tk.BOTH, expand=True)

        # Label da Linha Traduzida
        self.lbl_translation = tk.Label(
            self.lyrics_frame,
            text="",
            font=("Segoe UI", int(self.config.get("fontSize", 15) * 1.15), "bold"),
            fg="#38bdf8",
            bg="#121216",
            wraplength=self.config.get("width", 650) - 24,
            justify="center",
            anchor="center"
        )
        self.lbl_translation.pack(fill=tk.BOTH, expand=True)

        # Permite arrastar também clicando na área de texto se não estiver travado
        for lbl in (self.lyrics_frame, self.lbl_original, self.lbl_translation):
            lbl.bind("<Button-1>", self._start_drag)
            lbl.bind("<B1-Motion>", self._on_drag)
            lbl.bind("<ButtonRelease-1>", self._stop_drag)

    def send_player_action(self, action: str):
        """Dispara comando de reprodução (play_pause, next) para o YouTube Music"""
        if self.on_player_action:
            self.on_player_action(action)
        elif self.state:
            self.state.pending_command = action

    def _refresh_play_pause_color(self):
        is_paused = getattr(self.state, "is_paused", False) if self.state else False
        self.btn_play_pause.configure(fg="#38bdf8" if is_paused else "#f8fafc")

    # ----------------------------------------------------
    # Arraste / Movimentação da Janela
    # ----------------------------------------------------
    def _start_drag(self, event):
        if self.config.get("locked", False):
            return
        self.drag_data["x"] = event.x_root
        self.drag_data["y"] = event.y_root
        self.drag_data["win_x"] = self.root.winfo_x()
        self.drag_data["win_y"] = self.root.winfo_y()
        self.is_dragging = True

    def _on_drag(self, event):
        if not self.is_dragging or self.config.get("locked", False):
            return
        dx = event.x_root - self.drag_data["x"]
        dy = event.y_root - self.drag_data["y"]
        new_x = self.drag_data["win_x"] + dx
        new_y = self.drag_data["win_y"] + dy
        self.root.geometry(f"+{new_x}+{new_y}")

    def _stop_drag(self, event):
        if not self.is_dragging:
            return
        self.is_dragging = False
        new_x = self.root.winfo_x()
        new_y = self.root.winfo_y()
        self.config["x"] = new_x
        self.config["y"] = new_y
        save_config({"x": new_x, "y": new_y})

    # ----------------------------------------------------
    # Redimensionamento (Largura e Altura)
    # ----------------------------------------------------
    def _start_resize(self, event):
        if self.config.get("locked", False):
            return
        self.resize_data["start_x"] = event.x_root
        self.resize_data["start_y"] = event.y_root
        self.resize_data["start_w"] = self.root.winfo_width()
        self.resize_data["start_h"] = self.root.winfo_height()
        self.is_resizing = True

    def _on_resize(self, event):
        if not self.is_resizing or self.config.get("locked", False):
            return
        dx = event.x_root - self.resize_data["start_x"]
        dy = event.y_root - self.resize_data["start_y"]

        # Limites mínimos para não colapsar a interface
        new_w = max(320, self.resize_data["start_w"] + dx)
        new_h = max(80, self.resize_data["start_h"] + dy)

        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.root.geometry(f"{new_w}x{new_h}+{x}+{y}")

        # Atualiza a quebra de linha das letras dinamicamente
        self.lbl_original.configure(wraplength=new_w - 24)
        self.lbl_translation.configure(wraplength=new_w - 24)

    def _stop_resize(self, event):
        if not self.is_resizing:
            return
        self.is_resizing = False
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        self.config["width"] = w
        self.config["height"] = h
        save_config({"width": w, "height": h})

    def _toggle_lock(self):
        locked = not self.config.get("locked", False)
        self.config["locked"] = locked
        self.btn_lock.configure(text="🔒" if locked else "🔓", fg="#ef4444" if locked else "#94a3b8")
        save_config({"locked": locked})

    def _toggle_compact_mode(self):
        """Oculta/exibe barra de título para modo ultra compacto"""
        if self.top_bar.winfo_viewable():
            self.top_bar.pack_forget()
            self.root.bind("<Double-Button-1>", lambda e: self._toggle_compact_mode())
        else:
            self.top_bar.pack(side=tk.TOP, fill=tk.X, before=self.lyrics_frame)
            self.root.unbind("<Double-Button-1>")

    def _apply_config(self, cfg: dict):
        self.config.update(cfg)

        x = self.config.get("x", 100)
        y = self.config.get("y", 100)
        w = max(320, int(self.config.get("width", 650)))
        h = max(80, int(self.config.get("height", 110)))
        opacity = max(0.2, min(1.0, float(self.config.get("opacity", 0.85))))
        font_size = max(10, min(36, int(self.config.get("fontSize", 15))))
        locked = self.config.get("locked", False)
        display_mode = self.config.get("displayMode", "both")

        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.attributes("-alpha", opacity)

        self.lbl_original.configure(
            font=("Segoe UI", font_size),
            wraplength=w - 24
        )
        self.lbl_translation.configure(
            font=("Segoe UI", int(font_size * 1.15), "bold"),
            wraplength=w - 24
        )

        self.btn_lock.configure(text="🔒" if locked else "🔓", fg="#ef4444" if locked else "#94a3b8")
        self._update_display_mode(display_mode)

    def _update_display_mode(self, mode: str):
        self.lbl_original.pack_forget()
        self.lbl_translation.pack_forget()

        if mode == "trans":
            self.lbl_translation.pack(fill=tk.BOTH, expand=True)
        elif mode == "orig":
            self.lbl_original.pack(fill=tk.BOTH, expand=True)
        else:  # "both"
            self.lbl_original.pack(fill=tk.BOTH, expand=True)
            self.lbl_translation.pack(fill=tk.BOTH, expand=True)

    def _on_external_config_change(self, new_config: dict):
        """Chamado quando a configuração é atualizada pela API ou Extensão"""
        try:
            self.root.after(0, lambda: self._apply_config(new_config))
        except Exception:
            pass

    def _tick(self):
        """Loop a cada 100ms para refletir letras, status e miniplayer em tempo real"""
        if self.state:
            title = self.state.title or ""
            artist = self.state.artist or ""
            orig = self.state.active_original or ""
            trans = self.state.active_translation or ""
            lang = (self.state.lang or "pt").upper()
            is_paused = getattr(self.state, "is_paused", False)

            # Atualiza botão do miniplayer (Pausado vs Reproduzindo)
            if is_paused != self.last_paused:
                self.last_paused = is_paused
                self.btn_play_pause.configure(
                    text="▶" if is_paused else "⏸",
                    fg="#38bdf8" if is_paused else "#f8fafc"
                )

            # Atualiza título/artista na barra superior se mudou
            curr_title_str = f"{artist} - {title} [{lang}]" if title else ""
            if curr_title_str != self.last_title:
                self.last_title = curr_title_str
                self.title_bar_label.configure(text=curr_title_str)

            # Atualiza texto das letras
            if orig != self.last_orig or trans != self.last_trans:
                self.last_orig = orig
                self.last_trans = trans

                if not orig and not trans:
                    if title:
                        self.lbl_original.configure(text=f"{artist} - {title}", fg="#94a3b8")
                        self.lbl_translation.configure(text="⏳ Aguardando início dos versos...")
                    else:
                        self.lbl_original.configure(text="Aguardando reprodução no YouTube Music...", fg="#64748b")
                        self.lbl_translation.configure(text="")
                else:
                    self.lbl_original.configure(text=orig if orig else " ", fg="#cbd5e1")
                    self.lbl_translation.configure(text=trans if trans else " ", fg="#38bdf8")

        self.root.after(100, self._tick)

    def open_settings(self):
        """Janela flutuante de configurações moderna"""
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_force()
            return

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Configurações do Tradutor")
        self.settings_window.geometry("380x480")
        self.settings_window.configure(bg="#181822")
        self.settings_window.attributes("-topmost", True)
        self.settings_window.resizable(False, False)

        # Centraliza próximo ao overlay
        win_x = self.root.winfo_x() + 30
        win_y = self.root.winfo_y() + 30
        self.settings_window.geometry(f"+{win_x}+{win_y}")

        # Título
        lbl_header = tk.Label(
            self.settings_window,
            text="⚙ Configurações do Overlay",
            font=("Segoe UI", 13, "bold"),
            fg="#f8fafc",
            bg="#181822"
        )
        lbl_header.pack(pady=(14, 8))

        container = tk.Frame(self.settings_window, bg="#181822", padx=20)
        container.pack(fill=tk.BOTH, expand=True)

        # 1. Opacidade
        lbl_op = tk.Label(container, text="Opacidade da Janela:", font=("Segoe UI", 10, "bold"), fg="#94a3b8", bg="#181822")
        lbl_op.pack(anchor="w", pady=(4, 2))

        op_val = tk.DoubleVar(value=float(self.config.get("opacity", 0.85)))
        slider_op = ttk.Scale(container, from_=0.2, to=1.0, variable=op_val, orient=tk.HORIZONTAL)
        slider_op.pack(fill=tk.X, pady=(0, 2))

        lbl_op_indicator = tk.Label(container, text=f"{int(op_val.get() * 100)}%", font=("Segoe UI", 9), fg="#38bdf8", bg="#181822")
        lbl_op_indicator.pack(anchor="e")

        def on_opacity_change(val):
            v = float(val)
            lbl_op_indicator.configure(text=f"{int(v * 100)}%")
            self.config["opacity"] = round(v, 2)
            self.root.attributes("-alpha", v)
            save_config({"opacity": self.config["opacity"]})

        slider_op.configure(command=on_opacity_change)

        # 2. Tamanho da Fonte
        lbl_fs = tk.Label(container, text="Tamanho da Fonte:", font=("Segoe UI", 10, "bold"), fg="#94a3b8", bg="#181822")
        lbl_fs.pack(anchor="w", pady=(6, 2))

        fs_val = tk.IntVar(value=int(self.config.get("fontSize", 15)))
        slider_fs = ttk.Scale(container, from_=10, to=30, variable=fs_val, orient=tk.HORIZONTAL)
        slider_fs.pack(fill=tk.X, pady=(0, 2))

        lbl_fs_indicator = tk.Label(container, text=f"{fs_val.get()} px", font=("Segoe UI", 9), fg="#38bdf8", bg="#181822")
        lbl_fs_indicator.pack(anchor="e")

        def on_font_change(val):
            v = int(float(val))
            lbl_fs_indicator.configure(text=f"{v} px")
            self.config["fontSize"] = v
            self.lbl_original.configure(font=("Segoe UI", v))
            self.lbl_translation.configure(font=("Segoe UI", int(v * 1.15), "bold"))
            save_config({"fontSize": v})

        slider_fs.configure(command=on_font_change)

        # 3. Tamanho da Janela (Presets Rápidos)
        lbl_size = tk.Label(container, text="Tamanho da Janela (Largura x Altura):", font=("Segoe UI", 10, "bold"), fg="#94a3b8", bg="#181822")
        lbl_size.pack(anchor="w", pady=(6, 4))

        size_frame = tk.Frame(container, bg="#181822")
        size_frame.pack(fill=tk.X, pady=(0, 6))

        def apply_size(w, h):
            self.config["width"] = w
            self.config["height"] = h
            self.root.geometry(f"{w}x{h}+{self.root.winfo_x()}+{self.root.winfo_y()}")
            self.lbl_original.configure(wraplength=w - 24)
            self.lbl_translation.configure(wraplength=w - 24)
            save_config({"width": w, "height": h})

        presets = [("Pequeno", 480, 95), ("Médio", 650, 115), ("Grande", 820, 140)]
        for label, pw, ph in presets:
            b = tk.Button(
                size_frame,
                text=f"{label} ({pw}x{ph})",
                font=("Segoe UI", 8),
                bg="#27273a",
                fg="#cbd5e1",
                activebackground="#38bdf8",
                activeforeground="#ffffff",
                relief=tk.FLAT,
                padx=4,
                pady=3,
                cursor="hand2",
                command=lambda w=pw, h=ph: apply_size(w, h)
            )
            b.pack(side=tk.LEFT, expand=True, padx=2)

        # 4. Modo de Exibição
        lbl_mode = tk.Label(container, text="Modo de Exibição:", font=("Segoe UI", 10, "bold"), fg="#94a3b8", bg="#181822")
        lbl_mode.pack(anchor="w", pady=(6, 4))

        mode_var = tk.StringVar(value=self.config.get("displayMode", "both"))
        mode_frame = tk.Frame(container, bg="#181822")
        mode_frame.pack(fill=tk.X, pady=(0, 4))

        def on_mode_change():
            m = mode_var.get()
            self.config["displayMode"] = m
            self._update_display_mode(m)
            save_config({"displayMode": m})

        modes = [("Ambos", "both"), ("Tradução", "trans"), ("Original", "orig")]
        for text, val in modes:
            rb = tk.Radiobutton(
                mode_frame,
                text=text,
                value=val,
                variable=mode_var,
                command=on_mode_change,
                fg="#f1f5f9",
                bg="#181822",
                selectcolor="#0f172a",
                activebackground="#181822",
                activeforeground="#38bdf8"
            )
            rb.pack(side=tk.LEFT, expand=True)

        # 5. Idioma da Tradução
        lbl_lang = tk.Label(container, text="Idioma da Tradução (Letras.mus.br):", font=("Segoe UI", 10, "bold"), fg="#94a3b8", bg="#181822")
        lbl_lang.pack(anchor="w", pady=(6, 4))

        lang_frame = tk.Frame(container, bg="#181822")
        lang_frame.pack(fill=tk.X, pady=(0, 8))

        current_lang = (self.state.lang if self.state else self.config.get("lang", "pt")).lower()
        lang_var = tk.StringVar(value=current_lang)

        def on_lang_click(code):
            lang_var.set(code)
            self.config["lang"] = code
            save_config({"lang": code})
            if self.on_language_change:
                self.on_language_change(code)
            # Atualiza cores dos botões
            for btn_code, b in lang_buttons.items():
                if btn_code == code:
                    b.configure(bg="#0284c7", fg="#ffffff")
                else:
                    b.configure(bg="#27273a", fg="#94a3b8")

        lang_buttons = {}
        langs = [("🇧🇷 PT", "pt"), ("🇺🇸 EN", "en"), ("🇪🇸 ES", "es"), ("🇫🇷 FR", "fr")]
        for text, code in langs:
            is_active = (code == current_lang)
            b = tk.Button(
                lang_frame,
                text=text,
                font=("Segoe UI", 9, "bold"),
                bg="#0284c7" if is_active else "#27273a",
                fg="#ffffff" if is_active else "#94a3b8",
                activebackground="#38bdf8",
                activeforeground="#ffffff",
                relief=tk.FLAT,
                padx=6,
                pady=4,
                cursor="hand2",
                command=lambda c=code: on_lang_click(c)
            )
            b.pack(side=tk.LEFT, expand=True, padx=2)
            lang_buttons[code] = b

        # Botão Fechar Configurações
        btn_done = tk.Button(
            self.settings_window,
            text="Concluir",
            font=("Segoe UI", 10, "bold"),
            bg="#38bdf8",
            fg="#0f172a",
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self.settings_window.destroy
        )
        btn_done.pack(pady=(6, 12))

    def run(self):
        """Inicia a aplicação gráfica no thread principal"""
        self.root.mainloop()

    def quit(self):
        self.root.destroy()
        sys.exit(0)


if __name__ == "__main__":
    overlay = LyricsOverlay()
    overlay.run()
