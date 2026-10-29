"""
Neon Beats Factory (NBF) MOBILE FORMAT - High-Performance 60 FPS Audio-Reactive
Vertical Visualizer Engine for Facebook Reels / YouTube Shorts (1080x1920).
Generates viral vertical Electronic Dance Music (EDM) videos and matching covers:
1. Intelligent Background Darkening Mask & Cinematic Vignette (prevents neon washout)
2. Iconic NBF (NEON BEATS FACTORY) Branding at the Bottom-Center
3. 3D Topographic Mesh Core Visualizer with Sub-Bass BeatPulse (Upper Area)
4. Optional Song Title in the Bottom Caption Zone
5. Multi-Stage Neon Cyan Glow & Dynamic Bloom
6. Sample-accurate 0.0ms Audio Sync
7. High-Impact Matching Vertical Cover Generation
"""

import os
import sys
import re
import time
import zipfile
import subprocess
import tempfile
import numpy as np
import cv2
import soundfile as sf
import scipy.signal
from PIL import Image, ImageSequence, ImageDraw, ImageFont, ImageFilter
from dotenv import load_dotenv

load_dotenv()

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Expanded EDM Neon Aesthetic Palettes (BGR)
NEON_PALETTE = {
    "cyan": (250, 240, 60),          # Electric Cyan / Aqua (#3CF0FA)
    "amber_gold": (10, 180, 255),    # Radiant Lantern Amber / Gold (#FFB40A)
    "magenta": (255, 60, 220),       # Cyber Neon Magenta (#DC3CFF)
    "electric_blue": (255, 120, 10), # Deep Cobalt / Azure Blue (#0A78FF)
    "toxic_lime": (30, 255, 60),     # High-Voltage Lime Green (#3CFF1E)
    "fire_orange": (10, 60, 255),    # Molten Lava Fire (#FF3C0A)
    "neon_purple": (255, 30, 160),   # Electric Ultraviolet (#A01EFF)
    "cyber_yellow": (30, 235, 255),  # Neon Laser Lemon (#FFE71E)
    "hot_pink": (180, 20, 255),      # Synthwave Hot Pink (#FF14B4)
    "frosted_sky": (255, 225, 140),  # Frosted Sky Cyan (#8CE1FF)
    "emerald_mint": (140, 255, 30),  # Neo Mint Green (#1EFF8C)
    "crimson_flare": (60, 20, 255),  # Crimson Neon Flare (#FF143C)
    "white": (255, 255, 255),        # Pure Diamond White
}


def load_viz_core(viz_path, color_bgr=(250, 240, 60)):
    """
    Extracts mesh_core.gif from Visualizer_Core_Only.viz and pre-tints frames with neon glow.
    """
    print(f"[NBF Visualizer] Extracting core from: {viz_path}", flush=True)
    with zipfile.ZipFile(viz_path, 'r') as z:
        names = z.namelist()
        if "mesh_core.gif" in names:
            gif_bytes = z.read("mesh_core.gif")
        elif "1089483" in names:
            gif_bytes = z.read("1089483")
        else:
            largest = max(z.infolist(), key=lambda x: x.file_size)
            gif_bytes = z.read(largest.filename)

    import io
    gif_file = io.BytesIO(gif_bytes)
    im = Image.open(gif_file)

    pil_frames = [f.copy().convert("RGBA") for f in ImageSequence.Iterator(im)]
    num_frames = len(pil_frames)
    print(f"[NBF Visualizer] Loaded {num_frames} animation frames from .viz core.", flush=True)

    tinted_frames = []
    cb, cg, cr = color_bgr

    for frame in pil_frames:
        arr = np.array(frame)
        alpha = arr[:, :, 3]
        gray = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGBA2GRAY).astype(np.float32) / 255.0

        tinted = np.zeros((arr.shape[0], arr.shape[1], 3), dtype=np.float32)
        tinted[:, :, 0] = gray * cb
        tinted[:, :, 1] = gray * cg
        tinted[:, :, 2] = gray * cr

        alpha_mask = (alpha.astype(np.float32) / 255.0)[:, :, np.newaxis]
        tinted_alpha = tinted * alpha_mask

        # Multi-stage neon bloom
        b1 = cv2.GaussianBlur(tinted_alpha, (11, 11), 0)
        b2 = cv2.GaussianBlur(tinted_alpha, (29, 29), 0)
        glowing = np.clip(tinted_alpha * 1.25 + b1 * 0.75 + b2 * 0.40, 0, 255).astype(np.uint8)

        tinted_frames.append(glowing)

    return tinted_frames


