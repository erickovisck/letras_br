import os
import sys
import threading
import time

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

    inner_ytm = os.path.join(current_dir, "ytmusicapi")
    if os.path.exists(os.path.join(inner_ytm, "ytmusicapi", "__init__.py")):
        if inner_ytm not in sys.path:
            sys.path.insert(0, inner_ytm)

    from main import app, state, change_language_internal, queue_command
    from overlay import LyricsOverlay
    from protocol import register_protocol

    # Registra protocolo personalizado letrasbr:// para inicialização com 1 clique do navegador
    register_protocol()

    print("=" * 65)
    print("  TRADUTOR YOUTUBE MUSIC - SERVIDOR API & OVERLAY FLUTUANTE")
    print("  Acesse o YouTube Music no navegador com a extensão carregada")
    print("  Overlay ativo na tela: arraste e use ⚙️ para configurações")
    print("=" * 65 + "\n")

    # Inicia Uvicorn no thread de background
    def run_server():
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8000,
            log_level="warning",
            access_log=False
        )
        server = uvicorn.Server(config)
        server.run()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Dá um breve instante para o servidor iniciar
    time.sleep(0.5)

    # Inicia a interface do Overlay no thread principal
    if "--no-overlay" in sys.argv:
        print("[Tradutor] Rodando em modo headless (sem overlay). Pressione Ctrl+C para sair.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Tradutor] Servidor finalizado.")
    else:
        overlay = LyricsOverlay(
            playback_state=state,
            on_language_change=change_language_internal,
            on_player_action=queue_command
        )
        try:
            overlay.run()
        except KeyboardInterrupt:
            pass
