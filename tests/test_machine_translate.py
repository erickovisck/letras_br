import json
import os

import httpx
import pytest

from letrasbr_api import machine_translate
from letrasbr_api.machine_translate import _chunk_lines, detect_language, translate_lines


def mock_google(monkeypatch, handler):
    real_client = httpx.Client
    monkeypatch.setattr(machine_translate.httpx, "Client",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))


def fake_translation(request: httpx.Request) -> str:
    text = dict(httpx.QueryParams(request.content.decode()))["q"]
    return "\n".join(f"PT:{line}" for line in text.split("\n"))


def test_chunk_lines_respects_limit(monkeypatch):
    monkeypatch.setattr(machine_translate, "MAX_CHUNK_CHARS", 20)
    chunks = _chunk_lines(["aaaaaaaa", "bbbbbbbb", "cccccccc"])
    assert chunks == [["aaaaaaaa", "bbbbbbbb"], ["cccccccc"]]


def test_translate_dedupes_and_caches_on_disk(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=[[fake_translation(request), "en"]])

    mock_google(monkeypatch, handler)
    result = translate_lines(["Hello", "World", "Hello", "  "], "pt")
    assert result == {"Hello": "PT:Hello", "World": "PT:World"}
    assert len(requests) == 1

    with open(machine_translate.CACHE_FILE, encoding="utf-8") as f:
        assert json.load(f)["pt|||Hello"] == "PT:Hello"

    # Segunda chamada vem do cache, sem requisição
    monkeypatch.setattr(machine_translate, "_cache", None)
    assert translate_lines(["Hello"], "pt") == {"Hello": "PT:Hello"}
    assert len(requests) == 1


def test_blocked_endpoint_falls_back_to_next(monkeypatch):
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        if request.url.host == "clients5.google.com":
            return httpx.Response(429, text="<html>Sorry...</html>")
        segments = [[fake_translation(request), "x"]]
        return httpx.Response(200, json=[segments, None, "en"])

    mock_google(monkeypatch, handler)
    assert translate_lines(["Hi"], "pt") == {"Hi": "PT:Hi"}
    # Endpoint bloqueado fica pausado: a próxima tradução vai direto ao segundo
    translate_lines(["Bye"], "pt")
    assert hosts == ["clients5.google.com", "translate.googleapis.com", "translate.googleapis.com"]


def test_line_count_mismatch_is_discarded(monkeypatch):
    mock_google(monkeypatch, lambda request: httpx.Response(200, json=[["linhas\njuntadas\nerradas", "en"]]))
    assert translate_lines(["a", "b"], "pt") == {}
    assert not os.path.exists(machine_translate.CACHE_FILE)


def test_network_errors_never_raise(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("sem internet")

    mock_google(monkeypatch, handler)
    assert translate_lines(["Hello"], "pt") == {}


def test_detect_language():
    assert detect_language(["When the world is cold", "I will feel a glow just thinking of you"]) == "en"
    assert detect_language(["oi"]) is None  # texto curto demais


@pytest.mark.network
def test_real_google_translation():
    assert translate_lines(["Good morning, my friend"], "pt")
