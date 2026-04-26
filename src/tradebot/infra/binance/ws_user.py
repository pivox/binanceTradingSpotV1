from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional, TYPE_CHECKING

import aiohttp
import structlog
import websockets

if TYPE_CHECKING:
    from temporalio.client import Client as TemporalClient

log = structlog.get_logger()

TEMPORAL_TASK_QUEUE = "tradebot"

_LISTEN_KEY_RENEW_INTERVAL_S = 25 * 60  # renew every 25 min (Binance expires after 60 min)
_RECONNECT_BASE_DELAY_S = 2
_RECONNECT_MAX_DELAY_S = 60

_UPD_INTENT_SQL = """
UPDATE order_intents
SET status        = $1,
    filled_qty    = $2,
    avg_price     = $3,
    binance_order_id = $4,
    updated_at_ms = $5
WHERE intent_key = $6
  AND status NOT IN ('FILLED', 'CANCELLED', 'FAILED')
"""

_GET_POSITION_ROW_SQL = """
SELECT p.id, p.status, p.exit_plan_json
FROM positions p
JOIN order_intents oi ON oi.position_id = p.id
WHERE oi.intent_key = $1
"""

_UPD_POSITION_ACTIVE_SQL = """
UPDATE positions
SET status = 'ACTIVE', entry_price = $1
WHERE id = $2
  AND status IN ('PENDING_ENTRY', 'OPEN_ENTRY_SENT')
"""

_UPD_POSITION_EXIT_PLAN_SQL = """
UPDATE positions
SET exit_plan_json = $1
WHERE id = $2
"""

_UPD_POSITION_CLOSED_SQL = """
UPDATE positions
SET status = 'CLOSED', closed_at_ms = $1
WHERE id = $2
  AND status NOT IN ('CLOSED')
"""

# Binance executionReport X field → DB status
_STATUS_MAP: dict[str, str] = {
    "NEW": "SENT",
    "PARTIALLY_FILLED": "PARTIALLY_FILLED",
    "FILLED": "FILLED",
    "CANCELED": "CANCELLED",
    "EXPIRED": "CANCELLED",
    "REJECTED": "FAILED",
}


def _lot_id_from_intent_key(intent_key: str) -> str:
    """Extract lot id from 'sell:{position_id}:{lot_id}'."""
    parts = intent_key.split(":")
    return parts[-1] if len(parts) >= 3 else "A"


def _mark_lot_filled(exit_plan: dict, lot_id: str, fill_price: str, fill_time_ms: int) -> None:
    for lot in exit_plan.get("lots", []):
        if lot.get("id") == lot_id:
            lot["is_filled"] = True
            lot["fill_price"] = fill_price
            lot["fill_time_ms"] = fill_time_ms
            break


