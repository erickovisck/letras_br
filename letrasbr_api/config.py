import os
import json
import threading

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "overlay_config.json")

# Garante que a pasta config exista
os.makedirs(CONFIG_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "x": 100,
    "y": 100,
    "width": 650,
    "height": 110,
    "opacity": 0.88,
    "bgColor": "#121216",
    "origColor": "#cbd5e1",
    "transColor": "#38bdf8",
    "fontFamily": "Segoe UI",
    "fontSize": 15,
    "fontBold": True,
    "fontItalic": False,
    "displayMode": "both",  # "both", "trans", "orig"
    "lang": "pt",           # "pt", "en", "es", "fr"
    "locked": False,
    "serverUrl": "http://127.0.0.1:8000"
}


_lock = threading.Lock()
_current_config = DEFAULT_CONFIG.copy()
_listeners = []


def load_config() -> dict:
    global _current_config
    with _lock:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        _current_config[k] = v
            except Exception as e:
                print(f"[Config] Erro ao carregar {CONFIG_FILE}: {e}")
        else:
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(_current_config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[Config] Erro ao salvar padrão {CONFIG_FILE}: {e}")
        return _current_config.copy()


def save_config(cfg: dict):
    global _current_config
    with _lock:
        _current_config.update(cfg)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(_current_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Erro ao salvar {CONFIG_FILE}: {e}")

    # Notifica ouvintes
    for callback in _listeners:
        try:
            callback(_current_config.copy())
        except Exception:
            pass


def get_config() -> dict:
    with _lock:
        return _current_config.copy()


def add_config_listener(callback):
    _listeners.append(callback)


# Carrega na inicialização
load_config()
