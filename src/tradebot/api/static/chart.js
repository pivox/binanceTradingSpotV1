const DEFAULT_SYMBOL = "BTCUSDC";
const DEFAULT_TIMEFRAME = "1m";
const DEFAULT_LIMIT = 500;
const MAX_RENDER_CANDLES = 500;
const FALLBACK_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h"];
const TIMEFRAME_RE = /^[1-9][0-9]*[mhdwM]$/;

const chartStateEl = document.getElementById("chartState");
const chartHostEl = document.getElementById("chartHost");
const pairValueEl = document.getElementById("pairValue");
const timeframeValueEl = document.getElementById("timeframeValue");
const countValueEl = document.getElementById("countValue");
const lastOpenValueEl = document.getElementById("lastOpenValue");
const liveUpdateValueEl = document.getElementById("liveUpdateValue");
const liveStatusValueEl = document.getElementById("liveStatusValue");
const ohlcOpenEl = document.getElementById("ohlcOpen");
const ohlcHighEl = document.getElementById("ohlcHigh");
const ohlcLowEl = document.getElementById("ohlcLow");
const ohlcCloseEl = document.getElementById("ohlcClose");
const indicatorMetaEl = document.getElementById("indicatorMeta");
const indicatorStatusEl = document.getElementById("indicatorStatus");
const indicatorGridEl = document.getElementById("indicatorGrid");
const timeframeSwitchEl = document.getElementById("timeframeSwitch");
const timeframeHintEl = document.getElementById("timeframeHint");
const pairTriggerEl = document.getElementById("pairTrigger");
const symbolOverlayEl = document.getElementById("symbolOverlay");
const symbolListEl = document.getElementById("symbolList");
const symbolHelpEl = document.getElementById("symbolHelp");
const symbolCloseBtnEl = document.getElementById("symbolCloseBtn");
const symbolSearchInputEl = document.getElementById("symbolSearchInput");
const symbolTrendFilterEl = document.getElementById("symbolTrendFilter");
const symbolSortByEl = document.getElementById("symbolSortBy");
const symbolSortDirectionEl = document.getElementById("symbolSortDirection");

const state = {
  symbol: "",
  timeframe: "",
  candles: [],
  timeframes: [...FALLBACK_TIMEFRAMES],
  symbols: [],
  symbolsLoaded: false,
  symbolSearch: "",
  symbolTrendFilter: "all",
  symbolSortBy: "change_pct",
  symbolSortDirection: "desc",
  symbolMetrics: {},
  symbolMetricsLoading: false,
  symbolSearchTimerId: null,
  requestId: 0,
  overlayRequestId: 0,
  abortController: null,
  liveGeneration: 0,
  liveTimerId: null,
  liveAbortController: null,
  indicatorRequestId: 0,
  indicatorAbortController: null,
  indicatorSnapshot: null,
  indicatorLastFetchedAtMs: 0,
};

let chart = null;

function showState(kind, message) {
  chartStateEl.textContent = message;
  chartStateEl.className = "state visible " + kind;
}

function hideState() {
  chartStateEl.className = "state";
}

function setTimeframeHint(message) {
  timeframeHintEl.textContent = message;
}

function setLiveUpdateNow() {
  liveUpdateValueEl.textContent = new Date().toLocaleTimeString();
}

function setLiveStatus(message, tone = "idle") {
  liveStatusValueEl.textContent = message;
  liveStatusValueEl.className = "live-status " + tone;
}

function setIndicatorStatus(message, tone = "idle") {
  indicatorStatusEl.textContent = message;
  indicatorStatusEl.className = "indicator-status " + tone;
}

function setPairTriggerLabel(symbol) {
  const value = symbol || "-";
  pairTriggerEl.textContent = "Pair: " + value;
  pairTriggerEl.setAttribute("aria-label", "Pair active " + value);
}

function isOverlayOpen() {
  return symbolOverlayEl.classList.contains("visible");
}

function openOverlayContainer() {
  symbolOverlayEl.hidden = false;
  symbolOverlayEl.classList.add("visible");
  pairTriggerEl.setAttribute("aria-expanded", "true");
}

function closeOverlayContainer({ restoreFocus = true } = {}) {
  state.overlayRequestId += 1;
  symbolOverlayEl.classList.remove("visible");
  symbolOverlayEl.hidden = true;
  pairTriggerEl.setAttribute("aria-expanded", "false");
  if (restoreFocus) {
    pairTriggerEl.focus();
  }
}

async function fetchPayload(url, options = {}) {
  const response = await fetch(url, options);
  let payload = null;
  try {
    payload = await response.json();
  } catch (_error) {
    throw new Error("Reponse invalide API chart");
  }

  if (!response.ok || !payload.ok) {
    const message = payload?.error?.message || "Erreur API chart";
    throw new Error(message);
  }
  return payload.data;
}

function formatPrice(value) {
  return Number(value).toFixed(4);
}

function formatNumber(value, digits) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  return number.toFixed(digits);
}

function formatSigned(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  if (number === 0) {
    return "0.0000";
  }
  return (number > 0 ? "+" : "") + number.toFixed(4);
}

function formatSignedPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  if (number === 0) {
    return "0.00%";
  }
  return (number > 0 ? "+" : "") + number.toFixed(2) + "%";
}

function computeTrend(changeValue) {
  const value = Number(changeValue);
  if (!Number.isFinite(value) || value === 0) {
    return "flat";
  }
  return value > 0 ? "up" : "down";
}

function formatDate(ms) {
  const value = Number(ms);
  if (!Number.isFinite(value)) {
    return "-";
  }
  return new Date(value).toLocaleString();
}

