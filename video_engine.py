"""
video_engine.py
MoviePy 2.x compatible video assembly pipeline for property promotional videos.
Works on Python 3.10 – 3.13.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import numpy as np

from script_generator import VideoScript, SceneScript, PropertyInput


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TARGET_W = 1280
TARGET_H = 720
FPS = 30
CROSSFADE = 0.6


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------
def _load_and_fit(image_path: str, size: Tuple[int, int] = (TARGET_W, TARGET_H)) -> Image.Image:
    """Load image and cover-fit to target size (center-crop)."""
    img = Image.open(image_path).convert("RGB")
    tw, th = size
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _darken(img: Image.Image, factor: float = 0.55) -> Image.Image:
    enhancer = ImageEnhance.Brightness(img)
    return enhancer.enhance(factor)


def _add_gradient_overlay(img: Image.Image, bottom_dark: bool = True) -> Image.Image:
    arr = np.array(img).astype(np.float32)
    h = arr.shape[0]
    if bottom_dark:
        gradient = np.linspace(1.0, 0.35, h)[:, np.newaxis, np.newaxis]
    else:
        gradient = np.linspace(0.45, 1.0, h)[:, np.newaxis, np.newaxis]
    arr = arr * gradient
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _get_font(size: int = 42, bold: bool = True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int) -> List[str]:
    words = text.replace("\n", " \n ").split()
    lines: List[str] = []
    current = ""
    for w in words:
        if w == "\n":
            if current:
                lines.append(current)
                current = ""
            continue
        test = f"{current} {w}".strip()
        try:
            bbox = font.getbbox(test)
            width = bbox[2] - bbox[0]
        except Exception:
            width = len(test) * 10
        if width <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines or [""]


def create_text_overlay_image(
    base_img: Image.Image,
    caption: str,
    scene_type: str = "feature",
    property_name: str = "",
) -> Image.Image:
    img = base_img.copy()
    draw = ImageDraw.Draw(img, "RGBA")

    w, h = img.size
    font_large = _get_font(48)
    font_small = _get_font(28)
    font_cta = _get_font(34)

    if scene_type == "intro":
        lines = caption.split("\n")
        banner_h = min(280, 70 * len(lines) + 40)
        banner_y = (h - banner_h) // 2
        draw.rectangle([(0, banner_y), (w, banner_y + banner_h)], fill=(0, 0, 0, 170))
        y = banner_y + 25
        for i, line in enumerate(lines):
            f = font_large if i == 0 else font_small
            try:
                bbox = f.getbbox(line)
                tw = bbox[2] - bbox[0]
                line_h = bbox[3] - bbox[1]
            except Exception:
                tw, line_h = len(line) * 12, 30
            x = (w - tw) // 2
            draw.text((x + 2, y + 2), line, font=f, fill=(0, 0, 0, 200))
            draw.text((x, y), line, font=f, fill=(255, 255, 255, 255))
            y += line_h + 12

    elif scene_type == "outro":
        lines = _wrap_text(caption, font_cta, w - 80)
        banner_h = 40 + 42 * len(lines)
        banner_y = h - banner_h - 20
        draw.rectangle([(0, banner_y), (w, h)], fill=(0, 0, 0, 185))
        y = banner_y + 18
        for line in lines:
            try:
                bbox = font_cta.getbbox(line)
                tw = bbox[2] - bbox[0]
            except Exception:
                tw = len(line) * 12
            x = (w - tw) // 2
            draw.text((x + 2, y + 2), line, font=font_cta, fill=(0, 0, 0, 180))
            draw.text((x, y), line, font=font_cta, fill=(255, 220, 100, 255))
            y += 42
        brand = "AI Property Video Generator"
        bf = _get_font(18)
        try:
            bbox = bf.getbbox(brand)
            bw = bbox[2] - bbox[0]
        except Exception:
            bw = 200
        draw.text((w - bw - 20, 18), brand, font=bf, fill=(255, 255, 255, 160))

    else:  # feature
        lines = _wrap_text(caption, font_small, w - 60)
        banner_h = 30 + 36 * len(lines)
        banner_y = h - banner_h - 15
        draw.rectangle([(0, banner_y), (w, h)], fill=(0, 0, 0, 165))
        y = banner_y + 12
        for line in lines:
            try:
                bbox = font_small.getbbox(line)
                tw = bbox[2] - bbox[0]
            except Exception:
                tw = len(line) * 10
            x = (w - tw) // 2
            draw.text((x + 1, y + 1), line, font=font_small, fill=(0, 0, 0, 180))
            draw.text((x, y), line, font=font_small, fill=(255, 255, 255, 255))
            y += 36

    return img.convert("RGB")


# ---------------------------------------------------------------------------
# MoviePy 2.x helpers
# ---------------------------------------------------------------------------
def _import_moviepy():
    try:
        from moviepy import (
            ImageClip,
            AudioFileClip,
            CompositeAudioClip,
            concatenate_videoclips,
        )
        return ImageClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips
    except ImportError:
        try:
            from moviepy.video.VideoClip import ImageClip
            from moviepy.audio.io.AudioFileClip import AudioFileClip
            from moviepy.audio.AudioClip import CompositeAudioClip
            from moviepy.video.compositing.CompositeVideoClip import concatenate_videoclips
            return ImageClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips
        except ImportError as e:
            raise ImportError(
                "MoviePy is not installed correctly. Run:\n"
                "  pip uninstall moviepy -y\n"
                "  pip install moviepy==2.1.2\n"
            ) from e


def _apply_fade(clip, fade_in: float = 0.0, fade_out: float = 0.0):
    try:
        from moviepy.video.fx.FadeIn import FadeIn
        from moviepy.video.fx.FadeOut import FadeOut
        effects = []
        if fade_in > 0:
            effects.append(FadeIn(fade_in))
        if fade_out > 0:
            effects.append(FadeOut(fade_out))
        if effects:
            return clip.with_effects(effects)
    except Exception:
        pass
    try:
        if fade_in > 0 and hasattr(clip, "fadein"):
            clip = clip.fadein(fade_in)
        if fade_out > 0 and hasattr(clip, "fadeout"):
            clip = clip.fadeout(fade_out)
    except Exception:
        pass
    return clip


def _with_duration(clip, duration: float):
    if hasattr(clip, "with_duration"):
        return clip.with_duration(duration)
    return clip.set_duration(duration)


def _with_fps(clip, fps: int):
    if hasattr(clip, "with_fps"):
        return clip.with_fps(fps)
    return clip.set_fps(fps)


def _with_audio(clip, audio):
    if hasattr(clip, "with_audio"):
        return clip.with_audio(audio)
    return clip.set_audio(audio)


def _with_volume(clip, factor: float):
    if hasattr(clip, "with_volume_scaled"):
        return clip.with_volume_scaled(factor)
    if hasattr(clip, "volumex"):
        return clip.volumex(factor)
    return clip


def build_video(
    script: VideoScript,
    image_paths: List[str],
    voice_audio_path: str,
    output_path: str,
    bg_music_path: Optional[str] = None,
    progress_callback=None,
) -> str:
    ImageClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips = _import_moviepy()

    if not image_paths:
        raise ValueError("At least one property image is required.")

    scenes = script.scenes
    n_scenes = len(scenes)
    n_images = len(image_paths)
    scene_images = [image_paths[i % n_images] for i in range(n_scenes)]

    voice = AudioFileClip(voice_audio_path)
    total_audio_dur = float(voice.duration)

    hints = [s.duration_hint for s in scenes]
    hint_sum = sum(hints) or 1.0
    raw_durs = [h / hint_sum * total_audio_dur for h in hints]
    durs = [max(3.5, d) for d in raw_durs]
    scale = total_audio_dur / sum(durs)
    durs = [d * scale for d in durs]

    clips = []
    temp_files = []

    for idx, (scene, img_path, dur) in enumerate(zip(scenes, scene_images, durs)):
        if progress_callback:
            progress_callback(f"Rendering scene {idx + 1}/{n_scenes} ({scene.scene_type})…")

        base = _load_and_fit(img_path)
        base = _darken(base, 0.72)
        base = _add_gradient_overlay(base, bottom_dark=True)

        overlay = create_text_overlay_image(
            base,
            caption=scene.caption,
            scene_type=scene.scene_type,
            property_name=script.title,
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        overlay.save(tmp.name, quality=92)
        tmp.close()
        temp_files.append(tmp.name)

        clip = ImageClip(tmp.name)
        clip = _with_duration(clip, dur)
        clip = _with_fps(clip, FPS)

        if idx == 0:
            clip = _apply_fade(clip, fade_in=0.8)
        if idx == n_scenes - 1:
            clip = _apply_fade(clip, fade_out=0.9)

        clips.append(clip)

    if len(clips) > 1:
        try:
            final = concatenate_videoclips(clips, method="compose", padding=-CROSSFADE)
        except TypeError:
            final = concatenate_videoclips(clips, method="compose")
    else:
        final = clips[0]

    final_audio = voice
    if bg_music_path and os.path.exists(bg_music_path):
        try:
            bg = AudioFileClip(bg_music_path)
            if bg.duration < final.duration:
                try:
                    from moviepy import concatenate_audioclips
                except ImportError:
                    from moviepy.audio.AudioClip import concatenate_audioclips
                n = int(final.duration / bg.duration) + 2
                bg = concatenate_audioclips([bg] * n)
            if hasattr(bg, "subclipped"):
                bg = bg.subclipped(0, final.duration)
            else:
                bg = bg.subclip(0, final.duration)
            bg = _with_volume(bg, 0.15)
            final_audio = CompositeAudioClip([_with_volume(voice, 1.0), bg])
        except Exception as e:
            print(f"[video_engine] BG music mix skipped: {e}")

    final = _with_audio(final, final_audio)
    try:
        final = _with_duration(final, min(float(final.duration), float(final_audio.duration)))
    except Exception:
        pass

    if progress_callback:
        progress_callback("Encoding final MP4… this may take 20–60 seconds.")

    final.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger=None,
        bitrate="4000k",
    )

    try:
        final.close()
    except Exception:
        pass
    try:
        voice.close()
    except Exception:
        pass
    for c in clips:
        try:
            c.close()
        except Exception:
            pass
    for t in temp_files:
        try:
            os.unlink(t)
        except Exception:
            pass

    print(f"[video_engine] Video written → {output_path}")
    return output_path


def create_placeholder_images(count: int = 5, out_dir: Optional[str] = None) -> List[str]:
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="prop_imgs_")
    os.makedirs(out_dir, exist_ok=True)

    colors = [
        (40, 70, 110), (70, 50, 90), (50, 90, 70), (100, 60, 50),
        (60, 60, 90), (80, 70, 50), (50, 80, 100), (90, 50, 70),
    ]
    paths = []
    for i in range(count):
        img = Image.new("RGB", (TARGET_W, TARGET_H), colors[i % len(colors)])
        draw = ImageDraw.Draw(img)
        font = _get_font(36)
        label = f"Sample Property Image {i + 1}"
        try:
            bbox = font.getbbox(label)
            x = (TARGET_W - (bbox[2] - bbox[0])) // 2
            y = (TARGET_H - (bbox[3] - bbox[1])) // 2
        except Exception:
            x, y = 400, 340
        draw.text((x, y), label, font=font, fill=(255, 255, 255))
        p = os.path.join(out_dir, f"placeholder_{i + 1}.jpg")
        img.save(p, quality=90)
        paths.append(p)
    return paths