def apply_darkening_mask(bg_bgr, darken_factor=0.50, vignette_intensity=0.25):
    """
    Applies cinematic darkening mask & vignette to prevent bright backgrounds
    from drowning out the neon visualizer and white branding.
    """
    H, W = bg_bgr.shape[:2]

    # 1. Base Darkening Multiplier (0.50 = 50% luminance of original)
    darkened = (bg_bgr.astype(np.float32) * darken_factor).astype(np.uint8)

    # 2. Smooth Radial Vignette Mask
    Y, X = np.ogrid[:H, :W]
    cx_v, cy_v = W / 2.0, H / 2.0
    dist_from_center = np.sqrt((X - cx_v) ** 2 + (Y - cy_v) ** 2)
    max_dist = np.sqrt(cx_v ** 2 + cy_v ** 2)
    vignette = 1.0 - vignette_intensity * (dist_from_center / max_dist) ** 1.5
    vignette = np.clip(vignette, 0.4, 1.0)

    darkened = (darkened.astype(np.float32) * vignette[:, :, np.newaxis]).astype(np.uint8)
    return darkened


def overlay_nbf_branding(cv2_img, logo_path=None, target_logo_width=740, **kwargs):
    """
    Overlays the official NBF (NEON BEATS FACTORY) branding on the
    bottom-center of the vertical (9:16) canvas - matching the NBF reels
    reference (visualizer up top, big logo below it).
    On wide landscape canvases it falls back to the classic left-side placement.
    """
    H, W = cv2_img.shape[:2]
    is_vertical = H > W

    if logo_path is None:
        possible_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "nbf_logo.png"),
            os.path.join("assets", "nbf_logo.png"),
            os.path.join("..", "assets", "nbf_logo.png"),
        ]
        logo_path = next((p for p in possible_paths if os.path.exists(p)), None)

    if not logo_path or not os.path.exists(logo_path):
        print(f"[NBF Branding] Warning: Logo not found at {logo_path}, skipping logo overlay.", flush=True)
        return cv2_img

    logo = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
    if logo is None:
        return cv2_img

    # Proportional logo scale (target width ~620px on 1080-wide vertical canvas)
    scale = (target_logo_width * (W / 1080.0)) / logo.shape[1]
    scaled_w = int(logo.shape[1] * scale)
    scaled_h = int(logo.shape[0] * scale)
    logo_resized = cv2.resize(logo, (scaled_w, scaled_h), interpolation=cv2.INTER_LANCZOS4)

    if is_vertical:
        # Bottom-center placement on mobile canvas (visualizer sits above it)
        lx = int(W * 0.50 - scaled_w / 2)
        ly = int(H * 0.71 - scaled_h / 2)
    else:
        # Classic left-side placement on landscape canvas
        lx = int(W * 0.22 - scaled_w / 2)
        ly = int(H * 0.485 - scaled_h / 2)

    lx = max(0, min(W - scaled_w, lx))
    ly = max(0, min(H - scaled_h, ly))

    # Convert to PIL for smooth text + shadow rendering
    rgb = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    pil_canvas = Image.fromarray(rgb)
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))

    # Convert logo to PIL Image
    logo_rgba = cv2.cvtColor(logo_resized, cv2.COLOR_BGRA2RGBA)
    pil_logo = Image.fromarray(logo_rgba)

    # Add soft drop shadow behind logo
    shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    shadow.paste(pil_logo, (lx, ly + 4), pil_logo)
    # Tint shadow black with alpha
    s_arr = np.array(shadow)
    s_arr[:, :, :3] = 0
    s_arr[:, :, 3] = (s_arr[:, :, 3].astype(np.float32) * 0.70).astype(np.uint8)
    shadow = Image.fromarray(s_arr).filter(ImageFilter.GaussianBlur(8))

    overlay = Image.alpha_composite(overlay, shadow)
    overlay.paste(pil_logo, (lx, ly), pil_logo)

    pil_canvas = Image.alpha_composite(pil_canvas.convert('RGBA'), overlay)
    return cv2.cvtColor(np.array(pil_canvas), cv2.COLOR_RGBA2BGR)


