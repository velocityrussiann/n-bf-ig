# Neon Beats Factory (NBF) — Mobile Format

Vertical 1080×1920 EDM visualizer videos for **Facebook Reels** and **YouTube Shorts**.
Same engine and branding as the long-form [nbf](../nbf) project, re-laid-out for the 9:16 mobile canvas:

- NBF logo top-center (clear of captions and platform UI)
- 3D topographic mesh core centered with sub-bass BeatPulse
- 10-day anti-repetition neon color selection
- 60 FPS, 1080×1920, AAC 320k audio

## Local preview

```bash
pip install -r requirements.txt
python visualizer_core.py --image Images/<cover>.png --audio Audio/<song>.mp3 --output preview_mobile.mp4 --duration 30
```

Or render one full reel clip (default 60 s, configurable via `REEL_DURATION`):

```bash
python process_videos.py Images/<cover>.png Audio/<song>.mp3 "Song Name" 60
```

## Full pipeline (Drive → render → YouTube Shorts + Facebook Reels)

```bash
copy .env.example .env   # then fill in credentials
python auto_pipeline.py
```

Set `REEL_DURATION=0` in `.env` to render the full song instead of a 60-second clip.
YouTube classifies vertical videos ≤60 s as Shorts automatically; the pipeline
also appends the `#Shorts` hashtag. Facebook uploads go to the `video_reels`
edge with fallback to the `videos` edge.
