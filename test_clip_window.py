"""Focused test for the mobile clip window: 45s reels start mid-song.

Run:  python test_clip_window.py
"""
import sys
import types


class _FakeInfo:
    def __init__(self, frames, samplerate):
        self.frames = frames
        self.samplerate = samplerate


def _install_fake_soundfile(total_seconds, samplerate=44100):
    fake = types.ModuleType("soundfile")
    fake.info = lambda _path: _FakeInfo(int(total_seconds * samplerate), samplerate)
    sys.modules["soundfile"] = fake


def main():
    _install_fake_soundfile(total_seconds=200.0)
    import process_videos as pv

    # Default: 45s clip starting at the halfway point of a 200s song.
    start, clip = pv.resolve_clip_window("song.mp3")
    assert start == 100.0, f"expected start 100.0, got {start}"
    assert clip == 45.0, f"expected clip 45.0, got {clip}"

    # "start" mode begins at 0:00.
    start, clip = pv.resolve_clip_window("song.mp3", start_mode="start")
    assert start == 0.0, f"expected start 0.0, got {start}"
    assert clip == 45.0, f"expected clip 45.0, got {clip}"

    # Short song: clamped so the whole clip fits.
    _install_fake_soundfile(total_seconds=30.0)
    start, clip = pv.resolve_clip_window("short.mp3")
    assert start == 0.0, f"expected start 0.0, got {start}"
    assert clip == 30.0, f"expected clip 30.0, got {clip}"

    # Explicit start_sec wins over the mode.
    _install_fake_soundfile(total_seconds=200.0)
    start, clip = pv.resolve_clip_window("song.mp3", start_sec=10.0)
    assert start == 10.0, f"expected start 10.0, got {start}"
    assert clip == 45.0, f"expected clip 45.0, got {clip}"

    # duration=0 means the full song.
    start, clip = pv.resolve_clip_window("song.mp3", duration=0)
    assert start == 0.0 and clip is None, f"expected full song, got {(start, clip)}"

    print("test_clip_window: all 5 checks passed.")


if __name__ == "__main__":
    main()