function getLastCloseTimeMs(candles) {
  if (!candles.length) {
    return null;
  }
  const last = candles[candles.length - 1];
  const ms = Number(last?.close_time_ms);
  return Number.isFinite(ms) ? ms : null;
}

function toCandleList(rows) {
  return rows
    .map((row) => ({
      open: Number(row.open),
      high: Number(row.high),
      low: Number(row.low),
      close: Number(row.close),
      open_time_ms: Number(row.open_time_ms),
      close_time_ms: Number(row.close_time_ms),
      volume: Number(row.volume),
      is_partial: Boolean(row.is_partial),
    }))
    .filter(
      (row) =>
        Number.isFinite(row.open) &&
        Number.isFinite(row.high) &&
        Number.isFinite(row.low) &&
        Number.isFinite(row.close) &&
        Number.isFinite(row.open_time_ms)
    )
    .sort((a, b) => a.open_time_ms - b.open_time_ms);
}

function timeframeRank(value) {
  const match = value.match(/^([1-9][0-9]*)([mhdwM])$/);
  if (!match) {
    return Number.MAX_SAFE_INTEGER;
  }
  const amount = Number(match[1]);
  const unit = match[2];
  const factor =
    {
      m: 1,
      h: 60,
      d: 1440,
      w: 10080,
      M: 43200,
    }[unit] || 1;
  return amount * factor;
}

function normalizeTimeframes(input) {
  const raw = Array.isArray(input) ? input : [];
  const dynamic = raw
    .map((value) => String(value || "").trim())
    .filter((value) => TIMEFRAME_RE.test(value));

  const merged = new Set([...FALLBACK_TIMEFRAMES, ...dynamic]);
  const extra = [...merged]
    .filter((value) => !FALLBACK_TIMEFRAMES.includes(value))
    .sort((a, b) => {
      const diff = timeframeRank(a) - timeframeRank(b);
      if (diff !== 0) {
        return diff;
      }
      return a.localeCompare(b);
    });
  return [...FALLBACK_TIMEFRAMES, ...extra];
}

function normalizeSymbols(input) {
  if (!Array.isArray(input)) {
    return [];
  }
  const out = new Set();
  for (const value of input) {
    const symbol = String(value || "").trim().toUpperCase();
    if (!symbol) {
      continue;
    }
    out.add(symbol);
  }
  return [...out].sort((a, b) => a.localeCompare(b));
}

function updateMeta(symbol, timeframe, candles) {
  pairValueEl.textContent = symbol || "-";
  timeframeValueEl.textContent = timeframe || "-";
  countValueEl.textContent = String(candles.length);
  lastOpenValueEl.textContent =
    candles.length > 0 ? formatDate(candles[candles.length - 1].open_time_ms) : "-";
  setPairTriggerLabel(symbol);

  const last = candles[candles.length - 1];
  if (!last) {
    ohlcOpenEl.textContent = "O: -";
    ohlcHighEl.textContent = "H: -";
    ohlcLowEl.textContent = "L: -";
    ohlcCloseEl.textContent = "C: -";
    return;
  }
  ohlcOpenEl.textContent = "O: " + formatPrice(last.open);
  ohlcHighEl.textContent = "H: " + formatPrice(last.high);
  ohlcLowEl.textContent = "L: " + formatPrice(last.low);
  ohlcCloseEl.textContent = "C: " + formatPrice(last.close);
}

function clearIndicators() {
  indicatorMetaEl.textContent = "-";
  indicatorGridEl.innerHTML = "";
  setIndicatorStatus("Indicateurs: -", "idle");
  state.indicatorSnapshot = null;
}

function normalizeIndicatorNode(node) {
  if (!node || typeof node !== "object") {
    return { status: "unavailable", reason: "missing" };
  }
  if (node.status === "available") {
    return { status: "available", value: Number(node.value) };
  }
  if (node.status === "unavailable") {
    return { status: "unavailable", reason: String(node.reason || "unavailable") };
  }
  return { status: "unavailable", reason: "invalid" };
}

function getIndicatorNode(snapshot, path) {
  let current = snapshot;
  for (const key of path) {
    if (!current || typeof current !== "object") {
      return null;
    }
    current = current[key];
  }
  return current;
}

function indicatorDigits(path) {
  const joined = path.join(".");
  if (joined === "rsi" || joined === "adx" || joined === "stoch_rsi.k" || joined === "stoch_rsi.d") {
    return 2;
  }
  if (joined.startsWith("macd.")) {
    return 6;
  }
  if (joined === "atr") {
    return 6;
  }
  return 4;
}

function renderIndicatorPill({ label, node, note }) {
  const normalized = normalizeIndicatorNode(node);
  const pill = document.createElement("div");
  pill.className = "indicator-pill" + (normalized.status !== "available" ? " unavailable" : "");

  const labelEl = document.createElement("div");
  labelEl.className = "label";
  labelEl.textContent = label;

  const valueEl = document.createElement("div");
  valueEl.className = "value";
  if (normalized.status === "available") {
    valueEl.textContent = formatNumber(normalized.value, indicatorDigits(note?.path || []));
  } else {
    valueEl.textContent = "-";
    pill.title = "Indicateur indisponible: " + (normalized.reason || "unavailable");
  }

  pill.append(labelEl, valueEl);

  if (note?.text) {
    const noteEl = document.createElement("div");
    noteEl.className = "note";
    noteEl.textContent = note.text;
    pill.append(noteEl);
  }

  return pill;
}

