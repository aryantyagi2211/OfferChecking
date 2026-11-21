import os

from models import ExtractedOffer
from llm import PROMPTS, gemini_json


async def extract_offer(text: str) -> ExtractedOffer:
    prompt = (PROMPTS / "extractor.txt").read_text(encoding="utf-8")
    model = os.getenv("EXTRACT_MODEL")
    if not model:
        raise RuntimeError("EXTRACT_MODEL is not configured")

    result = await gemini_json(prompt, {"offer_text": text}, model)
    return ExtractedOffer.model_validate(result)
