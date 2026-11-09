import logging
from collections import deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import MAX_AUDIO_UPLOAD_BYTES, get_cors_origins
from app.routers.coding import router as coding_router
from app.routers.voice import router as voice_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


class RequestSizeLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        max_size: int = MAX_AUDIO_UPLOAD_BYTES + 1024 * 1024,
    ) -> None:
        self.app = app
        self.max_size = max_size

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_size:
                    await self._reject(send)
                    return
            except ValueError:
                await self._reject(send)
                return

        messages: list[Message] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.max_size:
                await self._reject(send)
                return
            messages.append(message)
            if not message.get("more_body", False):
                break

        buffered = deque(messages)

        async def replay() -> Message:
            return buffered.popleft() if buffered else await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = (
            b'{"error":{"code":"http_413",'
            b'"message":"Request body exceeds the configured size limit"}}'
        )
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


app = FastAPI(
    title="Voice2Code",
    description="Indian-language voice interface for the Gemma 4 coding agent.",
    version="0.1.0",
)
app.add_middleware(
    RequestSizeLimitMiddleware,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(HTTPException)
async def handle_http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"http_{exc.status_code}",
                "message": exc.detail,
            }
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    _request: Request, _exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "invalid_request",
                "message": "Request validation failed",
            }
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
    logger.error("Unhandled backend error (%s)", type(_exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "The request could not be completed",
            }
        },
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Voice2Code backend is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(voice_router)
app.include_router(coding_router)
