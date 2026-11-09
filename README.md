# Gemma 4 Autonomous Coding Agent

An autonomous, multi-agent software engineering system designed for repository-level issue investigation, root-cause analysis, code modification, testing, and verified patch submission using Google's Gemma 4 models.

## Project Overview

This project is designed for the **Gemma 4 Developer Agent Competition 2026**.

The agent follows a structured software engineering workflow:

1. Understand the problem statement.
2. Explore the repository and identify relevant files.
3. Investigate dependencies and trace the root cause.
4. Implement a minimal and reliable fix.
5. Identify and execute relevant tests.
6. Review the changes and verify the final patch.
7. Submit the verified patch.

The system uses declarative YAML agent configurations, specialized prompts, and competition-provided tools.

## Architecture

The system consists of three specialized agents.

### 1. Root Coding Agent

The root agent coordinates the complete software engineering workflow.

Responsibilities:

- Understand repository issues and requirements.
- Coordinate code investigation.
- Implement fixes using available editing tools.
- Execute tests and inspect results.
- Verify changes before patch submission.

### 2. Code Analyzer Agent

A read-only investigation specialist registered through `AgentTool`.

Responsibilities:

- Explore repository structure.
- Identify relevant source files.
- Trace code dependencies.
- Investigate potential root causes.
- Return focused findings to the root agent.

The analyzer uses `skip_summarization: true` to preserve detailed investigation context.

### 3. Testing Agent

A read-only testing specialist registered as a sub-agent.

Responsibilities:

- Review code changes.
- Identify relevant test cases.
- Analyze edge cases.
- Identify possible regressions.
- Recommend additional testing.

The root agent remains responsible for executing tests.

## Agent Workflow

```text
       Problem Description
               |
               v
        Root Coding Agent
               |
               v
        Code Investigation
               |
               v
          Code Analyzer
               |
               v
         Root Cause Found
               |
               v
         Minimal Code Fix
               |
               v
          Testing Agent
               |
               v
        Test Recommendations
               |
               v
        Root Agent Executes
              Tests
               |
               v
        Review Final Changes
               |
               v
         Submit Verified Patch
```

## Model Configuration

Current configured model:

`gemma-4-e4b-it-qat-w4a16-ct`

The root agent and both specialized agents use the same base model.

The configuration includes:

- Thinking budget: 4096
- Include thoughts: enabled
- Maximum output tokens: 16384

The E4B model is selected as the current development configuration. The competition also documents other supported Gemma 4 model variants.

## Project Structure

```text
gemma4-autonomous-coding-agent/
│
├── agent.yaml
├── eval_config.yaml
├── .gitignore
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── routers/
│   │   │   ├── voice.py
│   │   │   └── coding.py
│   │   └── services/
│   │       ├── prisma.py
│   │       ├── timbre.py
│   │       ├── gemma_agent.py
│   │       ├── patch_manager.py
│   │       └── test_runner.py
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── style.css
│   ├── package.json
│   └── vite.config.ts
│
├── prompts/
│   ├── system.md
│
├── sub_agents/
│   ├── code_analyzer.yaml
│   ├── tester.yaml
│   └── prompts/
│       ├── analyzer.md
│       └── tester.md
│
├── scripts/
│   └── validate_config.py
│
├── evaluation/
│   ├── experiment_card.json
│   ├── holdout.py
│   ├── failure_analysis.py
│   ├── trajectory_audit.py
│   └── experiment_tracker.py
│
├── test/
│   ├── test_holdout.py
│   ├── test_failure_analysis.py
│   ├── test_trajectory_audit.py
│   └── test_experiment_tracker.py
```

## Competition Tools

The configuration uses the competition-provided tools:

- `run_command`
- `submit_patch`
- `get_status`
- `read_file`
- `edit_file`
- `write_file`
- `get_code_neighbors`
- `search_similar_code`
- `get_code_subgraph`

These tools support repository exploration, code editing, testing, dependency investigation, and patch submission.

## Local Configuration Validation

The project includes a local YAML configuration validator.

### Requirements

- Python 3.12
- PyYAML

### Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install pyyaml
```

### Run Validation

```powershell
python scripts/validate_config.py
```

The validator checks:

- Root agent configuration.
- YAML syntax and included prompt files.
- Agent configuration paths.
- Model consistency.
- AgentTool registration.
- Sub-agent registration.
- Evaluation configuration.

**Note:** Passing local validation confirms configuration checks only. It does not establish successful execution inside the official competition harness.

## Evaluation Configuration

The project contains `eval_config.yaml` for evaluation limits, including:

- Command timeout.
- Maximum tool calls.
- Maximum execution time.
- Maximum agent turns.

These values are configuration limits, not measured performance results.

## Evaluation Utilities

The project includes lightweight Python utilities to support reproducible evaluation and experiment tracking.

### 1. Public Holdout Selection

File: `evaluation/holdout.py`

- Selects a deterministic subset of public benchmark task IDs.
- Distributes selections across repositories.
- Supports a configurable holdout limit.

This utility supports holdout selection but is not yet connected to the official evaluation harness.

### 2. Failure Analysis

File: `evaluation/failure_analysis.py`

- Counts resolved and failed tasks.
- Calculates the resolution rate.
- Groups failures by stages:
  - Localization
  - Diagnosis
  - Editing
  - Testing
  - Submission

The caller must provide task results and failure-stage labels.

### 3. Trajectory Audit

File: `evaluation/trajectory_audit.py`

- Performs basic structural validation of trajectory JSONL records.
- Checks required fields.
- Verifies successful resolution labels.
- Checks patch format and tool-step structure.
- Rejects records containing a `test_patch` field to reduce verification-label leakage.

This is a structural audit utility, not a complete security scanner, data-quality validator, or training pipeline.

### 4. Experiment Tracking

File: `evaluation/experiment_tracker.py`

- Updates experiment metadata.
- Records total and resolved task counts.
- Calculates resolution rate.
- Records elapsed time.
- Validates evaluation metrics before updating the experiment card.

Experiment metadata is maintained in:

`evaluation/experiment_card.json`

The initial experiment is recorded as `not_evaluated` until actual evaluation results are available.

### 5. Unit Tests

The utilities have dedicated tests in the `test/` directory.

Install pytest:

```powershell
python -m pip install pytest
```

Run all tests:

```powershell
python -m pytest test/ -v
```

Current local test suite:

**8 legacy evaluation-utility tests passing** (additional Voice2Code tests are in `backend/tests/`).

These tests validate the utility functions using synthetic test data. They do not measure the coding agent's benchmark performance.

## Engineering Principles

The agent is designed around the following principles:

- Root-cause analysis before implementation.
- Minimal and targeted code changes.
- Preserve existing APIs and backward compatibility.
- Avoid unrelated refactoring.
- Do not hardcode solutions for individual tests.
- Verify changes with relevant tests.
- Inspect the final patch before submission.
- Report limitations and failures honestly.

## Competition Submission Notes

The competition uses declarative agent configuration rather than arbitrary custom Python agent entrypoints.

The submission must follow the official harness requirements, including:

- A supported root YAML configuration.
- Valid agent and sub-agent configurations.
- Supported tools and model identifiers.
- Correct prompt and include paths.
- Evaluation configuration where applicable.

The official evaluation environment provides its own runtime and dependencies. Local configuration validation should not be confused with official harness execution.

## Current Development Status

| Component | Status |
|---|---|
| Root agent YAML | Configured |
| Code Analyzer | Configured |
| Testing Agent | Configured |
| System prompts | Created |
| Evaluation configuration | Created |
| Local YAML validator | Passing |
| Holdout selection utility | Implemented and tested |
| Failure analysis utility | Implemented and tested |
| Trajectory audit utility | Implemented and tested |
| Experiment tracker | Implemented and tested |
| Legacy evaluation-utility tests | 8 passing |
| Git version control | Initialized |
| Official harness execution | Not yet verified |
| Official benchmark performance | Not yet measured |

## Future Improvements

- Validate against the official competition harness.
- Run repository-level evaluation tasks.
- Connect evaluation utilities to actual harness results.
- Improve issue investigation and root-cause accuracy.
- Improve test selection and regression detection.
- Evaluate model configurations against benchmark tasks.
- Measure patch correctness and execution efficiency.
- Expand trajectory quality checks when authorized data becomes available.

## Evaluation Integrity

This repository distinguishes between local software tests and official benchmark evaluation.

- Passing unit tests validates utility implementation.
- Local configuration validation checks YAML and project configuration.
- Official benchmark resolution rate requires actual competition-harness execution.
- No benchmark resolution rate or performance improvement is claimed until measured results are available.

## License

Add the license required by the competition or your chosen distribution terms before public release.

---

**Built for the Gemma 4 Developer Agent Competition 2026.**

## Voice2Code local prototype

This repository also contains a local **Voice2Code** interface that combines
the existing Gemma 4 competition project with Gnani voice APIs. The original
agent YAML, prompts, sub-agent configuration, and evaluation utilities remain
the source of truth for competition-harness execution.

### Architecture and current status

```text
Browser (React + TypeScript + Vite)
  ├─ audio upload / microphone recording
  ├─ FastAPI ── Gnani Prisma STT ── transcript
  ├─ FastAPI ── Gemma adapter ── proposal ── patch preview
  ├─ explicit approve/reject ── safe project-local patch application
  ├─ approved patch ── fixed pytest command
  └─ explanation ── Gnani Timbre TTS ── WAV playback
