from fastapi.testclient import TestClient

from app.main import RequestSizeLimitMiddleware, app
from app.routers import coding, voice
from app.services.prisma import PrismaAuthenticationError
from app.services.timbre import TimbreAuthenticationError

client = TestClient(app)


def test_health_swagger_and_agent_status(monkeypatch):
    async def unavailable():
        return {"available": False, "runtime": "ollama", "model": "gemma4:e4b"}

    monkeypatch.setattr(coding.agent, "status", unavailable)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/openapi.json").status_code == 200
    status = client.get("/api/v1/coding/status")
    assert status.status_code == 200
    assert status.json()["available"] is False


def test_proposal_endpoint_reports_unavailable_runtime(monkeypatch):
    from app.services.gemma_agent import AgentRuntimeUnavailable

    async def unavailable(_instruction):
        raise AgentRuntimeUnavailable("Gemma 4 model is not installed")

    monkeypatch.setattr(coding.agent, "propose", unavailable)
    response = client.post(
        "/api/v1/coding/proposals",
        json={"instruction": "Add a test"},
    )
    assert response.status_code == 503
    assert "Gemma 4 model is not installed" in response.json()["error"]["message"]


def test_transcription_validates_audio_upload(monkeypatch):
    unsupported = client.post(
        "/api/v1/voice/transcribe",
        files={"audio_file": ("recording.webm", b"sample", "audio/webm")},
    )
    assert unsupported.status_code == 415

    import app.routers.voice as voice_router

    monkeypatch.setattr(voice_router, "MAX_AUDIO_UPLOAD_BYTES", 4)
    oversized = client.post(
        "/api/v1/voice/transcribe",
        files={"audio_file": ("recording.wav", b"12345", "audio/wav")},
    )
    assert oversized.status_code == 413


def test_transcription_does_not_expose_provider_auth_body(monkeypatch):
    async def rejected(*args, **kwargs):
        raise PrismaAuthenticationError

    monkeypatch.setattr(voice, "transcribe_audio", rejected)
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"audio_file": ("recording.wav", b"sample", "audio/wav")},
    )
    assert response.status_code == 502
    assert response.json()["error"]["message"] == (
        "Gnani authentication or speech service scope was rejected"
    )


def test_tts_validates_model_voice_and_credentials(monkeypatch):
    invalid_voice = client.post(
        "/api/v1/voice/synthesize",
        json={
            "text": "Test",
            "model": "timbre-v3.0",
            "voice": "Nalini",
            "language": "hi-IN",
        },
    )
    assert invalid_voice.status_code == 422

    monkeypatch.delenv("GNANI_API_KEY_ID", raising=False)
    no_credentials = client.post(
        "/api/v1/voice/synthesize",
        json={"text": "नमस्ते"},
    )
    assert no_credentials.status_code == 503


def test_tts_does_not_expose_provider_auth_body(monkeypatch):
    async def rejected(*args, **kwargs):
        raise TimbreAuthenticationError

    monkeypatch.setattr(voice, "synthesize", rejected)
    response = client.post(
        "/api/v1/voice/synthesize",
        json={"text": "Hello", "voice": "Kaveri", "language": "en-IN"},
    )
    assert response.status_code == 502
    assert response.json()["error"]["message"] == (
        "Gnani authentication or TTS service scope was rejected"
    )


def test_cors_preflight_allows_configured_frontend_origin():
    response = client.options(
        "/api/v1/voice/transcribe",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_asgi_request_size_limit_rejects_chunked_oversize_body():
    async def unused_app(scope, receive, send):
        raise AssertionError("Oversized request reached the application")

    messages = iter(
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"456", "more_body": False},
        ]
    )
    sent = []

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    middleware = RequestSizeLimitMiddleware(unused_app, max_size=5)
    import anyio

    anyio.run(middleware, {"type": "http", "headers": []}, receive, send)

    assert sent[0]["status"] == 413
    assert b"http_413" in sent[1]["body"]
