"""Manual ingestion triggers. No auth gate yet — RBAC lands in Phase 9 (admin
panel); until then, treat every endpoint under here as dev-only.
"""
from pydantic import BaseModel, Field

from fastapi import APIRouter

from moneyball.celery_app.tasks import sync_afl

router = APIRouter(prefix="/admin/ingestion", tags=["ingestion"])


class AflSyncRequest(BaseModel):
    year: int = Field(..., ge=1897, le=2100)
    round: int | None = Field(default=None, ge=1)


class TaskAccepted(BaseModel):
    task_id: str
    status: str = "queued"


@router.post("/afl/sync", response_model=TaskAccepted)
def trigger_afl_sync(payload: AflSyncRequest) -> TaskAccepted:
    async_result = sync_afl.delay(year=payload.year, round_=payload.round)
    return TaskAccepted(task_id=async_result.id)
