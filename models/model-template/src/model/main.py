"""
QML Model Template
==================
Clone this directory and replace the dummy logic with your real model.
The platform expects every model container to expose these five endpoints.
"""

import random
import time
from typing import Any

from fastapi import FastAPI

app = FastAPI(title="Model Template")

# ---------------------------------------------------------------------------
# TODO: Replace these constants with your model's actual metadata.
# ---------------------------------------------------------------------------
MODEL_NAME = "model-template"
MODEL_VERSION = "0.1.0"
MODEL_DESCRIPTION = "A dummy model that returns random predictions."
MODEL_PARAMETERS: dict[str, Any] = {"seed": 42}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metadata")
async def metadata():
    return {
        "name": MODEL_NAME,
        "version": MODEL_VERSION,
        "description": MODEL_DESCRIPTION,
        "parameters": MODEL_PARAMETERS,
    }


@app.post("/generate-dataset")
async def generate_dataset(body: dict[str, Any]):
    """
    TODO: Replace with your real data generation logic.
    Expected request:  {"n_samples": int}
    Expected response: [{"input": ..., "expected": ...}, ...]
    """
    n_samples = body.get("n_samples", 100)
    rng = random.Random(42)
    dataset = []
    for _ in range(n_samples):
        value = rng.uniform(-5.0, 5.0)
        dataset.append({
            "input": [value, rng.uniform(-5.0, 5.0)],
            "expected": int(value >= 0),
        })
    return dataset


@app.post("/predict")
async def predict(body: dict[str, Any]):
    """
    TODO: Replace with your real inference logic.
    Expected request:  {"input": <any>}
    Expected response: {"output": <any>, "latency_ms": float}
    """
    start = time.perf_counter()
    output = random.choice([0, 1])
    latency_ms = (time.perf_counter() - start) * 1000
    return {"output": output, "latency_ms": latency_ms}


@app.post("/evaluate")
async def evaluate(body: dict[str, Any]):
    """
    TODO: Replace with your real evaluation logic.
    Expected request:  {"dataset": [{"input": ..., "expected": ...}, ...]}
    Expected response: {"accuracy": float, "latency_ms": float, "extra_metrics": dict}
    """
    dataset: list[dict] = body.get("dataset", [])
    start = time.perf_counter()

    correct = 0
    for sample in dataset:
        prediction = random.choice([0, 1])
        if prediction == sample.get("expected"):
            correct += 1

    accuracy = correct / len(dataset) if dataset else 0.0
    latency_ms = (time.perf_counter() - start) * 1000

    return {
        "accuracy": accuracy,
        "latency_ms": latency_ms,
        "extra_metrics": {"total_samples": len(dataset)},
    }
