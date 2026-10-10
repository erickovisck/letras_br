import pytest

from letrasbr_api import pipeline
from letrasbr_api.providers.base import TimedLine
from letrasbr_api.scraper import TranslationResult

ENGLISH = ["When the world is cold", "I will feel a glow just thinking of you", "And the way you look tonight"]


def timed(texts):
    return [TimedLine(i * 3000, (i + 1) * 3000, t) for i, t in enumerate(texts)]


@pytest.fixture
def fake_services(monkeypatch):
    """Substitui rede: letra sincronizada, Letras.mus.br e Google ficam sob controle do teste."""
    state = {
        "timed": timed(ENGLISH), "timing_source": "ytmusic",
        "translation": TranslationResult(), "auto": {}, "auto_calls": [], "translation_calls": [],
    }
    monkeypatch.setattr(pipeline, "fetch_timed_lyrics", lambda track, source: (list(state["timed"]), state["timing_source"]))

    def fetch_translation(artist, title, lang, allow_pt_fallback=True, song_path=None):
        state["translation_calls"].append((title, lang, allow_pt_fallback))
        state["song_path"] = song_path
        return state["translation"]

    def translate_lines(lines, lang):
        state["auto_calls"].append(list(lines))
        return {l: state["auto"].get(l, f"[{lang}] {l}") for l in lines}

    monkeypatch.setattr(pipeline, "fetch_translation", fetch_translation)
    monkeypatch.setattr(pipeline, "translate_lines", translate_lines)
    return state


def letras(*pairs):
    return TranslationResult(
        ordered_verses=[{"index": i, "translation": t, "originals": [o]} for i, (o, t) in enumerate(pairs)],
        url="https://www.letras.mus.br/x/y/traducao.html", lang_used="pt", song_found=True,
    )


def test_letras_translation_complete(fake_services):
    fake_services["translation"] = letras(*[(o, f"tradução {i}") for i, o in enumerate(ENGLISH)])
    result = pipeline.fetch_and_align("The Way You Look Tonight", "Frank Sinatra", lang="pt")
    assert result.translation_source == "letras"
    assert [l.translation for l in result.aligned] == ["tradução 0", "tradução 1", "tradução 2"]
    assert fake_services["auto_calls"] == []
    assert result.translation_url.endswith("traducao.html")


def test_missing_verses_are_filled_automatically(fake_services):
    fake_services["translation"] = letras((ENGLISH[0], "Quando o mundo estiver frio"))
    result = pipeline.fetch_and_align("Song", "Artist", lang="pt")
    assert result.aligned[0].source == "letras"
    assert all(l.source == "auto" and l.translation.startswith("[pt]") for l in result.aligned[1:])
    assert result.translation_source == "mixed"


def test_song_not_on_letras_is_fully_auto_translated(fake_services):
    result = pipeline.fetch_and_align("Song", "Artist", lang="pt")
    assert result.translation_source == "auto"
    assert result.translation_url is None
    assert fake_services["translation_calls"][0][2] is False  # sem cair para PT quando há fallback automático


def test_auto_translate_disabled(fake_services):
    result = pipeline.fetch_and_align("Song", "Artist", lang="pt", auto_translate=False)
    assert result.translation_source == "none"
    assert fake_services["auto_calls"] == []
    assert fake_services["translation_calls"][0][2] is True


def test_same_language_shows_original_only(fake_services):
    result = pipeline.fetch_and_align("Song", "Artist", lang="en")
    assert result.translation_source == "original"
    assert all(l.source == "original" and l.translation == "" for l in result.aligned)
    assert fake_services["translation_calls"] == []  # nem consulta o Letras


def test_google_echo_marks_line_as_original(fake_services):
    fake_services["auto"] = {l: l for l in ENGLISH}  # Google devolveu o mesmo texto
    result = pipeline.fetch_and_align("Song", "Artist", lang="pt")
    assert all(l.source == "original" for l in result.aligned)


def test_estimated_timings_without_synced_lyrics(fake_services):
    fake_services["timed"], fake_services["timing_source"] = [], "none"
    fake_services["translation"] = letras(("First line", "Primeira"), ("A much longer second line here", "Segunda"))
    result = pipeline.fetch_and_align("Song", "Artist", duration=100, lang="pt")
    assert result.timing_source == "estimated"
    first, second = result.aligned
    assert first.start_time == 5000 and second.end_time == 95000
    assert second.end_time - second.start_time > first.end_time - first.start_time


def test_manual_letras_page_is_used(fake_services):
    from letrasbr_api import track_prefs
    track_prefs.set_letras_path("Ado", "Odo", "/ado/odo/")
    pipeline.fetch_and_align("Odo", "Ado", lang="pt")
    assert fake_services["song_path"] == "/ado/odo/"


def test_stale_fetch_returns_none(fake_services):
    assert pipeline.fetch_and_align("Song", "Artist", lang="pt", is_current=lambda: False) is None


def test_reuses_timed_lyrics(fake_services, monkeypatch):
    monkeypatch.setattr(pipeline, "fetch_timed_lyrics", lambda *a: pytest.fail("não deveria buscar de novo"))
    result = pipeline.fetch_and_align("Song", "Artist", lang="pt", timed_lyrics=timed(ENGLISH))
    assert len(result.aligned) == 3


def test_source_order_depends_on_player(monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "fetch_lrclib_lyrics", lambda *a: calls.append("lrclib") or None)

    class FakeYtm:
        def get_timed_lyrics(self, track):
            calls.append("ytmusic")

    monkeypatch.setattr(pipeline.ProviderFactory, "get_provider", staticmethod(lambda source: FakeYtm()))
    pipeline.fetch_timed_lyrics(pipeline.TrackInfo(title="t", artist="a"), "spotify")
    pipeline.fetch_timed_lyrics(pipeline.TrackInfo(title="t", artist="a"), "youtube")
    assert calls == ["lrclib", "ytmusic", "ytmusic", "lrclib"]
