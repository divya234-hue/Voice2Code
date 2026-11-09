import logging
from typing import Any

import httpx

from app.config import get_prisma_api_key

logger = logging.getLogger(__name__)

PRISMA_STT_ENDPOINT = "https://api.vachana.ai/stt/v3"
PRISMA_MODEL = "prisma-v3.0"
REQUEST_TIMEOUT_SECONDS = 60.0
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a"}


class PrismaConfigurationError(Exception):
    """Raised when the Gnani API key is missing."""


class PrismaTimeoutError(Exception):
    """Raised when Gnani does not respond before the request timeout."""


class PrismaAuthenticationError(Exception):
    """Raised when Gnani rejects credentials or the requested service scope."""


class PrismaRateLimitError(Exception):
    """Raised when Gnani applies an account or service rate limit."""


class PrismaUpstreamError(Exception):
    """Raised when the Gnani request or response is unsuccessful."""


async def transcribe_audio(
    audio: bytes,
    filename: str,
    content_type: str,
    language_code: str,
) -> dict[str, Any]:
    api_key = get_prisma_api_key()
    if not api_key:
        raise PrismaConfigurationError

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                PRISMA_STT_ENDPOINT,
                headers={"X-API-Key-ID": api_key},
                files={"audio_file": (filename, audio, content_type)},
                data={"model": PRISMA_MODEL, "language_code": language_code},
            )
            if response.status_code in {401, 403}:
                raise PrismaAuthenticationError
            if response.status_code == 429:
                raise PrismaRateLimitError
            response.raise_for_status()
            payload = response.json()
    except PrismaAuthenticationError:
        raise
    except PrismaRateLimitError:
        raise
    except httpx.TimeoutException as exc:
        raise PrismaTimeoutError from exc
    except httpx.HTTPError as exc:
        logger.warning("Gnani STT request failed with status %s", getattr(
            getattr(exc, "response", None), "status_code", "unavailable"
        ))
        raise PrismaUpstreamError from exc
    except ValueError as exc:
        raise PrismaUpstreamError from exc

    if (
        not isinstance(payload, dict)
        or payload.get("success") is not True
        or not isinstance(payload.get("transcript"), str)
    ):
        raise PrismaUpstreamError
    return payload
