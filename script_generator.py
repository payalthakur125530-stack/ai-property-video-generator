"""
script_generator.py
AI / Template-based script & caption generator for property promotional videos.
Strictly uses only the facts supplied by the user. Never invents amenities or details.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class PropertyInput(BaseModel):
    """Validated property data model."""
    name: str = Field(..., min_length=1, description="Property name")
    location: str = Field(..., min_length=1, description="Location / city")
    price: str = Field(..., min_length=1, description="Price as string, e.g. '$450,000'")
    property_type: str = Field(default="Residential", description="Type of property")
    features: List[str] = Field(default_factory=list, description="Key features list")
    cta: str = Field(default="Contact us today for a private viewing!", description="Call-to-action text")
    contact: str = Field(default="", description="Optional contact info")

    @field_validator("features", mode="before")
    @classmethod
    def parse_features(cls, v):
        if isinstance(v, str):
            # Split on commas and clean
            return [f.strip() for f in v.split(",") if f.strip()]
        if isinstance(v, list):
            return [str(f).strip() for f in v if str(f).strip()]
        return []


class SceneScript(BaseModel):
    """One scene in the video."""
    scene_type: str  # intro | feature | outro
    caption: str
    voiceover: str
    duration_hint: float = 5.0  # seconds


class VideoScript(BaseModel):
    """Complete video script."""
    full_voiceover: str
    scenes: List[SceneScript]
    title: str


def _clean_price(price: str) -> str:
    """Normalize price string for speech."""
    return price.strip()


def generate_template_script(prop: PropertyInput) -> VideoScript:
    """
    Deterministic, rule-based script generator.
    Uses ONLY the data provided. Never invents features.
    """
    features = prop.features[:6]  # Cap at 6 for timing
    name = prop.name.strip()
    location = prop.location.strip()
    price = _clean_price(prop.price)
    ptype = prop.property_type.strip() or "property"
    cta = prop.cta.strip() or "Contact us today for a private viewing!"
    contact = prop.contact.strip()

    # --- Intro ---
    intro_voice = (
        f"Welcome to {name}, a stunning {ptype} located in {location}. "
        f"Priced at {price}."
    )
    intro_caption = f"{name}\n{location}\n{price}"

    scenes: List[SceneScript] = [
        SceneScript(
            scene_type="intro",
            caption=intro_caption,
            voiceover=intro_voice,
            duration_hint=6.0,
        )
    ]

    # --- Feature scenes ---
    if features:
        # Distribute features across 3–5 scenes
        n_feature_scenes = min(max(3, len(features)), 5)
        chunk_size = max(1, len(features) // n_feature_scenes)
        for i in range(n_feature_scenes):
            start = i * chunk_size
            end = start + chunk_size if i < n_feature_scenes - 1 else len(features)
            chunk = features[start:end]
            if not chunk:
                continue
            feat_text = ", ".join(chunk)
            voice = f"Highlights include {feat_text}."
            caption = " • ".join(chunk)
            scenes.append(
                SceneScript(
                    scene_type="feature",
                    caption=caption,
                    voiceover=voice,
                    duration_hint=5.0,
                )
            )
    else:
        # Fallback single feature scene when no features given
        scenes.append(
            SceneScript(
                scene_type="feature",
                caption=f"Discover {name}",
                voiceover=f"Explore the exceptional living experience offered by {name}.",
                duration_hint=5.0,
            )
        )

    # --- Outro ---
    outro_parts = [cta]
    if contact:
        outro_parts.append(contact)
    outro_voice = " ".join(outro_parts)
    outro_caption = cta
    if contact:
        outro_caption += f"\n{contact}"

    scenes.append(
        SceneScript(
            scene_type="outro",
            caption=outro_caption,
            voiceover=outro_voice,
            duration_hint=6.0,
        )
    )

    full_voiceover = " ".join(s.voiceover for s in scenes)

    return VideoScript(
        full_voiceover=full_voiceover,
        scenes=scenes,
        title=f"{name} – {location}",
    )


def generate_llm_script(prop: PropertyInput) -> Optional[VideoScript]:
    """
    Attempt to generate a more natural script using an LLM.
    Falls back to None if no API key or any error occurs.
    Strict prompt enforces: use ONLY the supplied facts.
    """
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    features_str = ", ".join(prop.features) if prop.features else "None provided"
    prompt = f"""You are a professional real-estate copywriter. Write a short promotional video script.

