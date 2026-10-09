import time

import pytest

from letrasbr_api.aligner import AlignedLine, align_lyrics, find_active_aligned_line
from letrasbr_api.providers.base import TimedLine
from letrasbr_api.text_utils import is_instrumental


def timed(*texts, step=2000):
    return [TimedLine(start_time=i * step, end_time=(i + 1) * step, text=t) for i, t in enumerate(texts)]


def verse(original, translation):
    return {"originals": [original], "translation": translation}


# --- Casos de borda ---

def test_empty_inputs_return_empty():
    assert align_lyrics([], [verse("Hello", "Olá")]) == []
    assert align_lyrics([], []) == []


def test_without_translation_lines_are_empty_and_marked_none():
    res = align_lyrics(timed("First line", "♪ ♫ ♪", "Third line"), [])
    assert [r.translation for r in res] == ["", "(♪)", ""]
    assert [r.source for r in res] == ["none", "none", "none"]
    assert res[1].is_instrumental


def test_unmatched_line_has_no_placeholder_translation():
    # Linha sem correspondência não recebe "♪" (que se confundia com instrumental)
    res = align_lyrics(timed("Hello there", "Completely different adlib"), [verse("Hello there", "Olá")])
    assert res[0].translation == "Olá" and res[0].source == "letras"
    assert all(r.translation != "♪" for r in res)


@pytest.mark.parametrize("text", ["♪ ♫ ♪", "[Instrumental]", "(Instrumental)", "", "solo"])
def test_instrumental_markers(text):
    assert is_instrumental(text)


def test_many_timed_few_translated():
    texts = [f"Timed lyric line {i}" for i in range(100)]
    anchors = {0: "Start of the song", 25: "First chorus here", 50: "Middle bridge section",
               75: "Second chorus repetition", 99: "Final outro line"}
    for i, t in anchors.items():
        texts[i] = t
    letras = [verse(t, f"tradução {i}") for i, t in anchors.items()]
    res = align_lyrics(timed(*texts), letras)
    assert len(res) == 100
    for i in anchors:
        assert f"tradução {i}" in res[i].translation


def test_few_timed_many_translated():
    blocks = ["Verse one block", "Chorus block", "Verse two block", "Bridge block", "Outro block"]
    letras = [verse(f"Lyric segment {j}", f"Tradução {j}") for j in range(100)]
    for k, j in enumerate([0, 25, 50, 75, 99]):
        letras[j] = verse(blocks[k], f"Bloco {k}")
    res = align_lyrics(timed(*blocks, step=10000), letras)
    assert len(res) == 5
    assert all(r.source == "letras" and r.translation for r in res)


def test_repeated_chorus():
    chorus, chorus_pt = "Yeah, yeah, yeah, all night long", "Sim, sim, sim, a noite toda"
    texts, letras = [], []
    for section in range(5):
        texts.append(f"Unique verse line {section}")
        letras.append(verse(f"Unique verse line {section}", f"Verso único {section}"))
        for _ in range(4):
            texts.append(chorus)
            letras.append(verse(chorus, chorus_pt))
    res = align_lyrics(timed(*texts, step=1500), letras)
    assert sum(1 for r in res if chorus_pt in r.translation) == 20


def test_japanese():
    res = align_lyrics(
        timed("夜に駆ける", "沈むように溶けてゆくように", "二人だけの空が広がる夜に", "さよならだけだった"),
        [verse("夜に駆ける", "Correndo para a noite"),
         verse("沈むように溶けてゆくように", "Como se estivesse afundando"),
         verse("二人だけの空が広がる夜に", "Na noite onde o céu se espalha"),
         verse("「さよなら」だけだった", "Era apenas um adeus")],
    )
    assert [r.translation for r in res] == [
        "Correndo para a noite", "Como se estivesse afundando", "Na noite onde o céu se espalha", "Era apenas um adeus"
    ]


def test_cyrillic():
    pairs = [("Белый снег, серый лед", "Neve branca"), ("На растрескавшейся земле", "Na terra rachada"),
             ("Город в дорожной петле", "A cidade"), ("Группа крови на рукаве", "Tipo sanguíneo")]
    letras = [verse(o, t) for o, t in pairs]
    letras[-1] = verse("Группа крови — на рукаве", "Tipo sanguíneo")
    res = align_lyrics(timed(*[o for o, _ in pairs]), letras)
    assert [r.translation for r in res] == [t for _, t in pairs]


def test_worst_case_identical_lines_is_fast():
    line = "Repetitive chorus line repeating over and over"
    t0 = time.perf_counter()
    res = align_lyrics(timed(*[line] * 70), [verse(line, "Refrão")] * 70)
    assert time.perf_counter() - t0 < 6.0
    assert len(res) == 70


def test_gap_between_anchors():
    texts = [f"Speech adlib {i}" for i in range(20)]
    texts[0], texts[19] = "Start Anchor", "End Anchor"
    letras = [verse(f"Speech adlib {j}", f"Fala {j}") for j in range(18)]
    letras[0], letras[17] = verse("Start Anchor", "Âncora Inicial"), verse("End Anchor", "Âncora Final")
    res = align_lyrics(timed(*texts, step=1000), letras)
    assert "Âncora Inicial" in res[0].translation
    assert "Âncora Final" in res[19].translation


# --- Linha ativa por tempo ---

LINES = [
    AlignedLine(1000, 5000, "Line 1", "Linha 1", False),
    AlignedLine(5000, 10000, "Line 2", "Linha 2", False),
    AlignedLine(14000, 20000, "Line 3", "Linha 3", False),
]


@pytest.mark.parametrize("t, expected", [
    (-500, None), (0, None), (1000, "Line 1"), (10000, "Line 2"),
    (12000, "Line 2"),   # intervalo entre versos mantém o anterior
    (50000, "Line 3"),   # após o fim mantém o último
])
def test_find_active_line(t, expected):
    active = find_active_aligned_line(LINES, t)
    assert (active.original if active else None) == expected


def test_find_active_line_on_shared_boundary():
    assert find_active_aligned_line(LINES, 5000).original in ("Line 1", "Line 2")


def test_find_active_line_empty():
    assert find_active_aligned_line([], 5000) is None
