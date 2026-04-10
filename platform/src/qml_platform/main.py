import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from qml_platform.db import get_db
from qml_platform.evaluator import run_evaluation
from qml_platform.models import EvaluationRun, ModelRecord
from qml_platform.schemas import (
    EvaluateRequest,
    EvaluationRunResponse,
    ModelDetailResponse,
    ModelResponse,
    RegisterModelRequest,
)
from qml_platform.settings import settings

app = FastAPI(title="QML Evaluation Platform")


# ---- Model endpoints ----


@app.post("/api/models/register", response_model=ModelResponse, status_code=201)
async def register_model(body: RegisterModelRequest, db: AsyncSession = Depends(get_db)):
    tar_path = Path(settings.containers_dir) / body.tar_filename
    if not tar_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Tar file not found: {body.tar_filename}",
        )

    record = ModelRecord(
        name=body.name,
        version=body.version,
        description=body.description,
        parameters=body.parameters,
        tar_path=str(tar_path),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@app.get("/api/models", response_model=list[ModelResponse])
async def list_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelRecord).order_by(ModelRecord.registered_at.desc()))
    return result.scalars().all()


@app.get("/api/models/{model_id}", response_model=ModelDetailResponse)
async def get_model(model_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ModelRecord)
        .where(ModelRecord.id == model_id)
        .options(selectinload(ModelRecord.evaluation_runs))
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return record


# ---- Evaluation endpoints ----


@app.post("/api/models/{model_id}/evaluate", response_model=EvaluationRunResponse)
async def evaluate_model(
    model_id: uuid.UUID,
    body: EvaluateRequest,
    db: AsyncSession = Depends(get_db),
):
    record = (await db.execute(
        select(ModelRecord).where(ModelRecord.id == model_id)
    )).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Model not found")

    evaluation_run = EvaluationRun(model_id=record.id)
    db.add(evaluation_run)
    await db.commit()
    await db.refresh(evaluation_run)

    run = await run_evaluation(db, str(evaluation_run.id), record.tar_path, body.n_samples)
    return run


@app.get("/api/evaluations/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EvaluationRun).where(EvaluationRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return run
