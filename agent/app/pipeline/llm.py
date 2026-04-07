import re
import time

from groq import Groq

from app.config import get_settings

settings = get_settings()
_client = Groq(api_key=settings.groq_api_key)

_fallback_count = 0


def _wait_from_error(exc_str: str) -> float:
    m = re.search(r"try again in (\d+(?:\.\d+)?)s", exc_str)
    if m:
        return float(m.group(1)) + 1
    m = re.search(r"try again in (\d+)m", exc_str)
    if m:
        return float(m.group(1)) * 60 + 5
    return 15


def _create(model: str, prompt: str, temperature: float) -> str:
    response = _client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content if response.choices else None
    return content or "[]"


def call_llm(prompt: str, temperature: float = 0.0) -> str:
    global _fallback_count
    try:
        return _create(settings.groq_model, prompt, temperature)
    except Exception as exc:
        exc_str = str(exc)
        if "429" not in exc_str and "rate_limit" not in exc_str:
            raise
        if not settings.groq_fallback_model:
            raise
        wait = _wait_from_error(exc_str)
        if wait > 120:
            _fallback_count += 1
            return _create(settings.groq_fallback_model, prompt, temperature)
        time.sleep(min(wait, 30))
        try:
            return _create(settings.groq_model, prompt, temperature)
        except Exception:
            _fallback_count += 1
            return _create(settings.groq_fallback_model, prompt, temperature)


def get_fallback_count() -> int:
    return _fallback_count
