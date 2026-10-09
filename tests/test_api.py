import inspect

from fastapi.testclient import TestClient

from letrasbr_api import main


def test_reset_playback_state_clears_fetching():
    main.state.is_fetching = True
    main.reset_playback_state()
    assert main.state.is_fetching is False


def test_fetch_has_generation_guard():
    assert "generation" in inspect.signature(main._do_fetch_lyrics_sync).parameters


def test_invalid_language_is_rejected():
    with TestClient(main.app) as client:
        body = client.post("/api/language", json={"lang": "xx"}).json()
    assert body["status"] == "error"
    assert "pt, en, es, fr" in body["message"]


def test_health_and_current():
    main.reset_playback_state()
    with TestClient(main.app) as client:
        assert client.get("/api/health").json()["status"] == "running"
        current = client.get("/api/current").json()
    assert current["translationSource"] == "none"
    assert current["hasTranslation"] is False