function renderIndicators(snapshot, lastCandleCloseTimeMs) {
  indicatorGridEl.innerHTML = "";
  if (!snapshot) {
    clearIndicators();
    return;
  }

  const closeTime = Number(snapshot.close_time);
  const computedAt = Number(snapshot.computed_at);
  const metaParts = [];
  if (Number.isFinite(closeTime)) {
    metaParts.push("close: " + formatDate(closeTime));
  }
  if (Number.isFinite(computedAt)) {
    metaParts.push("computed: " + formatDate(computedAt));
  }
  if (lastCandleCloseTimeMs != null && Number.isFinite(closeTime)) {
    const diff = lastCandleCloseTimeMs - closeTime;
    if (diff > 0) {
      metaParts.push("retard: " + Math.round(diff / 1000) + "s");
    }
  }
  indicatorMetaEl.textContent = metaParts.length ? metaParts.join(" • ") : "-";

  const defs = [
    { label: "RSI(14)", path: ["rsi"] },
    { label: "ATR(14)", path: ["atr"] },
    { label: "ADX(14)", path: ["adx"] },
    { label: "VWAP", path: ["vwap"] },
    { label: "EMA(20)", path: ["ema20"] },
    { label: "EMA(50)", path: ["ema50"] },
    { label: "EMA(200)", path: ["ema200"] },
    { label: "SMA(9)", path: ["sma9"] },
    { label: "SMA(21)", path: ["sma21"] },
    { label: "BB Upper", path: ["bollinger", "upper"] },
    { label: "BB Middle", path: ["bollinger", "middle"] },
    { label: "BB Lower", path: ["bollinger", "lower"] },
    { label: "MACD", path: ["macd", "macd"] },
    { label: "MACD Signal", path: ["macd", "signal"] },
    { label: "MACD Hist", path: ["macd", "hist"] },
    { label: "StochRSI K", path: ["stoch_rsi", "k"] },
    { label: "StochRSI D", path: ["stoch_rsi", "d"] },
    { label: "Pivot PP", path: ["pivots", "pp"] },
    { label: "Pivot R1", path: ["pivots", "r1"] },
    { label: "Pivot R2", path: ["pivots", "r2"] },
    { label: "Pivot R3", path: ["pivots", "r3"] },
    { label: "Pivot S1", path: ["pivots", "s1"] },
    { label: "Pivot S2", path: ["pivots", "s2"] },
    { label: "Pivot S3", path: ["pivots", "s3"] },
  ];

  for (const def of defs) {
    const node = getIndicatorNode(snapshot, def.path);
    indicatorGridEl.appendChild(
      renderIndicatorPill({
        label: def.label,
        node,
        note: { path: def.path, text: "" },
      })
    );
  }
}

async function fetchLatestIndicators(symbol, timeframe, signal) {
  return await fetchPayload(
    "/indicators/latest?symbol=" +
      encodeURIComponent(symbol) +
      "&timeframe=" +
      encodeURIComponent(timeframe),
    { signal }
  );
}

async function refreshIndicators({ reason = "manual" } = {}) {
  if (!state.symbol || !state.timeframe) {
    clearIndicators();
    return;
  }

  state.indicatorRequestId += 1;
  const requestId = state.indicatorRequestId;

  if (state.indicatorAbortController) {
    state.indicatorAbortController.abort();
  }
  state.indicatorAbortController = new AbortController();
  setIndicatorStatus(reason === "live" ? "Indicateurs: rafraichissement..." : "Indicateurs: chargement...", "idle");

  try {
    const snapshot = await fetchLatestIndicators(
      state.symbol,
      state.timeframe,
      state.indicatorAbortController.signal
    );
    if (requestId !== state.indicatorRequestId) {
      return;
    }
    state.indicatorSnapshot = snapshot;
    state.indicatorLastFetchedAtMs = Date.now();
    renderIndicators(snapshot, getLastCloseTimeMs(state.candles));
    setIndicatorStatus("Indicateurs: OK", "ok");
  } catch (error) {
    if (error?.name === "AbortError") {
      return;
    }
    if (requestId !== state.indicatorRequestId) {
      return;
    }
    state.indicatorSnapshot = null;
    indicatorMetaEl.textContent = "-";
    indicatorGridEl.innerHTML = "";
    setIndicatorStatus("Indicateurs: indisponibles", "err");
    console.error("indicator_latest_error", error);
  }
}

function maybeRefreshIndicatorsAfterLiveUpdate() {
  if (!state.symbol || !state.timeframe) {
    return;
  }
  const now = Date.now();
  if (now - (state.indicatorLastFetchedAtMs || 0) < 2500) {
    return;
  }

  const lastCandleClose = getLastCloseTimeMs(state.candles);
  if (lastCandleClose == null) {
    return;
  }
  const snapshotClose = Number(state.indicatorSnapshot?.close_time);
  if (!Number.isFinite(snapshotClose) || snapshotClose < lastCandleClose) {
    void refreshIndicators({ reason: "live" });
  }
}

function getLastOpenTimeMs(candles) {
  if (!candles.length) {
    return null;
  }
  return candles[candles.length - 1].open_time_ms;
}

function mergeCandles(existing, incoming) {
  if (!incoming.length) {
    return existing.slice(-MAX_RENDER_CANDLES);
  }
  const byOpenTime = new Map(existing.map((candle) => [candle.open_time_ms, candle]));
  for (const candle of incoming) {
    byOpenTime.set(candle.open_time_ms, candle);
  }
  const merged = [...byOpenTime.values()].sort((a, b) => a.open_time_ms - b.open_time_ms);
  if (merged.length > MAX_RENDER_CANDLES) {
    return merged.slice(-MAX_RENDER_CANDLES);
  }
  return merged;
}

function needsLiveFallbackFullReload(existing, incoming) {
  if (incoming.length >= DEFAULT_LIMIT) {
    return true;
  }
  for (let index = 1; index < incoming.length; index += 1) {
    if (incoming[index].open_time_ms <= incoming[index - 1].open_time_ms) {
      return true;
    }
  }
  const lastKnownOpen = getLastOpenTimeMs(existing);
  if (lastKnownOpen == null || incoming.length === 0) {
    return false;
  }
  return incoming[0].open_time_ms <= lastKnownOpen;
}

