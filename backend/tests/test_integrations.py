import httpx
import pytest

from app.services import prisma, timbre
from app.services.prisma import (
    PrismaAuthenticationError,
    PrismaRateLimitError,
    PrismaUpstreamError,
)
from app.services.timbre import TimbreAuthenticationError, TimbreRateLimitError

REAL_ASYNC_CLIENT = httpx.AsyncClient


@pytest.mark.anyio
async def test_prisma_sends_documented_request_and_parses_real_response(monkeypatch):
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["key"] = request.headers["X-API-Key-ID"]
        observed["content_type"] = request.headers["content-type"]
        observed["body"] = request.read().decode("latin-1")
        return httpx.Response(
            200,
            json={
                "success": True,
                "request_id": "test-request",
                "transcript": "नमस्ते",
                "model": "prisma-v3.0",
            },
        )

    monkeypatch.setenv("GNANI_API_KEY_ID", "test-only-key")
    monkeypatch.setattr(
        prisma.httpx,
        "AsyncClient",
        lambda **kwargs: REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )

    response = await prisma.transcribe_audio(
        audio=b"sample bytes",
        filename="speech.wav",
        content_type="audio/wav",
        language_code="indic-auto",
    )

    assert response["transcript"] == "नमस्ते"
    assert observed["url"] == "https://api.vachana.ai/stt/v3"
    assert observed["key"] == "test-only-key"
    assert "name=\"audio_file\"" in observed["body"]
    assert "name=\"model\"" in observed["body"]
    assert "prisma-v3.0" in observed["body"]
    assert "indic-auto" in observed["body"]


@pytest.mark.anyio
async def test_prisma_maps_provider_auth_and_invalid_json(monkeypatch):
    monkeypatch.setenv("GNANI_API_KEY_ID", "test-only-key")

    def auth_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "do not leak provider body"})

    monkeypatch.setattr(
        prisma.httpx,
        "AsyncClient",
        lambda **kwargs: REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(auth_handler), **kwargs
        ),
    )
    with pytest.raises(PrismaAuthenticationError):
        await prisma.transcribe_audio(b"a", "speech.wav", "audio/wav", "hi-IN")

    def invalid_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    monkeypatch.setattr(
        prisma.httpx,
        "AsyncClient",
        lambda **kwargs: REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(invalid_handler), **kwargs
        ),
    )
    with pytest.raises(PrismaUpstreamError):
        await prisma.transcribe_audio(b"a", "speech.wav", "audio/wav", "hi-IN")


@pytest.mark.anyio
async def test_prisma_maps_provider_rate_limit(monkeypatch):
    monkeypatch.setenv("GNANI_API_KEY_ID", "test-only-key")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    monkeypatch.setattr(
        prisma.httpx,
        "AsyncClient",
        lambda **kwargs: REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    with pytest.raises(PrismaRateLimitError):
        await prisma.transcribe_audio(b"a", "speech.wav", "audio/wav", "hi-IN")


@pytest.mark.anyio
async def test_timbre_sends_documented_json_and_returns_audio(monkeypatch):
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["key"] = request.headers["X-API-Key-ID"]
        observed["body"] = request.read().decode()
        return httpx.Response(200, content=b"actual-test-wav", headers={"content-type": "audio/wav"})

    monkeypatch.setenv("GNANI_API_KEY_ID", "test-only-key")
    monkeypatch.setattr(
        timbre.httpx,
        "AsyncClient",
        lambda **kwargs: REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    audio, content_type = await timbre.synthesize(
        "नमस्ते", "timbre-v2.5", "Nalini", "hi-IN"
    )

    assert audio == b"actual-test-wav"
    assert content_type == "audio/wav"
    assert observed["url"] == "https://api.vachana.ai/api/v1/tts/inference"
    assert observed["key"] == "test-only-key"
    assert '"model":"timbre-v2.5"' in observed["body"]
    assert '"voice":"Nalini"' in observed["body"]
    assert '"language":"hi-IN"' in observed["body"]


@pytest.mark.anyio
async def test_timbre_maps_authentication_error(monkeypatch):
    monkeypatch.setenv("GNANI_API_KEY_ID", "test-only-key")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "private provider detail"})

    monkeypatch.setattr(
        timbre.httpx,
        "AsyncClient",
        lambda **kwargs: REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    with pytest.raises(TimbreAuthenticationError):
        await timbre.synthesize("Hello", "timbre-v2.5", "Kaveri", "en-IN")


@pytest.mark.anyio
async def test_timbre_maps_provider_rate_limit(monkeypatch):
    monkeypatch.setenv("GNANI_API_KEY_ID", "test-only-key")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    monkeypatch.setattr(
        timbre.httpx,
        "AsyncClient",
        lambda **kwargs: REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    with pytest.raises(TimbreRateLimitError):
        await timbre.synthesize("Hello", "timbre-v2.5", "Kaveri", "en-IN")
