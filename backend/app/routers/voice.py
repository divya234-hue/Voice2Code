import logging
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.config import MAX_AUDIO_UPLOAD_BYTES
from app.services.prisma import (
    SUPPORTED_AUDIO_EXTENSIONS,
    PrismaAuthenticationError,
    PrismaConfigurationError,
    PrismaRateLimitError,
    PrismaTimeoutError,
    PrismaUpstreamError,
    transcribe_audio,
)
from app.services.timbre import (
    TIMBRE_VOICES,
    TTS_LANGUAGES,
    TimbreAuthenticationError,
    TimbreConfigurationError,
    TimbreRateLimitError,
    TimbreTimeoutError,
    TimbreUpstreamError,
    synthesize,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


class TranscriptionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    success: Literal[True]
    transcript: str
    request_id: str | None = None
    model: str | None = None
    detected_language_code: str | None = None


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    model: Literal["timbre-v2.5", "timbre-v3.0"] = "timbre-v2.5"
    voice: str = "Nalini"
    language: str = "hi-IN"


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    audio_file: UploadFile = File(...),
    language_code: str = Form("indic-auto", min_length=1, max_length=64),
) -> TranscriptionResponse:
    suffix = (audio_file.filename or "").rsplit(".", 1)
    extension = f".{suffix[-1].lower()}" if len(suffix) == 2 else ""
    if extension not in SUPPORTED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported audio extension. Use WAV, MP3, OGG, FLAC, AAC, or M4A.",
        )

    audio = await audio_file.read(MAX_AUDIO_UPLOAD_BYTES + 1)
    if len(audio) > MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio upload exceeds the 20 MiB limit")
    if not audio:
        raise HTTPException(status_code=400, detail="Audio upload is empty")

    try:
        payload = await transcribe_audio(
            audio=audio,
            filename=audio_file.filename or f"audio{extension}",
            content_type=audio_file.content_type or "application/octet-stream",
            language_code=language_code,
        )
        return TranscriptionResponse.model_validate(payload)
    except PrismaConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Gnani API credentials are not configured",
        ) from exc
    except PrismaAuthenticationError as exc:
        logger.warning("Gnani rejected STT credentials or service scope")
        raise HTTPException(
            status_code=502,
            detail="Gnani authentication or speech service scope was rejected",
        ) from exc
    except PrismaRateLimitError as exc:
        raise HTTPException(
            status_code=503,
            detail="Gnani speech-to-text rate limit reached; retry later",
        ) from exc
    except PrismaTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Gnani speech-to-text request timed out",
        ) from exc
    except PrismaUpstreamError as exc:
        raise HTTPException(
            status_code=502,
            detail="Gnani speech-to-text service request failed",
        ) from exc


@router.post("/synthesize", responses={200: {"content": {"audio/wav": {}}}})
async def synthesize_explanation(request: SynthesisRequest) -> Response:
    if request.voice not in TIMBRE_VOICES[request.model]:
        raise HTTPException(status_code=422, detail="Voice is not supported by the selected model")
    if request.language not in TTS_LANGUAGES:
        raise HTTPException(status_code=422, detail="Unsupported Timbre language")

    try:
        audio, content_type = await synthesize(
            text=request.text,
            model=request.model,
            voice=request.voice,
            language=request.language,
        )
    except TimbreConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Gnani API credentials are not configured",
        ) from exc
    except TimbreAuthenticationError as exc:
        logger.warning("Gnani rejected TTS credentials or service scope")
        raise HTTPException(
            status_code=502,
            detail="Gnani authentication or TTS service scope was rejected",
        ) from exc
    except TimbreRateLimitError as exc:
        raise HTTPException(status_code=503, detail="Gnani TTS rate limit reached; retry later") from exc
    except TimbreTimeoutError as exc:
        raise HTTPException(status_code=504, detail="Gnani TTS request timed out") from exc
    except TimbreUpstreamError as exc:
        raise HTTPException(status_code=502, detail="Gnani TTS request failed") from exc

    return Response(
        content=audio,
        media_type=content_type,
        headers={"Content-Disposition": 'inline; filename="voice2code.wav"'},
    )
