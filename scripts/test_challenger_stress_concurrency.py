"""
Adversarial Concurrency & Stress Testing Suite
Challenger 3: Final Concurrency & Edge Case Stress Tester

Evaluates:
1. Re-verification of Track A (Believer) vs Track B (Yellow) cache overwrite race.
2. Rapid 5-track skipping burst (50ms interval).
3. Mixed cache-hit and cache-miss inversion burst.
4. Extreme rapid skipping hammer (10 tracks in 200ms).
5. In-flight background fetch invalidation via /api/playback/clear.
6. A -> B -> A rapid oscillation test.
7. Zombie `is_fetching` and Frankenstein metadata detection.
"""

import sys
import time
import requests
import json
from typing import Dict, Any, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"

def get_current() -> Dict[str, Any]:
    try:
        r = requests.get(f"{BASE_URL}/api/current", timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def clear_playback() -> bool:
    try:
        r = requests.post(f"{BASE_URL}/api/playback/clear", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def sync_song(song: Dict[str, Any]) -> requests.Response:
    payload = {
        "title": song.get("title", ""),
        "artist": song.get("artist", ""),
        "videoId": song.get("videoId", "fake_stress_vid"),
        "currentTime": song.get("currentTime", 0.0),
        "duration": song.get("duration", 200.0),
        "isPaused": song.get("isPaused", False),
        "lang": song.get("lang", "pt"),
        "source": song.get("source", "ytmusic")
    }
    return requests.post(f"{BASE_URL}/api/sync", json=payload, timeout=5)

def wait_for_idle(timeout_s: float = 12.0) -> None:
    """Waits until is_fetching becomes False or timeout expires."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        c = get_current()
        if not c.get("is_fetching", False):
            break
        time.sleep(0.5)

# -------------------------------------------------------------
# TEST 1: Re-verification of Track A (Believer) vs Track B (Yellow)
# -------------------------------------------------------------
def test_1_believer_yellow_race() -> Dict[str, Any]:
    print("\n" + "=" * 65)
    print("TEST 1: Re-verifying Believer (Uncached) vs Yellow (Cached) Race")
    print("=" * 65)

    clear_playback()
    time.sleep(1.0)

    # 1. Pre-cache Yellow
    print("Step 1: Pre-caching Yellow...")
    sync_song({"title": "Yellow", "artist": "Coldplay", "videoId": "sim_yellow_vid"})
    time.sleep(3.0)

    clear_playback()
    time.sleep(1.0)

    # 2. Dispatch Uncached Track A (Believer)
    print("Step 2: Dispatching Track A (Imagine Dragons - Believer)...")
    r_a = sync_song({"title": "Believer", "artist": "Imagine Dragons", "videoId": "7wtfhZwyrcc"})
    assert r_a.status_code == 200, f"Track A sync failed with {r_a.status_code}"

    # 3. 50ms later, dispatch Track B (Yellow)
    time.sleep(0.05)
    print("Step 3: Dispatching Track B (Coldplay - Yellow) 50ms later...")
    r_b = sync_song({"title": "Yellow", "artist": "Coldplay", "videoId": "sim_yellow_vid"})
    assert r_b.status_code == 200, f"Track B sync failed with {r_b.status_code}"

    # 4. Monitor state for 8 seconds
    print("Step 4: Monitoring state across 16 intervals (8s total)...")
    corruptions = []
    for step in range(16):
        time.sleep(0.5)
        c = get_current()
        curr_title = c.get("title")
        curr_url = c.get("translationUrl") or ""
        curr_trans = c.get("hasTranslation")
        curr_fetching = c.get("is_fetching", False)
        
        # Check if Believer contaminated Yellow
        if "believer" in curr_url.lower():
            corruptions.append((step * 0.5, curr_title, curr_url))
            print(f"  🚨 t={step*0.5:3.1f}s | CORRUPTION: Yellow overwritten by Believer ({curr_url})")
        else:
            print(f"  [OK] t={step*0.5:3.1f}s | Title: {curr_title} | Trans: {curr_trans} | URL: {curr_url[:45] if curr_url else 'None'}")

    final_c = get_current()
    final_url = final_c.get("translationUrl") or ""
    final_title = final_c.get("title")
    final_artist = final_c.get("artist")

    passed = (
        len(corruptions) == 0 and
        final_title == "Yellow" and
        final_artist == "Coldplay" and
        ("coldplay" in final_url.lower() or "8091" in final_url.lower())
    )
    print(f"Test 1 Verdict: {'PASS' if passed else 'FAIL'}")
    return {
        "name": "believer_yellow_race",
        "passed": passed,
        "corruptions": corruptions,
        "final_title": final_title,
        "final_artist": final_artist,
        "final_url": final_url
    }

# -------------------------------------------------------------
# TEST 2: Rapid 5-Track Skipping Burst (50ms interval)
# -------------------------------------------------------------
def test_2_rapid_5_track_skipping() -> Dict[str, Any]:
    print("\n" + "=" * 65)
    print("TEST 2: Rapid 5-Track Skipping Burst (50ms interval)")
    print("=" * 65)

    clear_playback()
    time.sleep(1.0)

    tracks = [
        {"title": "唱 (Uta)", "artist": "Ado", "videoId": "UL5x6kGauoY"},
        {"title": "Feel Good Inc.", "artist": "Gorillaz", "videoId": "HyHNuVaZJ-k"},
        {"title": "Thriller", "artist": "Michael Jackson", "videoId": "sOnqjkJTMaA"},
        {"title": "Bohemian Rhapsody", "artist": "Queen", "videoId": "fJ9rUzIMcZQ"},
        {"title": "In The End", "artist": "Linkin Park", "videoId": "eVTXPUF4Oz4"},
    ]

    print(f"Dispatching burst of {len(tracks)} songs at 50ms intervals...")
    latencies = []
    for i, t in enumerate(tracks):
        t_start = time.perf_counter()
        r = sync_song(t)
        lat = (time.perf_counter() - t_start) * 1000
        latencies.append(lat)
        print(f"  Track {i+1}: {t['artist']} - {t['title']} (status: {r.status_code}, latency: {lat:.1f}ms)")
        time.sleep(0.05)

    target_track = tracks[-1]
    print(f"\nFinal target track is: {target_track['artist']} - {target_track['title']}")
    print("Monitoring for 10 seconds (20 intervals of 500ms)...")

    states = []
    foreign_contaminations = []
    for step in range(20):
        time.sleep(0.5)
        c = get_current()
        curr_title = c.get("title")
        curr_artist = c.get("artist")
        curr_url = c.get("translationUrl") or ""
        curr_fetching = c.get("is_fetching", False)
        
        # Check if title matches target
        title_ok = (curr_title == target_track["title"])
        # Check if any earlier song's URL showed up
        earlier_matched = None
        for earlier in tracks[:-1]:
            earlier_slug = earlier["title"].lower().split()[0]
            if len(earlier_slug) > 3 and earlier_slug in curr_url.lower():
                earlier_matched = earlier["title"]
                break
            if earlier["artist"].lower() in curr_url.lower():
                earlier_matched = earlier["artist"]
                break
        
        if earlier_matched:
            foreign_contaminations.append((step * 0.5, curr_title, curr_url, earlier_matched))
            print(f"  🚨 t={step*0.5:4.1f}s | CONTAMINATION from earlier track '{earlier_matched}': {curr_url}")
        else:
            print(f"  [OK] t={step*0.5:4.1f}s | Title: {curr_title:<15} | Trans: {str(c.get('hasTranslation')):<5} | URL: {curr_url[:40] if curr_url else 'None'}")
        
        states.append(c)

    final_c = get_current()
    final_url = final_c.get("translationUrl") or ""
    passed = (
        len(foreign_contaminations) == 0 and
        final_c.get("title") == target_track["title"] and
        final_c.get("artist") == target_track["artist"] and
        ("linkin-park" in final_url.lower() or "in-the-end" in final_url.lower())
    )
    print(f"Test 2 Verdict: {'PASS' if passed else 'FAIL'}")
    return {
        "name": "rapid_5_track_skipping",
        "passed": passed,
        "latencies_ms": latencies,
        "max_latency_ms": max(latencies),
        "foreign_contaminations": foreign_contaminations,
        "final_title": final_c.get("title"),
        "final_artist": final_c.get("artist"),
        "final_url": final_url,
        "has_timed": final_c.get("hasTimedLyrics"),
        "has_trans": final_c.get("hasTranslation"),
        "has_aligned": final_c.get("hasAlignedLyrics")
    }

# -------------------------------------------------------------
# TEST 3: Mixed Cache-Hit / Cache-Miss Inversion Stress
# -------------------------------------------------------------
def test_3_cache_inversion_burst() -> Dict[str, Any]:
    print("\n" + "=" * 65)
    print("TEST 3: Mixed Cache-Hit vs Cache-Miss Inversion Stress")
    print("=" * 65)

    clear_playback()
    time.sleep(1.0)

    # Pre-cache Dua Lipa (Fast Hit)
    print("Step 1: Pre-caching Dua Lipa - Levitating...")
    sync_song({"title": "Levitating", "artist": "Dua Lipa", "videoId": "IXxi773tqgY"})
    time.sleep(3.0)

    clear_playback()
    time.sleep(1.0)

    # Sequence:
    # 1. Uncached: BTS - Dynamite (slow network fetch)
    # 2. Cached: Dua Lipa - Levitating (fast cache hit)
    # 3. Uncached: The Weeknd - Blinding Lights (slow network fetch)
    print("Step 2: Sending [Uncached: Dynamite] -> 100ms -> [Cached: Levitating] -> 100ms -> [Uncached: Blinding Lights]")
    sync_song({"title": "Dynamite", "artist": "BTS", "videoId": "gdZLi9oWNZg"})
    time.sleep(0.1)
    sync_song({"title": "Levitating", "artist": "Dua Lipa", "videoId": "IXxi773tqgY"})
    time.sleep(0.1)
    sync_song({"title": "Blinding Lights", "artist": "The Weeknd", "videoId": "4NRXx6U8ABQ"})

    print("Step 3: Monitoring state for 10 seconds (20 intervals)...")
    contaminations = []
    for step in range(20):
        time.sleep(0.5)
        c = get_current()
        curr_title = c.get("title")
        curr_url = c.get("translationUrl") or ""
        
        # Target must remain Blinding Lights
        if curr_title != "Blinding Lights":
            contaminations.append((step * 0.5, "title_mismatch", curr_title))
        if "bts" in curr_url.lower() or "dynamite" in curr_url.lower():
            contaminations.append((step * 0.5, "dynamite_leak", curr_url))
            print(f"  🚨 t={step*0.5:4.1f}s | LEAK: Dynamite contaminated target! URL={curr_url}")
        elif "dua-lipa" in curr_url.lower() or "levitating" in curr_url.lower():
            contaminations.append((step * 0.5, "levitating_leak", curr_url))
            print(f"  🚨 t={step*0.5:4.1f}s | LEAK: Cached Levitating contaminated target! URL={curr_url}")
        else:
            print(f"  [OK] t={step*0.5:4.1f}s | Title: {curr_title:<16} | Trans: {str(c.get('hasTranslation')):<5} | URL: {curr_url[:40] if curr_url else 'None'}")

    final_c = get_current()
    final_url = final_c.get("translationUrl") or ""
    passed = (
        len(contaminations) == 0 and
        final_c.get("title") == "Blinding Lights" and
        final_c.get("artist") == "The Weeknd" and
        ("blinding-lights" in final_url.lower() or "the-weeknd" in final_url.lower())
    )
    print(f"Test 3 Verdict: {'PASS' if passed else 'FAIL'}")
    return {
        "name": "cache_inversion_burst",
        "passed": passed,
        "contaminations": contaminations,
        "final_title": final_c.get("title"),
        "final_url": final_url
    }

# -------------------------------------------------------------
# TEST 4: Extreme Rapid Skipping Hammer (10 Songs in 200ms)
# -------------------------------------------------------------
def test_4_ten_song_hammer() -> Dict[str, Any]:
    print("\n" + "=" * 65)
    print("TEST 4: Extreme Rapid Skipping Hammer (10 Songs in 200ms)")
    print("=" * 65)

    clear_playback()
    time.sleep(1.0)

    songs = [
        {"title": "唱 (Uta)", "artist": "Ado", "videoId": "UL5x6kGauoY"},
        {"title": "Feel Good Inc.", "artist": "Gorillaz", "videoId": "HyHNuVaZJ-k"},
        {"title": "Thriller", "artist": "Michael Jackson", "videoId": "sOnqjkJTMaA"},
        {"title": "Overdose", "artist": "natori", "videoId": "LKz5eSBhTh4"},
        {"title": "YELL", "artist": "Ikimonogakari", "videoId": "fake_id_001"},
        {"title": "Bohemian Rhapsody", "artist": "Queen", "videoId": "fJ9rUzIMcZQ"},
        {"title": "In The End", "artist": "Linkin Park", "videoId": "eVTXPUF4Oz4"},
        {"title": "Believer", "artist": "Imagine Dragons", "videoId": "7wtfhZwyrcc"},
        {"title": "Dynamite", "artist": "BTS", "videoId": "gdZLi9oWNZg"},
        {"title": "Lose Yourself", "artist": "Eminem", "videoId": "_Yhyp-_hX2s"},
    ]

    print("Firing 10 tracks with 20ms delay...")
    t0 = time.perf_counter()
    for i, s in enumerate(songs):
        sync_song(s)
        time.sleep(0.02)
    elapsed = time.perf_counter() - t0
    print(f"Dispatched all 10 tracks in {elapsed*1000:.1f}ms")

    final_expected = songs[-1]
    print(f"Final expected target: {final_expected['artist']} - {final_expected['title']}")
    print("Monitoring for 12 seconds...")

    states = []
    zombies = []
    for step in range(24):
        time.sleep(0.5)
        c = get_current()
        curr_title = c.get("title")
        curr_artist = c.get("artist")
        curr_url = c.get("translationUrl") or ""
        print(f"  t={step*0.5:4.1f}s | Title: {curr_title:<15} | Trans: {str(c.get('hasTranslation')):<5} | URL: {curr_url[:40] if curr_url else 'None'}")
        states.append(c)

    final_c = get_current()
    final_url = final_c.get("translationUrl") or ""
    passed = (
        final_c.get("title") == final_expected["title"] and
        final_c.get("artist") == final_expected["artist"] and
        ("eminem" in final_url.lower() or "lose-yourself" in final_url.lower()) and
        final_c.get("is_fetching") is not True # Should not be stuck
    )
    print(f"Test 4 Verdict: {'PASS' if passed else 'FAIL'}")
    return {
        "name": "ten_song_hammer",
        "passed": passed,
        "elapsed_ms": elapsed * 1000,
        "final_title": final_c.get("title"),
        "final_artist": final_c.get("artist"),
        "final_url": final_url,
        "final_is_fetching": final_c.get("is_fetching")
    }

# -------------------------------------------------------------
# TEST 5: In-Flight Background Fetch Invalidation via /api/playback/clear
# -------------------------------------------------------------
def test_5_clear_during_fetch_invalidation() -> Dict[str, Any]:
    print("\n" + "=" * 65)
    print("TEST 5: In-Flight Background Fetch Invalidation via /api/playback/clear")
    print("=" * 65)

    clear_playback()
    time.sleep(1.0)

    # 1. Dispatch uncached slow fetch
    print("Step 1: Dispatching uncached song (Bad Bunny - Tití Me Preguntó)...")
    sync_song({"title": "Tití Me Preguntó", "artist": "Bad Bunny", "videoId": "SxGVMgSnJIY"})

    # 2. Wait 100ms while background fetch is running
    time.sleep(0.1)

    # 3. Issue clear/stop
    print("Step 2: Issuing POST /api/playback/clear during active fetch...")
    clear_playback()

    # 4. Check state immediately after clear
    c_immediate = get_current()
    print(f"Immediate state after clear: title='{c_immediate.get('title')}', is_fetching={c_immediate.get('is_fetching')}")

    # 5. Monitor for 6 seconds to verify background thread does NOT resurrect state
    print("Step 3: Monitoring for 6 seconds (12 intervals) to confirm no zombie resurrection...")
    resurrections = []
    for step in range(12):
        time.sleep(0.5)
        c = get_current()
        if c.get("title") != "" or c.get("artist") != "" or c.get("hasTranslation") or c.get("hasTimedLyrics") or c.get("translationUrl"):
            resurrections.append((step * 0.5, c))
            print(f"  🚨 t={step*0.5:3.1f}s | ZOMBIE RESURRECTION DETECTED: title={c.get('title')}, transUrl={c.get('translationUrl')}")
        else:
            print(f"  [OK] t={step*0.5:3.1f}s | Cleared state preserved (title='', artist='', hasTrans=False)")

    final_c = get_current()
    passed = (
        len(resurrections) == 0 and
        final_c.get("title") == "" and
        final_c.get("artist") == "" and
        final_c.get("hasTranslation") is False and
        final_c.get("hasTimedLyrics") is False and
        final_c.get("translationUrl") is None
    )
    print(f"Test 5 Verdict: {'PASS' if passed else 'FAIL'}")
    return {
        "name": "clear_during_fetch_invalidation",
        "passed": passed,
        "resurrections": resurrections,
        "final_title": final_c.get("title"),
        "final_is_fetching": final_c.get("is_fetching")
    }

# -------------------------------------------------------------
# TEST 6: Rapid A -> B -> A Oscillation
# -------------------------------------------------------------
def test_6_aba_oscillation() -> Dict[str, Any]:
    print("\n" + "=" * 65)
    print("TEST 6: Rapid A -> B -> A Oscillation Test")
    print("=" * 65)

    clear_playback()
    time.sleep(1.0)

    track_a = {"title": "Believer", "artist": "Imagine Dragons", "videoId": "7wtfhZwyrcc"}
    track_b = {"title": "Yellow", "artist": "Coldplay", "videoId": "sim_yellow_vid"}

    print("Step 1: Sending Track A (Believer)...")
    sync_song(track_a)
    time.sleep(0.08)

    print("Step 2: Sending Track B (Yellow)...")
    sync_song(track_b)
    time.sleep(0.08)

    print("Step 3: Sending Track A (Believer) again...")
    sync_song(track_a)

    print("Step 4: Monitoring for 8 seconds...")
    contaminations = []
    for step in range(16):
        time.sleep(0.5)
        c = get_current()
        curr_title = c.get("title")
        curr_url = c.get("translationUrl") or ""
        
        # Target must be Believer
        if curr_title != "Believer":
            contaminations.append((step * 0.5, "title_mismatch", curr_title))
        if "coldplay" in curr_url.lower() or "yellow" in curr_url.lower():
            contaminations.append((step * 0.5, "yellow_contamination", curr_url))
            print(f"  🚨 t={step*0.5:3.1f}s | CONTAMINATION: Yellow contaminated final Believer! URL={curr_url}")
        else:
            print(f"  [OK] t={step*0.5:3.1f}s | Title: {curr_title:<12} | Trans: {str(c.get('hasTranslation')):<5} | URL: {curr_url[:40] if curr_url else 'None'}")

    final_c = get_current()
    final_url = final_c.get("translationUrl") or ""
    passed = (
        len(contaminations) == 0 and
        final_c.get("title") == "Believer" and
        final_c.get("artist") == "Imagine Dragons" and
        ("believer" in final_url.lower() or "imagine-dragons" in final_url.lower())
    )
    print(f"Test 6 Verdict: {'PASS' if passed else 'FAIL'}")
    return {
        "name": "aba_oscillation",
        "passed": passed,
        "contaminations": contaminations,
        "final_title": final_c.get("title"),
        "final_url": final_url
    }

def run_all_tests():
    print("=" * 65)
    print("CHALLENGER 3: ADVERSARIAL CONCURRENCY & STRESS TEST SUITE")
    print("=" * 65)

    results = []
    results.append(test_1_believer_yellow_race())
    time.sleep(2.0)
    results.append(test_2_rapid_5_track_skipping())
    time.sleep(2.0)
    results.append(test_3_cache_inversion_burst())
    time.sleep(2.0)
    results.append(test_4_ten_song_hammer())
    time.sleep(2.0)
    results.append(test_5_clear_during_fetch_invalidation())
    time.sleep(2.0)
    results.append(test_6_aba_oscillation())

    all_passed = all(r["passed"] for r in results)
    print("\n" + "=" * 65)
    print("CHALLENGER 3 TEST SUITE SUMMARY")
    print("=" * 65)
    for r in results:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        print(f"  {status} | {r['name']}")
    print("=" * 65)
    print(f"OVERALL RESULT: {'ALL PASS - APPROVE' if all_passed else 'FAILURES DETECTED - REQUEST_CHANGES'}")
    print("=" * 65)

    with open("logs/challenger_3_stress_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.time(),
            "overall_passed": all_passed,
            "results": results
        }, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    run_all_tests()
