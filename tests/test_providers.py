import httpx
import pytest

from letrasbr_api.lyrics_sync import YTMManager, pick_closest_duration
from letrasbr_api.providers import lrclib
from letrasbr_api.providers.lrclib import _pick_search_result, fetch_lrclib_lyrics, parse_lrc


# --- LRCLIB ---

def test_parse_lrc_computes_end_times_and_skips_credits():
    lines = parse_lrc("[00:00.50] lrc by fulano\n[00:01.00] First\n[00:03.50] Second\nsem tempo\n[00:10.00] Last")
    assert [(l.start_time, l.end_time, l.text) for l in lines] == [
        (1000, 3500, "First"), (3500, 10000, "Second"), (10000, 14000, "Last"),
    ]


def test_parse_lrc_empty():
    assert parse_lrc("") == []


def test_pick_search_result_prefers_artist_and_duration():
    results = [
        {"artistName": "Cover Band", "duration": 187, "syncedLyrics": "[00:01.00] a"},
        {"artistName": "Linkin Park", "duration": 200, "syncedLyrics": "[00:01.00] b"},  # fora da tolerância
        {"artistName": "Linkin Park", "duration": 186, "syncedLyrics": "[00:01.00] c"},
        {"artistName": "Linkin Park", "duration": 187, "syncedLyrics": None},           # sem letra sincronizada
    ]
    assert _pick_search_result(results, "Linkin Park", 187)["syncedLyrics"].endswith("c")
    assert _pick_search_result(results, "Linkin Park", 999) is None


def test_lrclib_falls_back_to_search_on_404(monkeypatch):
    """Regressão: o 404 de /api/get impedia a busca aproximada."""
    def handler(request: httpx.Request):
        if request.url.path.endswith("/get"):
            return httpx.Response(404, json={"message": "not found"})
        return httpx.Response(200, json=[{"artistName": "Linkin Park", "duration": 187,
                                          "syncedLyrics": "[00:01.00] Crawling in my skin"}])

    real_client = httpx.Client
    monkeypatch.setattr(lrclib.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    lines = fetch_lrclib_lyrics("Crawling", "Linkin Park", album="Álbum errado", duration=187)
    assert [l.text for l in lines] == ["Crawling in my skin"]


# --- YouTube Music ---

def test_pick_closest_duration():
    results = [{"videoId": "a", "duration_seconds": 240}, {"videoId": "b", "duration_seconds": 201},
               {"videoId": "c", "duration_seconds": 330}]
    assert pick_closest_duration(results, 200)["videoId"] == "b"
    assert pick_closest_duration(results, None)["videoId"] == "a"   # sem duração: primeiro resultado
    assert pick_closest_duration(results, 100)["videoId"] == "a"    # nada dentro da tolerância


@pytest.mark.network
@pytest.mark.parametrize("title, artist", [("Bohemian Rhapsody", "Queen"), ("Levitating", "Dua Lipa")])
def test_ytm_fallback_search_with_invalid_video_id(title, artist):
    lines = YTMManager().get_timed_lyrics(video_id="invalid_video_id", title=title, artist=artist)
    assert lines and len(lines) > 20


@pytest.mark.network
def test_ytm_nonexistent_track_returns_none():
    assert YTMManager().get_timed_lyrics("fake_vid", "NonExistentSongXYZ99887766", "NonExistentArtistABC112233") is None