function pollDelayMs(timeframe, isHidden) {
  if (isHidden) {
    return 8000;
  }
  const match = String(timeframe || "").match(/^([1-9][0-9]*)([mhdwM])$/);
  if (!match) {
    return 1500;
  }

  const amount = Number(match[1]);
  const unit = match[2];
  if (unit === "m") {
    return Math.min(4000, 1000 + (amount - 1) * 200);
  }
  if (unit === "h") {
    return 5000;
  }
  return 10000;
}

function stopLiveUpdater({ bumpGeneration = true } = {}) {
  if (state.liveTimerId != null) {
    clearTimeout(state.liveTimerId);
    state.liveTimerId = null;
  }
  if (state.liveAbortController) {
    state.liveAbortController.abort();
    state.liveAbortController = null;
  }
  if (bumpGeneration) {
    state.liveGeneration += 1;
  }
}

function scheduleLiveTick(generation, delayMs) {
  if (state.liveTimerId != null) {
    clearTimeout(state.liveTimerId);
  }
  state.liveTimerId = setTimeout(() => {
    void runLiveTick(generation);
  }, delayMs);
}

function refreshChartFromState({ showEmptyOverlay = true } = {}) {
  const candles = state.candles;
  updateMeta(state.symbol, state.timeframe, candles);
  if (candles.length === 0) {
    chart.setData([]);
    clearIndicators();
    if (showEmptyOverlay) {
      showState(
        "empty",
        "Aucune donnee disponible pour " + state.symbol + " en " + state.timeframe + "."
      );
    }
    return;
  }
  chart.setData(candles);
  hideState();
}

async function fullReloadCurrentSelectionWithoutOverlay() {
  try {
    const candles = await fetchCandles(
      state.symbol,
      state.timeframe,
      state.liveAbortController?.signal
    );
    state.candles = candles;
    refreshChartFromState({ showEmptyOverlay: true });
    void refreshIndicators({ reason: "live" });
    setLiveUpdateNow();
    setLiveStatus("Live resynchronise", "ok");
  } catch (error) {
    if (error?.name === "AbortError") {
      return;
    }
    setLiveStatus("Erreur live temporaire (reprise auto)", "err");
    console.error("live_full_reload_error", error);
  }
}

async function runLiveTick(generation) {
  if (generation !== state.liveGeneration) {
    return;
  }
  if (!state.symbol || !state.timeframe) {
    return;
  }

  const hidden = document.visibilityState === "hidden";
  const fromOpenTimeMs = getLastOpenTimeMs(state.candles);
  const baseQuery =
    "/chart/candles?symbol=" +
    encodeURIComponent(state.symbol) +
    "&timeframe=" +
    encodeURIComponent(state.timeframe) +
    "&limit=" +
    DEFAULT_LIMIT;
  const url =
    fromOpenTimeMs == null
      ? baseQuery
      : baseQuery + "&from_open_time_ms=" + encodeURIComponent(fromOpenTimeMs);

  if (state.liveAbortController) {
    state.liveAbortController.abort();
  }
  state.liveAbortController = new AbortController();

  try {
    const rows = await fetchPayload(url, { signal: state.liveAbortController.signal });
    if (generation !== state.liveGeneration) {
      return;
    }

    const incoming = toCandleList(rows);
    setLiveUpdateNow();

    if (incoming.length === 0) {
      setLiveStatus(hidden ? "Live ralenti (onglet inactif)" : "Live actif, pas de nouveaute", "idle");
      return;
    }

    if (needsLiveFallbackFullReload(state.candles, incoming)) {
      await fullReloadCurrentSelectionWithoutOverlay();
      return;
    }

    state.candles = mergeCandles(state.candles, incoming);
    refreshChartFromState({ showEmptyOverlay: true });
    maybeRefreshIndicatorsAfterLiveUpdate();
    setLiveStatus("Live: +" + incoming.length + " bougie(s)", "ok");
  } catch (error) {
    if (error?.name === "AbortError") {
      return;
    }
    if (generation !== state.liveGeneration) {
      return;
    }
    setLiveStatus("Erreur live temporaire (reprise auto)", "err");
    console.error("live_poll_error", error);
  } finally {
    if (generation !== state.liveGeneration) {
      return;
    }
    scheduleLiveTick(generation, pollDelayMs(state.timeframe, document.hidden));
  }
}

function restartLiveUpdater() {
  stopLiveUpdater({ bumpGeneration: true });
  if (!state.symbol || !state.timeframe) {
    setLiveStatus("Live inactif", "idle");
    return;
  }

  const generation = state.liveGeneration;
  const hidden = document.visibilityState === "hidden";
  setLiveStatus(hidden ? "Live ralenti (onglet inactif)" : "Live actif", hidden ? "warn" : "ok");
  scheduleLiveTick(generation, pollDelayMs(state.timeframe, hidden));
}

class CandleCanvasChart {
  constructor(hostEl) {
    this.hostEl = hostEl;
    this.canvas = document.createElement("canvas");
    this.ctx = this.canvas.getContext("2d");
    this.data = [];
    this.width = 0;
    this.height = 0;
    this.palette = getComputedStyle(document.documentElement);
    this.hostEl.appendChild(this.canvas);

    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(this.hostEl);
    this.resize();
  }

  setData(data) {
    this.data = data;
    this.draw();
  }

