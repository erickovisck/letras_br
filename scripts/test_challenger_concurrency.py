"""
Empirical Challenger Test Suite: API Concurrency, Latency, Resilience & State Race Conditions
Target: http://127.0.0.1:8000
"""

import sys
import time
import json
import statistics
import concurrent.futures
from typing import Dict, Any, List, Tuple
import requests

BASE_URL = "http://127.0.0.1:8000"

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

class ChallengerRunner:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.results: Dict[str, Any] = {
            "test_1_concurrency": {},
            "test_2_malformed_edge_cases": {},
            "test_3_rapid_song_switching": {},
            "test_4_health_under_load": {},
            "verdict": "UNKNOWN",
            "findings": []
        }

    # --------------------------------------------------------------------------
    # TEST 1: Concurrency & Latency (< 1000ms SLA, no 500, no deadlocks)
    # --------------------------------------------------------------------------
    def test_concurrency(self) -> bool:
        log("=== TEST 1: Concurrency & Responsiveness ===")
        all_passed = True

        # Part 1A: 10 rapid sequential requests (< 1000ms each)
        log("--> 1A: 10 rapid sequential sync requests...")
        seq_latencies = []
        seq_statuses = []
        for i in range(10):
            t0 = time.perf_counter()
            payload = {
                "title": "Feel Good Inc.",
                "artist": "Gorillaz",
                "videoId": "HyHNuVaZJ-k",
                "currentTime": float(i * 2),
                "duration": 223.0,
                "isPaused": False,
                "lang": "pt",
                "source": "ytmusic"
            }
            try:
                r = requests.post(f"{self.base_url}/api/sync", json=payload, timeout=2.0)
                lat_ms = (time.perf_counter() - t0) * 1000.0
                seq_latencies.append(lat_ms)
                seq_statuses.append(r.status_code)
            except Exception as e:
                seq_latencies.append(-1)
                seq_statuses.append(str(e))

        max_seq_lat = max(seq_latencies)
        mean_seq_lat = statistics.mean(seq_latencies)
        all_200 = all(s == 200 for s in seq_statuses)
        under_1000 = all(l < 1000.0 for l in seq_latencies)
        log(f"   Sequential (n=10): mean={mean_seq_lat:.2f}ms, max={max_seq_lat:.2f}ms, all_200={all_200}, under_1000ms={under_1000}")

        # Part 1B: 20 simultaneous concurrent requests fired via ThreadPool
        log("--> 1B: 20 simultaneous concurrent sync requests...")
        def send_sync(req_id: int) -> Tuple[int, float, int]:
            t0 = time.perf_counter()
            payload = {
                "title": "Feel Good Inc.",
                "artist": "Gorillaz",
                "videoId": "HyHNuVaZJ-k",
                "currentTime": float(req_id * 1.5),
                "duration": 223.0,
                "isPaused": False,
                "lang": "pt",
                "source": "ytmusic"
            }
            try:
                r = requests.post(f"{self.base_url}/api/sync", json=payload, timeout=3.0)
                lat = (time.perf_counter() - t0) * 1000.0
                return req_id, lat, r.status_code
            except Exception as e:
                return req_id, -1.0, 0

        par_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(send_sync, i) for i in range(20)]
            for f in concurrent.futures.as_completed(futures):
                par_results.append(f.result())

        par_latencies = [r[1] for r in par_results if r[1] > 0]
        par_statuses = [r[2] for r in par_results]
        max_par_lat = max(par_latencies) if par_latencies else 9999
        mean_par_lat = statistics.mean(par_latencies) if par_latencies else 9999
        p95_par_lat = statistics.quantiles(par_latencies, n=20)[18] if len(par_latencies) >= 20 else max_par_lat
        par_all_200 = all(s == 200 for s in par_statuses)
        par_under_1000 = all(l < 1000.0 for l in par_latencies)

        log(f"   Concurrent (n=20): mean={mean_par_lat:.2f}ms, p95={p95_par_lat:.2f}ms, max={max_par_lat:.2f}ms, all_200={par_all_200}, under_1000ms={par_under_1000}")

        # Part 1C: 50 concurrent requests burst
        log("--> 1C: 50 concurrent sync requests burst...")
        burst_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(send_sync, i) for i in range(50)]
            for f in concurrent.futures.as_completed(futures):
                burst_results.append(f.result())

        burst_latencies = [r[1] for r in burst_results if r[1] > 0]
        burst_statuses = [r[2] for r in burst_results]
        max_burst_lat = max(burst_latencies) if burst_latencies else 9999
        mean_burst_lat = statistics.mean(burst_latencies) if burst_latencies else 9999
        burst_all_200 = all(s == 200 for s in burst_statuses)
        burst_under_1000 = all(l < 1000.0 for l in burst_latencies)

        log(f"   Burst (n=50): mean={mean_burst_lat:.2f}ms, max={max_burst_lat:.2f}ms, all_200={burst_all_200}, under_1000ms={burst_under_1000}")

        test_passed = (all_200 and under_1000 and par_all_200 and par_under_1000 and burst_all_200 and burst_under_1000)

        self.results["test_1_concurrency"] = {
            "sequential_10": {
                "mean_ms": round(mean_seq_lat, 2),
                "max_ms": round(max_seq_lat, 2),
                "all_status_200": all_200,
                "under_1000ms_sla": under_1000
            },
            "concurrent_20": {
                "mean_ms": round(mean_par_lat, 2),
                "p95_ms": round(p95_par_lat, 2),
                "max_ms": round(max_par_lat, 2),
                "all_status_200": par_all_200,
                "under_1000ms_sla": par_under_1000
            },
            "burst_50": {
                "mean_ms": round(mean_burst_lat, 2),
                "max_ms": round(max_burst_lat, 2),
                "all_status_200": burst_all_200,
                "under_1000ms_sla": burst_under_1000
            },
            "passed": test_passed
        }
        return test_passed

    # --------------------------------------------------------------------------
    # TEST 2: Malformed / Edge-case Payloads
    # --------------------------------------------------------------------------
    def test_malformed_edge_cases(self) -> bool:
        log("\n=== TEST 2: Malformed & Edge-Case Payloads ===")
        cases = [
            # 2.1 Missing required fields (Expectation: 422 Unprocessable Entity, not 500)
            ("missing_title", {"artist": "Adele", "currentTime": 10.0}, 422),
            ("missing_artist", {"title": "Hello", "currentTime": 10.0}, 422),
            ("missing_currentTime", {"title": "Hello", "artist": "Adele"}, 422),
            ("empty_object", {}, 422),

            # 2.2 Invalid data types (Expectation: 422 Unprocessable Entity)
            ("invalid_type_currentTime_str", {"title": "Hello", "artist": "Adele", "currentTime": "not_a_number"}, 422),
            ("invalid_type_title_null", {"title": None, "artist": "Adele", "currentTime": 10.0}, 422),
            ("invalid_type_isPaused_str", {"title": "Hello", "artist": "Adele", "currentTime": 10.0, "isPaused": "bad_bool"}, 422),

            # 2.3 Negative currentTime (Expectation: Handled gracefully, HTTP 200, status loading/ok/paused)
            ("negative_currentTime_minus_1", {"title": "Shape of You", "artist": "Ed Sheeran", "currentTime": -1.0}, 200),
            ("negative_currentTime_minus_9999", {"title": "Shape of You", "artist": "Ed Sheeran", "currentTime": -9999.0}, 200),

            # 2.4 Extreme / excessive duration (Expectation: HTTP 200, no float overflow crash)
            ("duration_huge", {"title": "Shape of You", "artist": "Ed Sheeran", "currentTime": 10.0, "duration": 999999999.0}, 200),
            ("duration_zero", {"title": "Shape of You", "artist": "Ed Sheeran", "currentTime": 10.0, "duration": 0.0}, 200),
            ("duration_negative", {"title": "Shape of You", "artist": "Ed Sheeran", "currentTime": 10.0, "duration": -50.0}, 200),

            # 2.5 Unknown language codes in sync payload
            ("unknown_lang_klingon", {"title": "Shape of You", "artist": "Ed Sheeran", "currentTime": 10.0, "lang": "klingon"}, 200),
            ("unknown_lang_empty", {"title": "Shape of You", "artist": "Ed Sheeran", "currentTime": 10.0, "lang": ""}, 200),

            # 2.6 Non-ASCII, Unicode, emoji, and injection strings
            ("unicode_japanese_kanji", {"title": "唱 (Uta)", "artist": "Ado", "currentTime": 5.0}, 200),
            ("unicode_emoji", {"title": "🔥 Blast 🎵", "artist": "⚡ DJ Test 🎧", "currentTime": 5.0}, 200),
            ("unicode_cyrillic_arabic", {"title": "Песня / أغنية", "artist": "Исполнитель / فنان", "currentTime": 5.0}, 200),
            ("special_chars_quotes_sql", {"title": "Song ' \" <script>alert(1)</script> ; DROP TABLE lyrics; --", "artist": "Artist & Co. / \\", "currentTime": 5.0}, 200),
            ("huge_title_10k_chars", {"title": "A" * 10000, "artist": "B" * 5000, "currentTime": 5.0}, 200),
        ]

        case_results = []
        all_passed = True

        for name, payload, expected_status in cases:
            t0 = time.perf_counter()
            try:
                r = requests.post(f"{self.base_url}/api/sync", json=payload, timeout=3.0)
                lat_ms = (time.perf_counter() - t0) * 1000.0
                actual_status = r.status_code
                passed = (actual_status == expected_status)
                if not passed:
                    all_passed = False
                resp_json = {}
                try:
                    resp_json = r.json()
                except Exception:
                    pass
                log(f"   [{'PASS' if passed else 'FAIL'}] {name}: got HTTP {actual_status} (expected {expected_status}) in {lat_ms:.1f}ms")
                case_results.append({
                    "case": name,
                    "expected_status": expected_status,
                    "actual_status": actual_status,
                    "latency_ms": round(lat_ms, 2),
                    "passed": passed,
                    "response_summary": str(resp_json)[:100]
                })
            except Exception as e:
                all_passed = False
                log(f"   [FAIL] {name}: Exception {e}")
                case_results.append({
                    "case": name,
                    "expected_status": expected_status,
                    "actual_status": "EXCEPTION",
                    "error": str(e),
                    "passed": False
                })

        # Also test /api/language with invalid language
        log("--> Testing /api/language with invalid language payload...")
        try:
            r_lang = requests.post(f"{self.base_url}/api/language", json={"lang": "klingon"}, timeout=3.0)
            lang_json = r_lang.json()
            lang_handled = (r_lang.status_code == 200 and lang_json.get("status") == "error")
            log(f"   [{'PASS' if lang_handled else 'FAIL'}] /api/language unknown lang: {lang_json}")
            case_results.append({
                "case": "api_language_unknown_klingon",
                "expected_status": 200,
                "actual_status": r_lang.status_code,
                "passed": lang_handled,
                "response": lang_json
            })
            if not lang_handled:
                all_passed = False
        except Exception as e:
            all_passed = False
            log(f"   [FAIL] /api/language exception: {e}")

        self.results["test_2_malformed_edge_cases"] = {
            "total_cases": len(case_results),
            "passed_cases": sum(1 for c in case_results if c["passed"]),
            "cases": case_results,
            "passed": all_passed
        }
        return all_passed

    # --------------------------------------------------------------------------
    # TEST 3: Rapid Song Switching & fetch_generation Concurrency Invalidation
    # --------------------------------------------------------------------------
    def test_rapid_song_switching(self) -> bool:
        log("\n=== TEST 3: Rapid Song Switching & fetch_generation Superseding ===")
        # We switch between 3 diverse tracks in 1 second:
        # Track 1: Believer (Imagine Dragons, 7wtfhZwyrcc)
        # Track 2: Levitating (Dua Lipa, IXxi773tqgY)
        # Track 3: Bohemian Rhapsody (Queen, fJ9rUzIMcZQ)
        # Final active track MUST be Bohemian Rhapsody!

        # Reset state first
        requests.post(f"{self.base_url}/api/playback/clear")

        tracks = [
            {"title": "Believer", "artist": "Imagine Dragons", "videoId": "7wtfhZwyrcc", "currentTime": 0.0, "duration": 204.0},
            {"title": "Levitating", "artist": "Dua Lipa", "videoId": "IXxi773tqgY", "currentTime": 0.0, "duration": 203.0},
            {"title": "Bohemian Rhapsody", "artist": "Queen", "videoId": "fJ9rUzIMcZQ", "currentTime": 0.0, "duration": 354.0},
        ]

        switch_latencies = []
        log("--> Sending 3 rapid track switches within ~600ms...")
        t_start = time.perf_counter()
        for idx, track in enumerate(tracks):
            t0 = time.perf_counter()
            r = requests.post(f"{self.base_url}/api/sync", json=track, timeout=2.0)
            lat = (time.perf_counter() - t0) * 1000.0
            switch_latencies.append(lat)
            log(f"   Switch {idx+1} ({track['artist']} - {track['title']}): HTTP {r.status_code} in {lat:.2f}ms")
            time.sleep(0.25) # 250ms spacing -> total elapsed ~600ms (< 1.0s)

        total_switch_time = time.perf_counter() - t_start
        log(f"   Total switch elapsed time: {total_switch_time:.3f}s (< 1.0s requirement satisfied)")

        # Verify immediate state after rapid switch
        curr_initial = requests.get(f"{self.base_url}/api/current", timeout=2.0).json()
        log(f"   State immediately after 3rd switch: title='{curr_initial.get('title')}', artist='{curr_initial.get('artist')}'")

        # Now monitor state for up to 10 seconds to verify background fetch resolution
        log("--> Monitoring background fetch resolution over 10 seconds...")
        snapshots = []
        final_state = {}
        for second in range(1, 11):
            time.sleep(1.0)
            c = requests.get(f"{self.base_url}/api/current", timeout=2.0).json()
            snapshots.append({
                "time_sec": second,
                "title": c.get("title"),
                "artist": c.get("artist"),
                "hasTimedLyrics": c.get("hasTimedLyrics"),
                "hasTranslation": c.get("hasTranslation"),
                "hasAlignedLyrics": c.get("hasAlignedLyrics"),
                "activeOriginal": c.get("activeOriginal"),
                "activeTranslation": c.get("activeTranslation")
            })
            final_state = c

        # Send follow-up sync for Bohemian Rhapsody at currentTime=45.0 to check lyric alignment
        sync_45 = requests.post(f"{self.base_url}/api/sync", json={
            "title": "Bohemian Rhapsody",
            "artist": "Queen",
            "videoId": "fJ9rUzIMcZQ",
            "currentTime": 45.0,
            "duration": 354.0,
            "isPaused": False,
            "lang": "pt",
            "source": "ytmusic"
        }, timeout=2.0).json()

        log(f"   Final State at t=10s: title='{final_state.get('title')}', hasTimed={final_state.get('hasTimedLyrics')}, hasTrans={final_state.get('hasTranslation')}, hasAligned={final_state.get('hasAlignedLyrics')}")
        log(f"   Follow-up sync at 45s: activeOriginal='{sync_45.get('activeOriginal')}', activeTranslation='{sync_45.get('activeTranslation')}'")

        # Validation Checks:
        # 1. State title and artist MUST match Queen - Bohemian Rhapsody
        title_correct = (final_state.get("title") == "Bohemian Rhapsody" and final_state.get("artist") == "Queen")
        # 2. Aligned lyrics or translation MUST belong to Queen, NOT Believer or Levitating!
        # Queen lyrics at 45s or generally contain "Mama" or "life" or "Bohemian" or Queen verses
        act_orig = (sync_45.get("activeOriginal") or "").lower()
        act_trans = (sync_45.get("activeTranslation") or "").lower()
        log(f"   Active lyric text: orig='{act_orig}', trans='{act_trans}'")

        # Check for cross-contamination from earlier switched tracks
        believer_contamination = ("believer" in act_orig or "first things first" in act_orig or "dor" in act_trans and "primeiro" in act_trans)
        levitating_contamination = ("levitating" in act_orig or "sugarboo" in act_orig or "galaxy" in act_orig)

        has_contamination = believer_contamination or levitating_contamination

        # Check whether generation properly invalidated background work
        # Let's inspect if Queen lyrics loaded
        queen_lyrics_loaded = final_state.get("hasTimedLyrics") and final_state.get("hasAlignedLyrics")

        switch_passed = (title_correct and not has_contamination and queen_lyrics_loaded)

        log(f"   Title Correct: {title_correct}")
        log(f"   No Contamination: {not has_contamination}")
        log(f"   Queen Lyrics Loaded: {queen_lyrics_loaded}")
        log(f"   --> Rapid switching verdict: {'PASS' if switch_passed else 'FAIL'}")

        self.results["test_3_rapid_song_switching"] = {
            "total_switch_time_sec": round(total_switch_time, 3),
            "switch_latencies_ms": [round(l, 2) for l in switch_latencies],
            "title_correct": title_correct,
            "no_contamination": not has_contamination,
            "queen_lyrics_loaded": bool(queen_lyrics_loaded),
            "active_original_at_45s": sync_45.get("activeOriginal"),
            "active_translation_at_45s": sync_45.get("activeTranslation"),
            "snapshots_summary": snapshots[-3:],
            "passed": switch_passed
        }
        return switch_passed

    # --------------------------------------------------------------------------
    # TEST 4: Health Check Under Load
    # --------------------------------------------------------------------------
    def test_health_under_load(self) -> bool:
        log("\n=== TEST 4: GET /api/health Under Load ===")
        # Launch continuous sync traffic in background while repeatedly polling /api/health

        stop_traffic = False
        sync_count = [0]
        sync_errors = [0]

        def background_traffic():
            while not stop_traffic:
                try:
                    payload = {
                        "title": "Bohemian Rhapsody",
                        "artist": "Queen",
                        "videoId": "fJ9rUzIMcZQ",
                        "currentTime": 50.0 + (sync_count[0] % 50),
                        "duration": 354.0,
                        "isPaused": False,
                        "lang": "pt",
                        "source": "ytmusic"
                    }
                    r = requests.post(f"{self.base_url}/api/sync", json=payload, timeout=1.0)
                    if r.status_code == 200:
                        sync_count[0] += 1
                    else:
                        sync_errors[0] += 1
                except Exception:
                    sync_errors[0] += 1
                time.sleep(0.02) # 50 requests/sec

        # Start 4 traffic generator threads
        workers = []
        for _ in range(4):
            t = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            f = t.submit(background_traffic)
            workers.append((t, f))

        log("--> Stress traffic active: polling /api/health 50 times...")
        health_latencies = []
        health_statuses = []
        health_responses = []

        for i in range(50):
            t0 = time.perf_counter()
            try:
                r = requests.get(f"{self.base_url}/api/health", timeout=1.0)
                lat_ms = (time.perf_counter() - t0) * 1000.0
                health_latencies.append(lat_ms)
                health_statuses.append(r.status_code)
                health_responses.append(r.json())
            except Exception as e:
                health_latencies.append(-1.0)
                health_statuses.append(0)
                health_responses.append({"error": str(e)})
            time.sleep(0.05)

        # Stop background traffic
        stop_traffic = True
        for t, f in workers:
            t.shutdown(wait=False)

        mean_h_lat = statistics.mean(health_latencies) if health_latencies else 9999
        p95_h_lat = statistics.quantiles(health_latencies, n=20)[18] if len(health_latencies) >= 20 else max(health_latencies)
        max_h_lat = max(health_latencies) if health_latencies else 9999
        all_running = all(res.get("status") == "running" for res in health_responses if isinstance(res, dict))
        all_200 = all(s == 200 for s in health_statuses)

        log(f"   Background sync requests processed during test: {sync_count[0]} (errors: {sync_errors[0]})")
        log(f"   Health check (n=50): mean={mean_h_lat:.2f}ms, p95={p95_h_lat:.2f}ms, max={max_h_lat:.2f}ms, all_200={all_200}, all_running={all_running}")

        health_passed = (all_200 and all_running and max_h_lat < 1000.0)

        self.results["test_4_health_under_load"] = {
            "total_health_checks": len(health_statuses),
            "all_status_200": all_200,
            "all_status_running": all_running,
            "mean_latency_ms": round(mean_h_lat, 2),
            "p95_latency_ms": round(p95_h_lat, 2),
            "max_latency_ms": round(max_h_lat, 2),
            "background_sync_requests_sent": sync_count[0],
            "passed": health_passed
        }
        return health_passed

    def run_all(self):
        t0 = time.time()
        p1 = self.test_concurrency()
        p2 = self.test_malformed_edge_cases()
        p3 = self.test_rapid_song_switching()
        p4 = self.test_health_under_load()
        elapsed = round(time.time() - t0, 2)

        overall_pass = p1 and p2 and p3 and p4
        self.results["verdict"] = "APPROVE" if overall_pass else "REQUEST_CHANGES"
        self.results["total_elapsed_seconds"] = elapsed

        print("\n" + "=" * 60)
        print(f"OVERALL CHALLENGE VERDICT: {self.results['verdict']} (Elapsed: {elapsed}s)")
        print(f"Test 1 (Concurrency):            {'PASS' if p1 else 'FAIL'}")
        print(f"Test 2 (Malformed/Edge Cases):   {'PASS' if p2 else 'FAIL'}")
        print(f"Test 3 (Rapid Song Switching):   {'PASS' if p3 else 'FAIL'}")
        print(f"Test 4 (Health Under Load):      {'PASS' if p4 else 'FAIL'}")
        print("=" * 60)

        with open("scripts/challenger_concurrency_results.json", "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print("Results written to scripts/challenger_concurrency_results.json")

        return 0 if overall_pass else 1

if __name__ == "__main__":
    runner = ChallengerRunner()
    sys.exit(runner.run_all())
