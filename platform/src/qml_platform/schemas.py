from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


# ---- Requests ----

class RegisterModelRequest(BaseModel):
    name: str
    version: str
    description: str = ""
    parameters: dict[str, Any] = {}
    tar_filename: str


class EvaluateRequest(BaseModel):
    n_samples: int = 100


# ---- Responses ----

class ModelResponse(BaseModel):
    id: UUID
    name: str
    version: str
    description: str
    parameters: dict[str, Any]
    tar_path: str
    registered_at: datetime

    model_config = {"from_attributes": True}


class EvaluationRunResponse(BaseModel):
    id: UUID
    model_id: UUID
    status: str
    accuracy: float | None = None
    latency_ms: float | None = None
    extra_metrics: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ModelDetailResponse(ModelResponse):
    evaluation_runs: list[EvaluationRunResponse] = []
