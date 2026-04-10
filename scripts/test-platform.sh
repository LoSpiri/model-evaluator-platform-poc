#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PLATFORM_URL="http://localhost:8000"
PASS=0
FAIL=0

assert_eq() {
  local label="$1" actual="$2" expected="$3"
  if [ "$actual" = "$expected" ]; then
    echo "  PASS: $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (expected '$expected', got '$actual')"
    FAIL=$((FAIL + 1))
  fi
}

cleanup() {
  echo ""
  echo "Tearing down docker compose ..."
  cd "$ROOT_DIR"
  docker compose down -v > /dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== Platform Integration Tests ==="
echo ""

echo "Starting docker compose ..."
cd "$ROOT_DIR"
docker compose up --build -d > /dev/null 2>&1

echo "Waiting for platform to be ready ..."
for i in $(seq 1 60); do
  if curl -sf "$PLATFORM_URL/api/models" > /dev/null 2>&1; then
    echo "  Platform is ready."
    break
  fi
  if [ "$i" = "60" ]; then
    echo "  FAIL: platform did not start within 60s"
    docker compose logs platform
    exit 1
  fi
  sleep 1
done

# Test 1: GET /api/models returns empty list
echo ""
echo "--- GET /api/models (empty) ---"
MODELS=$(curl -s "$PLATFORM_URL/api/models")
COUNT=$(echo "$MODELS" | jq 'length')
assert_eq "empty model list" "$COUNT" "0"

# Test 2: Build a minimal dummy tar for registration
echo ""
echo "--- Register a model ---"
mkdir -p "$ROOT_DIR/containers"

MODEL_DIR="$ROOT_DIR/models/model-template"
TAG="model-template:test"
docker build -t "$TAG" "$MODEL_DIR" > /dev/null 2>&1
docker save "$TAG" -o "$ROOT_DIR/containers/model-template-test.tar"

REGISTER_RESP=$(curl -s -w "\n%{http_code}" -X POST "$PLATFORM_URL/api/models/register" \
  -H "Content-Type: application/json" \
  -d '{"name":"model-template","version":"test","description":"CI test","parameters":{},"tar_filename":"model-template-test.tar"}')
HTTP_CODE=$(echo "$REGISTER_RESP" | tail -1)
BODY=$(echo "$REGISTER_RESP" | head -n -1)
assert_eq "register returns 201" "$HTTP_CODE" "201"

MODEL_ID=$(echo "$BODY" | jq -r '.id')
assert_eq "register returns UUID" "$(echo "$MODEL_ID" | grep -cE '^[0-9a-f-]{36}$')" "1"

# Test 3: GET /api/models returns 1 model
echo ""
echo "--- GET /api/models (1 model) ---"
COUNT=$(curl -s "$PLATFORM_URL/api/models" | jq 'length')
assert_eq "model list has 1 entry" "$COUNT" "1"

# Test 4: GET /api/models/{id}
echo ""
echo "--- GET /api/models/{id} ---"
DETAIL_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$PLATFORM_URL/api/models/$MODEL_ID")
assert_eq "model detail returns 200" "$DETAIL_STATUS" "200"

NAME=$(curl -s "$PLATFORM_URL/api/models/$MODEL_ID" | jq -r '.name')
assert_eq "model name matches" "$NAME" "model-template"

# Test 5: GET /api/evaluations with bad UUID returns 404
echo ""
echo "--- GET /api/evaluations (404) ---"
NOT_FOUND=$(curl -s -o /dev/null -w "%{http_code}" "$PLATFORM_URL/api/evaluations/00000000-0000-0000-0000-000000000000")
assert_eq "missing evaluation returns 404" "$NOT_FOUND" "404"

# Cleanup tar
rm -f "$ROOT_DIR/containers/model-template-test.tar"

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed"
echo "==============================="

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
