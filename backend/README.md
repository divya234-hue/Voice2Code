# Voice2Code backend

The FastAPI application is started from this directory with
`uvicorn app.main:app --reload`. Swagger UI is available at `/docs`.

## Setup

```powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Set `GNANI_API_KEY_ID` in the local `.env` file. Both Prisma STT and Timbre TTS
use Gnani's documented `X-API-Key-ID` authentication. Do not commit `.env`.
`FRONTEND_ORIGINS` is a comma-separated CORS allowlist; it defaults to
`http://localhost:5173`.

The local Gemma adapter uses the loopback-only Ollama API. The defaults are
`GEMMA_OLLAMA_BASE_URL=http://127.0.0.1:11434` and
`GEMMA_OLLAMA_MODEL=gemma4:e4b`. The Ollama model must be installed locally;
the adapter never downloads weights or falls back to another model. The chosen
model must be from the Gemma 4 family.

## Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Service status |
| GET | `/health` | Health check |
| POST | `/api/v1/voice/transcribe` | Multipart `audio_file` plus optional `language_code` |
| POST | `/api/v1/voice/synthesize` | JSON text/model/voice/language; returns actual WAV bytes |
| GET | `/api/v1/coding/status` | Reports whether a local Gemma runtime is available |
| POST | `/api/v1/coding/proposals` | Requests an agent proposal |
| GET | `/api/v1/coding/patches/{patch_id}` | Views a proposed patch |
| POST | `/api/v1/coding/patches/{patch_id}/approve` | Applies an explicit approval and runs tests |
| POST | `/api/v1/coding/patches/{patch_id}/reject` | Rejects an unapplied patch |
| POST | `/api/v1/coding/patches/{patch_id}/rollback` | Restores files from the applied patch |
| GET | `/api/v1/coding/tests/{run_id}` | Reads a test result |

Prisma uses `https://api.vachana.ai/stt/v3`, model `prisma-v3.0`, and accepts
WAV/MP3/OGG/FLAC/AAC/M4A uploads up to the backend's 20 MiB per-file limit
(with a 21 MiB total HTTP request-body limit).
Gnani's REST endpoint itself limits clips to 30 seconds; longer files are
rejected by Gnani. Timbre uses
`https://api.vachana.ai/api/v1/tts/inference` and returns the real audio response.

## Gemma runtime

The competition YAML remains unchanged and is the source of truth for
competition-harness execution. For this local prototype, the adapter sends the
task and bounded, secret-file-excluding repository context to the explicitly
configured Gemma 4 model through Ollama's `/api/chat` interface, then accepts
only a structured complete-file patch. It does not execute the YAML's
competition-only tools or sub-agents. It requires the user to install Gemma
weights separately; proposal generation returns HTTP 503 with an actionable
setup message while Ollama or the selected model is unavailable. The adapter
never substitutes another model family, fabricates patches, or applies changes.
The model's output remains a proposal and must be approved explicitly.

On Windows, start Ollama and install the configured model in another
PowerShell window:

```powershell
ollama pull gemma4:e4b
ollama list
```

The official Ollama Gemma 4 E4B package is approximately 6.6 GB. This machine's
GPU has 6 GB of VRAM, so loading E4B may require CPU/RAM offload and can be slow
or fail depending on runtime overhead. To use a different *Gemma 4* size, set
`GEMMA_OLLAMA_MODEL` in `.env` to that exact installed Ollama tag. Do not set it
to another model family.

## Safety and testing

Patch application requires a separate approval request, checks each original
file's hash again, rejects traversal/symlinks and protected `.env`/`.git` paths,
and keeps in-memory originals for rollback while the backend process is alive.
Patch/test records and rollback data are not persistent across server restarts.
The test runner executes only `python -m pytest -q` from the project root with a
120-second timeout; it does not accept arbitrary command strings.

The API is intended for local development on loopback. It has no user
authentication, so do not expose it to an untrusted network. Standard offline
tests use mocked HTTP responses; live Gnani calls require a real API key.

```powershell
python -m pytest
python -m compileall -q app tests test_backend.py
```
