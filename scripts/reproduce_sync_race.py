"""
scripts/reproduce_sync_race.py
Empirical reproduction script for race condition in letrasbr_api/main.py.
"""
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from letrasbr_api.main import (
    state,
    reset_playback_state,
    _reset_state_for_new_track,
)

print("=== TEST 1: Inspect reset_playback_state ===")
state.is_fetching = True
state.fetch_generation = 42
print(f"Before reset: is_fetching={state.is_fetching}, fetch_generation={state.fetch_generation}")
reset_playback_state()
print(f"After reset : is_fetching={state.is_fetching}, fetch_generation={state.fetch_generation}")

if state.is_fetching is True:
    print("[BUG CONFIRMED] reset_playback_state() fails to reset state.is_fetching!")
else:
    print("[OK] reset_playback_state() resets is_fetching.")

print("\n=== TEST 2: Inspect is_instrumental ===")
from letrasbr_api.aligner import is_instrumental

samples = [
    ("♪", True),
    ("♪ (♪) ♪", True),
    ("[Instrumental]", True),
    ("(Instrumental)", True),
    ("♪ [Instrumental] ♪", True),
    ("Só instrumental", True),
]

for text, expected in samples:
    actual = is_instrumental(text)
    match = (actual == expected)
    print(f"  '{text}' -> is_instrumental={actual} (expected {expected}) :: {'MATCH' if match else 'BUG'}")

print("\n=== TEST 3: Inspect Concurrency Overwrite in _do_fetch_lyrics_sync ===")
import inspect
from letrasbr_api.main import _do_fetch_lyrics_sync, _fetch_lyrics_background

sync_args = inspect.signature(_do_fetch_lyrics_sync).parameters
print(f"_do_fetch_lyrics_sync parameters: {list(sync_args.keys())}")
has_generation = "generation" in sync_args
print(f"Does _do_fetch_lyrics_sync receive 'generation'? {has_generation}")

if not has_generation:
    print("[BUG CONFIRMED] _do_fetch_lyrics_sync has no generation awareness and directly mutates global state!")
else:
    print("[OK] _do_fetch_lyrics_sync has generation guard.")