class BinanceWsUser:
    """
    Connects to Binance User Data Stream and persists order/position updates.

    Lifecycle:
      1. Creates a listen key via REST.
      2. Connects to wss://{ws_url}/{listenKey}.
      3. Renews the listen key every 25 minutes.
      4. On executionReport events, updates order_intents and positions tables.
      5. Reconnects with exponential backoff on any error.
    """

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        ws_url: str,
        rest_url: str,
        pool: Any,  # asyncpg.Pool
        shard_count: int = 8,
        temporal_client: Optional[Any] = None,  # temporalio.client.Client
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._ws_url = ws_url.rstrip("/")
        self._rest_url = rest_url.rstrip("/")
        self._pool = pool
        self._shard_count = shard_count
        self._temporal_client = temporal_client

    # ── Listen key management ─────────────────────────────────────────────────

    async def _listen_key_request(
        self, method: str, listen_key: Optional[str] = None
    ) -> Optional[str]:
        url = f"{self._rest_url}/api/v3/userDataStream"
        headers = {"X-MBX-APIKEY": self._api_key}
        params: dict = {}
        if listen_key is not None:
            params["listenKey"] = listen_key
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(method, url, headers=headers, params=params) as resp:
                if resp.status not in (200, 204):
                    text = (await resp.text())[:300]
                    raise RuntimeError(
                        f"listen key {method} failed: status={resp.status} body={text}"
                    )
                if method == "POST":
                    data = await resp.json()
                    return str(data["listenKey"])
                return None

    async def _create_listen_key(self) -> str:
        key = await self._listen_key_request("POST")
        log.info("user_stream_listen_key_created")
        return key  # type: ignore[return-value]

    async def _renew_listen_key(self, listen_key: str) -> None:
        await self._listen_key_request("PUT", listen_key)
        log.info("user_stream_listen_key_renewed")

    async def _delete_listen_key(self, listen_key: str) -> None:
        try:
            await self._listen_key_request("DELETE", listen_key)
        except Exception as exc:
            log.warning("user_stream_delete_key_failed", error=str(exc))

    async def _renew_loop(self, listen_key: str) -> None:
        """Background task: keeps the listen key alive."""
        while True:
            await asyncio.sleep(_LISTEN_KEY_RENEW_INTERVAL_S)
            try:
                await self._renew_listen_key(listen_key)
            except Exception as exc:
                log.warning("user_stream_renew_failed", error=str(exc))

    # ── Event handlers ────────────────────────────────────────────────────────

    async def _handle_execution_report(self, msg: dict) -> None:
        symbol = str(msg.get("s", "")).upper()
        client_order_id = str(msg.get("c", ""))
        binance_order_id = int(msg.get("i", 0))
        binance_status = str(msg.get("X", "")).upper()
        side = str(msg.get("S", "")).upper()
        cum_qty = str(msg.get("z", "0"))
        # avg fill price: "ap" field or last executed price "L"
        avg_price = str(msg.get("ap") or msg.get("L") or "0")

        db_status = _STATUS_MAP.get(binance_status)
        if db_status is None:
            return

        now_ms = int(time.time() * 1000)
        intent_key = client_order_id

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                updated = await conn.execute(
                    _UPD_INTENT_SQL,
                    db_status,
                    cum_qty,
                    avg_price,
                    binance_order_id,
                    now_ms,
                    intent_key,
                )
                log.info(
                    "user_stream_order_update",
                    symbol=symbol,
                    intent_key=intent_key,
                    status=db_status,
                    rows=updated,
                )

                if db_status != "FILLED":
                    return

                # Order filled — update position
                row = await conn.fetchrow(_GET_POSITION_ROW_SQL, intent_key)
                if row is None:
                    log.warning("user_stream_position_not_found", intent_key=intent_key)
                    return

                pos_id = str(row["id"])

                if side == "BUY":
                    await conn.execute(_UPD_POSITION_ACTIVE_SQL, avg_price, pos_id)
                    log.info(
                        "user_stream_position_activated",
                        position_id=pos_id,
                        avg_price=avg_price,
                    )
                    # F-002: place SL + TP orders via Temporal workflow
                    if self._temporal_client is not None:
                        asyncio.create_task(
                            self._start_post_fill_workflow(pos_id),
                            name=f"post-fill-{pos_id}",
                        )

                elif side == "SELL":
                    lot_id = _lot_id_from_intent_key(intent_key)
                    exit_plan_raw = row["exit_plan_json"]
                    try:
                        exit_plan: dict = json.loads(exit_plan_raw) if exit_plan_raw else {}
                        _mark_lot_filled(exit_plan, lot_id, avg_price, now_ms)
                        await conn.execute(
                            _UPD_POSITION_EXIT_PLAN_SQL, json.dumps(exit_plan), pos_id
                        )
                        log.info(
                            "user_stream_lot_filled",
                            position_id=pos_id,
                            lot_id=lot_id,
                            avg_price=avg_price,
                        )
                        # F-005: close position when all lots are filled
                        all_filled = all(lot.get("is_filled") for lot in exit_plan.get("lots", []))
                        if all_filled:
                            await conn.execute(_UPD_POSITION_CLOSED_SQL, now_ms, pos_id)
                            log.info("user_stream_position_closed", position_id=pos_id)
                            sl_order_id = exit_plan.get("sl_order_id")
                            if sl_order_id:
                                asyncio.create_task(
                                    self._cancel_binance_order(symbol, int(sl_order_id)),
                                    name=f"cancel-sl-{pos_id}",
                                )
                    except Exception as exc:
                        log.warning(
                            "user_stream_exit_plan_update_failed",
                            position_id=pos_id,
                            error=str(exc),
                        )

    async def _start_post_fill_workflow(self, position_id: str) -> None:
        """F-002: launch PostFillSetupWorkflow after BUY fill."""
        try:
            await self._temporal_client.start_workflow(  # type: ignore[union-attr]
                "PostFillSetupWorkflow",
                position_id,
                id=f"post-fill-{position_id}",
                task_queue=TEMPORAL_TASK_QUEUE,
            )
            log.info("user_stream_post_fill_workflow_started", position_id=position_id)
        except Exception as exc:
            log.warning("user_stream_post_fill_workflow_failed",
                        position_id=position_id, error=str(exc))

    async def _cancel_binance_order(self, symbol: str, order_id: int) -> None:
        """F-005: cancel the SL order when all lots are filled."""
        try:
            from tradebot.infra.binance._signing import add_auth_params
            params: dict = {"symbol": symbol, "orderId": order_id}
            add_auth_params(params, self._api_secret)
            headers = {"X-MBX-APIKEY": self._api_key}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.delete(
                    f"{self._rest_url}/api/v3/order",
                    params=params,
                    headers=headers,
                ) as resp:
                    if resp.status not in (200, 204, 400):  # 400 may be -2011 (already gone)
                        body = (await resp.text())[:200]
                        log.warning("user_stream_cancel_sl_failed", symbol=symbol,
                                    order_id=order_id, status=resp.status, body=body)
                    else:
                        log.info("user_stream_sl_cancelled", symbol=symbol, order_id=order_id)
        except Exception as exc:
            log.warning("user_stream_cancel_sl_error", symbol=symbol,
                        order_id=order_id, error=str(exc))

    async def _handle_message(self, msg: dict) -> None:
        event_type = str(msg.get("e", ""))
        if event_type == "executionReport":
            await self._handle_execution_report(msg)
        # outboundAccountPosition / balanceUpdate: no action needed for now

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Connect and process events forever, reconnecting on any error."""
        reconnect_attempt = 0
        while True:
            listen_key: Optional[str] = None
            renew_task: Optional[asyncio.Task] = None
            try:
                listen_key = await self._create_listen_key()
                renew_task = asyncio.create_task(self._renew_loop(listen_key))

                ws_endpoint = f"{self._ws_url}/{listen_key}"
                async with websockets.connect(
                    ws_endpoint,
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:
                    log.info("user_stream_connected", endpoint=ws_endpoint)
                    reconnect_attempt = 0
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            await self._handle_message(msg)
                        except Exception as exc:
                            log.warning("user_stream_msg_error", error=repr(exc))

            except Exception as exc:
                log.error("user_stream_disconnected", error=repr(exc))
                reconnect_attempt += 1
                delay_s = min(
                    _RECONNECT_MAX_DELAY_S,
                    _RECONNECT_BASE_DELAY_S * (2 ** (reconnect_attempt - 1)),
                )
                log.info(
                    "user_stream_reconnect_scheduled",
                    attempt=reconnect_attempt,
                    delay_s=delay_s,
                )
                await asyncio.sleep(delay_s)
            finally:
                if renew_task is not None:
                    renew_task.cancel()
                    try:
                        await renew_task
                    except asyncio.CancelledError:
                        pass
                if listen_key is not None:
                    await self._delete_listen_key(listen_key)
