import logging
import os
import json
import re
import threading

logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "overlay_config.json")
THEMES_DIR = os.path.join(CONFIG_DIR, "themes")

# Garante que as pastas existam
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(THEMES_DIR, exist_ok=True)

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
    "transition": "3d",     # "3d", "scroll", "slide", "fade", "none" (ver ui/lyric_view.py)
    "transitionMs": 300,
    "textEffect": "none",   # "none", "shadow", "outline"
    "autoHideControls": True,  # Barras somem quando o mouse sai do overlay
    "lang": "pt",           # "pt", "en", "es", "fr"
    "autoTranslate": True,  # Completa com tradução automática (Google) o que o Letras não tiver
    "locked": False,
    "theme": "Escuro (Padrão)",
}

# Chaves de configuração que um tema define
THEME_KEYS = ("bgColor", "opacity", "origColor", "transColor", "fontFamily", "fontSize", "fontBold", "fontItalic")
DEFAULT_THEME_NAME = "Escuro (Padrão)"
DYNAMIC_THEME_NAME = "Dinâmico (capa do álbum)"  # Cores extraídas da capa da música tocando


def get_available_themes() -> dict:
    """
    Retorna os temas da pasta config/themes: { "Nome do Tema": { ...dados do tema... } }.
    Se a pasta estiver vazia, retorna só o tema padrão montado a partir de DEFAULT_CONFIG.
    """
    themes = {}
    for f in sorted(os.listdir(THEMES_DIR)):
        if not f.endswith(".json"):
            continue
        path = os.path.join(THEMES_DIR, f)
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            themes[data.get("name", os.path.splitext(f)[0])] = data
        except Exception as e:
            logger.warning(f"Erro ao carregar tema {f}: {e}")

    if not themes:
        themes[DEFAULT_THEME_NAME] = {"name": DEFAULT_THEME_NAME, **{k: DEFAULT_CONFIG[k] for k in THEME_KEYS}}
    return themes


def save_custom_theme(name: str, theme_data: dict) -> str:
    """Salva um novo tema criado pelo usuário em config/themes/<slug>.json"""
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("O nome do tema não pode ser vazio.")

    # Gera nome de arquivo seguro
    slug = re.sub(r'[^a-zA-Z0-9_-]', '_', clean_name.lower())
    if not slug:
        slug = "tema_personalizado"

    file_path = os.path.join(THEMES_DIR, f"{slug}.json")
    counter = 1
    while os.path.exists(file_path):
        file_path = os.path.join(THEMES_DIR, f"{slug}_{counter}.json")
        counter += 1

    data = {
        "name": clean_name,
        "description": "Tema personalizado criado pelo usuário",
        **theme_data
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return file_path


_lock = threading.Lock()
_current_config = DEFAULT_CONFIG.copy()
_listeners = []


def load_config() -> dict:
    with _lock:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        _current_config[k] = v
            except Exception as e:
                logger.warning(f"Erro ao carregar {CONFIG_FILE}: {e}")
        else:
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(_current_config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Erro ao salvar padrão {CONFIG_FILE}: {e}")
        return _current_config.copy()


def save_config(cfg: dict):
    with _lock:
        _current_config.update(cfg)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(_current_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Erro ao salvar {CONFIG_FILE}: {e}")

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


# Carrega a configuração salva
load_config()
