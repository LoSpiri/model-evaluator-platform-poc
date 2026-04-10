"""
Cluster Classifier
===================
A minimal PyTorch binary classifier that separates two 2D point clusters
(left vs right). Trains a single linear layer on startup.
"""

import time
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from fastapi import FastAPI

MODEL_NAME = "cluster-classifier"
MODEL_VERSION = "0.1.0"
MODEL_DESCRIPTION = "Binary classifier for 2D point clusters (left=0 vs right=1)"
MODEL_PARAMETERS: dict[str, Any] = {
    "architecture": "Linear(2,1)+Sigmoid",
    "epochs": 200,
    "lr": 0.1,
}

model: nn.Module | None = None


class ClusterNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(2, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.linear(x))


def _train_model() -> nn.Module:
    rng = np.random.default_rng(42)
    n = 100
    left = rng.normal(loc=[-2.0, 0.0], scale=0.8, size=(n, 2))
    right = rng.normal(loc=[2.0, 0.0], scale=0.8, size=(n, 2))

    X = torch.tensor(np.vstack([left, right]), dtype=torch.float32)
    y = torch.tensor([0.0] * n + [1.0] * n, dtype=torch.float32).unsqueeze(1)

    net = ClusterNet()
    optimizer = torch.optim.SGD(net.parameters(), lr=0.1)
    loss_fn = nn.BCELoss()

    for _ in range(200):
        optimizer.zero_grad()
        loss = loss_fn(net(X), y)
        loss.backward()
        optimizer.step()

    return net


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global model
    model = _train_model()
    yield


app = FastAPI(title="Cluster Classifier", lifespan=lifespan)


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
    n_samples = body.get("n_samples", 100)
    rng = np.random.default_rng(123)
    half = n_samples // 2

    left = rng.normal(loc=[-2.0, 0.0], scale=0.8, size=(half, 2))
    right = rng.normal(loc=[2.0, 0.0], scale=0.8, size=(n_samples - half, 2))

    dataset: list[dict[str, Any]] = []
    for point in left:
        dataset.append({"input": point.tolist(), "expected": 0})
    for point in right:
        dataset.append({"input": point.tolist(), "expected": 1})

    rng.shuffle(dataset)
    return dataset


@app.post("/predict")
async def predict(body: dict[str, Any]):
    start = time.perf_counter()
    x = torch.tensor([body["input"]], dtype=torch.float32)
    with torch.no_grad():
        prob = model(x).item()
    output = int(prob >= 0.5)
    latency_ms = (time.perf_counter() - start) * 1000
    return {"output": output, "latency_ms": latency_ms}


@app.post("/evaluate")
async def evaluate(body: dict[str, Any]):
    dataset: list[dict] = body.get("dataset", [])
    start = time.perf_counter()

    inputs = [sample["input"] for sample in dataset]
    expected = [sample["expected"] for sample in dataset]

    X = torch.tensor(inputs, dtype=torch.float32)
    with torch.no_grad():
        probs = model(X).squeeze(-1)
    predictions = (probs >= 0.5).int().tolist()

    correct = sum(p == e for p, e in zip(predictions, expected))
    accuracy = correct / len(dataset) if dataset else 0.0
    latency_ms = (time.perf_counter() - start) * 1000

    return {
        "accuracy": accuracy,
        "latency_ms": latency_ms,
        "extra_metrics": {
            "total_samples": len(dataset),
            "correct": correct,
        },
    }