  resize() {
    const rect = this.hostEl.getBoundingClientRect();
    const nextWidth = Math.max(320, Math.floor(rect.width));
    const nextHeight = Math.max(260, Math.floor(rect.height));
    if (nextWidth === this.width && nextHeight === this.height) {
      return;
    }

    this.width = nextWidth;
    this.height = nextHeight;

    const ratio = window.devicePixelRatio || 1;
    this.canvas.width = Math.floor(nextWidth * ratio);
    this.canvas.height = Math.floor(nextHeight * ratio);
    this.canvas.style.width = nextWidth + "px";
    this.canvas.style.height = nextHeight + "px";
    this.ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    this.draw();
  }

  draw() {
    const ctx = this.ctx;
    const width = this.width;
    const height = this.height;
    if (!ctx || width <= 0 || height <= 0) {
      return;
    }

    ctx.clearRect(0, 0, width, height);

    if (this.data.length === 0) {
      return;
    }

    const marginTop = 20;
    const marginBottom = 22;
    const marginLeft = 14;
    const marginRight = 66;
    const plotWidth = width - marginLeft - marginRight;
    const plotHeight = height - marginTop - marginBottom;

    if (plotWidth <= 0 || plotHeight <= 0) {
      return;
    }

    const highs = this.data.map((item) => item.high);
    const lows = this.data.map((item) => item.low);
    const maxRaw = Math.max(...highs);
    const minRaw = Math.min(...lows);
    const span = Math.max(1e-9, maxRaw - minRaw);
    const pad = span * 0.08;
    const minPrice = minRaw - pad;
    const maxPrice = maxRaw + pad;
    const fullSpan = Math.max(1e-9, maxPrice - minPrice);

    const yForPrice = (price) =>
      marginTop + ((maxPrice - price) / fullSpan) * plotHeight;

    this.drawGrid(ctx, marginLeft, marginTop, plotWidth, plotHeight, minPrice, maxPrice);
    this.drawCandles(ctx, marginLeft, plotWidth, yForPrice);
  }

  drawGrid(ctx, left, top, plotWidth, plotHeight, minPrice, maxPrice) {
    const lineColor = this.palette.getPropertyValue("--line").trim() || "#d0d7e8";
    const textColor = this.palette.getPropertyValue("--muted").trim() || "#5e6d8f";
    const guides = 5;
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 1;
    ctx.fillStyle = textColor;
    ctx.font = '12px "JetBrains Mono", monospace';
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";

    for (let i = 0; i < guides; i += 1) {
      const ratio = i / (guides - 1);
      const y = top + ratio * plotHeight;
      ctx.beginPath();
      ctx.moveTo(left, y);
      ctx.lineTo(left + plotWidth, y);
      ctx.stroke();

      const price = maxPrice - ratio * (maxPrice - minPrice);
      ctx.fillText(formatPrice(price), left + plotWidth + 8, y);
    }
  }

  drawCandles(ctx, left, plotWidth, yForPrice) {
    const upColor = this.palette.getPropertyValue("--up").trim() || "#15a35b";
    const downColor = this.palette.getPropertyValue("--down").trim() || "#d74747";
    const n = this.data.length;
    const step = plotWidth / n;
    const bodyWidth = Math.max(2, Math.min(14, step * 0.64));

    for (let i = 0; i < n; i += 1) {
      const candle = this.data[i];
      const x = left + (i + 0.5) * step;
      const wickTop = yForPrice(candle.high);
      const wickBottom = yForPrice(candle.low);
      const openY = yForPrice(candle.open);
      const closeY = yForPrice(candle.close);
      const color = candle.close >= candle.open ? upColor : downColor;
      const bodyY = Math.min(openY, closeY);
      const bodyH = Math.max(1, Math.abs(openY - closeY));

      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(x, wickTop);
      ctx.lineTo(x, wickBottom);
      ctx.stroke();
      ctx.fillRect(x - bodyWidth / 2, bodyY, bodyWidth, bodyH);
    }
  }
}

async function fetchCandles(symbol, timeframe, signal, limit = DEFAULT_LIMIT) {
  const rows = await fetchPayload(
    "/chart/candles?symbol=" +
      encodeURIComponent(symbol) +
      "&timeframe=" +
      encodeURIComponent(timeframe) +
      "&limit=" +
      encodeURIComponent(String(limit)),
    { signal }
  );
  return toCandleList(rows);
}

async function fetchTimeframeOptions(symbol) {
  try {
    const rows = await fetchPayload(
      "/chart/timeframes?symbol=" + encodeURIComponent(symbol)
    );
    return normalizeTimeframes(rows);
  } catch (_error) {
    return normalizeTimeframes([]);
  }
}

async function ensureSymbolsLoaded({ force = false } = {}) {
  if (state.symbolsLoaded && !force) {
    return state.symbols;
  }
  const rows = await fetchPayload("/chart/symbols");
  state.symbols = normalizeSymbols(rows);
  state.symbolsLoaded = true;
  return state.symbols;
}

async function pickTimeframeWithData(symbol, options, preferredTimeframe) {
  const candidates = [
    preferredTimeframe,
    ...options.filter((value) => value !== preferredTimeframe),
  ];
  const first = candidates[0] || preferredTimeframe || FALLBACK_TIMEFRAMES[0];

  for (const timeframe of candidates) {
    const candles = await fetchCandles(symbol, timeframe);
    if (candles.length > 0) {
      return { timeframe, candles };
    }
  }

  return { timeframe: first, candles: [] };
}

function renderTimeframeSelector() {
  timeframeSwitchEl.innerHTML = "";
  for (const value of state.timeframes) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "timeframe-btn" + (value === state.timeframe ? " active" : "");
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", value === state.timeframe ? "true" : "false");
    button.dataset.timeframe = value;
    button.textContent = value;
    button.addEventListener("click", () => {
      void selectTimeframe(value);
    });
    timeframeSwitchEl.appendChild(button);
  }
}

