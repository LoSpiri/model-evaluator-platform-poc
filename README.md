# QML Model Evaluation Platform (POC)

A monorepo for evaluating ML models. Build models from a
template, CI packages them as Docker images, and the platform API loads and
runs those containers to produce evaluation metrics stored in PostgreSQL.

## Repo Structure

```
├── platform/                      # FastAPI evaluation platform API
│   ├── src/qml_platform/
│   │   ├── main.py                # API routes
│   │   ├── evaluator.py           # Docker load / run / evaluate / teardown
│   │   ├── db.py                  # Async SQLAlchemy engine
│   │   ├── models.py              # ORM models
│   │   ├── schemas.py             # Pydantic schemas
│   │   └── settings.py            # Centralized configuration
│   ├── alembic/                   # Database migrations
│   ├── Dockerfile
│   └── start.sh
├── models/
│   ├── model-template/            # Starter template for new models
│   └── cluster-classifier/        # Working example (PyTorch 2-cluster classifier)
│       └── scripts/
│           └── generate_clusters.py
├── scripts/
│   ├── test-model-contract.sh     # Validate model container endpoints
│   └── test-platform.sh           # Platform integration tests
├── docker-compose.yml
├── devbox.json
└── .github/workflows/
    ├── ci-models.yml              # Model contract tests on PR
    └── ci-platform.yml            # Platform integration tests on PR
```

## Models

Every model is a Docker container that exposes five HTTP endpoints on port 8000:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Returns `{"status": "ok"}` when the model is ready |
| `/metadata` | GET | Returns model name, version, description, and parameters |
| `/generate-dataset` | POST | Accepts `{"n_samples": int}`, returns a JSON array of `{"input": ..., "expected": ...}` samples |
| `/predict` | POST | Accepts `{"input": ...}`, returns `{"output": ..., "latency_ms": ...}` |
| `/evaluate` | POST | Accepts `{"dataset": [...]}`, returns `{"accuracy": ..., "latency_ms": ..., "extra_metrics": ...}` |

### Available Models

| Model | Description | Dependencies |
|-------|-------------|--------------|
| **model-template** | Dummy model that returns random predictions. Clone this to create a new model. | FastAPI, Uvicorn |
| **cluster-classifier** | Binary classifier for 2D point clusters using a single-layer PyTorch network. Trains on startup. | FastAPI, Uvicorn, PyTorch (CPU), NumPy |

### Creating a New Model

1. Copy `models/model-template/` to `models/<your-model>/`.
2. Edit `pyproject.toml` — update the name, description, and dependencies.
3. Replace the dummy logic in `src/model/main.py` with your real model.
4. Implement `/generate-dataset` to produce representative samples for your model
   (used by the platform during evaluation and by CI contract tests).
5. Build and test locally:

```bash
docker build -t my-model:test models/my-model/
docker run --rm -p 8000:8000 my-model:test
curl http://localhost:8000/health
```

---

## Getting Started

### Option A: With Devbox

