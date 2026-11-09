import os
from pathlib import Path

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.routers import voice
from app.services.prisma import PrismaTimeoutError, PrismaUpstreamError

client = TestClient(app)


def test_app_exports_fastapi_instance_and_health_routes() -> None:
    assert app.title == "Voice2Code"
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}


def test_environment_file_can_be_loaded_without_printing_key(
    tmp_path: Path, monkeypatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GNANI_API_KEY_ID=test-only-placeholder\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GNANI_API_KEY_ID", raising=False)

    try:
        config.load_environment(env_file)
        assert config.get_prisma_api_key() == "test-only-placeholder"
    finally:
        os.environ.pop("GNANI_API_KEY_ID", None)


def test_transcription_reports_missing_credentials(
    monkeypatch,
) -> None:
    monkeypatch.delenv("GNANI_API_KEY_ID", raising=False)
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"audio_file": ("sample.wav", b"test audio", "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "http_503",
            "message": "Gnani API credentials are not configured",
        }
    }


def test_transcription_maps_provider_timeout(monkeypatch) -> None:
    async def timeout(*args, **kwargs):
        raise PrismaTimeoutError

    monkeypatch.setattr(voice, "transcribe_audio", timeout)
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"audio_file": ("sample.wav", b"test audio", "audio/wav")},
    )

    assert response.status_code == 504


def test_transcription_maps_provider_failure(monkeypatch) -> None:
    async def provider_error(*args, **kwargs):
        raise PrismaUpstreamError

    monkeypatch.setattr(voice, "transcribe_audio", provider_error)
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"audio_file": ("sample.wav", b"test audio", "audio/wav")},
    )

    assert response.status_code == 502
