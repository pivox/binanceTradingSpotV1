Voici un squelette complet (Temporal Python SDK) qui écrit les Workflows + Activities qu’on a listés.
Tu peux copier/coller tel quel puis remplacer les parties TODO (DB/Binance/indicateurs).

temporal_app/types.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional


Timeframe = Literal["1m", "5m", "15m", "1h", "4h"]
Side = Literal["BUY", "SELL"]
IntentStatus = Literal["NEW", "SENT", "ACKED", "FILLED", "REJECTED", "CANCELED"]


@dataclass(frozen=True)
class CandleCloseEvent:
    symbol: str
    timeframe: Timeframe
    open_time_ms: int


@dataclass(frozen=True)
class IndicatorSnapshot:
    symbol: str
    timeframe: Timeframe
    open_time_ms: int
    payload: dict[str, Any]  # RSI, EMA, MACD, ATR...


@dataclass
class MtfState:
    symbol: str
    context_ok_4h: bool = False
    context_ok_1h: bool = False
    ok_15m: bool = False
    ok_5m: bool = False
    last_eval_1m_open_time_ms: int = 0
    retries_4h: int = 0
    retries_1h: int = 0
    retries_15m: int = 0
    retries_5m: int = 0
    next_allowed_eval_at_ms: int = 0


@dataclass
class OrderIntent:
    intent_key: str              # idempotence key
    symbol: str
    side: Side
    timeframe: Timeframe         # pour tracer l'origine (souvent "1m")
    open_time_ms: int
    payload: dict[str, Any]      # qty, price, type, lots, etc.
    status: IntentStatus = "NEW"


@dataclass
class Position:
    position_id: str
    symbol: str
    shard_id: int
    status: str                  # OPENING, OPEN, PARTIAL_EXIT, CLOSED
    qty_base: float
    avg_entry_price: float
    exit_plan: dict[str, Any]    # lots A/B/C, trailing, etc.
    next_check_at_ms: int



    temporal_app/activities.py
from __future__ import annotations

from temporalio import activity
from typing import Any, Optional

from .types import (
    CandleCloseEvent,
    IndicatorSnapshot,
    MtfState,
    OrderIntent,
    Position,
    Timeframe,
)

# =========================
# Helpers (placeholders)
# =========================

def stable_shard_of(symbol: str, shard_count: int) -> int:
    # IMPORTANT: utiliser un hash stable (crc32) en prod, pas hash() Python (variable).
    import zlib
    return zlib.crc32(symbol.encode("utf-8")) % shard_count


# =========================
# DB / Event ingestion
# =========================

@activity.defn(name="fetch_candle_close_events")
async def fetch_candle_close_events(shard_id: int, shard_count: int, limit: int) -> list[CandleCloseEvent]:
    """
    Récupère les candle_close_event non traités du shard.
    Implémentation recommandée : curseur watermark + ORDER BY open_time_ms / id.
    """
    # TODO: SELECT ... WHERE shard_id=? AND id > cursor LIMIT ?
    activity.logger.info("fetch_candle_close_events shard=%s limit=%s", shard_id, limit)
    return []


@activity.defn(name="mark_candle_close_events_processed")
async def mark_candle_close_events_processed(events: list[CandleCloseEvent]) -> None:
    """Marque/supprime les événements consommés (idempotent)."""
    # TODO: DELETE FROM candle_close_event WHERE (symbol,tf,open_time) IN (...)
    activity.logger.info("mark events processed count=%s", len(events))


# =========================
# Validation + Features
# =========================

@activity.defn(name="validate_candle_event")
async def validate_candle_event(evt: CandleCloseEvent) -> dict[str, Any]:
    """
    Sanity checks + détection de gaps.
    Retourne un dict (ok/gap/etc.). Si gap -> tu peux déclencher un backfill ailleurs.
    """
    # TODO: vérifier la bougie précédente, OHLCV, etc.
    return {"ok": True, "gap": False}


@activity.defn(name="compute_indicator_snapshot")
async def compute_indicator_snapshot(symbol: str, timeframe: Timeframe, open_time_ms: int) -> IndicatorSnapshot:
    """
    Calcule les indicateurs sur une fenêtre d'historique et persiste (ou retourne) un snapshot.
    """
    # TODO: charger N candles depuis DB + calcul RSI/EMA/MACD/ATR...
    payload = {"rsi": 50.0, "ema21": 0.0, "macd": 0.0, "atr": 0.0}
    return IndicatorSnapshot(symbol=symbol, timeframe=timeframe, open_time_ms=open_time_ms, payload=payload)