[Devbox](https://www.jetify.com/devbox) provides Python, uv, Docker CLI, PostgreSQL client,
curl, and jq in a reproducible shell — no global installs required.

#### Prerequisites

- [Devbox](https://www.jetify.com/devbox/docs/installing_devbox/) installed
- Docker daemon running

#### 1. Enter the dev environment

```bash
devbox shell
```

#### 2. Start the platform

```bash
devbox run up
```

#### 3. Tear down

```bash
devbox run down        # stop services (keep data)
devbox run down:clean  # stop services and delete volumes
```

#### 4. View logs

```bash
devbox run logs
```

### Option B: Without Devbox

You can use Docker Compose directly. Make sure you have:

- **Docker** (with Compose v2) installed and running
- **curl** and **jq** installed (for the test scripts)

#### 1. Start the platform

```bash
docker compose up --build -d
```

This builds the platform image, starts PostgreSQL and the API on
`http://localhost:8000`. Alembic migrations run automatically on startup.

#### 2. Tear down

```bash
docker compose down        # stop services (keep data)
docker compose down -v     # stop services and delete volumes
```

#### 3. View logs

```bash
docker compose logs -f
```

---

## Usage Walkthrough

Once the platform is running (via either option above):

### 1. Build a model image

```bash
docker build -t cluster-classifier:v0.1.0 models/cluster-classifier/
docker save cluster-classifier:v0.1.0 -o containers/cluster-classifier-v0.1.0.tar
```

### 2. Register the model

```bash
curl -X POST http://localhost:8000/api/models/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "cluster-classifier",
    "version": "v0.1.0",
    "description": "Binary classifier for 2D point clusters",
    "parameters": {},
    "tar_filename": "cluster-classifier-v0.1.0.tar"
  }'
```

Save the returned `id` — you will need it for evaluation. Otherwise call `GET /api/models` to list all registered models.

### 3. Evaluate the model

The platform starts the model container, asks it to generate a dataset, then
runs evaluation on that data — all in one call:

```bash
curl -X POST http://localhost:8000/api/models/<model-id>/evaluate \
  -H "Content-Type: application/json" \
  -d '{"n_samples": 100}'
```

### 4. Check results

```bash
curl http://localhost:8000/api/models/<model-id>
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/models/register` | Register a model from a `.tar` file |
| `GET` | `/api/models` | List all registered models |
| `GET` | `/api/models/{id}` | Get model details and evaluation history |
| `POST` | `/api/models/{id}/evaluate` | Run evaluation on a model |
| `GET` | `/api/evaluations/{id}` | Get a single evaluation run |

### Request / Response Examples

**Register a model** — `POST /api/models/register`

```json
{
  "name": "cluster-classifier",
  "version": "v0.1.0",
  "description": "Binary classifier for 2D point clusters",
  "parameters": {},
  "tar_filename": "cluster-classifier-v0.1.0.tar"
}
```

Response (`201`):

```json
{
  "id": "a1b2c3d4-...",
  "name": "cluster-classifier",
  "version": "v0.1.0",
  "description": "Binary classifier for 2D point clusters",
  "parameters": {},
  "tar_path": "/app/containers/cluster-classifier-v0.1.0.tar",
  "registered_at": "2026-04-10T12:00:00Z"
}
```

**Evaluate a model** — `POST /api/models/{id}/evaluate`

The platform starts the model container, calls `/generate-dataset` to produce
`n_samples` data points, then calls `/evaluate` with the generated dataset.

```json
{
  "n_samples": 100
}
```

Response (`200`):

```json
{
  "id": "e5f6a7b8-...",
  "model_id": "a1b2c3d4-...",
  "status": "completed",
  "accuracy": 1.0,
  "latency_ms": 0.25,
  "extra_metrics": {"total_samples": 100},
  "error": null,
  "started_at": "2026-04-10T12:01:00Z",
  "completed_at": "2026-04-10T12:01:02Z"
}
```

**List models** — `GET /api/models`

Response (`200`):

```json
[
  {
    "id": "a1b2c3d4-...",
    "name": "cluster-classifier",
    "version": "v0.1.0",
    "description": "Binary classifier for 2D point clusters",
    "parameters": {},
    "tar_path": "/app/containers/cluster-classifier-v0.1.0.tar",
    "registered_at": "2026-04-10T12:00:00Z"
  }
]
```

---

## Testing

### With Devbox

```bash
devbox shell

devbox run test:all             # platform + model contract tests
devbox run test:platform        # platform integration tests only
devbox run test:model-contract  # model contract tests only
```

### Without Devbox

The test scripts only require `bash`, `curl`, `jq`, and `docker`:

```bash
bash scripts/test-platform.sh        # platform integration tests
bash scripts/test-model-contract.sh  # model contract tests
```

`test-platform.sh` manages docker compose automatically (starts before tests, tears down after).
`test-model-contract.sh` builds each model image and validates all five endpoints.

---

## CI Workflows

### 1. Model Contract Tests (`ci-models.yml`)

**Trigger:** pull request touching `models/**`

Runs `devbox run test:model-contract` — builds each model container and
validates that all five endpoints respond correctly.

### 2. Platform Integration Tests (`ci-platform.yml`)

**Trigger:** pull request touching `platform/**` or `docker-compose.yml`

Runs `devbox run test:platform` — spins up docker compose, verifies the
API is healthy, tests model registration and retrieval, then tears down.

---

## Configuration

All platform settings are managed via environment variables (powered by
`pydantic-settings`). Set them in `docker-compose.yml`, a `.env` file, or
your deployment environment.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://qml:qml@localhost:5432/qml` | Async SQLAlchemy database URL |
| `CONTAINERS_DIR` | `../containers` | Path to directory containing `.tar` images |
| `DOCKER_NETWORK` | _(auto-detect)_ | Docker network for model containers |
| `HOST` | `0.0.0.0` | Uvicorn bind host |
| `PORT` | `8000` | Uvicorn bind port |
| `HEALTH_POLL_TIMEOUT` | `60` | Max seconds to wait for model container health |
| `HEALTH_POLL_INTERVAL` | `1.0` | Seconds between health poll attempts |

See `platform/.env.example` for a template.

---

## Generating Test Data

Each model generates its own dataset via the `/generate-dataset` endpoint.
When you call the platform's evaluate endpoint with `{"n_samples": N}`, it
starts the model container, calls `/generate-dataset`, and uses the result
for evaluation — no manual data files needed.

The cluster-classifier also ships with a standalone data generation script
for offline use:

```bash
cd models/cluster-classifier
uv run python scripts/generate_clusters.py --n-samples 200 --output dataset.json
```

---

## Devbox Scripts Reference

| Script | Command | Description |
|--------|---------|-------------|
| `up` | `devbox run up` | Build and start all services |
| `down` | `devbox run down` | Stop services (keep data) |
| `down:clean` | `devbox run down:clean` | Stop services and delete volumes |
| `logs` | `devbox run logs` | Follow service logs |
| `test:platform` | `devbox run test:platform` | Run platform integration tests |
| `test:model-contract` | `devbox run test:model-contract` | Run model contract tests |
| `test:all` | `devbox run test:all` | Run all tests |
