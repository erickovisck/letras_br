import os
import json
import re
import threading

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
    "lang": "pt",           # "pt", "en", "es", "fr"
    "locked": False,
    "theme": "Escuro (Padrão)",
    "serverUrl": "http://127.0.0.1:8000"
}

DEFAULT_THEMES = {
    "escuro_padrao.json": {
        "name": "Escuro (Padrão)",
        "description": "Tema escuro padrão com destaque em azul ciano e tipografia moderna",
        "bgColor": "#121216",
        "opacity": 0.88,
        "origColor": "#cbd5e1",
        "transColor": "#38bdf8",
        "fontFamily": "Segoe UI",
        "fontSize": 15,
        "fontBold": True,
        "fontItalic": False
    },
    "modo_claro.json": {
        "name": "Modo Claro",
        "description": "Tema claro inverso ao escuro padrão com tipografia moderna",
        "bgColor": "#ffffff",
        "opacity": 0.88,
        "origColor": "#334155",
        "transColor": "#0284c7",
        "fontFamily": "Segoe UI",
        "fontSize": 15,
        "fontBold": True,
        "fontItalic": False
    },
    "spotify.json": {
        "name": "Spotify Verde",
        "description": "Visual moderno inspirado no Spotify com tipografia geométrica encorpada",
        "bgColor": "#121212",
        "opacity": 0.90,
        "origColor": "#b3b3b3",
        "transColor": "#1db954",
        "fontFamily": "Bahnschrift",
        "fontSize": 15,
        "fontBold": True,
        "fontItalic": False
    },
    "cyberpunk.json": {
        "name": "Cyberpunk Neon",
        "description": "Estilo futurista com alto contraste, ciano, neon rosa e tipografia digital",
        "bgColor": "#0b0c10",
        "opacity": 0.92,
        "origColor": "#66fcf1",
        "transColor": "#ff007f",
        "fontFamily": "Cascadia Code",
        "fontSize": 14,
        "fontBold": True,
        "fontItalic": False
    },
    "dracula.json": {
        "name": "Drácula",
        "description": "Paleta Drácula com fundo escuro, acento roxo e tipografia literária serifada",
        "bgColor": "#282a36",
        "opacity": 0.90,
        "origColor": "#f8f8f2",
        "transColor": "#bd93f9",
        "fontFamily": "Georgia",
        "fontSize": 15,
        "fontBold": True,
        "fontItalic": True
    },
    "midnight.json": {
        "name": "Midnight Blue",
        "description": "Azul escuro profundo com letras nítidas, calmas e suaves",
        "bgColor": "#0f172a",
        "opacity": 0.88,
        "origColor": "#94a3b8",
        "transColor": "#38bdf8",
        "fontFamily": "Candara",
        "fontSize": 15,
        "fontBold": True,
        "fontItalic": False
    },
    "ametista.json": {
        "name": "Ametista Roxo",
        "description": "Visual sofisticado em tons violeta e lavanda com linhas geométricas elegantes",
        "bgColor": "#180e29",
        "opacity": 0.90,
        "origColor": "#e9d5ff",
        "transColor": "#c084fc",
        "fontFamily": "Century Gothic",
        "fontSize": 15,
        "fontBold": True,
        "fontItalic": False
    },
    "minimalista_claro.json": {
        "name": "Minimalista Claro",
        "description": "Fundo claro translúcido ideal para ambientes iluminados com fonte leve e arejada",
        "bgColor": "#f8fafc",
        "opacity": 0.92,
        "origColor": "#475569",
        "transColor": "#0284c7",
        "fontFamily": "Corbel",
        "fontSize": 15,
        "fontBold": True,
        "fontItalic": False
    }
}


def ensure_default_themes():
    """Garante que a pasta config/themes contenha os temas embutidos iniciais."""
    os.makedirs(THEMES_DIR, exist_ok=True)
    for filename, data in DEFAULT_THEMES.items():
        file_path = os.path.join(THEMES_DIR, filename)
        # Se não existe, cria; se existe mas não tem fontFamily customizado, atualiza
        if not os.path.exists(file_path):
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[Config] Erro ao criar tema padrão {filename}: {e}")
        else:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    curr_d = json.load(f)
                if curr_d.get("fontFamily") != data.get("fontFamily"):
                    curr_d.update(data)
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(curr_d, f, indent=2, ensure_ascii=False)
            except Exception:
                pass


def get_available_themes() -> dict:
    """
    Retorna dicionário de temas disponíveis na pasta config/themes:
    { "Nome do Tema": { ...dados do tema... } }
    """
    ensure_default_themes()
    themes = {}
    if os.path.exists(THEMES_DIR):
        for f in sorted(os.listdir(THEMES_DIR)):
            if f.endswith(".json"):
                path = os.path.join(THEMES_DIR, f)
                try:
                    with open(path, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                        name = data.get("name", os.path.splitext(f)[0])
                        themes[name] = data
                except Exception as e:
                    print(f"[Config] Erro ao carregar tema {f}: {e}")
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


# Inicializa temas e configurações
ensure_default_themes()
load_config()
