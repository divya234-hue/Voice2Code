import os
import re
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import PROJECT_ROOT, TEST_TIMEOUT_SECONDS


def _redact_secrets(output: str) -> str:
    secret_values = {
        value
        for name, value in os.environ.items()
        if value and re.search(r"(?:API_KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", name, re.I)
    }
    for secret in sorted(secret_values, key=len, reverse=True):
        output = output.replace(secret, "[REDACTED]")
    return output


def detect_test_command(project_root: Path = PROJECT_ROOT) -> list[str] | None:
    pyproject = project_root / "pyproject.toml"
    tox_config = project_root / "tox.ini"
    has_pytest_config = (
        (project_root / "pytest.ini").is_file()
        or (pyproject.is_file() and "[tool.pytest" in pyproject.read_text(encoding="utf-8"))
        or (tox_config.is_file() and "pytest" in tox_config.read_text(encoding="utf-8"))
    )
    test_directories = (
        project_root / "test",
        project_root / "tests",
        project_root / "backend" / "test",
        project_root / "backend" / "tests",
    )
    has_pytest_files = any(
        any(directory.glob("test_*.py"))
        for directory in test_directories
        if directory.is_dir()
    )
    if has_pytest_config or has_pytest_files:
        return [sys.executable, "-m", "pytest", "-q"]
    return None


@dataclass
class TestResult:
    __test__ = False

    run_id: str
    command: list[str]
    exit_code: int | None
    output: str
    timed_out: bool


class TestRunner:
    __test__ = False

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self.project_root = Path(project_root)
        self._results: dict[str, TestResult] = {}

    def run(self) -> TestResult:
        run_id = str(uuid.uuid4())
        command = detect_test_command(self.project_root)
        if command is None:
            result = TestResult(
                run_id,
                [],
                2,
                "No supported pytest suite was detected in the project.",
                False,
            )
            self._results[run_id] = result
            return result
        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=TEST_TIMEOUT_SECONDS,
                check=False,
                shell=False,
            )
            output = _redact_secrets(
                (completed.stdout + completed.stderr)[-20000:]
            )
            result = TestResult(run_id, command, completed.returncode, output, False)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            output = _redact_secrets(stdout + stderr + "\nTest run timed out.")
            result = TestResult(
                run_id,
                command,
                None,
                output[-20000:],
                True,
            )

        self._results[run_id] = result
        return result

    def get(self, run_id: str) -> dict | None:
        result = self._results.get(run_id)
        return asdict(result) if result else None
