"""
Main Automation Pipeline - NBF Mobile (Instagram Reels only)
1. Fetch NEXT unpublished audio + image pair from Google Drive (or local fallback)
2. Match audio filename to EDM title & description (with viral SEO fallbacks)
3. Render 60 FPS VERTICAL (1080x1920) 45s mid-song clip + matching cover
4. Publish to Instagram as a Reel (@neonbeatsfactory)
5. Record release in published_songs.json
"""
import os
import sys
import json
import shutil
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

PUBLISHED_LOG = "published_songs.json"
TITLES_FILE = "titles_descriptions.txt"


def get_published_songs():
    """Retrieve list of songs that have already been published."""
    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                return [item.get('song_name', '') for item in data]
            except json.JSONDecodeError:
                return []
    return []


def get_recent_visualizer_colors(limit=10):
    """Retrieve the visualizer BGR colors used in the last N published releases."""
    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                recent = []
                for item in data[-limit:]:
                    meta = item.get('metadata', {})
                    c_info = meta.get('visualizer_color')
                    if isinstance(c_info, dict) and 'bgr' in c_info and c_info['bgr']:
                        recent.append(tuple(c_info['bgr']))
                    elif isinstance(c_info, (list, tuple)):
                        recent.append(tuple(c_info))
                return recent
            except Exception:
                return []
    return []


def mark_as_published(song_name, metadata):
    """Appends published song info to published_songs.json."""
    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG, 'r', encoding='utf-8') as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                history = []
    else:
        history = []

    history.append({
        "song_name": song_name,
        "metadata": metadata
    })

    with open(PUBLISHED_LOG, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4)
    print(f"[Pipeline] Successfully logged '{song_name}' to {PUBLISHED_LOG}")


def build_reel_caption(title, description, tags):
    """Reel caption: title + description + lowercase hashtags (Instagram only)."""
    banned = ('shorts', 'youtube', 'subscribe', 'youtuber')
    base_tags = [t for t in (tags or []) if t.lower() not in banned]
    extra = ['reels', 'edm', 'electronicdancemusic', 'neonbeatsfactory', 'nbf']
    seen, hashtags = set(), []
    for t in base_tags + extra:
        tag = '#' + ''.join(c for c in t.lower() if c.isalnum())
        if tag not in seen and len(tag) > 1:
            seen.add(tag)
            hashtags.append(tag)
    caption = f"{title}"
    if description:
        caption += f"\n\n{description.strip()}"
    return caption + f"\n.\n.\n{' '.join(hashtags[:15])}"


def run_pipeline():
    print("\n" + "=" * 65)
    print("      NBF MOBILE - AUTOMATION PIPELINE (INSTAGRAM REELS)")
    print("=" * 65 + "\n")

    # Step 1: Fetch unpublished audio + image
    print("STEP 1: Fetching audio + image (Google Drive / Local)...")
    from google_drive_fetch import get_next_unpublished_pair

    published = get_published_songs()
    recent_colors = get_recent_visualizer_colors(limit=10)
    print(f"[Pipeline] Found {len(recent_colors)} recent visualizer color history entries for 10-day anti-repetition.")

    pair = get_next_unpublished_pair(published)

    if not pair:
        print("\n[Pipeline] No unpublished songs available. Pipeline complete.")
        return

    audio_path, image_path, song_index = pair
    song_filename = os.path.basename(audio_path)
    print(f"\nStep 1 Complete: Audio='{song_filename}', Image='{os.path.basename(image_path)}'")

    # Step 2: EDM SEO Metadata & Titles (Pollinations AI + Fallback)
    print("\nSTEP 2: Generating EDM title, description, and tags...")
    from titles_descriptions_parser import get_song_metadata_by_name

    metadata = get_song_metadata_by_name(song_filename, TITLES_FILE, use_pollinations=True)
    title = metadata['title']
    description = metadata['description']
    song_name = metadata.get('song_name', song_filename)
    tags = metadata.get('tags', ['edm', 'electronic dance music', 'nbf', 'neon beats factory'])

    print(f"  Title: {title}")
    print(f"  Song Display Name: {song_name}")

    # Step 3: Render 60 FPS vertical 45s mid-song clip + cover
    print("\nSTEP 3: Rendering 60 FPS vertical EDM reel...")
    from process_videos import process_single_song

    video_path, thumb_path, color_info = process_single_song(
        image_path=image_path,
        audio_path=audio_path,
        song_filename=song_filename,
        display_name=song_name,
        recent_colors=recent_colors
    )

    if not video_path or not os.path.exists(video_path):
        print("\n[Pipeline] ERROR: Video creation failed!")
        sys.exit(1)

    print(f"\nStep 3 Complete: Video created at {video_path}")
    print(f"  Visualizer Color Chosen: {color_info.get('label')} (BGR: {color_info.get('bgr')})")
    if os.path.exists(thumb_path):
        print(f"  Cover created at {thumb_path}")

    # Step 4: Publish to Instagram as Reel
    print("\nSTEP 4: Publishing to Instagram (@neonbeatsfactory)...")
    from publish_instagram import upload_reel_to_instagram

    caption = build_reel_caption(title, description, tags)

    ig_result = None
    ig_success = False
    try:
        ig_result = upload_reel_to_instagram(
            video_path=video_path,
            caption=caption
        )
        ig_success = True
    except Exception as e:
        print(f"\n[Pipeline] Instagram upload failed: {e}")
        ig_success = False

    # Step 5: Record release in published_songs.json
    print("\nSTEP 5: Logging release to published_songs.json...")
    mark_as_published(song_filename, {
        "title": title,
        "description": description,
        "song_index": song_index,
        "format": "mobile_1080x1920",
        "destination": "instagram_reels",
        "visualizer_color": color_info,
        "instagram_uploaded": ig_success,
        "instagram_result": ig_result
    })

    # Archive video
    published_dir = "Published_Videos"
    Path(published_dir).mkdir(parents=True, exist_ok=True)
    try:
        dest_video = os.path.join(published_dir, os.path.basename(video_path))
        shutil.move(video_path, dest_video)
        print(f"[Pipeline] Archived video to: {dest_video}")
    except Exception as e:
        print(f"[Pipeline] Could not archive video: {e}")

    print("\n" + "=" * 65)
    print("      NBF MOBILE - PIPELINE FINISHED")
    print("=" * 65)

    if not ig_success:
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline()
