"""
Google Drive Fetch & Local Asset Management Module - Neon Beats Factory (NBF)
Fetches audio (MP3/WAV) and image files from Google Drive folders.
Matches files by sorted position (1st audio pairs with 1st image).
Includes local directory fallback for offline and local testing.
Supports Repost/Recycling Mode when all songs have been published once.
"""
import os
import sys
import json
import random
import tempfile
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

GOOGLE_DRIVE_AUDIO_FOLDER_ID = os.getenv("GOOGLE_DRIVE_AUDIO_FOLDER_ID")
GOOGLE_DRIVE_IMAGE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_IMAGE_FOLDER_ID")
GOOGLE_SERVICE_ACCOUNT_KEY = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")

LOCAL_AUDIO_DIR = os.getenv("LOCAL_AUDIO_DIR", "Audio")
LOCAL_IMAGE_DIR = os.getenv("LOCAL_IMAGE_DIR", "Images")
ALLOW_REPOST = os.getenv("ALLOW_REPOST", "true").lower() == "true"
PUBLISHED_LOG = "published_songs.json"


def get_published_songs():
    """Get list of already published song names."""
    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                return [item.get('song_name', '').strip() for item in data if item.get('song_name')]
            except json.JSONDecodeError:
                return []
    return []


def get_drive_service():
    """Initializes Google Drive API client using service account key."""
    if not GOOGLE_SERVICE_ACCOUNT_KEY:
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

        if os.path.exists(GOOGLE_SERVICE_ACCOUNT_KEY):
            creds = service_account.Credentials.from_service_account_file(
                GOOGLE_SERVICE_ACCOUNT_KEY, scopes=SCOPES)
            return build('drive', 'v3', credentials=creds)
        elif GOOGLE_SERVICE_ACCOUNT_KEY.strip().startswith('{'):
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            temp_file.write(GOOGLE_SERVICE_ACCOUNT_KEY)
            temp_file.close()
            creds = service_account.Credentials.from_service_account_file(
                temp_file.name, scopes=SCOPES)
            service = build('drive', 'v3', credentials=creds)
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass
            return service
    except Exception as e:
        print(f"[Drive] Warning: Could not initialize Google Drive: {e}")
        return None
    return None


def list_drive_files(service, folder_id, mime_types):
    if not service or not folder_id:
        return []
    try:
        files = []
        for mime_type in mime_types:
            query = f"'{folder_id}' in parents and trashed=false and mimeType='{mime_type}'"
            results = service.files().list(
                q=query,
                fields="files(id, name, size, mimeType)",
                spaces='drive'
            ).execute()
            files.extend(results.get('files', []))
        files.sort(key=lambda x: x.get('name', ''))
        return files
    except Exception as e:
        print(f"[Drive] API list files error: {e}")
        return []


def download_drive_file(service, file_info, local_path):
    from googleapiclient.http import MediaIoBaseDownload
    try:
        request = service.files().get_media(fileId=file_info['id'])
        with open(local_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
        return True
    except Exception as e:
        print(f"[Drive] Failed to download {file_info['name']}: {e}")
        return False


def get_local_fallback_pair(published):
    """
    Checks local directories if Google Drive is not configured.
    Scans candidate directories and picks the first one containing files.
    """
    audio_dirs = ["input_audio", r"D:\NBF\AUDIO", "Audio"]
    image_dirs = ["input_images", r"D:\NBF\Cover Art", "Images", r"C:\Users\kreg9\Downloads"]

    audio_exts = ('.mp3', '.wav', '.flac', '.m4a')
    image_exts = ('.jpg', '.jpeg', '.png', '.webp')

    found_audio_dir = None
    audio_files = []
    for d in audio_dirs:
        if os.path.exists(d):
            files = sorted([os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(audio_exts)])
            if files:
                found_audio_dir = d
                audio_files = files
                break

    found_image_dir = None
    image_files = []
    for d in image_dirs:
        if os.path.exists(d):
            files = sorted([os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(image_exts)])
            if files:
                found_image_dir = d
                image_files = files
                break

    if not audio_files or not image_files:
        return None

    published_lower = [p.lower().strip() for p in published]

    # Find first unpublished
    for i, a_path in enumerate(audio_files):
        sname = os.path.basename(a_path)
        if sname.lower() in published_lower:
            continue
        # Pair with image (cycle if fewer images)
        img_path = image_files[i % len(image_files)]
        print(f"[Local Fallback] Selected Pair #{i+1}: Audio='{sname}' ({found_audio_dir}), Image='{os.path.basename(img_path)}' ({found_image_dir})")
        return a_path, img_path, i + 1

    # If all published and repost enabled
    if ALLOW_REPOST and audio_files:
        rand_audio = random.choice(audio_files)
        rand_img = random.choice(image_files)
        print(f"[Local Fallback Repost] Selected: Audio='{os.path.basename(rand_audio)}', Image='{os.path.basename(rand_img)}'")
        return rand_audio, rand_img, 1

    return None


def get_next_unpublished_pair(published=None):
    """
    Finds next unpublished audio + image pair.
    Uses Google Drive if configured, otherwise falls back to local media directories.
    """
    if published is None:
        published = get_published_songs()

    service = get_drive_service()

    if service and GOOGLE_DRIVE_AUDIO_FOLDER_ID and GOOGLE_DRIVE_IMAGE_FOLDER_ID:
        audio_files = list_drive_files(service, GOOGLE_DRIVE_AUDIO_FOLDER_ID, ["audio/mpeg", "audio/wav"])
        image_files = list_drive_files(service, GOOGLE_DRIVE_IMAGE_FOLDER_ID, ["image/jpeg", "image/png", "image/webp"])

        if audio_files and image_files:
            published_lower = [p.lower().strip() for p in published]
            pair_count = min(len(audio_files), len(image_files))

            for i in range(pair_count):
                a_info = audio_files[i]
                im_info = image_files[i]
                sname = a_info['name'].strip()

                if sname.lower() in published_lower:
                    continue

                Path(LOCAL_AUDIO_DIR).mkdir(parents=True, exist_ok=True)
                Path(LOCAL_IMAGE_DIR).mkdir(parents=True, exist_ok=True)

                a_path = os.path.join(LOCAL_AUDIO_DIR, sname)
                im_path = os.path.join(LOCAL_IMAGE_DIR, im_info['name'])

                print(f"[Drive] Downloading audio: {sname}...")
                if not download_drive_file(service, a_info, a_path):
                    continue
                print(f"[Drive] Downloading image: {im_info['name']}...")
                if not download_drive_file(service, im_info, im_path):
                    continue

                return a_path, im_path, i + 1

            if ALLOW_REPOST:
                print("[Drive] All songs published once. Selecting random pair for repost...")
                a_info = random.choice(audio_files)
                im_info = random.choice(image_files)
                a_path = os.path.join(LOCAL_AUDIO_DIR, a_info['name'])
                im_path = os.path.join(LOCAL_IMAGE_DIR, im_info['name'])
                download_drive_file(service, a_info, a_path)
                download_drive_file(service, im_info, im_path)
                return a_path, im_path, 1

    # Fallback to local files
    print("[Drive] Google Drive not active or empty. Checking local asset directories...")
    return get_local_fallback_pair(published)


if __name__ == "__main__":
    pair = get_next_unpublished_pair()
    if pair:
        print(f"\nResult: Audio={pair[0]}, Image={pair[1]}, Index={pair[2]}")
    else:
        print("\nNo pairs found.")
