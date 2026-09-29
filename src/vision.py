import json
import re

from pydantic import ValidationError

from .config import GEMINI_MODEL, VISION_API_KEY
from .models import VisionResponse

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class VisionError(Exception):
    """User-facing vision failure. Live mode does not switch to mock on error."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def build_prompt(names: list[str]) -> str:
    name_lines = "\n".join(f"- {name}" for name in names)
    return f"""Analyze this meal photo.

Choose each food name by copying a value EXACTLY from this list:
{name_lines}

Return JSON only (no markdown fences) with this shape:
{{
  "items": [
    {{
      "name": "<exact name from the list>",
      "grams": <estimated portion weight in grams, positive number>,
      "confidence": <number between 0.0 and 1.0>
    }}
  ],
  "notes": "<short note about uncertainty, hidden items, or sauces>"
}}

Rules:
- Produce name, grams, and confidence (0.0-1.0) for every detected food.
- Prefer names from the list. If a visible food is not on the list, still include it; our code will mark it unknown.
- Do not return calories, protein, carbohydrates, or fat.
"""


def strip_json_fences(text: str) -> str:
    stripped = text.strip()
    match = _FENCE_RE.search(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def parse_vision_json(text: str) -> VisionResponse:
    cleaned = strip_json_fences(text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise VisionError(
            "The vision model returned invalid JSON. Please try another photo."
        ) from exc
    try:
        return VisionResponse.model_validate(payload)
    except ValidationError as exc:
        raise VisionError(
            "The vision model returned JSON that does not match the expected items/notes schema."
        ) from exc


def _generate_content(image_bytes: bytes, mime_type: str, prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=VISION_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    text = (response.text or "").strip()
    if not text:
        raise VisionError("The vision model returned an empty response. Please try again.")
    return text


def analyze_image(image_bytes: bytes, mime_type: str, names: list[str]) -> VisionResponse:
    if not VISION_API_KEY:
        raise VisionError("VISION_API_KEY is missing. Set it in .env to use live vision.")

    prompt = build_prompt(names)
    last_error: VisionError | None = None
    for _ in range(2):
        try:
            raw = _generate_content(image_bytes, mime_type, prompt)
            parsed = parse_vision_json(raw)
        except VisionError as exc:
            last_error = exc
            continue
        except Exception:
            last_error = VisionError(
                "The vision model could not be reached. Check VISION_API_KEY and try again."
            )
            continue
        if not parsed.items:
            last_error = VisionError(
                "No foods were detected in the photo. Try a closer, well-lit photo."
            )
            continue
        return parsed

    raise last_error or VisionError("The vision model returned an unusable response.")
