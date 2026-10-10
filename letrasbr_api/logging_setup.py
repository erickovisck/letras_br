"""Configuração central de logs: console (quando houver) + arquivo rotativo em logs/letrasbr.log."""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOGS_DIR, "letrasbr.log")

_FORMAT = "%(asctime)s %(levelname)-7s [%(module)s] %(message)s"
_CONSOLE_DATEFMT = "%H:%M:%S"
_FILE_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO):
    """Configura o logger raiz uma única vez. Seguro para chamar mais de uma vez."""
    root = logging.getLogger()
    if getattr(root, "_letrasbr_configured", False):
        return

    # Windows: evita UnicodeEncodeError com emojis/acentos no console
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    formatter = logging.Formatter(_FORMAT, _CONSOLE_DATEFMT)
    root.setLevel(level)

    # pythonw.exe (LetrasBR.exe) roda sem console: sys.stdout pode ser None
    if sys.stdout is not None:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        root.addHandler(console)

    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_FORMAT, _FILE_DATEFMT))
        root.addHandler(file_handler)
    except Exception as e:
        root.warning(f"Não foi possível criar o arquivo de log {LOG_FILE}: {e}")

    # Bibliotecas muito verbosas
    for noisy in ("httpx", "httpcore", "urllib3", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root._letrasbr_configured = True
