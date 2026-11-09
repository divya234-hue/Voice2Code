import json
import subprocess

import httpx
import pytest

from app.services.gemma_agent import (
    AgentOutputError,
    AgentRuntimeUnavailable,
    GemmaAgentAdapter,
)
from app.services.test_runner import TestRunner, detect_test_command


@pytest.mark.anyio
async def test_gemma_adapter_reports_unavailable_local_runtime(monkeypatch):
    adapter = GemmaAgentAdapter()

    def failing_client(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr("app.services.gemma_agent.httpx.AsyncClient", failing_client)
    status = await adapter.status()
    assert status["available"] is False
    assert "Start Ollama" in status["detail"]
    with pytest.raises(AgentRuntimeUnavailable, match="Start Ollama"):
        await adapter.propose("Fix a bug")


@pytest.mark.anyio
async def test_gemma_adapter_generates_a_patch_from_local_gemma(monkeypatch, tmp_path):
    (tmp_path / "example.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / ".env").write_text("GNANI_API_KEY_ID=must-not-be-sent\n", encoding="utf-8")
    response_body = {
        "message": {
            "content": json.dumps(
                {
                    "summary": "Add the requested function",
                    "explanation": "The function now returns the expected value.",
                    "changes": {"example.py": "def value():\n    return 1\n"},
                }
            )
        }
    }

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "gemma4:e4b"}]})
        body = json.loads(request.content)
        assert body["model"] == "gemma4:e4b"
        assert "example.py" in body["messages"][1]["content"]
        assert "must-not-be-sent" not in body["messages"][1]["content"]
        return httpx.Response(200, json=response_body)

    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        "app.services.gemma_agent.httpx.AsyncClient",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(handler),
            timeout=kwargs["timeout"],
        ),
    )
    adapter = GemmaAgentAdapter(project_root=tmp_path)
    proposal = await adapter.propose("Add a function")

    assert proposal.summary == "Add the requested function"
    assert proposal.changes == {"example.py": "def value():\n    return 1\n"}


@pytest.mark.anyio
async def test_gemma_adapter_refuses_non_gemma_models():
    adapter = GemmaAgentAdapter(model="llama3.2")
    status = await adapter.status()

    assert status["available"] is False
    assert "Gemma 4 model" in status["detail"]


@pytest.mark.anyio
async def test_gemma_adapter_gives_install_command_when_model_is_missing(monkeypatch):
    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        "app.services.gemma_agent.httpx.AsyncClient",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    json={"models": [{"name": "llama3.2:latest"}]},
                )
            ),
            timeout=kwargs["timeout"],
        ),
    )

    status = await GemmaAgentAdapter().status()

    assert status["available"] is False
    assert "ollama pull gemma4:e4b" in status["detail"]


@pytest.mark.anyio
async def test_gemma_adapter_rejects_empty_or_invalid_patch_output(monkeypatch):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "gemma4:e4b"}]})
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {"summary": "No files", "explanation": "Nothing to change", "changes": {}}
                    )
                }
            },
        )

    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        "app.services.gemma_agent.httpx.AsyncClient",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(handler),
            timeout=kwargs["timeout"],
        ),
    )
    with pytest.raises(AgentOutputError, match="no patch was created"):
        await GemmaAgentAdapter().propose("Do nothing")


def test_test_runner_uses_fixed_command_and_stores_result(monkeypatch):
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "2 passed\n", "")

    monkeypatch.setattr("app.services.test_runner.subprocess.run", fake_run)
    runner = TestRunner()
    result = runner.run()

    assert result.exit_code == 0
    assert "pytest" in result.command
    assert observed["shell"] is False
    assert observed["capture_output"] is True
    assert runner.get(result.run_id)["output"] == "2 passed\n"


def test_test_runner_detects_pytest_suite(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_example.py").write_text("", encoding="utf-8")
    command = detect_test_command(tmp_path)

    assert command is not None
    assert command[-2:] == ["pytest", "-q"]


def test_test_runner_refuses_unknown_test_framework(tmp_path):
    result = TestRunner(tmp_path).run()

    assert result.exit_code == 2
    assert result.command == []
    assert "No supported pytest suite" in result.output


def test_test_runner_records_timeout(monkeypatch):
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output="partial")

    monkeypatch.setattr("app.services.test_runner.subprocess.run", timeout)
    result = TestRunner().run()

    assert result.timed_out is True
    assert result.exit_code is None
    assert "timed out" in result.output


def test_test_runner_redacts_api_key_from_captured_output(monkeypatch):
    monkeypatch.setenv("TEST_API_TOKEN", "secret-test-value")

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "secret-test-value", "")

    monkeypatch.setattr("app.services.test_runner.subprocess.run", fake_run)
    result = TestRunner().run()

    assert result.output == "[REDACTED]"
    assert "secret-test-value" not in result.output
