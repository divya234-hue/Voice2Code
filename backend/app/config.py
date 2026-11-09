import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = BACKEND_DIR / ".env"

MAX_AUDIO_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PATCH_FILES = 20
MAX_PATCH_FILE_BYTES = 1 * 1024 * 1024
MAX_PATCH_TOTAL_BYTES = 5 * 1024 * 1024
TEST_TIMEOUT_SECONDS = 120


def load_environment(env_file: Path = ENV_FILE) -> None:
    load_dotenv(dotenv_path=env_file, override=False)


load_environment()


def get_prisma_api_key() -> str | None:
    value = os.getenv("GNANI_API_KEY_ID")
    return value.strip() if value and value.strip() else None


def get_cors_origins() -> list[str]:
    configured = os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in configured.split(",") if origin.strip()]