function getPairCandidates() {
  const symbols = new Set(state.symbols);
  if (state.symbol) {
    symbols.add(state.symbol);
  }
  return [...symbols].sort((a, b) => a.localeCompare(b));
}

async function loadSymbolMetrics(timeframe) {
  const symbols = getPairCandidates();
  const activeRequestId = state.overlayRequestId;
  const targetTimeframe = timeframe || state.timeframe || DEFAULT_TIMEFRAME;
  if (!symbols.length) {
    if (activeRequestId !== state.overlayRequestId || !isOverlayOpen()) {
      return;
    }
    state.symbolMetrics = {};
    return;
  }

  state.symbolMetricsLoading = true;
  symbolHelpEl.textContent = "Chargement des variations en cours...";
  const requests = symbols.map(async (symbol) => {
    try {
      const candles = await fetchCandles(symbol, targetTimeframe, null, 2);
      const last = candles[candles.length - 1] || null;
      const previous = candles[candles.length - 2] || null;
      const lastPrice = last ? Number(last.close) : NaN;
      const previousPrice = previous ? Number(previous.close) : NaN;
      const changeValue =
        Number.isFinite(lastPrice) && Number.isFinite(previousPrice)
          ? lastPrice - previousPrice
          : NaN;
      const changePct =
        Number.isFinite(changeValue) && Number.isFinite(previousPrice) && previousPrice !== 0
          ? (changeValue / previousPrice) * 100
          : NaN;

      return [
        symbol,
        {
          symbol,
          last_price: lastPrice,
          change_value: changeValue,
          change_pct: changePct,
          trend: computeTrend(changeValue),
        },
      ];
    } catch (_error) {
      return [
        symbol,
        {
          symbol,
          last_price: NaN,
          change_value: NaN,
          change_pct: NaN,
          trend: "flat",
        },
      ];
    }
  });

  const entries = await Promise.all(requests);
  if (
    !isOverlayOpen() ||
    activeRequestId !== state.overlayRequestId ||
    targetTimeframe !== state.timeframe
  ) {
    state.symbolMetricsLoading = false;
    return;
  }
  state.symbolMetrics = Object.fromEntries(entries);
  state.symbolMetricsLoading = false;
  symbolHelpEl.textContent =
    "Lignes cliquables -> chart pair | Haut/Bas/Home/End pour naviguer | Enter pour choisir.";
  renderPairList();
}

function pairSortValue(symbol, sortBy) {
  const metrics = state.symbolMetrics[symbol] || {};
  if (sortBy === "symbol") {
    return symbol;
  }
  const value = Number(metrics[sortBy]);
  return Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY;
}

function filterAndSortPairCandidates(candidates) {
  const query = state.symbolSearch.trim().toUpperCase();
  const trendFilter = state.symbolTrendFilter;
  const sortBy = state.symbolSortBy;
  const direction = state.symbolSortDirection;

  const filtered = candidates.filter((symbol) => {
    if (query && !symbol.includes(query)) {
      return false;
    }
    if (trendFilter === "all") {
      return true;
    }
    const trend = state.symbolMetrics[symbol]?.trend || "flat";
    return trend === trendFilter;
  });

  filtered.sort((a, b) => {
    const left = pairSortValue(a, sortBy);
    const right = pairSortValue(b, sortBy);

    if (sortBy === "symbol") {
      const cmp = String(left).localeCompare(String(right));
      return direction === "asc" ? cmp : -cmp;
    }

    const cmp = Number(right) - Number(left);
    return direction === "asc" ? -cmp : cmp;
  });

  return filtered;
}

function makeSymbolMetricCell(text, extraClass = "") {
  const span = document.createElement("span");
  span.className = "symbol-cell" + (extraClass ? " " + extraClass : "");
  span.textContent = text;
  return span;
}

function renderPairList() {
  symbolListEl.innerHTML = "";
  const candidates = filterAndSortPairCandidates(getPairCandidates());

  if (candidates.length === 0) {
    const empty = document.createElement("div");
    empty.className = "symbol-empty";
    empty.textContent = "Aucune pair disponible avec les filtres actuels.";
    symbolListEl.appendChild(empty);
    symbolHelpEl.textContent = "Ajuster la recherche/les filtres.";
    return [];
  }

  symbolHelpEl.textContent =
    "Lignes cliquables -> chart pair | Haut/Bas/Home/End pour naviguer | Enter pour choisir.";

  for (const symbol of candidates) {
    const metrics = state.symbolMetrics[symbol] || {};
    const button = document.createElement("button");
    button.type = "button";
    button.className = "symbol-item" + (symbol === state.symbol ? " active" : "");
    button.dataset.symbol = symbol;
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", symbol === state.symbol ? "true" : "false");

    const symbolName = makeSymbolMetricCell(symbol, "symbol-name");
    const priceText = Number.isFinite(metrics.last_price)
      ? formatPrice(metrics.last_price)
      : "-";
    const priceCell = makeSymbolMetricCell("Prix: " + priceText);

    const changeCell = makeSymbolMetricCell(
      "Var: " + formatSigned(metrics.change_value),
      "trend-" + (metrics.trend || "flat")
    );
    const pctCell = makeSymbolMetricCell(
      "Var %: " + formatSignedPercent(metrics.change_pct),
      "trend-" + (metrics.trend || "flat")
    );

    button.append(symbolName, priceCell, changeCell, pctCell);
    button.addEventListener("click", () => {
      void selectPair(symbol);
    });
    symbolListEl.appendChild(button);
  }

  return candidates;
}

function focusPairButton(symbol) {
  const selector = symbol
    ? 'button[data-symbol="' + symbol + '"]'
    : "button[data-symbol]";
  const target = symbolListEl.querySelector(selector);
  if (target) {
    target.focus();
  }
}

