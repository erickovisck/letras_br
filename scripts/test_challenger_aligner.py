"""
scripts/test_challenger_aligner.py
Empirical stress-test harness for aligner.py, fallback search, and boundary queries.
Authored by Challenger 2 (Alignment & Fallback Challenger).
"""

import sys
import os
import time
import json
import dataclasses
from typing import List, Dict, Any, Optional

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project root and letrasbr_api to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
API_DIR = os.path.join(BASE_DIR, "letrasbr_api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from letrasbr_api.aligner import (
    align_lyrics,
    find_active_aligned_line,
    AlignedLine,
    normalize,
    get_variants,
    expand_lyric_variants,
    score_line_match,
    is_instrumental,
)
from letrasbr_api.providers.base import TimedLine
from letrasbr_api.lyrics_sync import YTMManager

# Test reporting structures
test_results: List[Dict[str, Any]] = []


def run_test(suite: str, name: str, fn):
    t0 = time.perf_counter()
    try:
        fn()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        test_results.append({
            "suite": suite,
            "name": name,
            "status": "PASS",
            "elapsed_ms": round(elapsed_ms, 3),
            "error": None
        })
        print(f"  [PASS] {suite} :: {name} ({elapsed_ms:.2f}ms)")
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        test_results.append({
            "suite": suite,
            "name": name,
            "status": "FAIL",
            "elapsed_ms": round(elapsed_ms, 3),
            "error": str(e)
        })
        print(f"  [FAIL] {suite} :: {name} ({elapsed_ms:.2f}ms) -> {e}")


# ==============================================================================
# SUITE 1: Alignment Engine Boundary & Edge Cases
# ==============================================================================
print("\n" + "=" * 60)
print("SUITE 1: ALIGNMENT ENGINE EDGE CASES & STRESS")
print("=" * 60)


def test_empty_timed_lyrics():
    verses = [{"originals": ["Hello"], "translation": "Olá"}]
    res = align_lyrics([], verses, title="Empty Test", artist="Challenger")
    assert res == [], f"Expected empty list, got {res}"

run_test("Suite 1", "0 timed lines (empty list)", test_empty_timed_lyrics)


def test_empty_translation_verses():
    timed = [
        TimedLine(start_time=1000, end_time=3000, text="First line"),
        TimedLine(start_time=3000, end_time=5000, text="♪ ♫ ♪"),
        TimedLine(start_time=5000, end_time=7000, text="Third line"),
    ]
    res = align_lyrics(timed, [], title="Empty Verses", artist="Challenger")
    assert len(res) == 3, f"Expected 3 lines, got {len(res)}"
    assert res[0].translation == "(sem tradução)", f"Expected '(sem tradução)', got '{res[0].translation}'"
    assert res[1].is_instrumental is True, f"Expected instrumental line"
    assert res[1].translation == "(♪)", f"Expected '(♪)', got '{res[1].translation}'"
    assert res[2].translation == "(sem tradução)", f"Expected '(sem tradução)', got '{res[2].translation}'"

run_test("Suite 1", "0 translation lines (empty list)", test_empty_translation_verses)


def test_both_empty():
    res = align_lyrics([], [], title="Both Empty", artist="Challenger")
    assert res == [], f"Expected empty list, got {res}"

run_test("Suite 1", "Both timed and translation empty", test_both_empty)


def test_disproportionate_many_timed_few_letras():
    # 100 timed lines vs 5 translated lines
    timed = [
        TimedLine(start_time=i * 2000, end_time=(i + 1) * 2000, text=f"Timed lyric line {i}")
        for i in range(100)
    ]
    timed[0].text = "Start of the song"
    timed[25].text = "First chorus here"
    timed[50].text = "Middle bridge section"
    timed[75].text = "Second chorus repetition"
    timed[99].text = "Final outro line"

    letras = [
        {"originals": ["Start of the song"], "translation": "Início da canção"},
        {"originals": ["First chorus here"], "translation": "Primeiro refrão aqui"},
        {"originals": ["Middle bridge section"], "translation": "Seção da ponte do meio"},
        {"originals": ["Second chorus repetition"], "translation": "Segunda repetição do refrão"},
        {"originals": ["Final outro line"], "translation": "Linha final do encerramento"},
    ]

    res = align_lyrics(timed, letras, title="Disprop 100v5", artist="Challenger")
    assert len(res) == 100, f"Expected 100 lines, got {len(res)}"
    assert "Início da canção" in res[0].translation
    assert "Primeiro refrão aqui" in res[25].translation
    assert "Seção da ponte do meio" in res[50].translation
    assert "Segunda repetição do refrão" in res[75].translation
    assert "Linha final do encerramento" in res[99].translation

