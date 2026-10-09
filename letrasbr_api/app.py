"""
Ponto de entrada do LetrasBR: sobe a API FastAPI em segundo plano e abre o overlay desktop (PySide6).
Uso: `python run_api.py` ou `python -m letrasbr_api` (adicione --no-overlay para rodar só a API).
"""

import os
import sys
import time
import logging
import threading

import uvicorn

from .logging_setup import setup_logging

logger = logging.getLogger(__name__)

API_HOST = "0.0.0.0"
API_PORT = 8000


def _ensure_std_streams():
    # pythonw.exe (LetrasBR.exe) roda sem console: stdout/stderr são None e quebrariam bibliotecas
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _start_api_server():
    from .main import app

    def run():
        try:
            config = uvicorn.Config(app=app, host=API_HOST, port=API_PORT, log_level="warning", access_log=False)
            uvicorn.Server(config).run()
        except Exception as e:
            logger.error(f"Servidor FastAPI em background falhou: {e}")

    threading.Thread(target=run, daemon=True, name="api_server").start()
    time.sleep(0.3)


def main(argv=None):
    argv = sys.argv if argv is None else argv
    _ensure_std_streams()
    setup_logging()

    from .protocol import register_protocol
    register_protocol()

    logger.info("LetrasBR Desktop — PySide6 + Windows Media Control (GSMTC)")
    _start_api_server()
    logger.info(f"API disponível em http://127.0.0.1:{API_PORT} (mobile: /mobile)")

    if "--no-overlay" in argv:
        logger.info("Modo headless (sem overlay). Pressione Ctrl+C para sair.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Servidor finalizado.")
        return 0

    from PySide6.QtWidgets import QApplication
    from .media_monitor import WindowsMediaMonitor
    from .ui.overlay_window import LyricsOverlayQt

    qt_app = QApplication(argv)
    qt_app.setQuitOnLastWindowClosed(False)  # Continua rodando na bandeja

    media_monitor = WindowsMediaMonitor()
    media_monitor.start()

    overlay = LyricsOverlayQt(media_monitor=media_monitor)
    overlay.show()

    try:
        return qt_app.exec()
    finally:
        media_monitor.stop()
        media_monitor.wait(1000)
