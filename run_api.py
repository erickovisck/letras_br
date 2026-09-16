import os
import sys
import threading
import time

# Garante stdout e stderr validos quando executado pelo pythonw.exe (sem console)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Força UTF-8 no console do Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import uvicorn

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    letrasbr_dir = os.path.join(current_dir, "letrasbr_api")
    if letrasbr_dir not in sys.path:
        sys.path.insert(0, letrasbr_dir)

    from main import app, state, change_language_internal, queue_command
    from protocol import register_protocol

    # Registra protocolo personalizado letrasbr://
    register_protocol()

    print("=" * 68)
    print("  LETRASBR TRADUTOR DESKTOP - PYSIDE6 & WINDOWS MEDIA CONTROL (GSMTC)")
    print("  Detecta YouTube Music e outros players nativamente no Windows!")
    print("  Use a barra superior para arrastar, miniplayer e ⚙️ para cores/fontes.")
    print("=" * 68 + "\n")

    # Inicia Uvicorn em thread de background para clientes móveis e rede local
    def run_server():
        try:
            config = uvicorn.Config(
                app=app,
                host="0.0.0.0",
                port=8000,
                log_level="warning",
                access_log=False
            )
            server = uvicorn.Server(config)
            server.run()
        except Exception as e:
            print(f"[API] Servidor FastAPI em background: {e}")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.3)

    if "--no-overlay" in sys.argv:
        print("[Tradutor] Rodando em modo headless (sem overlay). Pressione Ctrl+C para sair.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Tradutor] Servidor finalizado.")
    else:
        from PySide6.QtWidgets import QApplication
        from overlay_qt import LyricsOverlayQt
        from media_monitor import WindowsMediaMonitor

        # Inicia aplicação Qt
        qt_app = QApplication(sys.argv)
        qt_app.setQuitOnLastWindowClosed(False)  # Permite continuar rodando na bandeja

        # Inicia monitor nativo de mídia do Windows
        media_monitor = WindowsMediaMonitor()
        media_monitor.start()

        overlay = LyricsOverlayQt(media_monitor=media_monitor)
        overlay.show()

        try:
            sys.exit(qt_app.exec())
        finally:
            media_monitor.stop()
            media_monitor.wait(1000)