run_test("Suite 1", "Disproportionate: 100 timed lines vs 5 translated lines", test_disproportionate_many_timed_few_letras)


def test_disproportionate_few_timed_many_letras():
    # 5 timed lines vs 100 translated lines
    timed = [
        TimedLine(start_time=0, end_time=10000, text="Verse one block"),
        TimedLine(start_time=10000, end_time=20000, text="Chorus block"),
        TimedLine(start_time=20000, end_time=30000, text="Verse two block"),
        TimedLine(start_time=30000, end_time=40000, text="Bridge block"),
        TimedLine(start_time=40000, end_time=50000, text="Outro block"),
    ]
    letras = [
        {"originals": [f"Lyric segment {j}"], "translation": f"Tradução {j}"}
        for j in range(100)
    ]
    letras[0] = {"originals": ["Verse one block"], "translation": "Bloco do primeiro verso"}
    letras[25] = {"originals": ["Chorus block"], "translation": "Bloco do refrão"}
    letras[50] = {"originals": ["Verse two block"], "translation": "Bloco do segundo verso"}
    letras[75] = {"originals": ["Bridge block"], "translation": "Bloco da ponte"}
    letras[99] = {"originals": ["Outro block"], "translation": "Bloco do encerramento"}

    res = align_lyrics(timed, letras, title="Disprop 5v100", artist="Challenger")
    assert len(res) == 5, f"Expected 5 lines, got {len(res)}"
    for r in res:
        assert r.translation != "(sem tradução)", f"Line {r} has no translation"
        assert len(r.translation) > 0, f"Line {r} has empty translation"

run_test("Suite 1", "Disproportionate: 5 timed lines vs 100 translated lines", test_disproportionate_few_timed_many_letras)


def test_repeated_chorus_and_identical_lines():
    chorus_text = "Yeah, yeah, yeah, all night long"
    chorus_trans = "Sim, sim, sim, a noite toda"

    timed = []
    letras = []
    for section in range(5):
        t_base = section * 10000
        timed.append(TimedLine(start_time=t_base, end_time=t_base + 3000, text=f"Unique verse line {section}"))
        letras.append({"originals": [f"Unique verse line {section}"], "translation": f"Linha de verso único {section}"})
        for c in range(4):
            c_time = t_base + 3000 + c * 1500
            timed.append(TimedLine(start_time=c_time, end_time=c_time + 1500, text=chorus_text))
            letras.append({"originals": [chorus_text], "translation": chorus_trans})

    res = align_lyrics(timed, letras, title="Repeated Chorus", artist="Challenger")
    assert len(res) == len(timed)
    chorus_aligned_count = sum(1 for r in res if chorus_trans in r.translation)
    assert chorus_aligned_count == 20, f"Expected 20 chorus lines aligned, got {chorus_aligned_count}"

run_test("Suite 1", "Repeated chorus and identical text lines (25 lines)", test_repeated_chorus_and_identical_lines)


def test_non_latin_japanese():
    timed = [
        TimedLine(start_time=1000, end_time=4000, text="夜に駆ける"),
        TimedLine(start_time=4000, end_time=8000, text="沈むように溶けてゆくように"),
        TimedLine(start_time=8000, end_time=12000, text="二人だけの空が広がる夜に"),
        TimedLine(start_time=12000, end_time=16000, text="さよならだけだった"),
    ]
    letras = [
        {"originals": ["夜に駆ける"], "translation": "Correndo para a noite"},
        {"originals": ["沈むように溶けてゆくように"], "translation": "Como se estivesse afundando, como se estivesse derretendo"},
        {"originals": ["二人だけの空が広がる夜に"], "translation": "Na noite onde o céu se espalha apenas para nós dois"},
        {"originals": ["「さよなら」だけだった"], "translation": "Era apenas um adeus"},
    ]
    res = align_lyrics(timed, letras, title="Yoru ni Kakeru", artist="YOASOBI", lang="pt")
    assert len(res) == 4
    assert res[0].translation == "Correndo para a noite", f"Got {res[0].translation}"
    assert res[1].translation == "Como se estivesse afundando, como se estivesse derretendo"
    assert res[2].translation == "Na noite onde o céu se espalha apenas para nós dois"
    assert "adeus" in res[3].translation.lower(), f"Got {res[3].translation}"