STRICT RULES:
- Use ONLY the facts listed below. Do NOT invent any amenities, rooms, views, or details.
- If a feature is not listed, do not mention it.
- Keep the total spoken script under 45 seconds (approx 110–130 words).
- Structure: Intro (name + location + price) → 2–4 feature highlights → Closing CTA.
- Output format must be exactly:

VOICEOVER:
<full spoken text>

SCENES:
1. INTRO | <caption text> | <voiceover for this scene>
2. FEATURE | <caption text> | <voiceover for this scene>
...
N. OUTRO | <caption text> | <voiceover for this scene>

PROPERTY DATA:
Name: {prop.name}
Location: {prop.location}
Price: {prop.price}
Type: {prop.property_type}
Features: {features_str}
CTA: {prop.cta}
Contact: {prop.contact or "N/A"}
"""

    try:
        if gemini_key:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            text = response.text
        elif openai_key:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=600,
            )
            text = resp.choices[0].message.content
        else:
            return None

        return _parse_llm_response(text, prop)
    except Exception as e:
        print(f"[script_generator] LLM call failed: {e}. Falling back to template.")
        return None


def _parse_llm_response(text: str, prop: PropertyInput) -> Optional[VideoScript]:
    """Best-effort parser for the LLM output format."""
    try:
        # Extract full voiceover
        vo_match = re.search(r"VOICEOVER:\s*(.+?)(?=SCENES:|$)", text, re.DOTALL | re.IGNORECASE)
        full_vo = vo_match.group(1).strip() if vo_match else ""

        scenes: List[SceneScript] = []
        scene_pattern = re.compile(
            r"(\d+)\.\s*(INTRO|FEATURE|OUTRO)\s*\|\s*(.+?)\s*\|\s*(.+?)(?=\n\d+\.|$)",
            re.IGNORECASE | re.DOTALL,
        )
        for m in scene_pattern.finditer(text):
            stype = m.group(2).lower()
            caption = m.group(3).strip()
            voice = m.group(4).strip()
            scenes.append(
                SceneScript(
                    scene_type=stype,
                    caption=caption,
                    voiceover=voice,
                    duration_hint=5.5 if stype != "intro" else 6.5,
                )
            )

        if not scenes:
            return None

        if not full_vo:
            full_vo = " ".join(s.voiceover for s in scenes)

        return VideoScript(
            full_voiceover=full_vo,
            scenes=scenes,
            title=f"{prop.name} – {prop.location}",
        )
    except Exception:
        return None


def generate_script(prop: PropertyInput, prefer_llm: bool = True) -> VideoScript:
    """
    Main entry point.
    Tries LLM first (if keys present and prefer_llm=True), otherwise uses template.
    Always returns a valid VideoScript.
    """
    if prefer_llm:
        llm_script = generate_llm_script(prop)
        if llm_script is not None:
            print("[script_generator] Using LLM-generated script.")
            return llm_script
    print("[script_generator] Using deterministic template script.")
    return generate_template_script(prop)


# ---------------------------------------------------------------------------
# Convenience helper for quick testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample = PropertyInput(
        name="Skyline Apartments",
        location="Downtown Austin, TX",
        price="$450,000",
        property_type="2-BHK Apartment",
        features=["Open-plan kitchen", "Floor-to-ceiling windows", "Smart home system", "Rooftop terrace", "24/7 concierge"],
        cta="Schedule your private tour today!",
        contact="Call 512-555-0199",
    )
    script = generate_script(sample, prefer_llm=False)
    print("Title:", script.title)
    print("\nFull VO:\n", script.full_voiceover)
    print("\nScenes:")
    for i, s in enumerate(script.scenes, 1):
        print(f"  {i}. [{s.scene_type}] {s.caption[:60]}...")
