#!/usr/bin/env python
"""Script de diagnostico do ambiente LetrasBR."""
import sys
import os

print("=" * 60)
print("  LETRASBR — DIAGNOSTICO DO AMBIENTE PYTHON")
print("=" * 60)
print(f"Python:    {sys.version}")
print(f"Exec:      {sys.executable}")
print(f"Platform:  {sys.platform}")
print()

packages = [
    "ytmusicapi", "PySide6", "fastapi", "uvicorn",
    "httpx", "bs4", "winrt.windows.media.control",
    "pykakasi", "requests", "difflib"
]

print("Pacotes necessarios:")
for pkg in packages:
    try:
        mod = __import__(pkg.replace("-", "_").split(".")[0])
        ver = getattr(mod, "__version__", "instalado")
        print(f"  [OK] {pkg} ({ver})")
    except ImportError as e:
        print(f"  [FALTA] {pkg} — {e}")

print()

# Testa ytmusicapi especificamente
print("Teste ytmusicapi:")
try:
    from ytmusicapi import YTMusic
    try:
        from ytmusicapi.models.lyrics import LyricLine
        print("  [OK] LyricLine importado com sucesso")
    except ImportError as e:
        print(f"  [AVISO] LyricLine nao disponivel: {e}")

    yt = YTMusic()
    print("  [OK] YTMusic client inicializado!")

    results = yt.search("Bohemian Rhapsody Queen", filter="songs")
    if results:
        vid = results[0].get("videoId")
        title = results[0].get("title", "?")
        print(f"  [OK] Busca OK: '{title}' videoId={vid}")
        if vid:
            watch = yt.get_watch_playlist(videoId=vid)
            lyrics_id = watch.get("lyrics")
            print(f"  [OK] lyrics_browse_id: {lyrics_id}")
            if lyrics_id:
                lyrics = yt.get_lyrics(lyrics_id, timestamps=True)
                has_ts = lyrics.get("hasTimestamps") if lyrics else False
                print(f"  [OK] hasTimestamps: {has_ts}")
                if has_ts:
                    lines = lyrics.get("lyrics", [])
                    print(f"  [OK] {len(lines)} linhas temporizadas!")
                else:
                    print("  [AVISO] Sem timestamps — ytmusicapi pode estar desatualizado")
            else:
                print("  [AVISO] Sem lyrics_browse_id para esta musica")
    else:
        print("  [AVISO] Busca retornou vazio")
except Exception as e:
    print(f"  [ERRO] {e}")

print()

# Testa scraper
print("Teste scraper:")
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from scraper import get_translation
    d, v, url = get_translation("Queen", "Bohemian Rhapsody", lang="pt")
    print(f"  [OK] {len(d)} versos, {len(v)} ordered_verses")
    print(f"  [OK] URL: {url}")
except Exception as e:
    print(f"  [ERRO] {e}")

print()
print("=" * 60)
print("Diagnostico concluido.")
print("=" * 60)