run_test("Suite 1", "Non-Latin scripts: Japanese Kanji & Kana (YOASOBI)", test_non_latin_japanese)


def test_non_latin_cyrillic():
    timed = [
        TimedLine(start_time=1000, end_time=4000, text="Белый снег, серый лед"),
        TimedLine(start_time=4000, end_time=8000, text="На растрескавшейся земле"),
        TimedLine(start_time=8000, end_time=12000, text="Одеялом лоскутным на ней"),
        TimedLine(start_time=12000, end_time=16000, text="Город в дорожной петле"),
        TimedLine(start_time=16000, end_time=20000, text="Группа крови на рукаве"),
    ]
    letras = [
        {"originals": ["Белый снег, серый лед"], "translation": "Neve branca, gelo cinza"},
        {"originals": ["На растрескавшейся земле"], "translation": "Na terra rachada"},
        {"originals": ["Одеялом лоскутным на ней"], "translation": "Como uma colcha de retalhos sobre ela"},
        {"originals": ["Город в дорожной петле"], "translation": "A cidade em um nó rodoviário"},
        {"originals": ["Группа крови — на рукаве"], "translation": "Tipo sanguíneo na manga"},
    ]
    res = align_lyrics(timed, letras, title="Gruppa Krovi", artist="Kino", lang="pt")
    assert len(res) == 5
    assert "Neve branca" in res[0].translation, f"Got {res[0].translation}"
    assert "terra rachada" in res[1].translation, f"Got {res[1].translation}"
    assert "colcha de retalhos" in res[2].translation, f"Got {res[2].translation}"
    assert "nó rodoviário" in res[3].translation, f"Got {res[3].translation}"
    assert "Tipo sanguíneo" in res[4].translation, f"Got {res[4].translation}"

run_test("Suite 1", "Non-Latin scripts: Cyrillic (Kino - Gruppa Krovi)", test_non_latin_cyrillic)


def test_non_latin_arabic():
    timed = [
        TimedLine(start_time=1000, end_time=4000, text="حبيبي يا نور العين"),
        TimedLine(start_time=4000, end_time=8000, text="يا ساكن خيالي"),
        TimedLine(start_time=8000, end_time=12000, text="عاشق بقالي سنين"),
        TimedLine(start_time=12000, end_time=16000, text="ولا غيرك في بالي"),
    ]
    letras = [
        {"originals": ["حبيبي يا نور العين"], "translation": "Meu amor, luz dos olhos"},
        {"originals": ["يا ساكن خيالي"], "translation": "Que habita minha imaginação"},
        {"originals": ["عاشق بقالي سنين"], "translation": "Apaixonado há anos"},
        {"originals": ["ولا غيرك في بالي"], "translation": "E ninguém além de você na minha mente"},
    ]
    res = align_lyrics(timed, letras, title="Nour El Ain", artist="Amr Diab", lang="pt")
    assert len(res) == 4
    assert "luz dos olhos" in res[0].translation, f"Got {res[0].translation}"
    assert "imaginação" in res[1].translation, f"Got {res[1].translation}"
    assert "Apaixonado" in res[2].translation, f"Got {res[2].translation}"
    assert "ninguém além" in res[3].translation, f"Got {res[3].translation}"

run_test("Suite 1", "Non-Latin scripts: Arabic (Amr Diab - Nour El Ain)", test_non_latin_arabic)


