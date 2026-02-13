SHELL := /bin/bash

DATABASE_URL ?= postgresql://user:pass@localhost:5433/tradebot
SYMBOLS ?= SOLUSDC
SHARD_COUNT ?= 8

.PHONY: db-up daemon worker

db-up:
	docker compose up -d postgres

daemon:
	DATABASE_URL=$(DATABASE_URL) SYMBOLS=$(SYMBOLS) SHARD_COUNT=$(SHARD_COUNT) poetry run python ws_candle_daemon.py

worker:
	poetry run python -m tradebot.apps.temporal_worker_main