```

Implemented local components include the FastAPI app, Swagger docs, CORS
allowlist, upload validation, documented Gnani Prisma/Timbre HTTP clients,
patch review/apply/reject/rollback operations, a restricted pytest runner, and
a responsive browser interface with recording/upload, transcript editing,
patch preview/approval, test output, and WAV playback controls. Technology
stack: FastAPI/Pydantic/httpx, React/TypeScript/Vite, Prisma STT, and Timbre TTS.
Gnani services require a real API key and are not reported as live-verified by
the offline tests.

The competition configuration remains declarative and its competition-only
tools are not locally callable. The local prototype now has a real Ollama
adapter for an explicitly installed Gemma 4 model. It sends bounded project
context and the coding task to that model and parses its structured response
into the existing approval-gated patch manager. The adapter does not execute
competition-only sub-agents, download weights, use another model family, or
fabricate patches. It returns an actionable unavailable error until the local
Ollama service and configured Gemma 4 model are installed.

### Windows PowerShell setup

In the repository root:

```powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Set `GNANI_API_KEY_ID` in `.env`, then start the backend from `backend\`:

```powershell
uvicorn app.main:app --reload
```

Install the configured Gemma 4 model separately and ensure Ollama is running:

```powershell
ollama pull gemma4:e4b
ollama list
```

The default Ollama package is approximately 6.6 GB. This machine's 6 GB GPU
may need to offload some model work to system memory; inference performance is
not verified until a real local model request succeeds. The model tag is
configurable with `GEMMA_OLLAMA_MODEL` in `backend\.env`, but must remain a
Gemma 4 model.

In another PowerShell window, start the frontend:

```powershell
Set-Location .\frontend
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). The frontend can capture
short microphone audio or upload WAV/MP3/OGG/FLAC/AAC/M4A, show a Prisma
transcript, and enter or edit a coding instruction. When a real local Gemma
runtime is connected, inspect the proposed diff before choosing **Approve and
apply** or **Reject**; approval applies changes and runs pytest. Timbre can
return spoken explanation audio. The status indicator reports whether the
configured Gemma model is installed and the proposal endpoint reports specific
runtime setup errors. If frontend and backend origins differ, list the frontend
origin in `backend\.env` under `FRONTEND_ORIGINS`.

For a demo without a live provider, the offline tests exercise the local
validation, mocked provider requests, patch lifecycle, and Ollama adapter
request/response handling.
The browser UI intentionally shows provider/runtime errors instead of showing
sample transcripts, patches, or audio as if they were real.

### API and test commands

The backend exposes `/`, `/health`, `/docs`, and:

- `POST /api/v1/voice/transcribe` — multipart audio to Prisma v3.
- `POST /api/v1/voice/synthesize` — JSON input to Timbre; returns actual WAV.
- `/api/v1/coding/*` — agent status, proposal, patch lifecycle, and test results.

From the repository root:

```powershell
python -m pytest
python -m compileall -q backend\app backend\tests backend\test_backend.py
python scripts\validate_config.py
Set-Location .\frontend
npm test
npm run build
```

The test suite mocks provider HTTP responses and validates error handling; it
does not call Gnani. To exercise real STT/TTS, configure a valid key and use a
real audio clip/text request. The API has no user authentication and is for
loopback development only; do not expose it to untrusted networks. Patches are
confined to regular text files under the repository root, protected config and
secret paths are rejected, and original file contents are retained for
rollback until the backend process exits.