def overlay_song_title(cv2_img, text, font_path=None, base_font_size=84, y_ratio=0.86, **kwargs):
    """
    Draws the song title centered near the bottom of the vertical (9:16)
    canvas - the standard reels/shorts caption zone. Text auto-shrinks and
    wraps to max 2 lines; white with black stroke + soft shadow so it stays
    readable over any background. No-op on landscape canvas or empty text.
    """
    H, W = cv2_img.shape[:2]
    if H <= W or not text or not str(text).strip():
        return cv2_img
    text = str(text).strip()

    if font_path is None:
        possible_fonts = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Montserrat-Bold.ttf"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Poppins-Medium.ttf"),
            os.path.join("fonts", "Montserrat-Bold.ttf"),
        ]
        font_path = next((p for p in possible_fonts if os.path.exists(p)), None)
    if not font_path:
        return cv2_img

    max_width = int(W * 0.86)
    font_size = int(base_font_size * (W / 1080.0))
    lines = [text]
    # Shrink / wrap until it fits in max 2 lines
    while font_size > 28:
        font = ImageFont.truetype(font_path, font_size)
        words, cur, wrapped = text.split(), "", []
        for wd in words:
            trial = (cur + " " + wd).strip()
            if font.getlength(trial) <= max_width:
                cur = trial
            else:
                if cur:
                    wrapped.append(cur)
                cur = wd
        if cur:
            wrapped.append(cur)
        if len(wrapped) <= 2 and all(font.getlength(ln) <= max_width for ln in wrapped):
            lines = wrapped
            break
        font_size -= 6
    font = ImageFont.truetype(font_path, font_size)

    ascent, descent = font.getmetrics()
    line_h = ascent + descent + 10
    block_h = line_h * len(lines)
    cy = int(H * y_ratio)
    top = cy - block_h // 2

    rgb = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    pil_canvas = Image.fromarray(rgb).convert('RGBA')
    draw = ImageDraw.Draw(pil_canvas)
    y = top
    for ln in lines:
        lw = font.getlength(ln)
        x = (W - lw) / 2
        # Soft drop shadow
        draw.text((x + 3, y + 3), ln, font=font, fill=(0, 0, 0, 200))
        # White text with black stroke for readability
        draw.text((x, y), ln, font=font, fill=(255, 255, 255, 255),
                  stroke_width=max(2, font_size // 28), stroke_fill=(0, 0, 0, 255))
        y += line_h

    return cv2.cvtColor(np.array(pil_canvas), cv2.COLOR_RGBA2BGR)


def compute_audio_rhythm(mono_audio, sr, fps=60):
    """
    Analyzes kick transients (sub-bass 25-130 Hz) for authentic Avee BeatPulse,
    along with overall spectral energy for smooth visualizer dynamics.
    """
    total_frames = int(len(mono_audio) / sr * fps)
    hop_length = int(sr / fps)
    n_fft = 2048

    frequencies, times, Zxx = scipy.signal.stft(
        mono_audio, fs=sr, nperseg=n_fft, noverlap=n_fft - hop_length
    )
    magnitude = np.abs(Zxx)

    # Sub-bass for drum kicks (25 Hz to 130 Hz)
    bass_idx = np.where((frequencies >= 25) & (frequencies <= 130))[0]
    bass_energy = np.mean(magnitude[bass_idx, :], axis=0) if len(bass_idx) > 0 else np.zeros(magnitude.shape[1])

    # Overall spectral energy (energy envelope)
    total_energy = np.mean(magnitude, axis=0)

    # Truncate / pad
    if len(bass_energy) < total_frames:
        bass_energy = np.pad(bass_energy, (0, total_frames - len(bass_energy)))
        total_energy = np.pad(total_energy, (0, total_frames - len(total_energy)))
    else:
        bass_energy = bass_energy[:total_frames]
        total_energy = total_energy[:total_frames]

    # Beat smoothing with fast attack & natural exponential decay (~120ms kick feel)
    smoothed_bass = np.zeros(total_frames, dtype=np.float32)
    smoothed_energy = np.zeros(total_frames, dtype=np.float32)

    attack_rate = 0.82
    decay_rate = 0.085

    for i in range(total_frames):
        b_curr = bass_energy[i]
        e_curr = total_energy[i]
        if i == 0:
            smoothed_bass[i] = b_curr
            smoothed_energy[i] = e_curr
        else:
            if b_curr > smoothed_bass[i - 1]:
                smoothed_bass[i] = smoothed_bass[i - 1] + (b_curr - smoothed_bass[i - 1]) * attack_rate
            else:
                smoothed_bass[i] = smoothed_bass[i - 1] - (smoothed_bass[i - 1] - b_curr) * decay_rate

            if e_curr > smoothed_energy[i - 1]:
                smoothed_energy[i] = smoothed_energy[i - 1] + (e_curr - smoothed_energy[i - 1]) * attack_rate
            else:
                smoothed_energy[i] = smoothed_energy[i - 1] - (smoothed_energy[i - 1] - e_curr) * 0.05

    # Normalize to [0.0, 1.0] with soft sigmoid curve
    b_max = np.percentile(smoothed_bass, 97) if len(smoothed_bass) > 0 else 1.0
    if b_max > 0:
        norm_bass = np.clip(smoothed_bass / b_max, 0.0, 1.5)
    else:
        norm_bass = np.zeros_like(smoothed_bass)

    e_max = np.percentile(smoothed_energy, 95) if len(smoothed_energy) > 0 else 1.0
    if e_max > 0:
        norm_energy = np.clip(smoothed_energy / e_max, 0.0, 1.5)
    else:
        norm_energy = np.zeros_like(smoothed_energy)

    return norm_bass, norm_energy


def extract_artwork_color(img_bgr, mode="auto"):
    """
    Intelligently extracts visualizer neon glow color from the background artwork:
    - 'auto': Identifies the dominant vibrant hue, weighted by saturation, and boosts
              it into an intense EDM neon glow matching the artwork's atmosphere.
    - 'complementary': Rotates the dominant hue by 180 degrees on the color wheel
              to guarantee maximum contrast and pop against any background.
    - If the artwork has low saturation / no dominant hue, falls back to a cool neon
      palette color so the visualizer always looks vibrant and striking.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # Filter for vibrant, non-muddy pixels (sufficient saturation and brightness)
    mask = (s > 60) & (v > 50)
    if not np.any(mask):
        mask = (s > 35) & (v > 40)
    if not np.any(mask):
        mask = v > 40

    valid_h = h[mask]
    valid_s = s[mask]

    # If the image is largely monochromatic / grayscale (very low saturation throughout)
    # pick a cool vibrant signature neon color so the visualizer always looks awesome!
    if len(valid_s) == 0 or np.mean(valid_s) < 30:
        cool_neon_fallbacks = [
            (250, 240, 60),   # Electric Cyan
            (70, 215, 255),   # Radiant Gold
            (210, 140, 255),  # Cyber Rose Pink
            (255, 60, 220),   # Neon Magenta
            (80, 255, 120),   # Toxic Lime
            (255, 130, 180),  # Electric Violet
            (255, 225, 140),  # Frosted Sky
        ]
        idx = int(np.sum(img_bgr[:10, :10])) % len(cool_neon_fallbacks)
        return cool_neon_fallbacks[idx]

    # Compute histogram weighted by pixel saturation so vivid elements take priority
    weights = valid_s.astype(np.float32) / 255.0
    hist, bin_edges = np.histogram(valid_h, bins=18, range=(0, 180), weights=weights)
    dom_bin = np.argmax(hist)
    dom_hue = int((bin_edges[dom_bin] + bin_edges[dom_bin + 1]) / 2)

    if mode == "complementary":
        dom_hue = (dom_hue + 90) % 180

    # Luminous neon: high saturation (245/255), maximum value (255/255)
    neon_hsv = np.uint8([[[dom_hue, 245, 255]]])
    neon_bgr = cv2.cvtColor(neon_hsv, cv2.COLOR_HSV2BGR)[0][0]
    return tuple(int(c) for c in neon_bgr)


def color_hue_distance(bgr1, bgr2):
    """Calculates minimal circular hue difference (0 to 90 in OpenCV 0-180 scale)."""
    hsv1 = cv2.cvtColor(np.uint8([[bgr1]]), cv2.COLOR_BGR2HSV)[0][0]
    hsv2 = cv2.cvtColor(np.uint8([[bgr2]]), cv2.COLOR_BGR2HSV)[0][0]
    diff = abs(int(hsv1[0]) - int(hsv2[0]))
    return min(diff, 180 - diff)


def select_variety_color(img_bgr, recent_bgrs=None, min_distance_days=10):
    """
    Selects a vibrant visualizer color that guarantees NO repetition with the last 10 releases
    while staying deeply harmonized with the artwork:
    1. Extracts top dominant clusters (Dominant, Secondary Accent, Complementary Pop).
    2. Tests candidate colors against recent_bgrs[-10:].
    3. If there is a clash with recent colors, cycles to the next best candidate or
       harmonious palette aesthetic so the channel grid remains diverse and fresh.
    """
    if recent_bgrs is None:
        recent_bgrs = []

    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    mask = (s > 45) & (v > 40)
    if not np.any(mask):
        mask = (s > 25) & (v > 35)

    valid_h = h[mask]
    valid_s = s[mask]

    candidates = []
    if len(valid_s) > 0 and np.mean(valid_s) >= 30:
        weights = valid_s.astype(np.float32) / 255.0
        hist, bin_edges = np.histogram(valid_h, bins=18, range=(0, 180), weights=weights)
        top_bins = np.argsort(hist)[::-1]

        # Primary Dominant
        p_hue = int((bin_edges[top_bins[0]] + bin_edges[top_bins[0] + 1]) / 2)
        c1 = tuple(int(x) for x in cv2.cvtColor(np.uint8([[[p_hue, 245, 255]]]), cv2.COLOR_HSV2BGR)[0][0])
        candidates.append(("artwork_dominant", c1))

        # Secondary Accent (if significant)
        if len(top_bins) > 1 and hist[top_bins[1]] > 0.05 * hist[top_bins[0]]:
            s_hue = int((bin_edges[top_bins[1]] + bin_edges[top_bins[1] + 1]) / 2)
            c2 = tuple(int(x) for x in cv2.cvtColor(np.uint8([[[s_hue, 245, 255]]]), cv2.COLOR_HSV2BGR)[0][0])
            candidates.append(("artwork_accent", c2))

        # Complementary Pop (180 deg opposite)
        comp_hue = (p_hue + 90) % 180
        c_comp = tuple(int(x) for x in cv2.cvtColor(np.uint8([[[comp_hue, 245, 255]]]), cv2.COLOR_HSV2BGR)[0][0])
        candidates.append(("artwork_complementary", c_comp))

    # Add full EDM palette candidates
    for name, bgr in NEON_PALETTE.items():
        candidates.append((name, bgr))

    # Filter against the last 10 used colors (Hue distance >= 18 out of 180)
    recent_window = recent_bgrs[-min_distance_days:] if recent_bgrs else []
    for label, bgr in candidates:
        conflict = any(color_hue_distance(bgr, rec) < 18 for rec in recent_window)
        if not conflict:
            print(f"[NBF Color Engine] Selected '{label}' color (BGR: {bgr}) - No clash with last {len(recent_window)} uploads.")
            return label, bgr

    # If all conflict, return first candidate
    chosen = candidates[0]
    return chosen[0], chosen[1]


def generate_nbf_video(
    viz_path,
    bg_path,
    audio_path,
    output_path,
    fps=60,
    base_diameter=780,
    color="variety",
    recent_colors=None,
    darken_factor=0.50,
    song_title=None,
    target_width=1080,
    target_height=1920,
    crf=19,
    start_sec=0.0,
    duration=None,
):
    """
    Renders the complete 60 FPS NBF MOBILE (9:16 vertical) music video with:
    1. Background darkening mask & vignette
    2. NBF branding logo on top-center
    3. Beat-responsive core visualizer centered
    4. 10-day anti-repetition color selection
    5. Fast raw FFmpeg pipe encoding
    """
    W, H = target_width, target_height

    # 1. Load background image first so dynamic color extraction can analyze it
    raw_bg = cv2.imread(bg_path)
    if raw_bg is None:
        raise ValueError(f"Could not load image: {bg_path}")

    # 2. Resolve visualizer color
    color_label = "custom"
    if isinstance(color, str):
        c_low = color.lower().strip()
        if c_low in ("variety", "auto", "smart", "anti_repetition"):
            color_label, color_bgr = select_variety_color(raw_bg, recent_bgrs=recent_colors, min_distance_days=10)
        elif c_low in ("harmonized", "dominant"):
            color_label = "dominant"
            color_bgr = extract_artwork_color(raw_bg, mode="auto")
        elif c_low in ("complementary", "contrast"):
            color_label = "complementary"
            color_bgr = extract_artwork_color(raw_bg, mode="complementary")
        elif c_low == "random":
            import random
            color_label = "random"
            color_bgr = random.choice(list(NEON_PALETTE.values()))
        elif c_low.startswith("#") or (len(c_low) == 6 and all(c in "0123456789abcdef" for c in c_low)):
            hex_str = c_low.lstrip("#")
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            color_bgr = (b, g, r)
            color_label = f"hex_{hex_str}"
        else:
            color_label = c_low
            color_bgr = NEON_PALETTE.get(c_low, NEON_PALETTE["cyan"])
    else:
        color_bgr = color

    print(f"\n[NBF Visualizer] Starting video render ({W}x{H} @ {fps}fps)...")
    print(f"  - Background: {bg_path}")
    print(f"  - Audio: {audio_path}")
    print(f"  - Darkening factor: {darken_factor} (Mask applied)")
    print(f"  - Neon color BGR: {color_bgr} (Label: {color_label}, Mode: {color})")
    print(f"  - Core diameter: {base_diameter}px")

    bh, bw = raw_bg.shape[:2]
    target_ratio = W / float(H)
    orig_ratio = bw / float(bh)
    if orig_ratio > target_ratio:
        crop_w = int(bh * target_ratio)
        left = (bw - crop_w) // 2
        bg = raw_bg[:, left:left + crop_w]
    else:
        crop_h = int(bw / target_ratio)
        top = (bh - crop_h) // 2
        bg = raw_bg[top:top + crop_h, :]

    bg = cv2.resize(bg, (W, H), interpolation=cv2.INTER_LANCZOS4)

    # 3. Apply Darkening Mask
    bg = apply_darkening_mask(bg, darken_factor=darken_factor, vignette_intensity=0.25)

    # 4. Overlay NBF Branding (top-center on vertical, left side on landscape)
    #    + song title in the bottom caption zone (vertical only)
    bg = overlay_nbf_branding(bg)
    if song_title:
        bg = overlay_song_title(bg, song_title)

    # 5. Load Visualizer Core Frames from .viz file
    template_frames = load_viz_core(viz_path, color_bgr=color_bgr)
    num_template_frames = len(template_frames)

    # 6. Audio rhythm analysis
    print(f"[NBF Visualizer] Loading audio: {audio_path}", flush=True)
    audio_full, sr = sf.read(audio_path)
    if audio_full.ndim > 1:
        mono_full = np.mean(audio_full, axis=1)
    else:
        mono_full = audio_full

    total_duration = len(mono_full) / sr
    start_sample = int(start_sec * sr)
    if duration is not None and duration > 0:
        actual_duration = min(duration, total_duration - start_sec)
        num_samples = int(actual_duration * sr)
        audio_slice = audio_full[start_sample:start_sample + num_samples]
        mono_slice = mono_full[start_sample:start_sample + num_samples]
    else:
        actual_duration = total_duration - start_sec
        audio_slice = audio_full[start_sample:]
        mono_slice = mono_full[start_sample:]

    actual_frames = int(actual_duration * fps)
    print(f"[NBF Visualizer] Audio duration: {actual_duration:.2f}s ({actual_frames} frames @ {fps}fps)", flush=True)

    # Save temporary sync WAV
    temp_wav_fd, temp_wav_path = tempfile.mkstemp(suffix="_nbf_sync.wav")
    os.close(temp_wav_fd)
    sf.write(temp_wav_path, audio_slice, sr)

    # Analyze BeatPulse
    bass_env, energy_env = compute_audio_rhythm(mono_slice, sr, fps=fps)

    # 7. Setup Visualizer Coordinates
    # Vertical canvas: core sits in the upper area (big logo below it stays
    # clear). Landscape: classic right-side placement.
    if H > W:
        cx = int(W * 0.50)
        cy = int(H * 0.30)
    else:
        cx = int(W * 0.741)
        cy = int(H * 0.485)

    max_reach = int(base_diameter * 1.65)
    x1 = max(0, cx - max_reach // 2)
    x2 = min(W, cx + max_reach // 2)
    y1 = max(0, cy - max_reach // 2)
    y2 = min(H, cy + max_reach // 2)
    rcx = cx - x1
    rcy = cy - y1

    bg_roi_static = bg[y1:y2, x1:x2].copy()

    # 8. Launch FFmpeg encoder
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{W}x{H}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "-",
        "-i", temp_wav_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "320k",
        "-shortest",
        output_path
    ]

    print("[NBF Visualizer] Launching FFmpeg raw encoder...", flush=True)
    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    t0 = time.time()
    last_print = t0
    phase_accum = 0.0

    # Thumbnail snapshot frame
    thumb_frame_idx = min(actual_frames - 1, int(max(2.0, min(actual_duration * 0.35, 8.0)) * fps))
    saved_thumb = None

    try:
        for i in range(actual_frames):
            bass_val = float(bass_env[i])
            energy_val = float(energy_env[i])

            # Continuous rotation phase
            phase_accum += 0.85
            tpl_idx = int(phase_accum) % num_template_frames
            core_src = template_frames[tpl_idx]

            # Dynamic BeatPulse diameter expansion
            # Bass kick expands the core up to 18% dynamically
            scale = 1.0 + (bass_val * 0.18) + (energy_val * 0.05)
            curr_dia = int(round(base_diameter * scale))

            # Resize animated core
            core_scaled = cv2.resize(core_src, (curr_dia, curr_dia), interpolation=cv2.INTER_LINEAR)

            # Flash bloom intensity on drum hits
            if bass_val > 0.45:
                flash_mult = 1.0 + (bass_val - 0.45) * 0.65
                core_scaled = np.clip(core_scaled.astype(np.float32) * flash_mult, 0, 255).astype(np.uint8)

            # Composite onto background ROI
            frame_roi = bg_roi_static.copy()

            # Coordinates within ROI
            px1 = rcx - curr_dia // 2
            px2 = px1 + curr_dia
            py1 = rcy - curr_dia // 2
            py2 = py1 + curr_dia

            # Clip bounds
            spx1 = max(0, px1)
            spx2 = min(frame_roi.shape[1], px2)
            spy1 = max(0, py1)
            spy2 = min(frame_roi.shape[0], py2)

            c_crop_x1 = max(0, -px1)
            c_crop_x2 = c_crop_x1 + (spx2 - spx1)
            c_crop_y1 = max(0, -py1)
            c_crop_y2 = c_crop_y1 + (spy2 - spy1)

            if spx2 > spx1 and spy2 > spy1:
                roi_slice = frame_roi[spy1:spy2, spx1:spx2]
                core_slice = core_scaled[c_crop_y1:c_crop_y2, c_crop_x1:c_crop_x2]
                # Screen blend mode: 255 - ((255 - A) * (255 - B) / 255)
                blended = 255 - (((255 - roi_slice.astype(np.uint16)) * (255 - core_slice.astype(np.uint16))) // 255)
                frame_roi[spy1:spy2, spx1:spx2] = blended.astype(np.uint8)

            # Paste ROI back into full frame
            full_frame = bg.copy()
            full_frame[y1:y2, x1:x2] = frame_roi

            # Save snapshot for thumbnail
            if i == thumb_frame_idx or (saved_thumb is None and i > fps):
                saved_thumb = full_frame.copy()

            # Pipe to FFmpeg
            proc.stdin.write(full_frame.tobytes())

            # Progress log every 3 seconds
            now = time.time()
            if now - last_print >= 3.0 or i == actual_frames - 1:
                pct = ((i + 1) / actual_frames) * 100
                speed = (i + 1) / (now - t0 + 0.001)
                print(f"[NBF Visualizer] Render progress: {pct:.1f}% ({i + 1}/{actual_frames} frames) @ {speed:.1f} fps", flush=True)
                last_print = now

    finally:
        if proc.stdin:
            try:
                proc.stdin.close()
            except Exception:
                pass
        proc.wait()

        # Clean up temporary WAV
        if os.path.exists(temp_wav_path):
            try:
                os.remove(temp_wav_path)
            except Exception:
                pass

    total_time = time.time() - t0
    print(f"\n[NBF Visualizer] Video render finished in {total_time:.1f}s.")

    # 9. Save Matching High-Impact Thumbnail
    thumb_path = output_path.replace(".mp4", "_thumb.jpg")
    if saved_thumb is not None:
        cv2.imwrite(thumb_path, saved_thumb, [cv2.IMWRITE_JPEG_QUALITY, 96])
    color_info = {"label": color_label, "bgr": list(color_bgr)}
    return output_path, thumb_path, color_info


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NBF Music Video & Thumbnail Generator")
    parser.add_argument("--image", required=True, help="Background image path")
    parser.add_argument("--audio", required=True, help="Audio track path (MP3/WAV)")
    parser.add_argument("--output", default="output_nbf_mobile.mp4", help="Output MP4 video path")
    parser.add_argument("--title", default=None, help="Song title")
    parser.add_argument("--duration", type=float, default=None, help="Max duration in seconds (for preview/testing)")
    parser.add_argument("--start", type=float, default=0.0, help="Start offset in seconds into the audio track")
    parser.add_argument("--darken", type=float, default=0.50, help="Darkening mask factor (0.1 to 1.0)")
    parser.add_argument("--color", default="variety", help="Neon glow color (variety, cyan, magenta, etc.)")
    parser.add_argument("--width", type=int, default=1080, help="Output width (default 1080 for 9:16 mobile)")
    parser.add_argument("--height", type=int, default=1920, help="Output height (default 1920 for 9:16 mobile)")

    args = parser.parse_args()

    viz_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Visualizer_Core_Only.viz")
    if not os.path.exists(viz_file):
        viz_file = "Visualizer_Core_Only.viz"

    generate_nbf_video(
        viz_path=viz_file,
        bg_path=args.image,
        audio_path=args.audio,
        output_path=args.output,
        duration=args.duration,
        start_sec=args.start,
        darken_factor=args.darken,
        color=args.color,
        song_title=args.title,
        target_width=args.width,
        target_height=args.height
    )
