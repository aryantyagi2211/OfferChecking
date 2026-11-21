import asyncio
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent.parent / ".env")


async def main() -> None:
    you_key = os.getenv("YOU_API_KEY", "")
    llm_key = os.getenv("LLM_API_KEY", "")
    extract_model = os.getenv("EXTRACT_MODEL", "")
    analyze_model = os.getenv("ANALYZE_MODEL", "")

    print("config", {
        "you": bool(you_key),
        "llm": bool(llm_key),
        "extract_model": bool(extract_model),
        "analyze_model": bool(analyze_model),
    })

    if you_key:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://ydc-index.io/v1/search",
                headers={"X-API-Key": you_key, "Content-Type": "application/json"},
                json={"query": "Northgate Technologies official website", "count": 2, "country": "IN"},
            )
            result_count = 0
            if response.headers.get("content-type", "").startswith("application/json"):
                result_count = len(response.json().get("results", []))
            print("you_status", response.status_code, "results", result_count)

    if llm_key and analyze_model:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{analyze_model}:generateContent",
                params={"key": llm_key},
                json={
                    "contents": [{"role": "user", "parts": [{"text": "Reply with exactly OK"}]}],
                    "generationConfig": {"temperature": 0, "maxOutputTokens": 8},
                },
            )
            if response.status_code == 200:
                print("gemini_status", response.status_code, "ok", True)
            else:
                try:
                    error = response.json().get("error", {})
                    print("gemini_status", response.status_code, "error", error.get("status"), "message", error.get("message", "")[:200])
                except Exception:
                    print("gemini_status", response.status_code, "ok", False)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": llm_key, "pageSize": 100},
            )
            if response.status_code == 200:
                names = [
                    item["name"].removeprefix("models/")
                    for item in response.json().get("models", [])
                    if "generateContent" in item.get("supportedGenerationMethods", [])
                ]
                print("available_generate_models", names[:20])
            else:
                print("models_list_status", response.status_code)


asyncio.run(main())
