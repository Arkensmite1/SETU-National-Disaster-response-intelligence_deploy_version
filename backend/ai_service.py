"""Mistral wrapper — calls the Mistral AI API directly.

Previously this went through Emergent's Universal LLM proxy
(emergentintegrations.llm.chat.LlmChat), which only works inside the
Emergent platform. This version talks to https://api.mistral.ai
directly with a normal Mistral API key, so it works anywhere
(Render, your own server, etc). Function signatures are unchanged —
server.py did not need any edits.
"""
import os
from typing import AsyncGenerator, Optional

try:
    # mistralai >= 2.0
    from mistralai.client import Mistral
except ImportError:
    # mistralai < 2.0
    from mistralai import Mistral

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MODEL_NAME = os.environ.get("MISTRAL_MODEL", "mistral-large-latest")
VISION_MODEL_NAME = os.environ.get("MISTRAL_VISION_MODEL", "pixtral-12b-latest")

_client = Mistral(api_key=MISTRAL_API_KEY)

DISASTER_SYSTEM_PROMPT = (
    "You are 'Setu' — the official multilingual AI assistant of the National Disaster "
    "Response Intelligence Platform, Government of India. You help citizens, volunteers "
    "and government officials during floods and other disasters. "
    "Guidelines: (1) Respond in the same language the user writes in — Hindi, English, "
    "Bengali, Tamil, Malayalam, Marathi, etc. (2) Be concise, actionable and calm. "
    "(3) Prioritise safety over administrative detail. (4) Always suggest calling 1078 "
    "(NDMA) for life-threatening emergencies. (5) Cite official sources when possible. "
    "(6) Do not speculate about political or blame-oriented topics."
)


async def stream_chat(session_id: str, text: str) -> AsyncGenerator[str, None]:
    stream = await _client.chat.stream_async(
        model=MODEL_NAME,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": DISASTER_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    async for event in stream:
        delta = event.data.choices[0].delta.content
        if delta:
            yield delta


async def generate_text(prompt: str, system: Optional[str] = None) -> str:
    resp = await _client.chat.complete_async(
        model=MODEL_NAME,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system or DISASTER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


async def analyze_image(prompt: str, image_base64: str, system: Optional[str] = None) -> str:
    # Build a data: URL if the frontend sent raw base64 without one already.
    data_url = image_base64
    if not data_url.startswith("data:"):
        data_url = f"data:image/jpeg;base64,{image_base64}"

    resp = await _client.chat.complete_async(
        model=VISION_MODEL_NAME,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system or DISASTER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": data_url},
                ],
            },
        ],
    )
    return (resp.choices[0].message.content or "").strip()
