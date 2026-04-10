#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0

cleanup() {
  if [ -n "${CONTAINER_ID:-}" ]; then
    echo "  Cleaning up container $CONTAINER_ID"
    docker stop "$CONTAINER_ID" >/dev/null 2>&1 || true
    docker rm -f "$CONTAINER_ID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

assert_status() {
  local label="$1" url="$2" expected="$3" method="${4:-GET}" body="${5:-}"
  local status
  if [ "$method" = "POST" ]; then
    status=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$body" "$url")
  else
    status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  fi
  if [ "$status" = "$expected" ]; then
    echo "  PASS: $label (HTTP $status)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (expected $expected, got $status)"
    FAIL=$((FAIL + 1))
  fi
}

assert_json_field() {
  local label="$1" url="$2" field="$3" method="${4:-GET}" body="${5:-}"
  local value
  if [ "$method" = "POST" ]; then
    value=$(curl -s -X POST -H "Content-Type: application/json" -d "$body" "$url" | jq -r "$field")
  else
    value=$(curl -s "$url" | jq -r "$field")
  fi
  if [ -n "$value" ] && [ "$value" != "null" ]; then
    echo "  PASS: $label ($field = $value)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label ($field is null or missing)"
    FAIL=$((FAIL + 1))
  fi
}

for model_dir in "$ROOT_DIR"/models/*/; do
  model_name=$(basename "$model_dir")
  echo ""
  echo "=== Testing model: $model_name ==="

  if [ ! -f "$model_dir/Dockerfile" ]; then
    echo "  SKIP: no Dockerfile"
    continue
  fi

  TAG="${model_name}:test"
  echo "  Building $TAG ..."
  docker build -t "$TAG" "$model_dir" > /dev/null 2>&1

  CONTAINER_ID=$(docker run -d -p 0:8000 "$TAG")
  HOST_PORT=$(docker port "$CONTAINER_ID" 8000 | head -1 | cut -d: -f2)
  BASE="http://localhost:${HOST_PORT}"

  echo "  Waiting for container (port $HOST_PORT) ..."
  for i in $(seq 1 60); do
    if curl -sf "$BASE/health" > /dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  assert_status "GET /health" "$BASE/health" "200"
  assert_json_field "GET /health .status" "$BASE/health" ".status"

  assert_status "GET /metadata" "$BASE/metadata" "200"
  assert_json_field "GET /metadata .name" "$BASE/metadata" ".name"
  assert_json_field "GET /metadata .version" "$BASE/metadata" ".version"

  PREDICT_BODY='{"input": [1.0, 2.0]}'
  assert_status "POST /predict" "$BASE/predict" "200" "POST" "$PREDICT_BODY"
  assert_json_field "POST /predict .output" "$BASE/predict" ".output" "POST" "$PREDICT_BODY"

  GEN_BODY='{"n_samples": 20}'
  assert_status "POST /generate-dataset" "$BASE/generate-dataset" "200" "POST" "$GEN_BODY"
  GEN_COUNT=$(curl -s -X POST -H "Content-Type: application/json" -d "$GEN_BODY" "$BASE/generate-dataset" | jq 'length')
  if [ "$GEN_COUNT" = "20" ]; then
    echo "  PASS: POST /generate-dataset returns 20 samples"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: POST /generate-dataset expected 20 samples, got $GEN_COUNT"
    FAIL=$((FAIL + 1))
  fi

  DATASET=$(curl -s -X POST -H "Content-Type: application/json" -d "$GEN_BODY" "$BASE/generate-dataset")
  EVAL_BODY=$(echo "$DATASET" | jq -c '{dataset: .}')
  assert_status "POST /evaluate" "$BASE/evaluate" "200" "POST" "$EVAL_BODY"
  assert_json_field "POST /evaluate .accuracy" "$BASE/evaluate" ".accuracy" "POST" "$EVAL_BODY"
  assert_json_field "POST /evaluate .latency_ms" "$BASE/evaluate" ".latency_ms" "POST" "$EVAL_BODY"

  docker stop "$CONTAINER_ID" > /dev/null 2>&1 || true
  docker rm -f "$CONTAINER_ID" > /dev/null 2>&1 || true
  unset CONTAINER_ID

  echo "  Done: $model_name"
done

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed"
echo "==============================="

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
