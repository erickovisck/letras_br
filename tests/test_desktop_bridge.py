import time

import pytest
from fastapi.testclient import TestClient

from letrasbr_api import main
from letrasbr_api.aligner import AlignedLine
from letrasbr_api.desktop_bridge import DesktopBridge, bridge

LINES = [
    AlignedLine(1000, 4000, "Line 1", "Linha 1", False, "letras"),
    AlignedLine(4000, 8000, "Line 2", "Linha 2", False, "auto"),
]


@pytest.fixture
def desktop(monkeypatch):
    """Simula o overlay desktop conectado à API."""
    received = {"commands": [], "langs": []}
    monkeypatch.setattr(main, "save_config", lambda cfg: None)
    bridge.attach(received["commands"].append, received["langs"].append)
    main.reset_playback_state()
    main.state.last_remote_sync = 0.0
    original_lang = main.state.lang
    yield received
    bridge.detach()
    main.state.lang = original_lang


def test_snapshot_active_and_next_line():
    b = DesktopBridge()
    b.set_track("Song", "Artist", "", 200, source="youtube", lang="pt")
    assert b.snapshot()["isFetching"] is True

    b.set_lyrics(LINES, "https://www.letras.mus.br/x/y/traducao.html", "mixed", "ytmusic")
    before = b.snapshot()
    assert before["activeOriginal"] == "" and before["nextOriginal"] == "Line 1"

    b.set_position(5.0, 200, False, 1)
    snap = b.snapshot()
    assert snap["activeTranslation"] == "Linha 2" and snap["activeLineSource"] == "auto"
    assert snap["nextOriginal"] == "" and snap["source"] == "ytmusic"
    assert snap["isFetching"] is False and snap["hasTranslation"] is True


def test_new_track_bumps_lyrics_version_and_clears_lines():
    b = DesktopBridge()
    b.set_lyrics(LINES)
    version = b.snapshot()["lyricsVersion"]
    b.set_track("Other", "Artist")
    snap = b.snapshot()
    assert snap["lyricsVersion"] > version and snap["hasAlignedLyrics"] is False


def test_detached_bridge_ignores_requests():
    b = DesktopBridge()
    assert not b.attached
    assert b.send_command("next") is False
    assert b.request_language("en") is False


def test_api_current_reads_desktop_state(desktop):
    bridge.set_track("Song", "Artist", lang="pt")
    bridge.set_lyrics(LINES, translation_source="letras", timing_source="ytmusic")
    bridge.set_position(2.0, 200, False, 0)
    with TestClient(main.app) as client:
        current = client.get("/api/current").json()
        health = client.get("/api/health").json()
    assert current["origin"] == "desktop"
    assert current["activeOriginal"] == "Line 1" and current["nextTranslation"] == "Linha 2"
    assert health["desktop"] is True


def test_player_action_goes_to_desktop(desktop):
    with TestClient(main.app) as client:
        body = client.post("/api/player/action", json={"action": "next"}).json()
    assert body["source"] == "desktop"
    assert desktop["commands"] == ["next"]


def test_language_change_is_forwarded_to_desktop(desktop):
    with TestClient(main.app) as client:
        body = client.post("/api/language", json={"lang": "en"}).json()
    assert body["status"] == "ok"
    assert desktop["langs"] == ["en"]


def test_remote_sync_client_takes_priority(desktop):
    main.state.last_remote_sync = time.monotonic()
    with TestClient(main.app) as client:
        assert client.get("/api/current").json()["origin"] == "remote"
    main.state.last_remote_sync = 0.0
