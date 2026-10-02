"""
Isolated Rapid Song Switching Test:
Demonstrate whether switching between 3 tracks in 1 second causes
out-of-order state mutations or corrupts lyrics in PlaybackState.
"""

import time
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def run_isolated_rapid_switch():
    print("--- 1. Resetting playback state ---")
    requests.post(f"{BASE_URL}/api/playback/clear")

    print("Waiting 12 seconds for any background threads to idle...")
    time.sleep(12)

    # Track 1: Believer (Imagine Dragons)
    # Track 2: Levitating (Dua Lipa)
    # Track 3: Bohemian Rhapsody (Queen)
    tracks = [
        {"title": "Believer", "artist": "Imagine Dragons", "videoId": "7wtfhZwyrcc", "currentTime": 0.0, "duration": 204.0},
        {"title": "Levitating", "artist": "Dua Lipa", "videoId": "IXxi773tqgY", "currentTime": 0.0, "duration": 203.0},
        {"title": "Bohemian Rhapsody", "artist": "Queen", "videoId": "fJ9rUzIMcZQ", "currentTime": 0.0, "duration": 354.0},
    ]

    print("\n--- 2. Sending 3 track switches in rapid succession (~600ms total) ---")
    t0 = time.perf_counter()
    for i, t in enumerate(tracks):
        r = requests.post(f"{BASE_URL}/api/sync", json=t)
        print(f"Switch {i+1} sent: {t['artist']} - {t['title']} (HTTP {r.status_code})")
        time.sleep(0.3)
    total_switch_time = time.perf_counter() - t0
    print(f"Total switch elapsed: {total_switch_time:.3f}s")

    print("\n--- 3. Polling /api/current every 500ms for 20 seconds ---")
    states_observed = []
    for step in range(40):
        time.sleep(0.5)
        c = requests.get(f"{BASE_URL}/api/current").json()
        states_observed.append((
            step * 0.5,
            c.get("title"),
            c.get("artist"),
            c.get("hasTimedLyrics"),
            c.get("hasTranslation"),
            c.get("hasAlignedLyrics"),
            c.get("activeOriginal"),
            c.get("activeTranslation")
        ))
        print(f"t={step*0.5:4.1f}s | Title: {c.get('title'):<18} | Timed: {str(c.get('hasTimedLyrics')):<5} | Trans: {str(c.get('hasTranslation')):<5} | Aligned: {str(c.get('hasAlignedLyrics')):<5} | Orig: {str(c.get('activeOriginal'))[:30]}")

    # Check at t=45s
    res_45 = requests.post(f"{BASE_URL}/api/sync", json={
        "title": "Bohemian Rhapsody",
        "artist": "Queen",
        "videoId": "fJ9rUzIMcZQ",
        "currentTime": 45.0,
        "duration": 354.0,
        "isPaused": False,
        "lang": "pt",
        "source": "ytmusic"
    }).json()

    print("\n--- 4. Follow-up sync for Queen at currentTime=45.0s ---")
    print(json.dumps(res_45, indent=2, ensure_ascii=False))

    with open("scripts/rapid_switch_isolated_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "states_observed": states_observed,
            "res_45": res_45
        }, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    run_isolated_rapid_switch()
