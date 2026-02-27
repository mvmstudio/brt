"""
Groq client factory for fast AI inference.
Groq API is OpenAI-compatible. Uses SOCKS5 proxy for access from Russia.
"""
import httpx
from openai import OpenAI

from app.config import settings


def create_groq_client() -> OpenAI:
    """Create OpenAI client configured for Groq API with SOCKS5 proxy."""
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not set in environment")

    http_client = httpx.Client(
        proxy=settings.groq_proxy_url,
        timeout=httpx.Timeout(180.0, connect=15.0),
    )

    return OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        http_client=http_client,
    )
