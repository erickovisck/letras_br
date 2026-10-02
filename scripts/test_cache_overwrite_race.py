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

def test_cache_overwrite_race():
    print("Pre-caching Track B (Coldplay - Yellow)...")
    requests.post(f"{BASE_URL}/api/sync", json={
        "title": "Yellow",
        "artist": "Coldplay",
        "videoId": "simulated_invalid_vid_coldplay",
        "currentTime": 0.0
    })
    time.sleep(3) # Let Yellow cache

    print("Clearing state...")
    requests.post(f"{BASE_URL}/api/playback/clear")
    time.sleep(1)

    print("1. Sending Track A (Uncached: Imagine Dragons - Believer)...")
    requests.post(f"{BASE_URL}/api/sync", json={
        "title": "Believer",
        "artist": "Imagine Dragons",
        "videoId": "7wtfhZwyrcc",
        "currentTime": 0.0
    })

    print("2. Immediately (50ms) sending Track B (Cached: Coldplay - Yellow)...")
    time.sleep(0.05)
    requests.post(f"{BASE_URL}/api/sync", json={
        "title": "Yellow",
        "artist": "Coldplay",
        "videoId": "simulated_invalid_vid_coldplay",
        "currentTime": 0.0
    })

    print("3. State immediately after Track B switch:")
    c0 = requests.get(f"{BASE_URL}/api/current").json()
    print(f"Title: {c0.get('title')}, Artist: {c0.get('artist')}")

    print("\n4. Monitoring state for 8 seconds:")
    for i in range(16):
        time.sleep(0.5)
        c = requests.get(f"{BASE_URL}/api/current").json()
        print(f"t={(i+1)*0.5:3.1f}s | Title: {c.get('title')} | transUrl: {c.get('translationUrl')} | hasTrans: {c.get('hasTranslation')}")

    final_c = requests.get(f"{BASE_URL}/api/current").json()
    print("\n--- FINAL STATE ---")
    print(f"Title: {final_c.get('title')}")
    print(f"translationUrl: {final_c.get('translationUrl')}")

    if final_c.get("title") == "Yellow" and "believer" in (final_c.get("translationUrl") or "").lower():
        print("🚨 CRITICAL BUG CONFIRMED: Yellow (Track B) was PERMANENTLY OVERWRITTEN by Believer (Track A)!")
    elif final_c.get("title") == "Yellow" and "coldplay" in (final_c.get("translationUrl") or "").lower():
        print("Yellow's translation URL is correct.")
    else:
        print(f"Unexpected final URL: {final_c.get('translationUrl')}")

if __name__ == "__main__":
    test_cache_overwrite_race()