function updateSortDirectionButtonLabel() {
  symbolSortDirectionEl.textContent =
    "Ordre: " + (state.symbolSortDirection === "asc" ? "Asc" : "Desc");
}

function syncPairControls() {
  symbolSearchInputEl.value = state.symbolSearch;
  symbolTrendFilterEl.value = state.symbolTrendFilter;
  symbolSortByEl.value = state.symbolSortBy;
  updateSortDirectionButtonLabel();
}

async function openPairOverlay() {
  openOverlayContainer();
  symbolHelpEl.textContent = "Chargement des pairs...";
  symbolListEl.innerHTML = "";
  syncPairControls();

  state.overlayRequestId += 1;
  const requestId = state.overlayRequestId;

  try {
    await ensureSymbolsLoaded();
    if (requestId !== state.overlayRequestId || !isOverlayOpen()) {
      return;
    }
    renderPairList();
    focusPairButton(state.symbol);
    void loadSymbolMetrics(state.timeframe || DEFAULT_TIMEFRAME);
  } catch (_error) {
    if (requestId !== state.overlayRequestId || !isOverlayOpen()) {
      return;
    }
    symbolHelpEl.textContent = "Erreur lors du chargement des pairs.";
  }

}

function movePairFocus(step) {
  const buttons = [...symbolListEl.querySelectorAll("button[data-symbol]")];
  if (!buttons.length) {
    return;
  }
  const active = document.activeElement;
  const index = buttons.indexOf(active);
  const nextIndex = index < 0 ? 0 : (index + step + buttons.length) % buttons.length;
  buttons[nextIndex].focus();
}

function movePairFocusAbsolute(position) {
  const buttons = [...symbolListEl.querySelectorAll("button[data-symbol]")];
  if (!buttons.length) {
    return;
  }
  if (position === "first") {
    buttons[0].focus();
    return;
  }
  buttons[buttons.length - 1].focus();
}

async function loadAndRenderCandles({ symbol, timeframe, showLoadingOverlay }) {
  stopLiveUpdater({ bumpGeneration: true });

  if (showLoadingOverlay) {
    showState("loading", "Chargement des chandeliers...");
  }

  state.requestId += 1;
  const requestId = state.requestId;

  if (state.abortController) {
    state.abortController.abort();
  }
  state.abortController = new AbortController();
  setTimeframeHint("Chargement " + timeframe + "...");

  try {
    const candles = await fetchCandles(
      symbol,
      timeframe,
      state.abortController.signal
    );
    if (requestId !== state.requestId) {
      return;
    }
    state.candles = candles;
    refreshChartFromState({ showEmptyOverlay: true });
    void refreshIndicators({ reason: "manual" });
    setTimeframeHint("Active: " + timeframe);
    setLiveUpdateNow();
    setLiveStatus("Live actif", "ok");
  } catch (error) {
    if (error?.name === "AbortError") {
      return;
    }
    if (requestId !== state.requestId) {
      return;
    }
    showState(
      "error",
      "Erreur de chargement des chandeliers. Verifier l'API et les parametres."
    );
    setTimeframeHint("Erreur chargement");
    setLiveStatus("Live en attente", "idle");
    clearIndicators();
    console.error("chart_candles_load_error", error);
  } finally {
    restartLiveUpdater();
  }
}

async function selectTimeframe(nextTimeframe) {
  if (!state.symbol || !nextTimeframe || nextTimeframe === state.timeframe) {
    return;
  }
  state.timeframe = nextTimeframe;
  renderTimeframeSelector();
  await loadAndRenderCandles({
    symbol: state.symbol,
    timeframe: state.timeframe,
    showLoadingOverlay: false,
  });
}

async function selectPair(nextSymbol) {
  if (!nextSymbol) {
    return;
  }
  if (nextSymbol === state.symbol) {
    closeOverlayContainer();
    return;
  }

  closeOverlayContainer({ restoreFocus: false });
  state.symbol = nextSymbol;
  setPairTriggerLabel(state.symbol);
  showState("loading", "Chargement des chandeliers...");

  state.timeframes = await fetchTimeframeOptions(state.symbol);
  if (!state.timeframe) {
    state.timeframe = state.timeframes.includes(DEFAULT_TIMEFRAME)
      ? DEFAULT_TIMEFRAME
      : state.timeframes[0];
  }
  renderTimeframeSelector();

  await loadAndRenderCandles({
    symbol: state.symbol,
    timeframe: state.timeframe,
    showLoadingOverlay: true,
  });
}

function schedulePairListRender() {
  if (!isOverlayOpen()) {
    return;
  }
  renderPairList();
}

function handleSymbolSearchInput(event) {
  state.symbolSearch = String(event.target.value || "");
  if (state.symbolSearchTimerId != null) {
    clearTimeout(state.symbolSearchTimerId);
  }
  state.symbolSearchTimerId = setTimeout(() => {
    schedulePairListRender();
  }, 180);
}

function handleSymbolTrendFilterChange(event) {
  state.symbolTrendFilter = String(event.target.value || "all");
  schedulePairListRender();
}

function handleSymbolSortByChange(event) {
  state.symbolSortBy = String(event.target.value || "change_pct");
  schedulePairListRender();
}

function handleSymbolSortDirectionToggle() {
  state.symbolSortDirection = state.symbolSortDirection === "asc" ? "desc" : "asc";
  updateSortDirectionButtonLabel();
  schedulePairListRender();
}

