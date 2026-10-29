"""
Instagram Reels Publisher - NBF Mobile
Posts vertical 1080x1920 reels to the linked Instagram business account
via the Instagram Content Publishing API:
  1. Upload MP4 to a direct-link file host (public video_url is required)
  2. Create REEL media container
  3. Poll container until FINISHED
  4. Publish container, return media id + permalink
"""
import os
import sys
import time
import json
import urllib.request
import urllib.parse

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

GRAPH = "https://graph.facebook.com/v21.0"
IG_USER_ID = (os.getenv("IG_USER_ID") or "").strip()


def _get_page_token(page_id, meta_token, explicit_token):
    if explicit_token:
        return explicit_token
    if not (page_id and meta_token):
        return ""
    url = f"{GRAPH}/{page_id}?fields=access_token&access_token={urllib.parse.quote(meta_token)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r).get("access_token", "")


def get_credentials(page_id=None, meta_token=None, page_token=None, ig_user_id=None):
    page_id = (page_id or os.getenv("FB_PAGE_ID") or "").strip()
    meta_token = (meta_token or os.getenv("META_LONG_LIVED_ACCESS_TOKEN") or "").strip()
    page_token = (page_token or os.getenv("FB_PAGE_ACCESS_TOKEN") or "").strip()
    ig_user_id = (ig_user_id or os.getenv("IG_USER_ID") or IG_USER_ID).strip()
    token = _get_page_token(page_id, meta_token, page_token)
    if not token or not ig_user_id:
        raise ValueError("Missing Instagram credentials: need IG_USER_ID plus FB_PAGE_ACCESS_TOKEN (or FB_PAGE_ID + META_LONG_LIVED_ACCESS_TOKEN).")
    return ig_user_id, token


def upload_to_file_host(video_path, timeout=300):
    """Uploads MP4 to the project's Cloudflare R2 bucket and returns a
    time-limited direct download URL (6h).

    Instagram fetches the video within seconds of container creation,
    so a presigned URL is all it needs - no public bucket required.
    """
    import boto3
    bucket = (os.getenv("R2_BUCKET_NAME") or "").strip()
    endpoint = (os.getenv("R2_S3_ENDPOINT") or "").strip()
    key_id = (os.getenv("R2_ACCESS_KEY_ID") or "").strip()
    secret = (os.getenv("R2_SECRET_ACCESS_KEY") or "").strip()
    if not all([bucket, endpoint, key_id, secret]):
        raise ValueError("Missing R2 credentials (R2_BUCKET_NAME, R2_S3_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY).")
    s3 = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=key_id,
                       aws_secret_access_key=secret, region_name="auto")
    key = f"nbf-reels/{os.path.basename(video_path)}"
    s3.upload_file(video_path, bucket, key, ExtraArgs={"ContentType": "video/mp4"})
    return s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key},
                                     ExpiresIn=6 * 3600)


def _api(method, path, token, params=None, data=None):
    params = dict(params or {})
    params["access_token"] = token
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(params)}"
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except Exception as e:
        detail = ""
        try:
            detail = e.read().decode()[:300]
        except Exception:
            detail = str(e)[:300]
        raise RuntimeError(f"Instagram API {method} {path} failed: {detail}")


def create_reel_container(ig_user_id, token, video_url, caption):
    res = _api("POST", f"{ig_user_id}/media", token, data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        # False = reel lives only in the Reels tab, never on the profile grid.
        "share_to_feed": "false",
    })
    cid = res.get("id")
    if not cid:
        raise RuntimeError(f"No container id returned: {res}")
    return cid


def wait_for_container(container_id, token, timeout=600, interval=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        res = _api("GET", container_id, token, params={"fields": "status_code,status"})
        code = res.get("status_code")
        print(f"  - Reel container {container_id}: {code}", flush=True)
        if code == "FINISHED":
            return True
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Reel container failed: {res}")
        time.sleep(interval)
    raise RuntimeError("Timed out waiting for reel container processing.")


def publish_container(ig_user_id, token, container_id):
    res = _api("POST", f"{ig_user_id}/media_publish", token,
               data={"creation_id": container_id})
    media_id = res.get("id")
    if not media_id:
        raise RuntimeError(f"Publish returned no media id: {res}")
    info = _api("GET", media_id, token, params={"fields": "permalink,timestamp"})
    return {"id": media_id, "url": info.get("permalink", ""), "timestamp": info.get("timestamp", "")}


def upload_reel_to_instagram(video_path, caption, ig_user_id=None, page_id=None,
                             meta_token=None, page_token=None, publish=True):
    """Full chain: host file -> container -> (publish). publish=False leaves a draft."""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"\n[Instagram] Reel: {os.path.basename(video_path)} ({size_mb:.1f} MB)")

    uid, token = get_credentials(page_id, meta_token, page_token, ig_user_id)

    print("[Instagram] Uploading video to file host...", flush=True)
    video_url = upload_to_file_host(video_path)
    print(f"  - Public video URL ready ({len(video_url)} chars)")

    print("[Instagram] Creating REEL container...", flush=True)
    container_id = create_reel_container(uid, token, video_url, caption)
    print(f"  - Container ID: {container_id}")

    wait_for_container(container_id, token)

    if not publish:
        print("[Instagram] Draft container ready (not published).")
        return {"id": container_id, "url": "", "draft": True}

    print("[Instagram] Publishing reel...", flush=True)
    result = publish_container(uid, token, container_id)
    print(f"[Instagram] SUCCESS! Reel live: {result['url']}")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python publish_instagram.py <video_path> <caption> [--draft]")
        sys.exit(1)
    res = upload_reel_to_instagram(sys.argv[1], sys.argv[2], publish="--draft" not in sys.argv)
    print(res)
