import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.gemma_agent import (
    AgentOutputError,
    AgentRuntimeUnavailable,
    GemmaAgentAdapter,
)
from app.services.patch_manager import PatchError, PatchManager
from app.services.test_runner import TestRunner

router = APIRouter(prefix="/api/v1/coding", tags=["coding"])

agent = GemmaAgentAdapter()
patch_manager = PatchManager()
test_runner = TestRunner()


class ProposalRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=10000)


@router.get("/status")
async def coding_status() -> dict[str, Any]:
    return await agent.status()


@router.post("/proposals", status_code=201)
async def propose(request: ProposalRequest) -> dict:
    try:
        proposal = await agent.propose(request.instruction)
    except AgentRuntimeUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AgentOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    try:
        return patch_manager.create(
            changes=proposal.changes,
            summary=proposal.summary,
            explanation=proposal.explanation,
        )
    except PatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/patches/{patch_id}")
async def view_patch(patch_id: str) -> dict:
    patch = patch_manager.get(patch_id)
    if patch is None:
        raise HTTPException(status_code=404, detail="Patch not found")
    return patch


@router.post("/patches/{patch_id}/approve")
async def approve_patch(patch_id: str) -> dict:
    try:
        patch = patch_manager.apply(patch_id)
    except PatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    result = await asyncio.to_thread(test_runner.run)
    return {"patch": patch, "tests": result.__dict__}


@router.post("/patches/{patch_id}/reject")
async def reject_patch(patch_id: str) -> dict:
    try:
        return patch_manager.reject(patch_id)
    except PatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/patches/{patch_id}/rollback")
async def rollback_patch(patch_id: str) -> dict:
    try:
        return patch_manager.rollback(patch_id)
    except PatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/tests/{run_id}")
async def get_test_result(run_id: str) -> dict:
    result = test_runner.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    return result
