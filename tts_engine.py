"""
tts_engine.py
Text-to-Speech generation using edge-tts (preferred) with gTTS fallback.
MoviePy 2.x compatible audio mixing.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Optional


async def _edge_tts_save(text: str, output_path: str, voice: str = "en-US-JennyNeural") -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def generate_voiceover(
    text: str,
    output_path: Optional[str] = None,
    voice: str = "en-US-JennyNeural",
    prefer_edge: bool = True,
) -> str:
    if not text or not text.strip():
        raise ValueError("Voiceover text cannot be empty.")

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".mp3", prefix="prop_vo_")
        os.close(fd)

    output_path = str(output_path)

    if prefer_edge:
        try:
            asyncio.run(_edge_tts_save(text, output_path, voice=voice))
            if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                print(f"[tts_engine] edge-tts voiceover saved → {output_path}")
                return output_path
        except Exception as e:
            print(f"[tts_engine] edge-tts failed ({e}). Falling back to gTTS.")

    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(output_path)
        print(f"[tts_engine] gTTS voiceover saved → {output_path}")
        return output_path
    except Exception as e:
        raise RuntimeError(f"Both edge-tts and gTTS failed: {e}") from e


def _with_volume(clip, factor: float):
    if hasattr(clip, "with_volume_scaled"):
        return clip.with_volume_scaled(factor)
    if hasattr(clip, "volumex"):
        return clip.volumex(factor)
    return clip


def mix_voice_and_bg(
    voice_path: str,
    bg_path: Optional[str],
    output_path: Optional[str] = None,
    voice_volume: float = 1.0,
    bg_volume: float = 0.18,
) -> str:
    """Mix voiceover with background music (MoviePy 2 compatible)."""
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".mp3", prefix="mixed_audio_")
        os.close(fd)

    try:
        from moviepy import AudioFileClip, CompositeAudioClip
    except ImportError:
        try:
            from moviepy.audio.io.AudioFileClip import AudioFileClip
            from moviepy.audio.AudioClip import CompositeAudioClip
        except ImportError:
            # No moviepy audio – just return voice
            return voice_path

    voice = AudioFileClip(voice_path)
    voice = _with_volume(voice, voice_volume)

    if bg_path and os.path.exists(bg_path):
        try:
            bg = AudioFileClip(bg_path)
            if bg.duration < voice.duration:
                try:
                    from moviepy import concatenate_audioclips
                except ImportError:
                    from moviepy.audio.AudioClip import concatenate_audioclips
                n = int(voice.duration / bg.duration) + 1
                bg = concatenate_audioclips([bg] * n)
            if hasattr(bg, "subclipped"):
                bg = bg.subclipped(0, voice.duration)
            else:
                bg = bg.subclip(0, voice.duration)
            bg = _with_volume(bg, bg_volume)
            mixed = CompositeAudioClip([voice, bg])
            mixed.write_audiofile(output_path, fps=44100, logger=None)
            mixed.close()
            bg.close()
            voice.close()
            print(f"[tts_engine] Mixed audio saved → {output_path}")
            return output_path
        except Exception as e:
            print(f"[tts_engine] Background mix failed ({e}). Using voice only.")
            try:
                voice.close()
            except Exception:
                pass

    try:
        voice.write_audiofile(output_path, fps=44100, logger=None)
        voice.close()
    except Exception:
        # Last resort: copy file
        import shutil
        shutil.copy(voice_path, output_path)
    return output_path


def get_default_bg_music() -> Optional[str]:
    candidates = [
        Path(__file__).parent / "assets" / "ambient_bg.mp3",
        Path(__file__).parent / "assets" / "background.mp3",
        Path(__file__).parent / "assets" / "bg_music.mp3",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


if __name__ == "__main__":
    sample_text = (
        "Welcome to Skyline Apartments, a stunning 2-BHK apartment located in Downtown Austin. "
        "Priced at four hundred fifty thousand dollars."
    )
    path = generate_voiceover(sample_text)
    print("Generated:", path)
    print("Size:", os.path.getsize(path), "bytes")