@activity.defn(name="load_latest_snapshots")
async def load_latest_snapshots(symbol: str) -> dict[Timeframe, Optional[IndicatorSnapshot]]:
    """
    Récupère les derniers snapshots disponibles pour 4h/1h/15m/5m/1m.
    """
    # TODO: SELECT latest per tf
    return {"4h": None, "1h": None, "15m": None, "5m": None, "1m": None}


@activity.defn(name="load_mtf_state")
async def load_mtf_state(symbol: str) -> MtfState:
    # TODO: SELECT mtf_state WHERE symbol=...
    return MtfState(symbol=symbol)


@activity.defn(name="save_mtf_state")
async def save_mtf_state(state: MtfState) -> None:
    # TODO: UPSERT mtf_state
    activity.logger.info("save_mtf_state symbol=%s", state.symbol)


# =========================
# Signal -> OrderIntent
# =========================

@activity.defn(name="cascade_validate_mtf")
async def cascade_validate_mtf(symbol: str, snapshots: dict[Timeframe, Optional[IndicatorSnapshot]], state: MtfState) -> dict[str, Any]:
    """
    Applique la cascade 4h->1h->15m->5m->1m.
    Retourne: {"ok": bool, "failed_tf": "5m"|..., "reason": "..."}.
    """
    # TODO: implémenter tes règles exactes
    # Exemple simplifié :
    if snapshots.get("4h") is None or snapshots.get("1h") is None:
        return {"ok": False, "failed_tf": "4h", "reason": "missing_context"}
    return {"ok": True, "failed_tf": None, "reason": "ok"}


@activity.defn(name="create_buy_intent")
async def create_buy_intent(symbol: str, open_time_ms: int) -> OrderIntent:
    """
    Crée/UPSERT un OrderIntent BUY idempotent via intent_key.
    """
    intent_key = f"buy:{symbol}:{open_time_ms}"
    payload = {"order_type": "LIMIT", "quote_budget": 100.0}
    # TODO: UPSERT order_intent(intent_key UNIQUE)
    return OrderIntent(intent_key=intent_key, symbol=symbol, side="BUY", timeframe="1m", open_time_ms=open_time_ms, payload=payload)


@activity.defn(name="create_sell_intent")
async def create_sell_intent(position_id: str, symbol: str, lot_id: str, qty_pct: float) -> OrderIntent:
    intent_key = f"sell:{position_id}:{lot_id}"
    payload = {"order_type": "LIMIT", "qty_pct": qty_pct, "lot_id": lot_id}
    # TODO: UPSERT order_intent
    return OrderIntent(intent_key=intent_key, symbol=symbol, side="SELL", timeframe="1m", open_time_ms=0, payload=payload)


# =========================
# Execution (Binance via REST)
# =========================

@activity.defn(name="place_order")
async def place_order(intent: OrderIntent) -> dict[str, Any]:
    """
    Exécute l'intent sur Binance (I/O).
    """
    # TODO: call Binance REST, apply quantization, handle rate limits/retries.
    activity.logger.info("place_order %s %s", intent.side, intent.symbol)
    return {"ok": True, "order_id": "123456", "client_order_id": intent.intent_key}


@activity.defn(name="cancel_order")
async def cancel_order(symbol: str, order_id: str) -> dict[str, Any]:
    # TODO: Binance cancel
    return {"ok": True}


# =========================
# Positions + Exit Engine
# =========================

@activity.defn(name="fetch_due_positions")
async def fetch_due_positions(shard_id: int, limit: int) -> list[Position]:
    """
    Récupère les positions à traiter (next_check_at <= now).
    """
    # TODO: SELECT FROM position WHERE shard_id=? AND status IN (...) AND next_check_at<=now LIMIT ?
    return []


@activity.defn(name="apply_exit_engine")
async def apply_exit_engine(pos: Position) -> dict[str, Any]:
    """
    Calcule les actions de sortie (sell% / hold%) selon exit_plan + état.
    Retourne ex: {"actions":[{"type":"SELL","lot":"A","pct":0.60}, ...], "next_check_in_ms": 10000}
    """
    # TODO: TP1/TP2/runner trailing/time-stop...
    return {"actions": [], "next_check_in_ms": 10_000}


@activity.defn(name="update_position_after_actions")
async def update_position_after_actions(position_id: str, patch: dict[str, Any]) -> None:
    # TODO: UPDATE position SET ...
    activity.logger.info("update_position %s patch=%s", position_id, patch)


