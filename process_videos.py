"""
Video Processor - Neon Beats Factory (NBF) MOBILE FORMAT
Orchestrates rendering of 60 FPS vertical (1080x1920) EDM reels/shorts
using visualizer_core.py. Configurable via environment variables.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

LOCAL_OUTPUT_DIR = os.getenv("LOCAL_OUTPUT_DIR", "Processed_Videos")
BG_DARKEN_FACTOR = float(os.getenv("BG_DARKEN_FACTOR", "0.50"))
VISUALIZER_COLOR = os.getenv("VISUALIZER_COLOR", "variety")
VISUALIZER_DIAMETER = int(os.getenv("VISUALIZER_DIAMETER", "780"))
# Reels / Shorts clip length in seconds. 45 keeps YouTube Shorts eligibility
# (vertical + <=60s) while fitting Facebook Reels. 0 / empty = full song.
REEL_DURATION = float(os.getenv("REEL_DURATION", "45") or 0) or None
# Where the clip starts: "middle" begins at the halfway point of the song
# (clamped so the full clip always fits), "start" begins at 0:00.
REEL_START_MODE = os.getenv("REEL_START_MODE", "middle").strip().lower()
TARGET_WIDTH = int(os.getenv("TARGET_WIDTH", "1080"))
TARGET_HEIGHT = int(os.getenv("TARGET_HEIGHT", "1920"))
SHOW_SONG_TITLE = False  # Reference reels layout: big NBF logo at bottom, no title text


def resolve_clip_window(audio_path, duration=None, start_sec=None, start_mode=None):
    """Returns (start_sec, duration) for the reel clip. Defaults: 45s from the middle."""
    import soundfile as sf

    clip = duration if duration is not None else REEL_DURATION
    mode = (start_mode or REEL_START_MODE).strip().lower()

    if not clip or clip <= 0:
        return 0.0, None  # full song from the beginning

    total = 0.0
    try:
        info = sf.info(audio_path)
        if info.samplerate:
            total = info.frames / float(info.samplerate)
    except Exception as e:
        print(f"[Processor] Warning: could not probe audio length ({e}); starting at 0:00.")
        return 0.0, clip

    if start_sec is not None:
        start = max(0.0, float(start_sec))
    elif mode == "middle" and total > clip:
        start = total / 2.0  # the clip begins at the halfway point of the song
    else:
        start = 0.0
    # Clamp so the whole clip fits inside the track
    if total > 0:
        start = max(0.0, min(start, max(0.0, total - clip)))
        clip = min(clip, total - start)
    print(f"[Processor] Track length: {total:.1f}s -> clip: {clip:.1f}s starting at {start:.1f}s ({mode}).")
    return start, clip


def process_single_song(image_path, audio_path, song_filename, display_name=None, force_rebuild=True, duration=None, start_sec=None, start_mode=None, recent_colors=None):
    """
    Renders a vertical video + matching cover for a single song with
    10-day anti-repetition color selection.
    """
    safe_name = os.path.splitext(song_filename)[0]
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in (' ', '-', '_')).strip()
    if not safe_name:
        safe_name = "output"

    text_name = display_name if display_name else safe_name

    Path(LOCAL_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    output_filename = f"{safe_name}_mobile.mp4"
    output_path = os.path.join(LOCAL_OUTPUT_DIR, output_filename)
    thumb_path = os.path.join(LOCAL_OUTPUT_DIR, f"{safe_name}_mobile_thumb.jpg")

    if os.path.exists(output_path) and not force_rebuild:
        print(f"[Processor] Skipping '{output_filename}' - already generated.")
        return output_path, thumb_path, {"label": "cached", "bgr": None}

    from visualizer_core import generate_nbf_video

    viz_candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "Visualizer_Core_Only.viz"),
        "Visualizer_Core_Only.viz",
        r"D:\E agy cli\E youtube bots\nbf\Visualizer_Core_Only.viz",
        r"C:\Users\kreg9\Downloads\Visualizer_Core_Only.viz",
    ]
    viz_path = next((p for p in viz_candidates if os.path.exists(p)), "Visualizer_Core_Only.viz")

    title_arg = text_name if SHOW_SONG_TITLE else None

    clip_start, clip_duration = resolve_clip_window(
        audio_path, duration=duration, start_sec=start_sec, start_mode=start_mode
    )

    v_path, t_path, color_info = generate_nbf_video(
        viz_path=viz_path,
        bg_path=image_path,
        audio_path=audio_path,
        output_path=output_path,
        fps=60,
        base_diameter=VISUALIZER_DIAMETER,
        color=VISUALIZER_COLOR,
        recent_colors=recent_colors,
        darken_factor=BG_DARKEN_FACTOR,
        song_title=title_arg,
        target_width=TARGET_WIDTH,
        target_height=TARGET_HEIGHT,
        start_sec=clip_start,
        duration=clip_duration
    )

    return v_path, t_path, color_info


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python process_videos.py <image_path> <audio_path> <song_name>")
        sys.exit(1)

    img = sys.argv[1]
    aud = sys.argv[2]
    name = sys.argv[3]
    dur = float(sys.argv[4]) if len(sys.argv) > 4 else None
    start = float(sys.argv[5]) if len(sys.argv) > 5 else None

    v, t, c = process_single_song(img, aud, name, display_name=name, duration=dur, start_sec=start)
    print(f"\n[Processor] Complete:\n  Video: {v}\n  Thumbnail: {t}\n  Color: {c}")
