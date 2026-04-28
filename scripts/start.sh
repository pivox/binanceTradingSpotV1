#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS_DIR="$ROOT/logs"
mkdir -p "$LOGS_DIR"

# Load .env if present
if [[ -f "$ROOT/.env" ]]; then
  set -a; source "$ROOT/.env"; set +a
fi

TEMPORAL_ADDRESS="${TEMPORAL_ADDRESS:-localhost:7234}"
TEMPORAL_HOST="${TEMPORAL_ADDRESS%%:*}"
TEMPORAL_PORT="${TEMPORAL_ADDRESS##*:}"

# ── PIDs ────────────────────────────────────────────────────────────────────
PIDS=()

cleanup() {
  echo ""
  echo "[start.sh] Shutting down..."
  if [[ ${#PIDS[@]} -gt 0 ]]; then
    for pid in "${PIDS[@]}"; do
      kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
  fi
  echo "[start.sh] Done."
}
trap cleanup SIGINT SIGTERM EXIT

# ── 1. Infrastructure ────────────────────────────────────────────────────────
echo "[start.sh] Starting Docker infrastructure..."
docker compose -f "$ROOT/docker-compose.yml" up -d

# ── 2. Wait for PostgreSQL ───────────────────────────────────────────────────
echo "[start.sh] Waiting for PostgreSQL..."
for i in $(seq 1 30); do
  if docker compose -f "$ROOT/docker-compose.yml" exec -T postgres \
       pg_isready -U user -d tradebot -q 2>/dev/null; then
    echo "[start.sh] PostgreSQL ready."
    break
  fi
  if [[ $i -eq 30 ]]; then
    echo "[start.sh] ERROR: PostgreSQL did not become ready in time." >&2
    exit 1
  fi
  sleep 2
done

# ── 3. Wait for Temporal ─────────────────────────────────────────────────────
echo "[start.sh] Waiting for Temporal ($TEMPORAL_ADDRESS)..."
for i in $(seq 1 30); do
  if bash -c ">/dev/tcp/$TEMPORAL_HOST/$TEMPORAL_PORT" 2>/dev/null; then
    echo "[start.sh] Temporal TCP ready."
    break
  fi
  if [[ $i -eq 30 ]]; then
    echo "[start.sh] ERROR: Temporal did not become ready in time." >&2
    exit 1
  fi
  sleep 2
done

# Wait for the default namespace to be registered (auto-setup takes a few seconds after TCP)
# Temporal listens on the Docker bridge IP, not 127.0.0.1 — retrieve it dynamically.
echo "[start.sh] Waiting for Temporal namespace 'default'..."
TEMPORAL_CONTAINER_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' \
  "$(docker compose -f "$ROOT/docker-compose.yml" ps -q temporal)" 2>/dev/null | head -1)
for i in $(seq 1 30); do
  if docker compose -f "$ROOT/docker-compose.yml" exec -T temporal \
       temporal operator namespace describe -n default \
       --address "${TEMPORAL_CONTAINER_IP}:7233" >/dev/null 2>&1; then
    echo "[start.sh] Temporal namespace ready."
    break
  fi
  if [[ $i -eq 30 ]]; then
    echo "[start.sh] ERROR: Temporal namespace 'default' did not become ready in time." >&2
    exit 1
  fi
  sleep 2
done

# ── 4. WebSocket candle daemon ───────────────────────────────────────────────
echo "[start.sh] Starting ws_candle_daemon..."
poetry -C "$ROOT" run python "$ROOT/ws_candle_daemon.py" \
  >"$LOGS_DIR/daemon.log" 2>&1 &
PIDS+=($!)
echo "[start.sh] ws_candle_daemon PID=$!  →  logs/daemon.log"

# ── 5. Temporal worker (bootstraps schedules automatically) ──────────────────
echo "[start.sh] Starting temporal_worker..."
poetry -C "$ROOT" run python -m tradebot.apps.temporal_worker_main \
  >"$LOGS_DIR/worker.log" 2>&1 &
PIDS+=($!)
echo "[start.sh] temporal_worker   PID=$!  →  logs/worker.log"

# ── 6. Daemon API ────────────────────────────────────────────────────────────
echo "[start.sh] Starting daemon_api..."
poetry -C "$ROOT" run python -m tradebot.apps.daemon_api_main \
  >"$LOGS_DIR/api.log" 2>&1 &
PIDS+=($!)
echo "[start.sh] daemon_api        PID=$!  →  logs/api.log"

# ── 7. User data stream (Binance executionReport) ────────────────────────────
echo "[start.sh] Starting user_stream..."
poetry -C "$ROOT" run python -m tradebot.apps.user_stream_main \
  >"$LOGS_DIR/user_stream.log" 2>&1 &
PIDS+=($!)
echo "[start.sh] user_stream       PID=$!  →  logs/user_stream.log"

echo ""
echo "[start.sh] All processes running. Press Ctrl+C to stop."
echo "           API       → http://localhost:${API_PORT:-8000}"
echo "           Temporal  → http://localhost:8080"
echo ""

wait "${PIDS[@]}"
