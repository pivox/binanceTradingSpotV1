SHELL := /bin/bash

DATABASE_URL ?= postgresql://user:pass@localhost:5433/tradebot
SYMBOLS ?= SOLUSDC
SHARD_COUNT ?= 8

.PHONY: start stop infra-up infra-down db-up daemon worker api logs

# ── Main entry point ─────────────────────────────────────────────────────────
start:
	bash scripts/start.sh

stop:
	docker compose down
	@pkill -f ws_candle_daemon    2>/dev/null || true
	@pkill -f temporal_worker_main 2>/dev/null || true
	@pkill -f daemon_api_main      2>/dev/null || true
	@echo "Stopped."

# ── Infrastructure ────────────────────────────────────────────────────────────
infra-up:
	docker compose up -d

infra-down:
	docker compose down

db-up:
	docker compose up -d postgres

# ── Individual processes ──────────────────────────────────────────────────────
daemon:
	DATABASE_URL=$(DATABASE_URL) SYMBOLS=$(SYMBOLS) SHARD_COUNT=$(SHARD_COUNT) poetry run python ws_candle_daemon.py

worker:
	poetry run python -m tradebot.apps.temporal_worker_main

api:
	poetry run python -m tradebot.apps.daemon_api_main

# ── Logs ─────────────────────────────────────────────────────────────────────
logs:
	tail -f logs/daemon.log logs/worker.log logs/api.log