def test_performance_worst_case_candidate_explosion():
    line_text = "Repetitive chorus line repeating over and over"
    line_trans = "Linha repetitiva de refrão se repetindo sem parar"
    N = 70
    timed = [TimedLine(start_time=i * 2000, end_time=(i + 1) * 2000, text=line_text) for i in range(N)]
    letras = [{"originals": [line_text], "translation": line_trans} for _ in range(N)]

    t0 = time.perf_counter()
    res = align_lyrics(timed, letras, title="Worst Case DP", artist="Challenger")
    duration = time.perf_counter() - t0
    print(f"    [TELEMETRY] N={N} identical lines took {duration:.3f}s, len(res)={len(res)}")
    assert duration < 6.0, f"Performance issue: took {duration:.2f}s, expected < 6.0s"
    assert len(res) == N

run_test("Suite 1", "Performance & Complexity: 70x70 identical candidate stress", test_performance_worst_case_candidate_explosion)


def test_gap_dp_deep_recursion_resilience():
    timed = [TimedLine(start_time=i * 1000, end_time=(i + 1) * 1000, text=f"Speech adlib {i}") for i in range(20)]
    letras = [{"originals": [f"Speech adlib {j}"], "translation": f"Fala traduzida {j}"} for j in range(18)]
    timed[0].text = "Start Anchor"
    letras[0] = {"originals": ["Start Anchor"], "translation": "Âncora Inicial"}
    timed[19].text = "End Anchor"
    letras[17] = {"originals": ["End Anchor"], "translation": "Âncora Final"}

    t0 = time.perf_counter()
    res = align_lyrics(timed, letras, title="Recursion Test", artist="Challenger")
    dur = time.perf_counter() - t0
    assert len(res) == 20
    assert "Âncora Inicial" in res[0].translation
    assert "Âncora Final" in res[19].translation

run_test("Suite 1", "Gap DP recursion resilience (20 YTM vs 18 Letras)", test_gap_dp_deep_recursion_resilience)


# ==============================================================================
# SUITE 2: Time-Boundary Queries in find_active_aligned_line
# ==============================================================================
print("\n" + "=" * 60)
print("SUITE 2: TIME-BOUNDARY QUERIES IN find_active_aligned_line")
print("=" * 60)

test_lines = [
    AlignedLine(start_time=1000, end_time=5000, original="Line 1", translation="Linha 1", is_instrumental=False),
    AlignedLine(start_time=5000, end_time=10000, original="Line 2", translation="Linha 2", is_instrumental=False),
    AlignedLine(start_time=14000, end_time=20000, original="Line 3", translation="Linha 3", is_instrumental=False),
]


def test_boundary_t_zero():
    # Song lyrics start at 1000ms. At t = 0ms:
    active = find_active_aligned_line(test_lines, 0)
    assert active is None, f"Expected None at t=0 before song, got {active}"

run_test("Suite 2", "Time-boundary: t = 0ms before first lyric (start=1000)", test_boundary_t_zero)


def test_boundary_t_zero_when_song_starts_at_zero():
    zero_lines = [
        AlignedLine(start_time=0, end_time=3000, original="Intro", translation="Introdução", is_instrumental=False),
        AlignedLine(start_time=3000, end_time=6000, original="Verse", translation="Verso", is_instrumental=False),
    ]
    active = find_active_aligned_line(zero_lines, 0)
    assert active is not None
    assert active.original == "Intro", f"Expected Intro at t=0, got {active.original}"

run_test("Suite 2", "Time-boundary: t = 0ms when first line starts at 0ms", test_boundary_t_zero_when_song_starts_at_zero)


def test_boundary_t_negative():
    active = find_active_aligned_line(test_lines, -500)
    assert active is None, f"Expected None at negative timestamp, got {active}"

run_test("Suite 2", "Time-boundary: t = negative (-500ms)", test_boundary_t_negative)


def test_boundary_exact_start_boundary():
    active = find_active_aligned_line(test_lines, 1000)
    assert active is not None
    assert active.original == "Line 1", f"Expected Line 1 at t=1000, got {active.original}"

run_test("Suite 2", "Time-boundary: t = 1000ms (exact start_time of Line 1)", test_boundary_exact_start_boundary)