function handleTimeframeKeyboard(event) {
  const keys = ["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown", "Home", "End"];
  if (!keys.includes(event.key) || state.timeframes.length === 0) {
    return;
  }
  event.preventDefault();

  const currentIndex = Math.max(0, state.timeframes.indexOf(state.timeframe));
  let nextIndex = currentIndex;
  if (event.key === "ArrowRight" || event.key === "ArrowDown") {
    nextIndex = (currentIndex + 1) % state.timeframes.length;
  }
  if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
    nextIndex = (currentIndex - 1 + state.timeframes.length) % state.timeframes.length;
  }
  if (event.key === "Home") {
    nextIndex = 0;
  }
  if (event.key === "End") {
    nextIndex = state.timeframes.length - 1;
  }

  const next = state.timeframes[nextIndex];
  void selectTimeframe(next);

  const targetButton = timeframeSwitchEl.querySelector(
    'button[data-timeframe="' + next + '"]'
  );
  if (targetButton) {
    targetButton.focus();
  }
}

function handlePairTriggerKeydown(event) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    void openPairOverlay();
  }
  if (event.key === "ArrowDown") {
    event.preventDefault();
    void openPairOverlay();
  }
}

function handlePairListKeydown(event) {
  if (!isOverlayOpen()) {
    return;
  }

  if (event.key === "Escape") {
    event.preventDefault();
    closeOverlayContainer();
    return;
  }
  if (event.key === "ArrowDown") {
    event.preventDefault();
    movePairFocus(1);
    return;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    movePairFocus(-1);
    return;
  }
  if (event.key === "Home") {
    event.preventDefault();
    movePairFocusAbsolute("first");
    return;
  }
  if (event.key === "End") {
    event.preventDefault();
    movePairFocusAbsolute("last");
  }
}

function handleOverlayBackdropClick(event) {
  if (event.target === symbolOverlayEl) {
    closeOverlayContainer();
  }
}

function handleVisibilityChange() {
  if (!state.symbol || !state.timeframe) {
    return;
  }
  restartLiveUpdater();
}

async function resolveInitialSelection() {
  const defaultCandles = await fetchCandles(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME);
  if (defaultCandles.length > 0) {
    const options = await fetchTimeframeOptions(DEFAULT_SYMBOL);
    const timeframe = options.includes(DEFAULT_TIMEFRAME) ? DEFAULT_TIMEFRAME : options[0];
    const candles =
      timeframe === DEFAULT_TIMEFRAME
        ? defaultCandles
        : await fetchCandles(DEFAULT_SYMBOL, timeframe);
    return {
      symbol: DEFAULT_SYMBOL,
      timeframe,
      timeframes: options,
      candles,
      symbols: [],
    };
  }

  const symbols = normalizeSymbols(await fetchPayload("/chart/symbols"));
  if (!symbols.length) {
    return {
      symbol: "",
      timeframe: "",
      timeframes: normalizeTimeframes([]),
      candles: [],
      symbols: [],
    };
  }

  const symbol = symbols.includes(DEFAULT_SYMBOL) ? DEFAULT_SYMBOL : symbols[0];
  const options = await fetchTimeframeOptions(symbol);
  const picked = await pickTimeframeWithData(symbol, options, DEFAULT_TIMEFRAME);
  return {
    symbol,
    timeframe: picked.timeframe,
    timeframes: options,
    candles: picked.candles,
    symbols,
  };
}

async function initChartPage() {
  chart = new CandleCanvasChart(chartHostEl);
  timeframeSwitchEl.addEventListener("keydown", handleTimeframeKeyboard);
  pairTriggerEl.addEventListener("click", () => {
    void openPairOverlay();
  });
  pairTriggerEl.addEventListener("keydown", handlePairTriggerKeydown);
  symbolListEl.addEventListener("keydown", handlePairListKeydown);
  symbolCloseBtnEl.addEventListener("click", () => closeOverlayContainer());
  symbolSearchInputEl.addEventListener("input", handleSymbolSearchInput);
  symbolTrendFilterEl.addEventListener("change", handleSymbolTrendFilterChange);
  symbolSortByEl.addEventListener("change", handleSymbolSortByChange);
  symbolSortDirectionEl.addEventListener("click", handleSymbolSortDirectionToggle);
  symbolOverlayEl.addEventListener("click", handleOverlayBackdropClick);
  symbolOverlayEl.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeOverlayContainer();
    }
  });
  document.addEventListener("visibilitychange", handleVisibilityChange);

  showState("loading", "Chargement des chandeliers...");
  setTimeframeHint("Chargement des options...");
  setPairTriggerLabel("");
  setLiveStatus("Initialisation", "idle");
  setIndicatorStatus("Initialisation", "idle");

  try {
    const selection = await resolveInitialSelection();
    state.symbol = selection.symbol;
    state.timeframe = selection.timeframe;
    state.timeframes = selection.timeframes;
    state.symbols = selection.symbols;
    state.symbolsLoaded = selection.symbols.length > 0;
    state.candles = selection.candles;
    renderTimeframeSelector();

    if (!state.symbol || !state.timeframe) {
      refreshChartFromState({ showEmptyOverlay: true });
      setTimeframeHint("Aucune donnee");
      setLiveStatus("Live inactif", "idle");
      clearIndicators();
      return;
    }

    refreshChartFromState({ showEmptyOverlay: true });
    void refreshIndicators({ reason: "manual" });
    setTimeframeHint("Active: " + state.timeframe);
    setLiveUpdateNow();
    restartLiveUpdater();
    if (!state.symbolsLoaded) {
      void ensureSymbolsLoaded().catch((_error) => {});
    }
  } catch (error) {
    chart.setData([]);
    showState(
      "error",
      "Erreur de chargement des chandeliers. Verifier l'API et les parametres."
    );
    setTimeframeHint("Erreur chargement");
    setLiveStatus("Live en attente", "idle");
    clearIndicators();
    console.error("chart_init_error", error);
  }
}

initChartPage();
