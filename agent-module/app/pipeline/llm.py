import google.generativeai as genai

from app.config import get_settings

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)
_model = genai.GenerativeModel("gemini-2.5-flash")


def call_llm(prompt: str, temperature: float = 0.0) -> str:
    response = _model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    return response.text or "[]"