def test_boundary_exact_transition_boundary():
    # Line 1 ends at 5000ms and Line 2 starts at 5000ms
    active = find_active_aligned_line(test_lines, 5000)
    assert active is not None
    print(f"    [NOTE] At boundary t=5000ms between Line 1 (1000..5000) and Line 2 (5000..10000): returned '{active.original}'")
    assert active.original in ("Line 1", "Line 2")

run_test("Suite 2", "Time-boundary: t = 5000ms (exact shared boundary Line 1 / Line 2)", test_boundary_exact_transition_boundary)


def test_boundary_exact_end_boundary():
    # Query at exact end_time of Line 2 (10000ms)
    active = find_active_aligned_line(test_lines, 10000)
    assert active is not None
    assert active.original == "Line 2", f"Expected Line 2 at t=10000, got {active.original}"

run_test("Suite 2", "Time-boundary: t = 10000ms (exact end_time of Line 2)", test_boundary_exact_end_boundary)


def test_boundary_inside_vocal_gap():
    # Gap between Line 2 (ends at 10000) and Line 3 (starts at 14000)
    active = find_active_aligned_line(test_lines, 12000)
    print(f"    [NOTE] In gap t=12000ms between Line 2 and Line 3: returned '{active.original if active else None}'")
    assert active is not None
    assert active.original == "Line 2", f"Expected Line 2 held during gap, got {active}"

run_test("Suite 2", "Time-boundary: t = 12000ms (in gap between 10000ms and 14000ms)", test_boundary_inside_vocal_gap)


def test_boundary_beyond_end_of_song():
    active = find_active_aligned_line(test_lines, 50000)
    print(f"    [NOTE] Beyond end of song (t=50000ms > 20000ms): returned '{active.original if active else None}'")
    assert active is not None
    assert active.original == "Line 3", f"Expected last line held or returned, got {active}"

run_test("Suite 2", "Time-boundary: t = 50000ms (beyond end of song)", test_boundary_beyond_end_of_song)


def test_boundary_empty_lines():
    active = find_active_aligned_line([], 5000)
    assert active is None, f"Expected None on empty lines list, got {active}"

run_test("Suite 2", "Time-boundary: empty aligned_lines list", test_boundary_empty_lines)


# ==============================================================================
# SUITE 3: Fallback Search Resilience
# ==============================================================================
print("\n" + "=" * 60)
print("SUITE 3: FALLBACK SEARCH RESILIENCE & DETERMINISM")
print("=" * 60)

ytm = YTMManager()


def test_fallback_search_known_track_bad_videoid():
    fake_vid = "invalid_vid_queen_xyz"
    title = "Bohemian Rhapsody"
    artist = "Queen"
    print(f"    [TEST] Testing YTMManager.get_timed_lyrics with invalid videoId='{fake_vid}', title='{title}', artist='{artist}'")
    lines = ytm.get_timed_lyrics(video_id=fake_vid, title=title, artist=artist)
    assert lines is not None, "Fallback search failed to find timed lyrics for Queen - Bohemian Rhapsody"
    assert len(lines) > 20, f"Expected >20 timed lines, got {len(lines)}"
    print(f"    [TELEMETRY] Successfully recovered {len(lines)} timed lines via fallback title+artist search!")

run_test("Suite 3", "Fallback Search: Known track with invalid videoId (Queen - Bohemian Rhapsody)", test_fallback_search_known_track_bad_videoid)


def test_fallback_search_second_track_bad_videoid():
    fake_vid = "bad_vid_dualipa_999"
    title = "Levitating"
    artist = "Dua Lipa"
    print(f"    [TEST] Testing YTMManager.get_timed_lyrics with invalid videoId='{fake_vid}', title='{title}', artist='{artist}'")
    lines = ytm.get_timed_lyrics(video_id=fake_vid, title=title, artist=artist)
    assert lines is not None, "Fallback search failed to find timed lyrics for Dua Lipa - Levitating"
    assert len(lines) > 20, f"Expected >20 timed lines, got {len(lines)}"
    print(f"    [TELEMETRY] Successfully recovered {len(lines)} timed lines via fallback title+artist search!")

run_test("Suite 3", "Fallback Search: Second track with invalid videoId (Dua Lipa - Levitating)", test_fallback_search_second_track_bad_videoid)


