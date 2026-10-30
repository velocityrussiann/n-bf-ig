"""Focused test for Instagram Reel metadata: title from song name,
beautiful description in caption, all hashtags lowercase.

Run:  python test_caption_metadata.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import auto_pipeline as ap
from titles_descriptions_parser import generate_viral_edm_metadata


def _hashtags(caption):
    return re.findall(r'#\S+', caption)


def main():
    # 1. Caption carries title AND description, hashtags all lowercase.
    caption = ap.build_reel_caption(
        "Stay For The Afterglow",
        "A midnight-to-dawn EDM rush built for festival crowds.",
        ["EDM", "ElectronicDanceMusic", "NeonBeatsFactory", "Shorts", "YouTube"],
    )
    assert "Stay For The Afterglow" in caption, "caption must contain the title"
    assert "midnight-to-dawn" in caption, "caption must contain the description"
    for tag in _hashtags(caption):
        assert tag == tag.lower(), f"hashtag not lowercase: {tag}"
    lowered = caption.lower()
    assert "shorts" not in lowered.replace("hashtag", ""), "YouTube-ism 'shorts' leaked"
    assert "youtube" not in lowered, "YouTube-ism leaked into caption"
    assert "subscribe" not in lowered, "YouTube-ism 'subscribe' leaked into caption"

    # 2. Fallback metadata: title starts with the song name.
    meta = generate_viral_edm_metadata("005 - Stay for the Afterglow.mp3")
    assert meta["title"].lower().startswith("stay for the afterglow"), (
        f"title must start with song name, got: {meta['title']}"
    )
    assert "Track Chapters" not in meta["description"], "YouTube chapters in description"
    assert "Subscribe" not in meta["description"], "YouTube subscribe in description"
    for tag in meta["tags"]:
        assert tag == tag.lower(), f"fallback tag not lowercase: {tag}"

    # 3. Caption built from fallback metadata is fully lowercase-tagged.
    caption2 = ap.build_reel_caption(meta["title"], meta["description"], meta["tags"])
    for tag in _hashtags(caption2):
        assert tag == tag.lower(), f"hashtag not lowercase: {tag}"

    print("test_caption_metadata: all checks passed.")


if __name__ == "__main__":
    main()
