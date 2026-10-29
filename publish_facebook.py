"""
Facebook Page REELS Publisher - Neon Beats Factory (NBF) MOBILE FORMAT
Publishes 60 FPS vertical (1080x1920) EDM reels + covers to the official
Facebook Page: https://www.facebook.com/neonbeatsfactory (ID: 538586562680121)
Using Meta Graph API v21.0 Resumable / Chunked Upload on the `video_reels`
edge, with automatic fallback to the `videos` edge if Reels upload is not
available for the Page.
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def get_fb_credentials():
    page_id = (os.getenv("FB_PAGE_ID") or "").strip()
    page_token = (os.getenv("FB_PAGE_ACCESS_TOKEN") or "").strip()

    if not page_id or not page_token:
        meta_token = (os.getenv("META_LONG_LIVED_ACCESS_TOKEN") or "").strip()
        if meta_token and not page_token:
            print("[Facebook Auth] Resolving page token from META_LONG_LIVED_ACCESS_TOKEN...")
            try:
                url = "https://graph.facebook.com/v21.0/me/accounts"
                params = {"access_token": meta_token, "limit": 100}
                while url:
                    r = requests.get(url, params=params, timeout=20)
                    res = r.json()
                    for p in res.get("data", []):
                        p_name = p.get("name", "")
                        p_id = p.get("id", "")
                        if p_id == "538586562680121" or "neon" in p_name.lower():
                            page_id = p_id
                            page_token = p.get("access_token")
                            break
                    if page_token:
                        break
                    url = res.get("paging", {}).get("next")
                    params = None
            except Exception as e:
                print(f"[Facebook Auth] Warning: Could not resolve page token: {e}")

    return page_id, page_token


def upload_to_facebook_page(
    video_path,
    title,
    description,
    thumb_path=None,
    page_id=None,
    page_token=None,
    default_chunk_size=10 * 1024 * 1024  # 10 MB chunks
):
    """
    Uploads a video to the Neon Beats Factory Facebook Page via Graph API Resumable Upload.
    Handles large 60 FPS video files (>300 MB) with chunking, retries, and thumbnail setting.
    Returns dict with 'id' and 'url' of the published video.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found at: {video_path}")

    file_size = os.path.getsize(video_path)

    if not page_id or not page_token:
        p_id, p_token = get_fb_credentials()
        page_id = page_id or p_id
        page_token = page_token or p_token

    if not page_id or not page_token:
        raise ValueError(
            "Missing Facebook Page credentials! Ensure FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN "
            "(or META_LONG_LIVED_ACCESS_TOKEN) are set."
        )

    def mask(s):
        return f"{s[:4]}...{s[-4:]}" if s and len(s) > 8 else "MISSING"

    print(f"\n[Facebook Publisher] Publishing to Page ID: {page_id}")
    print(f"  - Title: {title}")
    print(f"  - Video File: {video_path} ({file_size / (1024*1024):.1f} MB)")
    print(f"  - Access Token: {mask(page_token)}")

    t0 = time.time()

    # PHASE 1: Start Session (Reels edge first, Videos edge as fallback)
    print("[Facebook Publisher] Initiating resumable REEL upload session...", flush=True)
    start_payload = {
        "upload_phase": "start",
        "access_token": page_token,
        "file_size": file_size
    }
    upload_url = None
    sr = None
    for edge in ("video_reels", "videos"):
        candidate = f"https://graph.facebook.com/v21.0/{page_id}/{edge}"
        try:
            resp = requests.post(candidate, data=start_payload, timeout=45)
        except Exception as ex:
            print(f"  - Edge '{edge}' unreachable: {ex}")
            continue
        if resp.status_code == 200:
            upload_url = candidate
            sr = resp
            if edge == "videos":
                print("  - Note: video_reels edge unavailable, using videos edge fallback.")
            break
        print(f"  - Edge '{edge}' returned {resp.status_code}: {resp.text[:200]}")
    if sr is None or sr.status_code != 200:
        err_msg = sr.text if sr is not None else "no response"
        try:
            err_msg = sr.json().get("error", {}).get("message", err_msg)
        except Exception:
            pass
        raise RuntimeError(f"Facebook Graph API Start Session Error: {err_msg}")

    sdata = sr.json()
    upload_session_id = sdata.get("upload_session_id")
    video_id = sdata.get("video_id")
    start_offset = int(sdata.get("start_offset", 0))
    end_offset = int(sdata.get("end_offset", min(file_size, start_offset + default_chunk_size)))

    print(f"  - Session ID: {upload_session_id}")
    print(f"  - Video ID: {video_id}")

    # PHASE 2: Transfer Chunks
    print(f"[Facebook Publisher] Uploading chunks ({file_size / (1024*1024):.1f} MB total)...", flush=True)
    with open(video_path, "rb") as vf:
        while start_offset < file_size:
            chunk_len = end_offset - start_offset
            if chunk_len <= 0:
                chunk_len = min(default_chunk_size, file_size - start_offset)
            vf.seek(start_offset)
            chunk_bytes = vf.read(chunk_len)
            if not chunk_bytes:
                break

            transfer_payload = {
                "upload_phase": "transfer",
                "access_token": page_token,
                "upload_session_id": upload_session_id,
                "start_offset": str(start_offset)
            }
            transfer_files = {
                "video_file_chunk": (os.path.basename(video_path), chunk_bytes, "application/octet-stream")
            }

            chunk_success = False
            for attempt in range(1, 4):
                try:
                    tr = requests.post(upload_url, data=transfer_payload, files=transfer_files, timeout=120)
                    if tr.status_code == 200:
                        tdata = tr.json()
                        new_start = int(tdata.get("start_offset", start_offset + len(chunk_bytes)))
                        new_end = int(tdata.get("end_offset", min(file_size, new_start + default_chunk_size)))
                        start_offset = new_start
                        end_offset = new_end
                        pct = min(100, int((start_offset / file_size) * 100))
                        print(f"  Facebook upload progress: {pct}% ({start_offset / (1024*1024):.1f}/{file_size / (1024*1024):.1f} MB)", flush=True)
                        chunk_success = True
                        break
                    else:
                        print(f"  Warning: Chunk upload attempt {attempt} returned {tr.status_code}: {tr.text[:200]}")
                        time.sleep(3 * attempt)
                except Exception as ex:
                    print(f"  Warning: Chunk upload attempt {attempt} failed: {ex}")
                    time.sleep(3 * attempt)

            if not chunk_success:
                raise RuntimeError(f"Failed to transfer chunk at offset {start_offset} after 3 attempts.")

    # PHASE 3: Finish Session & Set Metadata
    print("[Facebook Publisher] Finalizing video upload & attaching metadata...", flush=True)
    finish_payload = {
        "upload_phase": "finish",
        "access_token": page_token,
        "upload_session_id": upload_session_id,
        "title": title[:255],
        "description": description
    }
    finish_files = {}
    thumb_fp = None
    if thumb_path and os.path.exists(thumb_path):
        print(f"  - Attaching Thumbnail: {thumb_path}")
        thumb_fp = open(thumb_path, "rb")
        finish_files["thumb"] = (os.path.basename(thumb_path), thumb_fp, "image/jpeg")

    try:
        fr = requests.post(upload_url, data=finish_payload, files=finish_files, timeout=90)
        if fr.status_code != 200:
            err_msg = fr.text
            try:
                err_msg = fr.json().get("error", {}).get("message", err_msg)
            except Exception:
                pass
            raise RuntimeError(f"Facebook Graph API Finish Session Error ({fr.status_code}): {err_msg}")

        fdata = fr.json()
        final_video_id = fdata.get("id") or video_id
    finally:
        if thumb_fp:
            thumb_fp.close()

    # Explicitly set preferred thumbnail if provided
    if thumb_path and os.path.exists(thumb_path) and final_video_id:
        try:
            with open(thumb_path, "rb") as tf:
                t_resp = requests.post(
                    f"https://graph.facebook.com/v21.0/{final_video_id}/thumbnails",
                    data={"access_token": page_token, "is_preferred": "true"},
                    files={"source": (os.path.basename(thumb_path), tf, "image/jpeg")},
                    timeout=30
                )
                if t_resp.status_code == 200:
                    print(f"  - Thumbnail set as preferred successfully on video {final_video_id}.")
        except Exception as te:
            print(f"  - Note: Preferred thumbnail endpoint notice: {te}")

    elapsed = time.time() - t0
    fb_url = f"https://www.facebook.com/{page_id}/videos/{final_video_id}"
    print(f"[Facebook Publisher] SUCCESS! Video published to Facebook Page in {elapsed:.1f}s.")
    print(f"  - Video ID: {final_video_id}")
    print(f"  - Facebook Video URL: {fb_url}")

    return {
        "id": final_video_id,
        "url": fb_url,
        "page_id": page_id
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python publish_facebook.py <video_path> <title> [description] [thumb_path]")
        sys.exit(1)

    v_path = sys.argv[1]
    v_title = sys.argv[2]
    v_desc = sys.argv[3] if len(sys.argv) > 3 else "Neon Beats Factory (NBF) - Best Electronic Dance Music & EDM Hits"
    t_path = sys.argv[4] if len(sys.argv) > 4 else None

    result = upload_to_facebook_page(v_path, v_title, v_desc, thumb_path=t_path)
    print(f"\nPublished successfully:\n{result}")
