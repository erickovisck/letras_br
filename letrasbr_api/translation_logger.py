import logging
import os
import threading
from datetime import datetime
from typing import List, Any

logger = logging.getLogger(__name__)

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOGS_DIR, "sem_traducao.log")
LOG_UNSYNCED_FILE = os.path.join(LOGS_DIR, "sem_sincronizacao.log")

_lock = threading.Lock()
_logged_cache = set()
_logged_unsynced_cache = set()


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

            logger.info(f"{len(missing_snippets)} trecho(s) sem tradução registrado(s) em logs/sem_traducao.log para '{title}'")
        except Exception as e:
            logger.warning(f"Erro ao registrar trechos sem tradução: {e}")


def log_unsynced_song(
    title: str,
    artist: str,
    source: str = "ytmusic",
    reason: str = "Letra sincronizada não encontrada no provedor",
    force: bool = False
):
    """
    Registra no arquivo logs/sem_sincronizacao.log quando uma música é tocada
    mas nenhuma letra sincronizada é encontrada para ela.
    """
    if not title:
        return

    cache_key = f"{artist.strip().lower()}|||{title.strip().lower()}"
    with _lock:
        if not force and cache_key in _logged_unsynced_cache:
            return
        _logged_unsynced_cache.add(cache_key)

        try:
            os.makedirs(LOGS_DIR, exist_ok=True)

            if not os.path.exists(LOG_UNSYNCED_FILE) or os.path.getsize(LOG_UNSYNCED_FILE) == 0:
                with open(LOG_UNSYNCED_FILE, "w", encoding="utf-8") as f:
                    f.write("=" * 80 + "\n")
                    f.write("  LETRASBR - REGISTRO DE MÚSICAS SEM SINCRONIZAÇÃO\n")
                    f.write("  Armazena automaticamente as músicas onde não foi encontrada letra com timestamps.\n")
                    f.write("=" * 80 + "\n\n")

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            src_display = "Spotify" if "spotify" in (source or "").lower() else "YouTube Music"
            lines_to_write = [
                f"[{timestamp}]",
                f"Música:  {title}",
                f"Artista: {artist or 'Desconhecido'}",
                f"Fonte:   {src_display}",
                f"Motivo:  {reason}",
                "-" * 80 + "\n"
            ]

            with open(LOG_UNSYNCED_FILE, "a", encoding="utf-8") as f:
                f.write("\n".join(lines_to_write) + "\n")

            logger.info(f"Música sem sincronização registrada em logs/sem_sincronizacao.log: '{artist} - {title}'")
        except Exception as e:
            logger.warning(f"Erro ao registrar música sem sincronização: {e}")
