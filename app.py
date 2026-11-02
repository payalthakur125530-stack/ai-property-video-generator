#!/usr/bin/env python3
"""
app.py
AI Property Video Generator – Streamlit UI + CLI mode.

Usage:
  streamlit run app.py          # Web UI
  python app.py --cli           # Command-line mode with sample data
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import List, Optional

# Ensure local imports work when run from any cwd
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from script_generator import PropertyInput, generate_script, VideoScript
from tts_engine import generate_voiceover, get_default_bg_music, mix_voice_and_bg
from video_engine import build_video, create_placeholder_images


# ---------------------------------------------------------------------------
# Sample data for instant demo
# ---------------------------------------------------------------------------
SAMPLE_PROPERTY = {
    "name": "Skyline Apartments",
    "location": "Downtown Austin, TX",
    "price": "$450,000",
    "property_type": "2-BHK Apartment",
    "features": "Open-plan kitchen, Floor-to-ceiling windows, Smart home system, Rooftop terrace, 24/7 concierge, Underground parking",
    "cta": "Schedule your private tour today!",
    "contact": "Call 512-555-0199  |  skyline@example.com",
}


def run_pipeline(
    prop: PropertyInput,
    image_paths: List[str],
    output_path: str,
    prefer_llm: bool = True,
    progress_callback=None,
) -> str:
    """
    Full pipeline: script → TTS → video render.
    Returns path to the generated MP4.
    """
    def log(msg: str):
        if progress_callback:
            progress_callback(msg)
        else:
            print(msg)

    log("① Generating script…")
    script: VideoScript = generate_script(prop, prefer_llm=prefer_llm)
    log(f"   → {len(script.scenes)} scenes | title: {script.title}")

    log("② Generating voiceover (TTS)…")
    voice_path = generate_voiceover(script.full_voiceover)
    log(f"   → voiceover ready")

    bg = get_default_bg_music()
    if bg:
        log("③ Mixing background ambient audio…")
        mixed = mix_voice_and_bg(voice_path, bg)
        audio_path = mixed
    else:
        log("③ No background music found – using voice only.")
        audio_path = voice_path

    log("④ Assembling video (this is the longest step)…")
    final = build_video(
        script=script,
        image_paths=image_paths,
        voice_audio_path=audio_path,
        output_path=output_path,
        bg_music_path=None,  # already mixed if present
        progress_callback=log,
    )
    log(f"✅ Done → {final}")
    return final


# ---------------------------------------------------------------------------
# CLI mode
# ---------------------------------------------------------------------------
def cli_main():
    print("=" * 60)
    print("  AI Property Video Generator – CLI Mode")
    print("=" * 60)

    prop = PropertyInput(
        name=SAMPLE_PROPERTY["name"],
        location=SAMPLE_PROPERTY["location"],
        price=SAMPLE_PROPERTY["price"],
        property_type=SAMPLE_PROPERTY["property_type"],
        features=SAMPLE_PROPERTY["features"],
        cta=SAMPLE_PROPERTY["cta"],
        contact=SAMPLE_PROPERTY["contact"],
    )

    print("\nUsing sample property:")
    print(f"  {prop.name} | {prop.location} | {prop.price}")
    print(f"  Features: {', '.join(prop.features)}")

    # Create placeholder images if no real ones exist
    sample_img_dir = ROOT / "sample_data" / "images"
    if sample_img_dir.exists() and any(sample_img_dir.glob("*.jpg")):
        images = sorted(str(p) for p in sample_img_dir.glob("*.jpg"))
        print(f"\nFound {len(images)} sample images.")
    else:
        print("\nGenerating placeholder images…")
        images = create_placeholder_images(5, out_dir=str(sample_img_dir))

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    output_path = str(out_dir / "skyline_apartments_promo.mp4")

    try:
        run_pipeline(prop, images, output_path, prefer_llm=True)
        print("\n" + "=" * 60)
        print(f"SUCCESS! Video saved to:\n  {output_path}")
        print("=" * 60)
    except Exception as e:
        print("\n❌ Pipeline failed:")
        traceback.print_exc()
        sys.exit(1)


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
def streamlit_app():
    import streamlit as st

    st.set_page_config(
        page_title="AI Property Video Generator",
        page_icon="🏠",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("🏠 AI Property Video Generator")
    st.markdown(
        "Create a professional 20–40 second promotional property video in one click. "
        "Just fill in the details, upload photos, and let the AI handle the rest."
    )

    # Sidebar – settings & info
    with st.sidebar:
        st.header("Settings")
        prefer_llm = st.toggle("Use LLM for script (if API key present)", value=True)
        st.caption(
            "If `OPENAI_API_KEY` or `GEMINI_API_KEY` is set in the environment, "
            "a natural-language script is generated. Otherwise a high-quality "
            "deterministic template is used automatically."
        )
        st.divider()
        st.markdown("### Sample Data")
        if st.button("Load sample property"):
            st.session_state["load_sample"] = True
        st.divider()
        st.markdown(
            "**Tech stack**  \n"
            "Streamlit · MoviePy · edge-tts / gTTS · "
            "Pydantic · Pillow · OpenAI / Gemini (optional)"
        )

    # ---- Input form ----
    col1, col2 = st.columns(2)

    # Pre-fill from sample if requested
    defaults = SAMPLE_PROPERTY if st.session_state.get("load_sample") else {
        "name": "", "location": "", "price": "", "property_type": "Apartment",
        "features": "", "cta": "Contact us today for a private viewing!", "contact": "",
    }

    with col1:
        name = st.text_input("Property Name *", value=defaults["name"], placeholder="Skyline Apartments")
        location = st.text_input("Location *", value=defaults["location"], placeholder="Downtown Austin, TX")
        price = st.text_input("Price *", value=defaults["price"], placeholder="$450,000")
        property_type = st.selectbox(
            "Property Type",
            ["Apartment", "House", "Condo", "Townhouse", "Villa", "Commercial", "Other"],
            index=0 if not defaults["property_type"] else (
                ["Apartment", "House", "Condo", "Townhouse", "Villa", "Commercial", "Other"]
                .index(defaults["property_type"]) if defaults["property_type"] in
                ["Apartment", "House", "Condo", "Townhouse", "Villa", "Commercial", "Other"] else 0
            ),
        )

    with col2:
        features = st.text_area(
            "Key Features (comma-separated)",
            value=defaults["features"],
            height=100,
            placeholder="Open-plan kitchen, Floor-to-ceiling windows, Rooftop terrace…",
        )
        cta = st.text_input("Call-to-Action Text", value=defaults["cta"])
        contact = st.text_input("Contact Info (optional)", value=defaults["contact"],
                               placeholder="Call 512-555-0199")

    st.markdown("#### Property Images (4–8 recommended)")
    uploaded = st.file_uploader(
        "Upload JPG / PNG images",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        help="At least 1 image required. 4–8 images give the best results.",
    )

    # Validation
    missing = []
    if not name.strip():
        missing.append("Property Name")
    if not location.strip():
        missing.append("Location")
    if not price.strip():
        missing.append("Price")

    if missing:
        st.warning(f"Please fill in: **{', '.join(missing)}**")

    generate_btn = st.button(
        "🎬 Generate Property Video",
        type="primary",
        disabled=bool(missing),
        use_container_width=True,
    )

    if generate_btn:
        # Save uploaded images to temp files
        image_paths: List[str] = []
        if uploaded:
            tmp_dir = tempfile.mkdtemp(prefix="prop_upload_")
            for i, uf in enumerate(uploaded):
                ext = Path(uf.name).suffix or ".jpg"
                p = os.path.join(tmp_dir, f"img_{i}{ext}")
                with open(p, "wb") as f:
                    f.write(uf.getbuffer())
                image_paths.append(p)
        else:
            st.info("No images uploaded – using generated placeholder images for demo.")
            image_paths = create_placeholder_images(5)

        if len(image_paths) < 1:
            st.error("At least one image is required.")
            st.stop()

        try:
            prop = PropertyInput(
                name=name.strip(),
                location=location.strip(),
                price=price.strip(),
                property_type=property_type,
                features=features,
                cta=cta.strip(),
                contact=contact.strip(),
            )
        except Exception as e:
            st.error(f"Invalid input: {e}")
            st.stop()

        progress = st.progress(0, text="Starting pipeline…")
        status = st.empty()

        def cb(msg: str):
            status.markdown(f"**Status:** {msg}")

        out_dir = ROOT / "output"
        out_dir.mkdir(exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:40]
        output_path = str(out_dir / f"{safe_name}_promo.mp4")

        try:
            progress.progress(10, text="Generating script…")
            final_path = run_pipeline(
                prop=prop,
                image_paths=image_paths,
                output_path=output_path,
                prefer_llm=prefer_llm,
                progress_callback=cb,
            )
            progress.progress(100, text="Complete!")

            st.success("Video generated successfully!")
            st.video(final_path)

            with open(final_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download MP4",
                    data=f,
                    file_name=Path(final_path).name,
                    mime="video/mp4",
                    use_container_width=True,
                )

            # Show script for transparency
            with st.expander("View generated script"):
                from script_generator import generate_script as gs
                sc = gs(prop, prefer_llm=prefer_llm)
                st.markdown(f"**Title:** {sc.title}")
                st.markdown("**Full voiceover:**")
                st.write(sc.full_voiceover)
                st.markdown("**Scenes:**")
                for i, s in enumerate(sc.scenes, 1):
                    st.markdown(f"{i}. **{s.scene_type.upper()}** – {s.caption}")

        except Exception as e:
            st.error("An error occurred while generating the video.")
            st.code(traceback.format_exc())
            st.info(
                "Common fixes:\n"
                "- Make sure `ffmpeg` is installed and on PATH.\n"
                "- Install all packages: `pip install -r requirements.txt`\n"
                "- Try with fewer / smaller images."
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _is_streamlit_runtime() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


# Streamlit executes the entire script on every rerun.
# We only want the UI when we are inside that runtime (or when the user
# explicitly launches via `streamlit run`).
if _is_streamlit_runtime():
    streamlit_app()
elif __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Property Video Generator")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in CLI mode with sample data (no browser)",
    )
    args, unknown = parser.parse_known_args()

    if args.cli:
        cli_main()
    else:
        import subprocess
        print("Launching Streamlit UI…")
        print("  (Tip: you can also run  →  streamlit run app.py)")
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve()), *unknown],
            check=False,
        )
