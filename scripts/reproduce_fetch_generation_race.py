"""
Reproduction script: Demonstrating race condition in fetch_generation.
Shows that background threads for superseded tracks mutate global PlaybackState
without verifying fetch_generation, leading to stale state / cross-contamination.
"""

import sys
import time
import requests
import json

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"

def test_race_reproduction():
    print("Resetting state...")
    requests.post(f"{BASE_URL}/api/playback/clear")
    time.sleep(2)

    # Track A: Ado - 唱 (Uta) - takes ~1.5-2.5s for scraping/alignment
    # Track B: Ed Sheeran - Shape of You - starts right after
    print("1. Sending Track A (Ado - 唱)...")
    r1 = requests.post(f"{BASE_URL}/api/sync", json={
        "title": "唱 (Uta)",
        "artist": "Ado",
        "videoId": "UL5x6kGauoY",
        "currentTime": 0.0,
        "duration": 180.0
    })
    print("Track A status:", r1.json().get("status"))

    print("2. Immediately (100ms) sending Track B (Ed Sheeran - Shape of You)...")
    time.sleep(0.1)
    r2 = requests.post(f"{BASE_URL}/api/sync", json={
        "title": "Shape of You",
        "artist": "Ed Sheeran",
        "videoId": "JGwWNGJdvx8",
        "currentTime": 0.0,
        "duration": 233.0
    })
    print("Track B status:", r2.json().get("status"))

    print("3. State immediately after Track B switch:")
    c0 = requests.get(f"{BASE_URL}/api/current").json()
    print(f"Title: {c0.get('title')}, Artist: {c0.get('artist')}")

    # Inspect state every 200ms
    print("\n4. Polling state every 200ms to observe mutations by background threads:")
    corruptions_observed = []
    for i in range(25):
        time.sleep(0.2)
        c = requests.get(f"{BASE_URL}/api/current").json()
        trans_url = c.get("translationUrl") or ""
        has_trans = c.get("hasTranslation")
        has_timed = c.get("hasTimedLyrics")
        has_aligned = c.get("hasAlignedLyrics")
        title = c.get("title")

        # Corruption condition: Title is "Shape of You", but translationUrl or lyrics belong to Ado
        is_corrupted = ("ado" in trans_url.lower() and title == "Shape of You")
        if is_corrupted:
            corruptions_observed.append({
                "time_ms": int((i + 1) * 200),
                "title": title,
                "translationUrl": trans_url,
                "hasTranslation": has_trans
            })
            print(f"🚨 [CORRUPTION at {(i+1)*200}ms] Title is '{title}', but translationUrl is '{trans_url}'!")
        else:
            print(f"   t={(i+1)*200:4d}ms | Title: {title:<14} | transUrl: {trans_url[:40]} | hasTrans: {has_trans}")

    print("\n--- RESULTS ---")
    if corruptions_observed:
        print(f"BUG CONFIRMED: Observed {len(corruptions_observed)} instances of stale background thread mutating global state for a newer track!")
    else:
        print("No corruption observed in this window.")

if __name__ == "__main__":
    test_race_reproduction()
