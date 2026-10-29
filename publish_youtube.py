"""
YouTube Publisher with Auto-Playlist Integration - Neon Beats Factory (NBF) MOBILE
Publishes vertical 1080x1920 videos (Shorts shelf eligible when <=60s).
Features:
1. Resumable video upload with progress monitoring
2. Automatic High-Impact thumbnail attachment
3. Auto-creation of official EDM Shorts playlist if not existing
4. Automatic addition of every published release into the playlist
"""
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

DEFAULT_PLAYLIST_TITLE = os.getenv(
    "YT_PLAYLIST_TITLE",
    "Neon Beats Factory | EDM Shorts & Reels"
)
DEFAULT_PLAYLIST_DESC = os.getenv(
    "YT_PLAYLIST_DESC",
    "Official vertical shorts & reels by Neon Beats Factory (NBF). High-energy electronic dance music, electro house, slap house and festival anthems in mobile format."
)


def get_authenticated_service():
    """Authenticate using OAuth 2.0 refresh token."""
    client_id = (os.getenv('YT_CLIENT_ID') or os.getenv('YOUTUBE_CLIENT_ID', '')).strip()
    client_secret = (os.getenv('YT_CLIENT_SECRET') or os.getenv('YOUTUBE_CLIENT_SECRET', '')).strip()
    refresh_token = (os.getenv('YT_REFRESH_TOKEN') or os.getenv('YOUTUBE_REFRESH_TOKEN', '')).strip()

    def mask(s):
        return f"{s[:4]}...{s[-4:]}" if s and len(s) > 8 else "MISSING"

    print(f"[YouTube Auth] Client ID: {mask(client_id)}")
    print(f"[YouTube Auth] Client Secret: {mask(client_secret)}")
    print(f"[YouTube Auth] Refresh Token: {mask(refresh_token)}")

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError(
            "Missing YouTube credentials! Ensure the following environment variables are set:\n"
            "  - YT_CLIENT_ID\n"
            "  - YT_CLIENT_SECRET\n"
            "  - YT_REFRESH_TOKEN"
        )

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube"]
    )

    try:
        creds.refresh(Request())
    except Exception as e:
        if "invalid_grant" in str(e).lower():
            print("\n❌ [YouTube Auth] ERROR: Refresh token has EXPIRED or been REVOKED.")
            print("💡 Please generate a new refresh token from Google Cloud Console.")
        raise

    return build('youtube', 'v3', credentials=creds)


def get_or_create_playlist(youtube, title=DEFAULT_PLAYLIST_TITLE, description=DEFAULT_PLAYLIST_DESC):
    """
    Finds existing playlist with matching title, or creates a new one.
    Returns playlist_id.
    """
    # Check if playlist ID is explicitly configured in .env
    env_playlist_id = os.getenv("YT_PLAYLIST_ID", "").strip()
    if env_playlist_id:
        print(f"[YouTube Playlist] Using configured playlist ID: {env_playlist_id}")
        return env_playlist_id

    try:
        print(f"[YouTube Playlist] Searching for playlist: '{title}'...")
        request = youtube.playlists().list(
            part="snippet,status",
            mine=True,
            maxResults=50
        )
        response = request.execute()

        for item in response.get("items", []):
            if item.get("snippet", {}).get("title", "").strip().lower() == title.strip().lower():
                p_id = item["id"]
                print(f"[YouTube Playlist] Found existing playlist ID: {p_id}")
                return p_id

        # Not found, create new playlist
        print(f"[YouTube Playlist] Creating new playlist: '{title}'...")
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "defaultLanguage": "en"
            },
            "status": {
                "privacyStatus": "public"
            }
        }
        create_req = youtube.playlists().insert(
            part="snippet,status",
            body=body
        )
        create_res = create_req.execute()
        new_id = create_res["id"]
        print(f"[YouTube Playlist] Created playlist successfully! ID: {new_id}")
        print(f"[YouTube Playlist] Playlist URL: https://www.youtube.com/playlist?list={new_id}")
        return new_id

    except Exception as e:
        print(f"[YouTube Playlist] Warning: Failed to query or create playlist: {e}")
        return None


def add_video_to_playlist(youtube, playlist_id, video_id, max_retries=3):
    """Adds an uploaded video into the specified playlist with retries."""
    if not playlist_id or not video_id:
        return None

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[YouTube Playlist] Adding video {video_id} to playlist {playlist_id} (attempt {attempt}/{max_retries})...")
            body = {
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
            req = youtube.playlistItems().insert(
                part="snippet",
                body=body
            )
            res = req.execute()
            print(f"[YouTube Playlist] Video added to playlist! Item ID: {res.get('id')}")
            return res
        except Exception as e:
            print(f"[YouTube Playlist] Warning: Failed to add video to playlist on attempt {attempt}: {e}")
            if attempt < max_retries:
                time.sleep(3 * attempt)

    return None


def upload_to_youtube(video_path, title, description, tags=None, category_id='10', thumbnail_path=None):
    """
    Uploads a video to YouTube, attaches thumbnail, and adds to official EDM playlist.
    Category 10 = Music.
    """
    if tags is None:
        tags = ['edm', 'electronic dance music', 'neon beats factory', 'nbf', 'club hits', 'festival']

    youtube = get_authenticated_service()

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': category_id
        },
        'status': {
            'privacyStatus': os.getenv('YT_PRIVACY_STATUS', 'public'),
            'selfDeclaredMadeForKids': False,
        }
    }

    media = MediaFileUpload(
        str(video_path),
        chunksize=1024 * 1024 * 10,  # 10MB chunks
        resumable=True,
        mimetype='video/mp4'
    )

    print(f"\n[YouTube Upload] Starting upload: {title}")
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Upload progress: {int(status.progress() * 100)}%")

    video_id = response['id']
    video_url = f"https://youtube.com/watch?v={video_id}"
    print(f"[YouTube Upload] Upload completed! Video ID: {video_id}")
    print(f"[YouTube Upload] URL: {video_url}")

    # Set custom thumbnail if provided or if matching _thumb.jpg exists
    if thumbnail_path is None:
        cand_thumb = str(video_path).replace('.mp4', '_thumb.jpg')
        if os.path.exists(cand_thumb):
            thumbnail_path = cand_thumb

    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            print(f"[YouTube Upload] Setting custom thumbnail: {thumbnail_path}")
            thumb_media = MediaFileUpload(thumbnail_path, mimetype='image/jpeg')
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=thumb_media
            ).execute()
            print("[YouTube Upload] Thumbnail set successfully!")
        except Exception as e:
            print(f"[YouTube Upload] Warning: Failed to set thumbnail: {e}")

    # Add to Official EDM Playlist
    playlist_id = get_or_create_playlist(youtube)
    if playlist_id:
        add_video_to_playlist(youtube, playlist_id, video_id)

    return {
        "id": video_id,
        "url": video_url,
        "playlist_id": playlist_id
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python publish_youtube.py <video_path> [title] [description]")
        sys.exit(1)

    video_file = sys.argv[1]
    if not os.path.exists(video_file):
        print(f"Video file not found: {video_file}")
        sys.exit(1)

    v_title = sys.argv[2] if len(sys.argv) > 2 else "Neon Beats Factory Release"
    v_desc = sys.argv[3] if len(sys.argv) > 3 else "New electronic dance music release from Neon Beats Factory (NBF)."
    upload_to_youtube(video_file, v_title, v_desc)