# =========================
# Reconciliation / Maintenance
# =========================

@activity.defn(name="reconcile_klines")
async def reconcile_klines() -> dict[str, Any]:
    """
    Détecte les gaps et backfill via REST si nécessaire.
    """
    # TODO: scan per symbol/tf, backfill /api/v3/klines
    return {"ok": True, "gaps_filled": 0}


@activity.defn(name="reconcile_orders")
async def reconcile_orders() -> dict[str, Any]:
    """
    Resync ordres/positions vs Binance REST.
    """
    # TODO: fetch open orders, compare DB, patch states
    return {"ok": True, "fixed": 0}


@activity.defn(name="refresh_exchange_info")
async def refresh_exchange_info() -> dict[str, Any]:
    """
    Refresh exchangeInfo (filters LOT_SIZE/PRICE_FILTER/MIN_NOTIONAL...).
    """
    # TODO: call exchangeInfo, store cache
    return {"ok": True}



temporal_app/workflows.py

from __future__ import annotations

from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

from .types import CandleCloseEvent, Position


DEFAULT_RETRY = RetryPolicy(maximum_attempts=3)

AIO_TIMEOUT = timedelta(seconds=30)


@workflow.defn
class ConsumeCandleEventsWorkflow:
    """
    Batch consumer par shard :
    - lit candle_close_event
    - valide + calcule snapshot
    - met à jour mtf_state
    """
    @workflow.run
    async def run(self, shard_id: int, shard_count: int, batch_limit: int = 500) -> dict:
        events: list[CandleCloseEvent] = await workflow.execute_activity(
            "fetch_candle_close_events",
            shard_id, shard_count, batch_limit,
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        processed = 0
        for evt in events:
            # 1) validation
            v = await workflow.execute_activity(
                "validate_candle_event",
                evt,
                start_to_close_timeout=AIO_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            if not v.get("ok", False):
                continue

            # 2) compute snapshot du TF concerné
            await workflow.execute_activity(
                "compute_indicator_snapshot",
                evt.symbol, evt.timeframe, evt.open_time_ms,
                start_to_close_timeout=AIO_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            processed += 1

        # marquer consommé
        if events:
            await workflow.execute_activity(
                "mark_candle_close_events_processed",
                events,
                start_to_close_timeout=AIO_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )

        return {"shard": shard_id, "events": len(events), "processed": processed}


@workflow.defn
class CascadeValidateAndEnterWorkflow:
    """
    Cascade 4h->1h->15m->5m->1m pour un symbol et une clôture 1m,
    puis création + exécution d'un BUY intent.
    """
    @workflow.run
    async def run(self, symbol: str, open_time_ms_1m: int) -> dict:
        snapshots = await workflow.execute_activity(
            "load_latest_snapshots",
            symbol,
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        state = await workflow.execute_activity(
            "load_mtf_state",
            symbol,
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        decision = await workflow.execute_activity(
            "cascade_validate_mtf",
            symbol, snapshots, state,
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        if not decision.get("ok", False):
            # update state (retry counters / next_allowed_eval) côté activity si tu veux
            return {"ok": False, "symbol": symbol, "failed_tf": decision.get("failed_tf"), "reason": decision.get("reason")}

        # create intent (idempotent)
        intent = await workflow.execute_activity(
            "create_buy_intent",
            symbol, open_time_ms_1m,
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        # execution
        placed = await workflow.execute_activity(
            "place_order",
            intent,
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )

        return {"ok": True, "symbol": symbol, "intent_key": intent.intent_key, "placed": placed}


@workflow.defn
class ProcessClosedCandlesWorkflow:
    """
    Workflow “wrapper” appelé par Schedule :
    - consomme les events (batch shard)
    - (optionnel) déclenche la cascade sur les events 1m (si tu veux le faire ici)
    """
    @workflow.run
    async def run(self, shard_id: int, shard_count: int) -> dict:
        # 1) consume events + compute snapshots
        summary = await workflow.execute_child_workflow(
            ConsumeCandleEventsWorkflow.run,
            shard_id, shard_count, 500,
        )
        # 2) option: ici tu pourrais relire les events 1m traités et lancer CascadeValidate...
        return {"ok": True, "summary": summary}


@workflow.defn
class ManageOpenPositionsWorkflow:
    """
    Tick batch par shard :
    - charge positions dues
    - applique ExitEngine -> SELL intents -> place orders
    """
    @workflow.run
    async def run(self, shard_id: int, max_positions: int = 200) -> dict:
        positions: list[Position] = await workflow.execute_activity(
            "fetch_due_positions",
            shard_id, max_positions,
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        acted = 0
        for pos in positions:
            out = await workflow.execute_activity(
                "apply_exit_engine",
                pos,
                start_to_close_timeout=AIO_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            actions = out.get("actions", [])
            for a in actions:
                if a.get("type") == "SELL":
                    intent = await workflow.execute_activity(
                        "create_sell_intent",
                        pos.position_id, pos.symbol, a.get("lot", "A"), float(a.get("pct", 0.0)),
                        start_to_close_timeout=AIO_TIMEOUT,
                        retry_policy=DEFAULT_RETRY,
                    )
                    await workflow.execute_activity(
                        "place_order",
                        intent,
                        start_to_close_timeout=timedelta(seconds=20),
                        retry_policy=RetryPolicy(maximum_attempts=5),
                    )
                    acted += 1

            # update position next_check
            next_in = int(out.get("next_check_in_ms", 10_000))
            await workflow.execute_activity(
                "update_position_after_actions",
                pos.position_id, {"next_check_in_ms": next_in},
                start_to_close_timeout=AIO_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )

        return {"ok": True, "shard": shard_id, "positions": len(positions), "actions": acted}


@workflow.defn
class ReconcileKlinesWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            "reconcile_klines",
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


@workflow.defn
class ReconcileOrdersWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            "reconcile_orders",
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


@workflow.defn
class RefreshExchangeInfoWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            "refresh_exchange_info",
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


@workflow.defn
class IntentDispatcherWorkflow:
    """
    Optionnel : isoler l'exécution d'un intent (BUY/SELL) + gestion erreurs.
    """
    @workflow.run
    async def run(self, intent_key: str) -> dict:
        # TODO: load intent from DB, then place/cancel with stronger retry semantics
        return {"ok": True, "intent_key": intent_key}


@workflow.defn
class PositionWorkflow:
    """
    Optionnel : 1 workflow par position (au lieu de ManageOpenPositions batch).
    """
    @workflow.run
    async def run(self, position_id: str) -> dict:
        # TODO: loop avec timers, continue-as-new si besoin
        return {"ok": True, "position_id": position_id}


  Voici un daemon Python (service long-lived) qui :

ouvre 1 seule connexion WebSocket Binance et s’abonne à 150 streams @kline_1m (chunké pour respecter la limite “5 messages/s” côté client)

ne persiste que les bougies 1m fermées (k.x == true)

agrège à partir de ces 1m pour produire 5m / 15m / 1h / 4h

upsert les candles en DB + insère des événements candle_close_event idempotents (les klines sont identifiées par leur open_time)


1) Schéma SQL minimal (PostgreSQL)

CREATE TABLE IF NOT EXISTS candles (
  symbol        TEXT   NOT NULL,
  timeframe     TEXT   NOT NULL,            -- '1m','5m','15m','1h','4h'
  open_time_ms  BIGINT NOT NULL,
  close_time_ms BIGINT NOT NULL,
  open          NUMERIC NOT NULL,
  high          NUMERIC NOT NULL,
  low           NUMERIC NOT NULL,
  close         NUMERIC NOT NULL,
  volume        NUMERIC NOT NULL,
  is_partial    BOOLEAN NOT NULL DEFAULT FALSE,
  shard_id      INT NOT NULL,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(symbol, timeframe, open_time_ms)
);

CREATE TABLE IF NOT EXISTS candle_close_event (
  id           BIGSERIAL PRIMARY KEY,
  symbol       TEXT   NOT NULL,
  timeframe    TEXT   NOT NULL,
  open_time_ms BIGINT NOT NULL,
  shard_id     INT    NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(symbol, timeframe, open_time_ms)
);

-- optionnel : log de gaps 1m (pour backfill REST ensuite)
CREATE TABLE IF NOT EXISTS candle_gap_request (
  id               BIGSERIAL PRIMARY KEY,
  symbol           TEXT NOT NULL,
  from_open_time_ms BIGINT NOT NULL,
  to_open_time_ms   BIGINT NOT NULL,
  detected_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


2) Le daemon (un seul fichier, prêt à lancer)

Dépendances
pip install websockets asyncpg

ws_candle_daemon.py

import asyncio
import json
import os
import time
import zlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import asyncpg
import websockets

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
MIN_MS = 60_000

TF_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
}
DERIVED_TFS = ["5m", "15m", "1h", "4h"]


def stable_shard(symbol: str, shard_count: int) -> int:
    return zlib.crc32(symbol.encode("utf-8")) % shard_count


def env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    return default if v is None or v.strip() == "" else int(v)


def load_symbols() -> List[str]:
    raw = os.environ.get("SYMBOLS", "").strip()
    if not raw:
        raise RuntimeError("SYMBOLS env est vide (ex: BTCUSDT,ETHUSDT,...)")
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


@dataclass
class Candle:
    symbol: str
    timeframe: str
    open_time_ms: int
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_partial: bool = False


@dataclass
class AggState:
    bucket_start_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    last_close_time_ms: int
    count_1m: int
    is_partial: bool = False

    def to_candle(self, symbol: str, tf: str) -> Candle:
        return Candle(
            symbol=symbol,
            timeframe=tf,
            open_time_ms=self.bucket_start_ms,
            close_time_ms=self.last_close_time_ms,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            is_partial=self.is_partial,
        )


class MultiTfAggregator:
    """
    Agrège uniquement à partir des 1m *fermées*.
    Si un gap 1m est détecté, on marque les agrégats en partial et on log un gap_request.
    """
    def __init__(self) -> None:
        self.last_1m_open: Optional[int] = None
        self.states: Dict[str, Optional[AggState]] = {tf: None for tf in DERIVED_TFS}

    def on_closed_1m(self, c1m: Candle) -> Tuple[List[Candle], Optional[Tuple[int, int]]]:
        closed_out: List[Candle] = []
        gap: Optional[Tuple[int, int]] = None

        # Detect gap on 1m (best-effort)
        if self.last_1m_open is not None:
            expected = self.last_1m_open + MIN_MS
            if c1m.open_time_ms != expected:
                gap = (expected, c1m.open_time_ms)
                # Mark all current aggregates as partial
                for tf in DERIVED_TFS:
                    st = self.states.get(tf)
                    if st is not None:
                        st.is_partial = True

        self.last_1m_open = c1m.open_time_ms

        # Update each derived TF
        for tf in DERIVED_TFS:
            tf_ms = TF_MS[tf]
            bucket = c1m.open_time_ms - (c1m.open_time_ms % tf_ms)
            st = self.states[tf]

            # New bucket => flush old (partial or complete)
            if st is not None and st.bucket_start_ms != bucket:
                closed_out.append(st.to_candle(c1m.symbol, tf))
                st = None

            # Create / update current bucket
            if st is None:
                st = AggState(
                    bucket_start_ms=bucket,
                    open=c1m.open,
                    high=c1m.high,
                    low=c1m.low,
                    close=c1m.close,
                    volume=c1m.volume,
                    last_close_time_ms=c1m.close_time_ms,
                    count_1m=1,
                    is_partial=False,
                )
                self.states[tf] = st
            else:
                st.high = max(st.high, c1m.high)
                st.low = min(st.low, c1m.low)
                st.close = c1m.close
                st.volume += c1m.volume
                st.last_close_time_ms = c1m.close_time_ms
                st.count_1m += 1

            # Close bucket when next minute would start a new bucket boundary:
            # ex: for 5m, when (open_time + 1m) % 5m == 0 => last minute of the 5m bucket.
            if ((c1m.open_time_ms + MIN_MS) % tf_ms) == 0:
                closed_out.append(st.to_candle(c1m.symbol, tf))
                self.states[tf] = None

        return closed_out, gap


# ---------------- DB layer ----------------

UPSERT_CANDLE_SQL = """
INSERT INTO candles(symbol, timeframe, open_time_ms, close_time_ms, open, high, low, close, volume, is_partial, shard_id)
VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
ON CONFLICT(symbol, timeframe, open_time_ms) DO UPDATE
SET close_time_ms = EXCLUDED.close_time_ms,
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low  = EXCLUDED.low,
    close= EXCLUDED.close,
    volume = EXCLUDED.volume,
    is_partial = EXCLUDED.is_partial,
    shard_id = EXCLUDED.shard_id,
    updated_at = now()
"""

INSERT_EVENT_SQL = """
INSERT INTO candle_close_event(symbol, timeframe, open_time_ms, shard_id)
VALUES($1,$2,$3,$4)
ON CONFLICT(symbol, timeframe, open_time_ms) DO NOTHING
"""

INSERT_GAP_SQL = """
INSERT INTO candle_gap_request(symbol, from_open_time_ms, to_open_time_ms)
VALUES($1,$2,$3)
"""


async def get_pool() -> asyncpg.Pool:
    db = os.environ.get("DATABASE_URL", "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL env est vide")
    return await asyncpg.create_pool(db, min_size=1, max_size=10)


async def persist_candles_and_events(pool: asyncpg.Pool, candles: List[Candle], shard_count: int) -> None:
    if not candles:
        return

    async with pool.acquire() as conn:
        async with conn.transaction():
            for c in candles:
                sid = stable_shard(c.symbol, shard_count)
                await conn.execute(
                    UPSERT_CANDLE_SQL,
                    c.symbol, c.timeframe, c.open_time_ms, c.close_time_ms,
                    c.open, c.high, c.low, c.close, c.volume,
                    c.is_partial, sid
                )
                await conn.execute(INSERT_EVENT_SQL, c.symbol, c.timeframe, c.open_time_ms, sid)


async def persist_gap(pool: asyncpg.Pool, symbol: str, gap_from: int, gap_to: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(INSERT_GAP_SQL, symbol, gap_from, gap_to)


# ---------------- WS client ----------------

async def subscribe_in_chunks(ws, symbols: List[str], chunk_size: int = 200) -> None:
    """
    Binance limite les messages entrants (PING/PONG/JSON subscribe) à 5/s. :contentReference[oaicite:2]{index=2}
    On envoie des SUBSCRIBE par paquets + petit sleep.
    """
    streams = [f"{s.lower()}@kline_1m" for s in symbols]
    msg_id = 1
    for i in range(0, len(streams), chunk_size):
        part = streams[i:i + chunk_size]
        msg = {"method": "SUBSCRIBE", "params": part, "id": msg_id}
        await ws.send(json.dumps(msg))
        msg_id += 1
        await asyncio.sleep(0.25)  # ~4 msg/s (safe)


def parse_closed_1m(msg: dict) -> Optional[Candle]:
    # Expect event type kline
    if msg.get("e") != "kline":
        return None
    k = msg.get("k")
    if not isinstance(k, dict):
        return None
    if not k.get("x"):  # only closed candles
        return None

    symbol = str(k["s"]).upper()
    open_time_ms = int(k["t"])
    close_time_ms = int(k["T"])

    # Binance numbers are strings
    o = float(k["o"])
    h = float(k["h"])
    l = float(k["l"])
    c = float(k["c"])
    v = float(k["v"])

    return Candle(
        symbol=symbol,
        timeframe="1m",
        open_time_ms=open_time_ms,
        close_time_ms=close_time_ms,
        open=o, high=h, low=l, close=c, volume=v,
        is_partial=False,
    )


async def ws_loop():
    symbols = load_symbols()
    shard_count = env_int("SHARD_COUNT", 8)
    pool = await get_pool()

    aggs: Dict[str, MultiTfAggregator] = {s: MultiTfAggregator() for s in symbols}

    while True:
        try:
            async with websockets.connect(
                BINANCE_WS_URL,
                ping_interval=20,
                ping_timeout=20,
                max_queue=10_000,
            ) as ws:
                await subscribe_in_chunks(ws, symbols, chunk_size=200)
                print(f"[ws] connected, subscribed to {len(symbols)} streams")

                async for raw in ws:
                    msg = json.loads(raw)

                    # Ignore subscribe acks like {"result":null,"id":1}
                    if "result" in msg and "id" in msg and msg.get("result") is None:
                        continue

                    c1m = parse_closed_1m(msg)
                    if c1m is None:
                        continue

                    # 1) Persist 1m + event
                    to_persist: List[Candle] = [c1m]

                    # 2) Build derived candles
                    agg = aggs.get(c1m.symbol)
                    if agg is None:
                        agg = MultiTfAggregator()
                        aggs[c1m.symbol] = agg

                    derived_closed, gap = agg.on_closed_1m(c1m)
                    to_persist.extend(derived_closed)

                    await persist_candles_and_events(pool, to_persist, shard_count)

                    # 3) Log gap request (optionnel)
                    if gap is not None:
                        gap_from, gap_to = gap
                        await persist_gap(pool, c1m.symbol, gap_from, gap_to)
                        print(f"[gap] {c1m.symbol} missing 1m from {gap_from} to {gap_to}")

        except Exception as e:
            print("[ws] disconnected, retry in 2s:", repr(e))
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(ws_loop())


3) Comment tu lances ce daemon

export DATABASE_URL="postgresql://user:pass@localhost:5432/trading"
export SYMBOLS="BTCUSDT,ETHUSDT,BNBUSDT,..."     # tes 150
export SHARD_COUNT="8"

python ws_candle_daemon.py


