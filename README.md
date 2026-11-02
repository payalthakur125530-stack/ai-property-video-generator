# AI Property Video Generator

A complete, production-style prototype that turns property details + photos into a ready-to-share promotional MP4 video (20–40 seconds).

Built as a technical assessment for a real-estate technology company.

---

## Features

| Feature | Implementation |
|---------|----------------|
| **Input Form** | Property name, location, price, type, features, CTA, 4–8 image upload |
| **AI Script** | LLM (Gemini / OpenAI) when API key present · deterministic template fallback |
| **Safety Rule** | Script never invents amenities – only uses supplied facts |
| **Voiceover** | `edge-tts` (Microsoft neural voices) with `gTTS` fallback |
| **Video Assembly** | MoviePy – intro / feature scenes / outro, cross-dissolves, text banners |
| **Output** | 1280×720 MP4 @ 30 fps, in-app preview + download button |
| **CLI Mode** | `python app.py --cli` runs end-to-end with sample data |

---

## Project Structure

```
ai_property_video_generator/
├── app.py                 # Streamlit UI + CLI entrypoint
├── video_engine.py        # MoviePy rendering pipeline & text overlays
├── script_generator.py    # LLM / template script logic (Pydantic models)
├── tts_engine.py          # edge-tts / gTTS + optional background mix
├── assets/                # Place optional ambient_bg.mp3 here
├── sample_data/           # Auto-generated placeholders + synthetic data
├── output/                # Generated videos land here
├── requirements.txt
└── README.md
```

---

## Installation

### 1. System dependencies

**ffmpeg** is required by MoviePy:

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html and add to PATH
```

### 2. Python environment

```bash
cd ai_property_video_generator
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. (Optional) API keys for richer scripts

```bash
export OPENAI_API_KEY="sk-..."          # or
export GEMINI_API_KEY="AIza..."         # Google AI Studio key
```

If neither key is present the app **automatically** falls back to a high-quality rule-based template. No crash, no hardcoded secrets.

---

## How to Run

### Web UI (recommended)

```bash
streamlit run app.py
```

Open the URL shown in the terminal (usually `http://localhost:8501`).

1. Click **“Load sample property”** in the sidebar (or fill the form yourself).
2. Optionally upload 4–8 property photos.
3. Click **Generate Property Video**.
4. Preview the result and download the MP4.

### CLI Mode (great for reviewers / CI)

```bash
python app.py --cli
```

This uses the built-in sample property (“Skyline Apartments”, $450 k, 2-BHK) and placeholder images, then writes:

```
output/skyline_apartments_promo.mp4
```

---

## AI Approach & Design Decisions

### Script Generation
- **Primary path**: Google Gemini 1.5 Flash or OpenAI GPT-4o-mini.
- Prompt is tightly constrained: “Use ONLY the facts listed below. Do NOT invent any amenities…”
- Output is parsed into structured `SceneScript` objects.
- **Fallback**: Pure Python template that builds intro → feature chunks → CTA. Always works offline.

### Why MoviePy + Pillow?
- Pure-Python, easy to install, excellent control over text overlays and transitions.
- Pillow is used to composite high-contrast banners (dark semi-transparent rectangles + white/gold text) so captions remain readable on any photo.

### Audio
- `edge-tts` gives natural neural voices with zero cost and no API key.
- Soft ambient background is mixed at ~15 % volume when a file is present in `assets/`.
- If no background track exists, voice-only audio is used – the pipeline never fails.

### Validation
- All user input is validated with **Pydantic** models before any processing.
- Missing fields surface friendly Streamlit warnings instead of stack traces.

---

## Models & Libraries Used

| Component | Library / Model | Notes |
|-----------|-----------------|-------|
| LLM (optional) | `google-generativeai` (gemini-1.5-flash) or `openai` (gpt-4o-mini) | No keys hard-coded |
| TTS | `edge-tts` (en-US-JennyNeural) → `gTTS` fallback | Offline-capable |
| Video | `moviepy` + `Pillow` + system `ffmpeg` | 720p 16:9 @ 30 fps |
| UI | `streamlit` | Single-file entrypoint |
| Validation | `pydantic` v2 | |

**Safety / Security**
- No API keys are embedded in source code.
- Script generator never fabricates property features.
- Uploaded images stay in temporary directories and are not persisted beyond the session.

---

## Current Limitations

- Video length is driven by the voiceover duration (typically 25–40 s). Extremely long feature lists are truncated.
- Cross-dissolve transitions are simple; advanced motion graphics or Ken-Burns zooms are out of scope for this prototype.
- Background music must be supplied manually (`assets/ambient_bg.mp3`). A silent track is used otherwise.
- Font rendering depends on system fonts (DejaVu / Liberation / Arial). Fallback to default bitmap font is possible but less polished.
- First run may download the edge-tts voice model; subsequent runs are fast.

---

## Quick Test Checklist for Reviewers

```bash
# 1. Install
pip install -r requirements.txt
# (ensure ffmpeg is available)

# 2. CLI smoke test
python app.py --cli
# → should produce output/skyline_apartments_promo.mp4

# 3. Web UI
streamlit run app.py
# → Load sample → Generate → Preview & Download
```

---

## License

Prototype created for technical assessment purposes. Feel free to adapt.
