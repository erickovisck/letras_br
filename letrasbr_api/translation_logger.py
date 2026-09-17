import os
import threading
from datetime import datetime
from typing import List, Any, Optional

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOGS_DIR, "sem_traducao.log")

_lock = threading.Lock()
_logged_cache = set()


def ms_to_time_str(ms: int) -> str:
    """Converte milissegundos para formato MM:SS."""
    seconds = max(0, int(ms / 1000))
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"


def log_untranslated_lyrics(
    title: str,
    artist: str,
    lang: str,
    aligned_lines: List[Any],
    force: bool = False
):
    """
    Verifica se a lista de versos alinhados possui linhas sem tradução.
    Se possuir, grava no arquivo logs/sem_traducao.log detalhando a música
    e cada trecho que ficou sem tradução.
    """
    if not title or not aligned_lines:
        return

    # Filtra linhas vocais sem tradução (ignora instrumentais ♪)
    missing_snippets = []
    total_vocal = 0

    for line in aligned_lines:
        orig = getattr(line, "original", "") or ""
        if getattr(line, "is_instrumental", False) or orig.strip() in ["♪", "(♪)", ""]:
            continue
        total_vocal += 1
        trans = (getattr(line, "translation", "") or "").strip().lower()
        if (
            not trans
            or "(sem tradução" in trans
            or "(tradução indisponível" in trans
            or trans == "(sem tradução para este verso)"
            or trans == "(tradução indisponível)"
        ):
            start_ms = getattr(line, "start_time", 0)
            time_str = ms_to_time_str(start_ms)
            missing_snippets.append((time_str, orig.strip()))

    if not missing_snippets:
        return  # Todos os versos têm tradução!

    # Chave para evitar duplicatas em lote na mesma sessão
    cache_key = f"{artist.strip().lower()}|||{title.strip().lower()}|||{lang.strip().lower()}"
    with _lock:
        if not force and cache_key in _logged_cache:
            return
        _logged_cache.add(cache_key)

        try:
            os.makedirs(LOGS_DIR, exist_ok=True)

            # Garante cabeçalho se arquivo estiver vazio
            if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    f.write("=" * 80 + "\n")
                    f.write("  LETRASBR - REGISTRO DE MÚSICAS E TRECHOS SEM TRADUÇÃO\n")
                    f.write("  Armazena automaticamente as músicas e versos onde não foi encontrada tradução.\n")
                    f.write("=" * 80 + "\n\n")

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            lines_to_write = [
                f"[{timestamp}]",
                f"Música:  {title}",
                f"Artista: {artist or 'Desconhecido'}",
                f"Idioma:  {lang.upper()}",
                f"Versos sem tradução: {len(missing_snippets)} de {total_vocal} vocais",
                "Trechos:"
            ]

            for t_str, orig_text in missing_snippets:
                lines_to_write.append(f"  • [{t_str}] \"{orig_text}\"")

            lines_to_write.append("-" * 80 + "\n")

            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write("\n".join(lines_to_write) + "\n")

            print(f"[Log] {len(missing_snippets)} trecho(s) sem tradução registrado(s) em logs/sem_traducao.log para '{title}'")
        except Exception as e:
            print(f"[Log] Erro ao registrar trechos sem tradução: {e}")
