import requests
from django.conf import settings

# Simple wrapper for Groq's OpenAI-compatible chat API.
# Returns plain text content from the first choice, or raises Exception.

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

TIMEOUT = 20


def chat_with_groq(
    prompt: str,
    system: str = None,
    temperature: float = 0.4,
    model: str = None,
) -> str:
    api_key = getattr(settings, "GROQ_API_KEY", None)
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured")

    selected_model = model or settings.GROQ_MODEL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = requests.post(
        GROQ_ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "text"},
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]
