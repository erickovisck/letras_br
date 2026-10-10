from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from letrasbr_api import scraper
from letrasbr_api.scraper import (
    clean_song_title, fetch_translation, find_best_song_link, get_translation_suffix, letras_path_from_url,
    split_multilingual, version_penalty,
)

TRANSLATION_PAGE = """
<div>
  <span class="verse"><span>Quando o mundo estiver frio</span><span><span>When the world is cold</span></span></span>
  <span class="verse"><span>Eu vou sentir um brilho</span><span><span>I will feel a glow</span></span></span>
</div>
"""


@pytest.mark.parametrize("raw, expected", [
    ("Numb (Official Music Video)", "Numb"),
    ("Blue Bird [Lyric Video]", "Blue Bird"),
    ("Song feat. Someone", "Song"),
    ("Базовый минимум (bazovyj minimum) (feat. SABI)", "Базовый минимум"),
    ("500 Miles (2004 Remaster)", "500 Miles"),
])
def test_clean_song_title(raw, expected):
    assert clean_song_title(raw) == expected


def test_split_multilingual_separates_scripts():
    cands = split_multilingual("ブルーバード - Blue Bird")
    assert cands[0] == "Blue Bird"
    assert "ブルーバード" in cands


def test_translation_suffix():
    assert get_translation_suffix("fr") == "traduction-francaise.html"
    assert get_translation_suffix("PT-BR") == "traducao.html"
    assert get_translation_suffix("xx") == "traducao.html"


@pytest.mark.parametrize("text, expected", [
    ("https://www.letras.mus.br/ado/odo/traducao.html", "/ado/odo/"),
    ("letras.mus.br/frank-sinatra/36439/", "/frank-sinatra/36439/"),
    ("/ado/odo", "/ado/odo/"),
    ("https://www.letras.mus.br/ado/", None),   # página do artista, não da música
    ("ado - odo", None),
    ("https://google.com/a/b/", None),
])
def test_letras_path_from_url(text, expected):
    assert letras_path_from_url(text) == expected


def test_manual_song_path_skips_search(monkeypatch):
    calls = fake_site(monkeypatch, {"traducao.html": (200, TRANSLATION_PAGE)})
    result = fetch_translation("Ado", "Odo", "pt", song_path="/ado/odo/")
    assert calls["song_url"] == 0
    assert calls["pages"] == ["https://www.letras.mus.br/ado/odo/traducao.html"]
    assert result.lang_used == "pt"


def test_version_penalty():
    assert version_penalty("Odo (Bon-Odo Remix)", "Odo") > 0
    assert version_penalty("Numb (Live)", "Numb (Live)") == 0
    assert version_penalty("DND (feat. KUROMI)", "DND") == 0


def links(*pairs):
    html = "".join(f'<a href="{href}" title="{title}">{title}</a>' for href, title in pairs)
    return BeautifulSoup(html, "html.parser").find_all("a", href=True)


def test_best_link_prefers_original_over_remix():
    """Regressão: 'Odo' pegava 'Odo (Bon-Odo Remix)' por aparecer antes na página."""
    page = links(("/ado/odo-bon-odo-remix/", "Odo (Bon-Odo Remix)"), ("/ado/odo/", "踊 (odo)"))
    assert find_best_song_link(page, split_multilingual("Odo"), "Odo")[0] == "/ado/odo/"


def test_best_link_uses_remix_when_it_is_the_only_option():
    page = links(("/ado/other/", "Other Song"), ("/ado/odo-bon-odo-remix/", "Odo (Bon-Odo Remix)"))
    assert find_best_song_link(page, ["Odo"], "Odo")[0] == "/ado/odo-bon-odo-remix/"


def test_best_link_exact_title_wins():
    page = links(("/x/love-me-forever/", "Love Me Forever"), ("/x/love/", "Love"))
    assert find_best_song_link(page, ["Love"], "Love")[0] == "/x/love/"


def test_best_link_none():
    assert find_best_song_link(links(("/x/a/", "Something Else")), ["Numb"], "Numb") is None


# --- fetch_translation: idioma usado e cache ---

def fake_site(monkeypatch, pages: dict, song_path="/artist/song/"):
    calls = {"song_url": 0, "pages": []}

    def get_song_url(artist, title):
        calls["song_url"] += 1
        return song_path

    def fetch_response(url, timeout=8.0):
        calls["pages"].append(url)
        status, text = pages.get(url.rsplit("/", 1)[-1], (404, ""))
        return SimpleNamespace(status_code=status, text=text)

    monkeypatch.setattr(scraper, "get_song_url", get_song_url)
    monkeypatch.setattr(scraper, "fetch_response", fetch_response)
    return calls


def test_fetch_translation_parses_verses(monkeypatch):
    fake_site(monkeypatch, {"traducao.html": (200, TRANSLATION_PAGE)})
    result = fetch_translation("Frank Sinatra", "The Way You Look Tonight", "pt")
    assert result.lang_used == "pt" and result.song_found
    assert [v["translation"] for v in result.ordered_verses] == ["Quando o mundo estiver frio", "Eu vou sentir um brilho"]
    assert result.lyrics_dict["I will feel a glow"] == "Eu vou sentir um brilho"


def test_missing_language_falls_back_to_pt_only_when_allowed(monkeypatch):
    fake_site(monkeypatch, {"traducao.html": (200, TRANSLATION_PAGE)})
    assert fetch_translation("A", "B", "fr", allow_pt_fallback=True).lang_used == "pt"
    without_fallback = fetch_translation("A", "B", "fr", allow_pt_fallback=False)
    assert without_fallback.lang_used is None and without_fallback.song_found


def test_definitive_not_found_is_cached(monkeypatch):
    calls = fake_site(monkeypatch, {}, song_path=None)
    fetch_translation("Ninguém", "Música Inexistente", "pt")
    fetch_translation("Ninguém", "Música Inexistente", "pt")
    assert calls["song_url"] == 1


def test_transient_failure_is_not_cached(monkeypatch):
    calls = {"n": 0}

    def flaky_song_url(artist, title):
        calls["n"] += 1
        scraper._mark_transient_failure()  # simula 403/timeout durante a busca
        return None

    monkeypatch.setattr(scraper, "get_song_url", flaky_song_url)
    fetch_translation("Artista", "Música", "pt")
    fetch_translation("Artista", "Música", "pt")
    assert calls["n"] == 2


@pytest.mark.network
def test_real_site_finds_translation():
    result = fetch_translation("Frank Sinatra", "The Way You Look Tonight", "pt")
    assert result.lang_used == "pt" and len(result.ordered_verses) > 10
