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

def test_permanent_corruption():
    print("Clearing playback...")
    requests.post(f"{BASE_URL}/api/playback/clear")
    time.sleep(2)

    # Track A has timed lyrics on YTM
    print("Sending Track A (Ado - 唱, has timed lyrics)...")
    requests.post(f"{BASE_URL}/api/sync", json={
        "title": "唱 (Uta)",
        "artist": "Ado",
        "videoId": "UL5x6kGauoY",
        "currentTime": 0.0
    })

    # Switch immediately to Track B (Fake Song that has NO timed lyrics on YTM and NO translation)
    print("Immediately (100ms) switching to Track B (Untimed Track)...")
    time.sleep(0.1)
    requests.post(f"{BASE_URL}/api/sync", json={
        "title": "Untimed Track",
        "artist": "Untimed Artist",
        "videoId": "non_existent_untimed_id",
        "currentTime": 0.0
    })

    print("Monitoring state for 6 seconds...")
    for i in range(12):
        time.sleep(0.5)
        c = requests.get(f"{BASE_URL}/api/current").json()
        print(f"t={(i+1)*0.5:3.1f}s | Title: {c.get('title')} | hasTimed: {c.get('hasTimedLyrics')} | hasTrans: {c.get('hasTranslation')} | url: {c.get('translationUrl')}")

    final_c = requests.get(f"{BASE_URL}/api/current").json()
    print("\n--- FINAL STATE ---")
    print(f"Title: {final_c.get('title')}")
    print(f"hasTimedLyrics: {final_c.get('hasTimedLyrics')}")
    print(f"hasTranslation: {final_c.get('hasTranslation')}")
    print(f"translationUrl: {final_c.get('translationUrl')}")

    if final_c.get("title") == "Untimed Track" and (final_c.get("hasTimedLyrics") or final_c.get("hasTranslation")):
        print("🚨 CRITICAL BUG CONFIRMED: Untimed Track was PERMANENTLY contaminated with Track A's lyrics/translation!")
    else:
        print("State did not retain Track A's data.")

if __name__ == "__main__":
    test_permanent_corruption()
