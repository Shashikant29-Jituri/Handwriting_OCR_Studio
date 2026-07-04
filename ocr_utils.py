"""
ocr_utils.py
Multi-provider vision OCR (Anthropic Claude / OpenAI GPT / Google Gemini).
Handles handwritten-image-to-text extraction across multiple languages,
returning both plain text and a lightweight layout structure
(paragraphs / bullets / table rows) for layout-preserving export.
"""

import base64
import io
import json
import os
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image

# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------

LANGUAGES = {
    "English": "en",
    "Hindi": "hi",
    "Kannada": "kn",
    "Tamil": "ta",
    "Telugu": "te",
    "Bengali": "bn",
    "Marathi": "mr",
}

# Fonts used later by export_utils.py for each language (Noto family covers all of these)
LANGUAGE_FONTS = {
    "en": "NotoSans",
    "hi": "NotoSansDevanagari",
    "mr": "NotoSansDevanagari",   # Marathi also uses Devanagari script
    "kn": "NotoSansKannada",
    "ta": "NotoSansTamil",
    "te": "NotoSansTelugu",
    "bn": "NotoSansBengali",
}

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

MODELS = {
    "Claude Sonnet 4.6 (Anthropic)": "anthropic",
    "Claude Opus 4.6 (Anthropic)": "anthropic",
    "GPT-5.4 Vision (OpenAI)": "openai",
    "GPT-4o Vision (OpenAI)": "openai",
    "Gemini 3 Flash (Google) — free tier": "google",
    "Gemini 3.1 Flash-Lite (Google) — free tier": "google",
    "Gemini 3.1 Pro (Google) — paid only": "google",
}

ANTHROPIC_MODEL_IDS = {
    "Claude Sonnet 4.6 (Anthropic)": "claude-sonnet-4-6",
    "Claude Opus 4.6 (Anthropic)": "claude-opus-4-6",
}
OPENAI_MODEL_IDS = {
    "GPT-5.4 Vision (OpenAI)": "gpt-5.4",
    "GPT-4o Vision (OpenAI)": "gpt-4o",
}
GOOGLE_MODEL_IDS = {
    "Gemini 3 Flash (Google) — free tier": "gemini-3-flash",
    "Gemini 3.1 Flash-Lite (Google) — free tier": "gemini-3.1-flash-lite",
    "Gemini 3.1 Pro (Google) — paid only": "gemini-3.1-pro",
}


@dataclass
class OcrBlock:
    """One structural unit of the extracted page: paragraph, bullet, heading, or table row."""
    kind: str                      # "paragraph" | "bullet" | "heading" | "table_row"
    text: str = ""
    cells: list = field(default_factory=list)   # populated when kind == "table_row"
    level: int = 0                 # indent / heading level


@dataclass
class OcrResult:
    filename: str
    page_number: int
    language: str
    raw_text: str
    blocks: list  # list[OcrBlock]
    error: Optional[str] = None


SYSTEM_PROMPT_TEMPLATE = """You are an expert OCR and handwriting transcription engine.
Transcribe ALL text visible in the image exactly as written, in {language}.
Preserve the original wording -- do not translate, summarize, or correct spelling.

Then return your answer as STRICT JSON only (no markdown fences, no commentary) matching this schema:

{{
  "blocks": [
    {{"kind": "heading", "text": "...", "level": 1}},
    {{"kind": "paragraph", "text": "..."}},
    {{"kind": "bullet", "text": "...", "level": 1}},
    {{"kind": "table_row", "cells": ["col1", "col2", "col3"]}}
  ]
}}

Rules:
- Use "bullet" for any bulleted or numbered list item (keep original numbering/markers inside the text if present).
- Use "table_row" whenever content is visually arranged in a grid/table, one object per row, including header rows.
- Use "heading" for titles/section headers, "level" 1-3 by visual prominence.
- Use "paragraph" for normal running text or handwriting lines that aren't list items.
- If the image contains multiple columns, transcribe left column fully, then right column, and note the column break with a heading block "-- column break --" only if genuinely two-column.
- If nothing is legible, return {{"blocks": []}}.
"""


def _image_to_base64(image: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _parse_json_blocks(raw: str) -> list:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1) if cleaned.startswith("json\n") else cleaned
    try:
        data = json.loads(cleaned)
        blocks = []
        for b in data.get("blocks", []):
            blocks.append(OcrBlock(
                kind=b.get("kind", "paragraph"),
                text=b.get("text", ""),
                cells=b.get("cells", []),
                level=b.get("level", 0),
            ))
        return blocks
    except Exception:
        # Fallback: treat the whole raw response as one paragraph block
        return [OcrBlock(kind="paragraph", text=raw.strip())] if raw.strip() else []


def _blocks_to_plain_text(blocks: list) -> str:
    lines = []
    for b in blocks:
        if b.kind == "table_row":
            lines.append(" | ".join(b.cells))
        elif b.kind == "bullet":
            lines.append(("  " * max(b.level - 1, 0)) + "- " + b.text)
        elif b.kind == "heading":
            lines.append(b.text.upper())
        else:
            lines.append(b.text)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Provider calls
# ---------------------------------------------------------------------------

def _call_anthropic(image: Image.Image, model_id: str, language: str, api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    b64 = _image_to_base64(image)
    system = SYSTEM_PROMPT_TEMPLATE.format(language=language)
    resp = client.messages.create(
        model=model_id,
        max_tokens=4096,
        system=system,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": "Transcribe this image per the JSON schema."},
            ],
        }],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def _call_openai(image: Image.Image, model_id: str, language: str, api_key: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    b64 = _image_to_base64(image)
    system = SYSTEM_PROMPT_TEMPLATE.format(language=language)
    resp = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": [
                {"type": "text", "text": "Transcribe this image per the JSON schema."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]},
        ],
        max_tokens=4096,
    )
    return resp.choices[0].message.content


def _call_google(image: Image.Image, model_id: str, language: str, api_key: str) -> str:
    # Uses the current Google Gen AI SDK (the older `google-generativeai` package is deprecated).
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    system = SYSTEM_PROMPT_TEMPLATE.format(language=language)
    resp = client.models.generate_content(
        model=model_id,
        contents=[system, image],
    )
    return resp.text


PROVIDER_FUNCS = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "google": _call_google,
}
MODEL_ID_MAPS = {
    "anthropic": ANTHROPIC_MODEL_IDS,
    "openai": OPENAI_MODEL_IDS,
    "google": GOOGLE_MODEL_IDS,
}


def run_ocr(image: Image.Image, model_label: str, language_name: str,
            filename: str = "image", page_number: int = 1) -> OcrResult:
    """Run OCR on a single image using the selected model + language."""
    provider = MODELS.get(model_label)
    if provider is None:
        return OcrResult(filename, page_number, language_name, "", [],
                          error=f"Unknown model '{model_label}'")

    key_env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "google": "GOOGLE_API_KEY"}[provider]
    api_key = os.environ.get(key_env, "")
    if not api_key:
        return OcrResult(filename, page_number, language_name, "", [],
                          error=f"Missing {key_env}. Add it in the sidebar or your .env file.")

    model_id = MODEL_ID_MAPS[provider][model_label]
    try:
        raw = PROVIDER_FUNCS[provider](image, model_id, language_name, api_key)
    except Exception as exc:
        return OcrResult(filename, page_number, language_name, "", [], error=str(exc))

    blocks = _parse_json_blocks(raw)
    plain = _blocks_to_plain_text(blocks)
    return OcrResult(filename, page_number, language_name, plain, blocks)
