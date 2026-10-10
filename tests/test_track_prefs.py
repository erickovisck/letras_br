import json

from letrasbr_api import track_prefs


def test_offset_roundtrip_and_persistence():
    track_prefs.set_offset_ms("Linkin Park", "Numb", 500)
    assert track_prefs.get_offset_ms("linkin park ", "NUMB") == 500   # chave ignora caixa e espaços

    with open(track_prefs.PREFS_FILE, encoding="utf-8") as f:
        assert json.load(f) == {"linkin park|||numb": {"offsetMs": 500}}

    track_prefs._prefs = None  # força releitura do disco
    assert track_prefs.get_offset_ms("Linkin Park", "Numb") == 500


def test_zero_or_none_removes_entry():
    track_prefs.set_offset_ms("A", "B", 250)
    track_prefs.set_letras_path("A", "B", "/a/b/")
    track_prefs.set_offset_ms("A", "B", 0)
    assert track_prefs.get_offset_ms("A", "B") == 0
    assert track_prefs.get_letras_path("A", "B") == "/a/b/"
    track_prefs.set_letras_path("A", "B", None)
    assert track_prefs._load() == {}


def test_defaults_for_unknown_track():
    assert track_prefs.get_offset_ms("x", "y") == 0
    assert track_prefs.get_letras_path("x", "y") is None
