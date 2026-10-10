import pytest

from letrasbr_api import genre
from letrasbr_api.genre import classify, style_for


@pytest.mark.parametrize("tag, style", [
    ("black metal", "extreme_metal"), ("thrash metal", "rock"), ("indie rock", "indie"), ("Hip-Hop/Rap", "hiphop"),
    ("trap", "trap"), ("grime", "trap"), ("boom bap", "boombap"), ("jazz rap", "hiphop"), ("hyperpop", "hyperpop"),
    ("dance-pop", "pop"), ("french house", "electronic"), ("synthwave", "synthwave"), ("chiptune", "chiptune"),
    ("k-pop", "kpop"), ("J-Pop", "jpop"), ("j-rock", "jrock"), ("sertanejo universitário", "sert_univ"),
    ("Sertanejo", "country"), ("bluegrass", "folk"), ("romantic classical", "classical"), ("Blues", "jazz"),
    ("female vocals", None), ("Karaoke", None),
])
def test_style_for_tag(tag, style):
    assert style_for(tag) == style


def test_top_tag_subgenre_wins():
    assert classify(["chiptune", "bitpop", "electronic rock"], "Alternative") == "chiptune"
    assert classify(["black metal", "metal"], "Metal") == "extreme_metal"


def test_track_genre_sets_family_and_tags_refine_it():
    assert classify(["hip hop", "trap", "southern hip hop"], "Hip-Hop/Rap") == "trap"
    assert classify(["pop", "country", "country pop"], "Pop") == "pop"
    assert classify(["j-rock", "rock"], "Rock") == "jrock"


def test_unknown_genre():
    assert classify([], "Worldwide") is None
    assert classify(["female vocals"], "") is None


def test_resolve_caches_results_and_skips_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(genre, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(genre, "CACHE_FILE", str(tmp_path / "genres.json"))
    monkeypatch.setattr(genre, "_cache", None)
    calls = []

    def fake_mb(client, artist):
        calls.append(artist)
        if len(calls) == 1:
            raise RuntimeError("timeout")
        return ["grime", "hip hop"]

    monkeypatch.setattr(genre, "_musicbrainz_tags", fake_mb)
    assert genre.resolve_style("Stormzy", "Shut Up") is None  # falha de rede não vai para o cache
    assert genre.resolve_style("Stormzy", "Shut Up") == "trap"
    assert genre.resolve_style("Stormzy", "Vossi Bop") == "trap"
    assert calls == ["Stormzy", "Stormzy"]


def test_artist_candidates():
    assert genre._artist_candidates("Jorge & Mateus") == ["Jorge & Mateus", "Jorge"]
    assert genre._artist_candidates("Travis Scott, Drake") == ["Travis Scott, Drake", "Travis Scott"]
    assert genre._artist_candidates("Ado") == ["Ado"]
