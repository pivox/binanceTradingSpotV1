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
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
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
    echo "[start.sh] Temporal ready."
    break
  fi
  if [[ $i -eq 30 ]]; then
    echo "[start.sh] ERROR: Temporal did not become ready in time." >&2
    exit 1
  fi
  sleep 2
done

# ── 4. WebSocket candle daemon ───────────────────────────────────────────────
echo "[start.sh] Starting ws_candle_daemon..."
poetry -C "$ROOT" run python "$ROOT/ws_candle_daemon.py" \
  >"$LOGS_DIR/daemon.log" 2>&1 &
PIDS+=($!)
echo "[start.sh] ws_candle_daemon PID=${PIDS[-1]}  →  logs/daemon.log"

# ── 5. Temporal worker (bootstraps schedules automatically) ──────────────────
echo "[start.sh] Starting temporal_worker..."
poetry -C "$ROOT" run python -m tradebot.apps.temporal_worker_main \
  >"$LOGS_DIR/worker.log" 2>&1 &
PIDS+=($!)
echo "[start.sh] temporal_worker   PID=${PIDS[-1]}  →  logs/worker.log"

# ── 6. Daemon API ────────────────────────────────────────────────────────────
echo "[start.sh] Starting daemon_api..."
poetry -C "$ROOT" run python -m tradebot.apps.daemon_api_main \
  >"$LOGS_DIR/api.log" 2>&1 &
PIDS+=($!)
echo "[start.sh] daemon_api        PID=${PIDS[-1]}  →  logs/api.log"

echo ""
echo "[start.sh] All processes running. Press Ctrl+C to stop."
echo "           API       → http://localhost:${API_PORT:-8000}"
echo "           Temporal  → http://localhost:8080"
echo ""

wait "${PIDS[@]}"
