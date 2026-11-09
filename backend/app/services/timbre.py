import logging
from typing import Literal

import httpx

from app.config import get_prisma_api_key

logger = logging.getLogger(__name__)

TIMBRE_TTS_ENDPOINT = "https://api.vachana.ai/api/v1/tts/inference"
TIMBRE_TIMEOUT_SECONDS = 60.0

TIMBRE_VOICES = {
    "timbre-v2.5": {
        "Ambuja", "Asmita", "Bhavna", "Brinda", "Chitra", "Deepak",
        "Devika", "Dhruva", "Falak", "Girish", "Hemraj", "Ishaan",
        "Jalaj", "Jwala", "Kaveri", "Kavin", "Kirra", "Lavanya",
        "Lehara", "Mehuli", "Nalini", "Noopur", "Omkar", "Poorvi",
        "Pranav", "Reshma", "Riyaan", "Roopesh", "Saanvi", "Shlok",
        "Suhana", "Trisha", "Trupti", "Urmila", "Varuni", "Vedika",
        "Veera", "Vikrant", "Yashvi", "Yukti", "Zahira", "Zayan",
    },
    "timbre-v3.0": {
        "Avinash", "Chetana", "Devansh", "Harshad", "Kalpana",
        "Lakshmi", "Prakash", "Riyaa", "Shivani", "Shubham",
        "Tarika", "Vasudha", "Yashraj",
    },
}

TTS_LANGUAGES = {
    "auto", "hi-IN", "en-IN", "ta-IN", "te-IN", "kn-IN",
    "ml-IN", "mr-IN", "pa-IN", "bn-IN", "gu-IN", "hi-en",
}


class TimbreConfigurationError(Exception):
    """Raised when the Gnani API key is missing."""


class TimbreTimeoutError(Exception):
    """Raised when Gnani TTS does not respond before the timeout."""


class TimbreAuthenticationError(Exception):
    """Raised when Gnani rejects credentials or the requested service scope."""


class TimbreRateLimitError(Exception):
    """Raised when Gnani applies an account or service rate limit."""


class TimbreUpstreamError(Exception):
    """Raised when the Gnani TTS request or response is unsuccessful."""


async def synthesize(
    text: str,
    model: Literal["timbre-v2.5", "timbre-v3.0"],
    voice: str,
    language: str,
) -> tuple[bytes, str]:
    api_key = get_prisma_api_key()
    if not api_key:
        raise TimbreConfigurationError

    payload = {
        "text": text,
        "voice": voice,
        "model": model,
        "language": language,
        "audio_config": {
            "sample_rate": 48000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=TIMBRE_TIMEOUT_SECONDS) as client:
            response = await client.post(
                TIMBRE_TTS_ENDPOINT,
                headers={"X-API-Key-ID": api_key},
                json=payload,
            )
            if response.status_code in {401, 403}:
                raise TimbreAuthenticationError
            if response.status_code == 429:
                raise TimbreRateLimitError
            response.raise_for_status()
    except TimbreAuthenticationError:
        raise
    except TimbreRateLimitError:
        raise
    except httpx.TimeoutException as exc:
        raise TimbreTimeoutError from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "Gnani TTS request failed with status %s",
            getattr(getattr(exc, "response", None), "status_code", "unavailable"),
        )
        raise TimbreUpstreamError from exc

    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type != "audio/wav" or not response.content:
        raise TimbreUpstreamError
    return response.content, content_type
