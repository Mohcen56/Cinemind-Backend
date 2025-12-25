import os
import requests
from django.conf import settings

# Simple wrappers for Groq and GitHub Models (OpenAI-compatible chat APIs)
# Returns plain text content from the first choice, or raises Exception

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions"

# Reasonable default models
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GITHUB_MODEL = os.getenv("GITHUB_MODEL", "gpt-4o")

TIMEOUT = 20


def chat_with_groq(prompt: str, system: str = None, temperature: float = 0.4) -> str:
    api_key = getattr(settings, "GROQ_API_KEY", None)
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured")

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
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "text"},
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def chat_with_github_models(prompt: str, system: str = None, temperature: float = 0.4) -> str:
    api_key = getattr(settings, "GITHUB_API_KEY", None)
    if not api_key:
        raise RuntimeError("GITHUB_API_KEY not configured")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = requests.post(
        GITHUB_MODELS_ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GITHUB_MODEL,
            "messages": messages,
            "temperature": temperature,
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    # GitHub Models uses the same shape as OpenAI chat completions
    if "choices" in data and data["choices"]:
        return data["choices"][0]["message"]["content"]
    # Some deployments place text under 'output_text'
    return data.get("output_text", "")


# Lightweight heuristic to choose provider: Groq for simple, GitHub for hard
HARD_KEYWORDS = [
    "why", "explain", "analyze", "comparison", "compare", "plan", "strategy",
    "step by step", "reason", "justify", "tradeoff", "evaluate", "how to design",
]


def choose_provider(user_query: str, needs_personalization: bool) -> str:
    q = (user_query or "").lower()
    if needs_personalization:
        return "github"  # smarter for nuanced recommendations
    if any(k in q for k in HARD_KEYWORDS):
        return "github"
    if len(q) > 220:
        return "github"
    return "groq"