def test_fallback_search_nonexistent_track():
    fake_vid = "fake_nonexistent_vid_00000"
    title = "NonExistentSongTitleXYZ99887766"
    artist = "NonExistentArtistABC112233"
    print(f"    [TEST] Testing nonexistent track handling: title='{title}', artist='{artist}'")
    lines = ytm.get_timed_lyrics(video_id=fake_vid, title=title, artist=artist)
    assert lines is None, f"Expected None for nonexistent track, got {lines}"
    print("    [TELEMETRY] Gracefully returned None with zero exceptions.")

run_test("Suite 3", "Fallback Search: Nonexistent song gracefully returns None", test_fallback_search_nonexistent_track)


# ==============================================================================
# SUITE 4: Identified Bugs & Edge-Case Verifications
# ==============================================================================
print("\n" + "=" * 60)
print("SUITE 4: IDENTIFIED ARCHITECTURAL BUGS & BEHAVIORAL GAPS")
print("=" * 60)


def test_instrumental_text_marker_gap():
    # Verifies that aligner.py:is_instrumental recognizes text markers like [Instrumental]
    sample_notes = "♪ ♫ ♪"
    sample_bracket = "[Instrumental]"
    sample_paren = "(Instrumental)"

    assert is_instrumental(sample_notes) is True, "Musical notes must be instrumental"
    bracket_res = is_instrumental(sample_bracket)
    paren_res = is_instrumental(sample_paren)
    print(f"    [OBSERVATION] is_instrumental('{sample_bracket}') = {bracket_res}")
    print(f"    [OBSERVATION] is_instrumental('{sample_paren}') = {paren_res}")
    assert bracket_res is True, f"Expected is_instrumental('{sample_bracket}') to be True"
    assert paren_res is True, f"Expected is_instrumental('{sample_paren}') to be True"

run_test("Suite 4", "aligner.py: Instrumental text marker recognition verification", test_instrumental_text_marker_gap)


def test_reset_playback_state_leaves_fetching_flag():
    # Verifies that main.py:reset_playback_state clears is_fetching
    from letrasbr_api.main import state, reset_playback_state
    state.is_fetching = True
    reset_playback_state()
    is_still_fetching = state.is_fetching
    print(f"    [OBSERVATION] After reset_playback_state(), state.is_fetching={is_still_fetching}")
    assert is_still_fetching is False, "reset_playback_state() must clear is_fetching"

run_test("Suite 4", "main.py: reset_playback_state clears is_fetching flag", test_reset_playback_state_leaves_fetching_flag)


def test_async_fetch_missing_generation_guard():
    # Verifies that _do_fetch_lyrics_sync has generation parameter to prevent race conditions
    import inspect
    from letrasbr_api.main import _do_fetch_lyrics_sync
    sig = inspect.signature(_do_fetch_lyrics_sync)
    has_generation = "generation" in sig.parameters
    print(f"    [OBSERVATION] _do_fetch_lyrics_sync parameters: {list(sig.parameters.keys())}")
    print(f"    [OBSERVATION] Has 'generation' guard: {has_generation}")
    assert has_generation is True, "_do_fetch_lyrics_sync must have generation parameter"

run_test("Suite 4", "main.py: _do_fetch_lyrics_sync has generation guard preventing race conditions", test_async_fetch_missing_generation_guard)


# ==============================================================================
# SUMMARY REPORT
# ==============================================================================
print("\n" + "=" * 60)
print("TEST EXECUTION SUMMARY")
print("=" * 60)
total = len(test_results)
passed = sum(1 for t in test_results if t["status"] == "PASS")
failed = sum(1 for t in test_results if t["status"] == "FAIL")
print(f"Total Tests : {total}")
print(f"Passed      : {passed}")
print(f"Failed      : {failed}")

# Output JSON summary for machine parsing
summary_data = {
    "total": total,
    "passed": passed,
    "failed": failed,
    "tests": test_results
}
summary_path = os.path.join(BASE_DIR, "logs", "challenger_2_test_results.json")
with open(summary_path, "w", encoding="utf-8") as f:
    json.dump(summary_data, f, indent=2, ensure_ascii=False)
print(f"Summary written to: {summary_path}")

if failed > 0:
    sys.exit(1)
else:
    sys.exit(0)
