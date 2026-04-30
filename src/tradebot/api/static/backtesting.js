"use strict";

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

function el(tag, attrs) {
  var node = document.createElement(tag);
  for (var k in attrs) {
    if (k === "textContent") {
      node.textContent = attrs[k];
    } else if (k === "className") {
      node.className = attrs[k];
    } else {
      node.setAttribute(k, attrs[k]);
    }
  }
  for (var i = 2; i < arguments.length; i++) {
    var child = arguments[i];
    if (typeof child === "string") {
      node.appendChild(document.createTextNode(child));
    } else if (child) {
      node.appendChild(child);
    }
  }
  return node;
}

function setFeedback(id, msg, kind) {
  var node = document.getElementById(id);
  if (!node) return;
  node.textContent = msg || "";
  node.className = "feedback" + (kind ? " " + kind : "");
}

function msToDate(ms) {
  if (!ms) return "-";
  return new Date(ms).toISOString().slice(0, 10);
}

function fmtMs(ms) {
  if (!ms) return "-";
  return new Date(ms).toISOString().replace("T", " ").slice(0, 19);
}

function dateToMs(str) {
  if (!str) return null;
  return new Date(str + "T00:00:00Z").getTime();
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

var state = {
  currentRunId: null,
  currentSymbol: null,
  currentFromMs: null,
  currentToMs: null,
  currentTrades: [],
  tradesCursor: null,
  tradesPrevCursors: [],
  runsCursor: null,
  runsPrevCursors: [],
  selectedTradeIdx: null,
};

// ---------------------------------------------------------------------------
// Section 1: Readiness
// ---------------------------------------------------------------------------

async function checkReadiness() {
  var symbol = document.getElementById("prepSymbol").value.trim().toUpperCase();
  var fromDate = document.getElementById("prepFromDate").value;
  var toDate = document.getElementById("prepToDate").value;
  var profile = document.getElementById("prepProfile").value;

  if (!symbol) { setFeedback("readinessFeedback", "Symbol requis", "err"); return; }
  if (!fromDate || !toDate) { setFeedback("readinessFeedback", "Dates requises", "err"); return; }

  var fromMs = dateToMs(fromDate);
  var toMs = dateToMs(toDate);
  if (!fromMs || !toMs || fromMs >= toMs) {
    setFeedback("readinessFeedback", "Dates invalides (from < to requis)", "err");
    return;
  }

  setFeedback("readinessFeedback", "Chargement...", "loading");
  try {
    var url = "/backtesting/readiness?symbol=" + encodeURIComponent(symbol)
      + "&from_ms=" + fromMs + "&to_ms=" + toMs + "&profile=" + encodeURIComponent(profile);
    var res = await fetch(url);
    var payload = await res.json();
    if (!payload.ok) {
      setFeedback("readinessFeedback", payload.error.message, "err");
      return;
    }
    renderReadiness(payload.data);
    setFeedback("readinessFeedback", "", "");
    state.currentSymbol = symbol;
    state.currentFromMs = fromMs;
    state.currentToMs = toMs;
    document.getElementById("prepSymbol").value = symbol;
  } catch (err) {
    setFeedback("readinessFeedback", err.message || "Erreur reseau", "err");
  }
}

function renderReadiness(data) {
  var resultDiv = document.getElementById("readinessResult");
  resultDiv.style.display = "block";

  var badge = document.getElementById("readinessStatusBadge");
  badge.textContent = data.status.toUpperCase();
  badge.className = "status-badge " + data.status;

  var warmupEl = document.getElementById("readinessWarmup");
  warmupEl.textContent = "Warmup: " + (data.warmup_ok ? "OK" : "Insuffisant");
  warmupEl.className = data.warmup_ok ? "warmup-ok" : "warmup-nok";

  var reasonsList = document.getElementById("readinessReasons");
  while (reasonsList.firstChild) reasonsList.removeChild(reasonsList.firstChild);
  (data.reasons || []).forEach(function(r) {
    reasonsList.appendChild(el("li", {textContent: r}));
  });

  var tbody = document.getElementById("coverageBody");
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
  (data.timeframes || []).forEach(function(tf) {
    var tr = el("tr", {});
    tr.appendChild(el("td", {textContent: tf.timeframe}));
    tr.appendChild(el("td", {textContent: tf.candle_count}));
    tr.appendChild(el("td", {textContent: tf.coverage_pct.toFixed(1) + "%"}));
    tr.appendChild(el("td", {textContent: tf.gaps.length}));
    tr.appendChild(el("td", {textContent: tf.has_snapshots ? "Oui" : "Non"}));
    var statusTd = el("td", {});
    statusTd.appendChild(el("span", {className: "status-badge " + tf.status, textContent: tf.status}));
    tr.appendChild(statusTd);
    tbody.appendChild(tr);
  });
}

// ---------------------------------------------------------------------------
// Section 2: Launch run
// ---------------------------------------------------------------------------

async function launchRun() {
  var symbol = document.getElementById("prepSymbol").value.trim().toUpperCase();
  var fromDate = document.getElementById("prepFromDate").value;
  var toDate = document.getElementById("prepToDate").value;

  if (!symbol) { setFeedback("runFeedback", "Symbol requis (remplir section 1 d'abord)", "err"); return; }
  if (!fromDate || !toDate) { setFeedback("runFeedback", "Dates requises (remplir section 1 d'abord)", "err"); return; }

  var fromMs = dateToMs(fromDate);
  var toMs = dateToMs(toDate);
  if (!fromMs || !toMs || fromMs >= toMs) {
    setFeedback("runFeedback", "Dates invalides", "err");
    return;
  }

  var config = {
    slippage_pct: parseFloat(document.getElementById("cfgSlippage").value) || 0.0005,
    fees_pct: parseFloat(document.getElementById("cfgFees").value) || 0.001,
    k_atr: parseFloat(document.getElementById("cfgKAtr").value) || 2.0,
    r_multiple: parseFloat(document.getElementById("cfgRMultiple").value) || 1.5,
    max_sl_pct: parseFloat(document.getElementById("cfgMaxSl").value) || 0.02,
    sl_buffer_pct: parseFloat(document.getElementById("cfgSlBuffer").value) || 0.003,
    risk_pct: parseFloat(document.getElementById("cfgRisk").value) || 0.01,
    initial_capital_usdc: parseFloat(document.getElementById("cfgCapital").value) || 10000.0,
    min_closed_trades: parseInt(document.getElementById("cfgMinClosed").value) || 20,
    mode: document.getElementById("cfgMode").value,
  };

  setFeedback("runFeedback", "Lancement...", "loading");
  document.getElementById("btnLaunchRun").disabled = true;

  try {
    var res = await fetch("/backtesting/runs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({symbol: symbol, from_ms: fromMs, to_ms: toMs, config: config}),
    });
    var payload = await res.json();
    if (!payload.ok) {
      setFeedback("runFeedback", payload.error.message, "err");
      return;
    }
    setFeedback("runFeedback", "Backtest termine — run " + payload.data.run_id, "ok");
    state.currentRunId = payload.data.run_id;
    state.currentSymbol = symbol;
    state.currentFromMs = fromMs;
    state.currentToMs = toMs;
    renderResults(payload.data);
    loadAndRenderTrades(payload.data.run_id);
    document.getElementById("reportSection").style.display = "block";
  } catch (err) {
    setFeedback("runFeedback", err.message || "Erreur reseau", "err");
  } finally {
    document.getElementById("btnLaunchRun").disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Section 3: Results
// ---------------------------------------------------------------------------

function renderResults(data) {
  var m = data.metrics;
  document.getElementById("resultsSection").style.display = "block";

  var badge = document.getElementById("verdictBadge");
  badge.textContent = m.verdict;
  badge.className = "verdict-badge " + m.verdict;

  var reasonsList = document.getElementById("verdictReasons");
  while (reasonsList.firstChild) reasonsList.removeChild(reasonsList.firstChild);
  (m.verdict_reasons || []).forEach(function(r) {
    reasonsList.appendChild(el("li", {textContent: r}));
  });

  var kpis = [
    ["Trades totaux", m.total_trades],
    ["Trades fermes", m.closed_trades],
    ["Gagnants", m.winning_trades],
    ["Winrate", (m.winrate * 100).toFixed(1) + "%"],
    ["Profit Factor", isFinite(m.profit_factor) ? m.profit_factor.toFixed(2) : "inf"],
    ["Max Drawdown", m.max_drawdown_pct.toFixed(2) + "%"],
    ["Expectancy R", m.expectancy_r.toFixed(3)],
    ["Avg MFE%", m.avg_mfe_pct.toFixed(2)],
    ["Avg MAE%", m.avg_mae_pct.toFixed(2)],
  ];
  var grid = document.getElementById("kpiGrid");
  while (grid.firstChild) grid.removeChild(grid.firstChild);
  kpis.forEach(function(kpi) {
    var card = el("div", {className: "kpi"});
    card.appendChild(el("div", {className: "kpi-label", textContent: kpi[0]}));
    card.appendChild(el("div", {className: "kpi-value", textContent: String(kpi[1])}));
    grid.appendChild(card);
  });
}

// ---------------------------------------------------------------------------
// Section 4: Chart
// ---------------------------------------------------------------------------

async function renderChart(symbol, fromMs, toMs, trades) {
  document.getElementById("chartSection").style.display = "block";
  var canvas = document.getElementById("chartCanvas");
  var url = "/chart/candles?symbol=" + encodeURIComponent(symbol) + "&timeframe=5m&limit=500"
    + "&from_open_time_ms=" + (fromMs - 1);
  var res;
  try {
    res = await fetch(url);
    var payload = await res.json();
    if (!payload.ok || !Array.isArray(payload.data)) return;
    drawChart(canvas, payload.data, trades || [], fromMs, toMs);
  } catch (_) {}
}

function drawChart(canvas, candles, trades, _fromMs, _toMs) {
  var dpr = window.devicePixelRatio || 1;
  var W = canvas.offsetWidth;
  var H = canvas.offsetHeight || 360;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  var ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  if (!candles.length) {
    ctx.fillStyle = "#b6c0de";
    ctx.font = "14px IBM Plex Mono";
    ctx.fillText("Aucune donnee", W / 2 - 60, H / 2);
    return;
  }

  var PAD_L = 60, PAD_R = 20, PAD_T = 20, PAD_B = 30;
  var cw = W - PAD_L - PAD_R;
  var ch = H - PAD_T - PAD_B;
  var n = candles.length;
  var candleW = Math.max(1, (cw / n) - 1);

  var loArr = candles.map(function(c) { return c.low; });
  var hiArr = candles.map(function(c) { return c.high; });
  var minP = loArr[0], maxP = hiArr[0];
  for (var i = 1; i < loArr.length; i++) {
    if (loArr[i] < minP) minP = loArr[i];
    if (hiArr[i] > maxP) maxP = hiArr[i];
  }
  var priceRange = maxP - minP || 1;

  function px(price) {
    return PAD_T + ch - ((price - minP) / priceRange) * ch;
  }
  function cx(idx) {
    return PAD_L + idx * (cw / n) + (cw / n) / 2;
  }

  // Background
  ctx.fillStyle = "rgba(0,0,0,0.15)";
  ctx.fillRect(PAD_L, PAD_T, cw, ch);

  // Candles
  for (var j = 0; j < candles.length; j++) {
    var c = candles[j];
    var x = PAD_L + j * (cw / n);
    var isGreen = c.close >= c.open;
    ctx.strokeStyle = isGreen ? "#4ee39a" : "#ff5c7a";
    ctx.fillStyle = isGreen ? "rgba(78,227,154,0.7)" : "rgba(255,92,122,0.7)";
    var bodyTop = px(Math.max(c.open, c.close));
    var bodyBot = px(Math.min(c.open, c.close));
    var bodyH = Math.max(1, bodyBot - bodyTop);
    ctx.fillRect(x + 1, bodyTop, candleW - 2, bodyH);
    ctx.beginPath();
    ctx.moveTo(cx(j), px(c.high));
    ctx.lineTo(cx(j), px(c.low));
    ctx.stroke();
  }

  // Trade markers
  var openTimeIndex = {};
  for (var k = 0; k < candles.length; k++) {
    openTimeIndex[candles[k].open_time_ms] = k;
  }

  function nearestIdx(ms) {
    var best = 0, bestDist = Math.abs(candles[0].open_time_ms - ms);
    for (var m = 1; m < candles.length; m++) {
      var d = Math.abs(candles[m].open_time_ms - ms);
      if (d < bestDist) { bestDist = d; best = m; }
    }
    return best;
  }

  trades.forEach(function(t, ti) {
    var entryIdx = nearestIdx(t.entry_time_ms);
    var ex = cx(entryIdx);
    var ey = px(t.entry_price);
    ctx.fillStyle = "#4ee39a";
    ctx.beginPath();
    ctx.arc(ex, ey, 4, 0, Math.PI * 2);
    ctx.fill();

    if (t.exit_time_ms && t.exit_price) {
      var exitIdx = nearestIdx(t.exit_time_ms);
      var rx = cx(exitIdx);
      var ry = px(t.exit_price);
      ctx.fillStyle = t.exit_reason === "TP" ? "#4ee39a" : "#ff5c7a";
      ctx.beginPath();
      ctx.arc(rx, ry, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,0.1)";
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(ex, ey);
      ctx.lineTo(rx, ry);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  });

  // Selected trade SL/TP lines
  if (state.selectedTradeIdx !== null && trades[state.selectedTradeIdx]) {
    var st = trades[state.selectedTradeIdx];
    var si = nearestIdx(st.entry_time_ms);
    var sx = cx(si);
    ctx.strokeStyle = "#ff5c7a";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(sx, px(st.stop_loss));
    ctx.lineTo(W - PAD_R, px(st.stop_loss));
    ctx.stroke();
    ctx.strokeStyle = "#4ee39a";
    ctx.beginPath();
    ctx.moveTo(sx, px(st.take_profit));
    ctx.lineTo(W - PAD_R, px(st.take_profit));
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.lineWidth = 1;
  }

  // Price axis labels
  ctx.fillStyle = "#b6c0de";
  ctx.font = "10px IBM Plex Mono";
  var steps = 5;
  for (var s = 0; s <= steps; s++) {
    var p = minP + (priceRange * s) / steps;
    var y = px(p);
    ctx.fillText(p.toFixed(1), 2, y + 4);
  }
}

// ---------------------------------------------------------------------------
// Section 5: Trades
// ---------------------------------------------------------------------------

async function loadAndRenderTrades(runId, cursor, filters) {
  var result = (filters || {}).result || "";
  var reason = (filters || {}).reason || "";
  var url = "/backtesting/runs/" + encodeURIComponent(runId) + "/trades?limit=50";
  if (cursor) url += "&cursor=" + cursor;
  if (result) url += "&result=" + encodeURIComponent(result);
  if (reason) url += "&reason=" + encodeURIComponent(reason);

  try {
    var res = await fetch(url);
    var payload = await res.json();
    if (!payload.ok) return;
    state.currentTrades = payload.data.items || [];
    state.tradesCursor = payload.data.next_cursor || null;
    renderTradesTable(state.currentTrades);
    document.getElementById("tradesSection").style.display = "block";
    document.getElementById("btnNextTrades").disabled = !state.tradesCursor;
    if (state.currentSymbol && state.currentFromMs && state.currentToMs) {
      renderChart(state.currentSymbol, state.currentFromMs, state.currentToMs, state.currentTrades);
    }
  } catch (_) {}
}

function renderTradesTable(trades) {
  var tbody = document.getElementById("tradesBody");
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
  trades.forEach(function(t, i) {
    var tr = el("tr", {});
    if (i === state.selectedTradeIdx) tr.className = "selected";
    tr.appendChild(el("td", {textContent: i + 1}));
    tr.appendChild(el("td", {textContent: fmtMs(t.entry_time_ms)}));
    tr.appendChild(el("td", {textContent: t.entry_price.toFixed(4)}));
    tr.appendChild(el("td", {textContent: t.stop_loss.toFixed(4)}));
    tr.appendChild(el("td", {textContent: t.take_profit.toFixed(4)}));
    tr.appendChild(el("td", {textContent: t.sl_method || "-"}));
    tr.appendChild(el("td", {textContent: t.exit_reason || "OPEN"}));
    var pnlTd = el("td", {});
    if (t.pnl_r !== null && t.pnl_r !== undefined) {
      var pnlSpan = el("span", {
        className: t.pnl_r > 0 ? "pnl-pos" : "pnl-neg",
        textContent: t.pnl_r.toFixed(3),
      });
      pnlTd.appendChild(pnlSpan);
    } else {
      pnlTd.textContent = "-";
    }
    tr.appendChild(pnlTd);
    tr.appendChild(el("td", {textContent: t.mfe_pct !== null ? t.mfe_pct.toFixed(2) : "-"}));
    tr.appendChild(el("td", {textContent: t.mae_pct !== null ? t.mae_pct.toFixed(2) : "-"}));

    (function(idx, trade) {
      tr.addEventListener("click", function() { selectTrade(idx, trade); });
    })(i, t);

    tbody.appendChild(tr);
  });
}

function selectTrade(idx, trade) {
  state.selectedTradeIdx = idx;
  renderTradesTable(state.currentTrades);
  // Re-render chart with selection
  if (state.currentSymbol && state.currentFromMs && state.currentToMs) {
    renderChart(state.currentSymbol, state.currentFromMs, state.currentToMs, state.currentTrades);
  }
  // MTF context
  var mtfSection = document.getElementById("mtfSection");
  var mtfPre = document.getElementById("mtfContext");
  mtfSection.style.display = "block";
  mtfPre.textContent = JSON.stringify(trade.signal_context || {}, null, 2);
}

// ---------------------------------------------------------------------------
// Section 7: Report
// ---------------------------------------------------------------------------

async function loadReport(runId, format) {
  var url = "/backtesting/runs/" + encodeURIComponent(runId) + "/report?format=" + format;
  try {
    var res = await fetch(url);
    if (format === "markdown") {
      var text = await res.text();
      document.getElementById("reportOutput").textContent = text;
    } else {
      var payload = await res.json();
      if (!payload.ok) {
        document.getElementById("reportOutput").textContent = JSON.stringify(payload.error, null, 2);
      } else {
        document.getElementById("reportOutput").textContent = JSON.stringify(payload.data, null, 2);
      }
    }
  } catch (err) {
    document.getElementById("reportOutput").textContent = err.message;
  }
}

// ---------------------------------------------------------------------------
// Historique des runs
// ---------------------------------------------------------------------------

async function loadRuns(cursor) {
  var symbol = document.getElementById("histSymbol").value.trim().toUpperCase() || "";
  var url = "/backtesting/runs?limit=20";
  if (symbol) url += "&symbol=" + encodeURIComponent(symbol);
  if (cursor) url += "&cursor=" + encodeURIComponent(cursor);

  try {
    var res = await fetch(url);
    var payload = await res.json();
    if (!payload.ok) return;
    state.runsCursor = payload.data.next_cursor || null;
    renderRunsList(payload.data.items || []);
    document.getElementById("btnNextRuns").disabled = !state.runsCursor;
  } catch (_) {}
}

function renderRunsList(items) {
  var list = document.getElementById("runsList");
  while (list.firstChild) list.removeChild(list.firstChild);
  if (!items.length) {
    list.appendChild(el("div", {className: "run-meta", textContent: "Aucun run"}));
    return;
  }
  items.forEach(function(r) {
    var item = el("div", {className: "run-item"});
    var left = el("div", {});
    left.appendChild(el("div", {className: "run-symbol", textContent: r.symbol}));
    var meta = el("div", {className: "run-meta"});
    meta.textContent = msToDate(r.from_ms) + " → " + msToDate(r.to_ms) + " | " + r.ran_at;
    left.appendChild(meta);
    item.appendChild(left);
    var right = el("div", {style: "display:flex;align-items:center;gap:10px"});
    right.appendChild(el("span", {className: "verdict-badge " + r.verdict, textContent: r.verdict}));
    var metricsSpan = el("span", {className: "run-meta"});
    metricsSpan.textContent = r.closed_trades + " trades | WR " + (r.winrate * 100).toFixed(1) + "%";
    right.appendChild(metricsSpan);
    item.appendChild(right);
    (function(runId) {
      item.addEventListener("click", function() { openRun(runId); });
    })(r.run_id);
    list.appendChild(item);
  });
}

async function openRun(runId) {
  try {
    var res = await fetch("/backtesting/runs/" + encodeURIComponent(runId));
    var payload = await res.json();
    if (!payload.ok) return;
    var r = payload.data;
    state.currentRunId = runId;
    state.currentSymbol = r.symbol;
    state.currentFromMs = r.from_ms;
    state.currentToMs = r.to_ms;

    // Populate prep fields
    document.getElementById("prepSymbol").value = r.symbol;
    document.getElementById("prepFromDate").value = msToDate(r.from_ms);
    document.getElementById("prepToDate").value = msToDate(r.to_ms);

    renderResults({metrics: {
      total_trades: r.total_trades,
      closed_trades: r.closed_trades,
      winning_trades: r.winning_trades,
      winrate: r.winrate,
      profit_factor: r.profit_factor,
      max_drawdown_pct: r.max_drawdown_pct,
      expectancy_r: r.expectancy_r,
      avg_mfe_pct: r.avg_mfe_pct,
      avg_mae_pct: r.avg_mae_pct,
      passes_phase_gate: r.passes_phase_gate,
      verdict: r.verdict,
      verdict_reasons: [],
    }});
    state.selectedTradeIdx = null;
    state.tradesCursor = null;
    state.tradesPrevCursors = [];
    loadAndRenderTrades(runId);
    document.getElementById("reportSection").style.display = "block";
    window.scrollTo({top: 0, behavior: "smooth"});
  } catch (_) {}
}

// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------

document.getElementById("btnCheckReadiness").addEventListener("click", checkReadiness);
document.getElementById("btnLaunchRun").addEventListener("click", launchRun);

document.getElementById("btnFilterTrades").addEventListener("click", function() {
  if (!state.currentRunId) return;
  state.tradesCursor = null;
  state.tradesPrevCursors = [];
  state.selectedTradeIdx = null;
  loadAndRenderTrades(state.currentRunId, null, {
    result: document.getElementById("filterResult").value,
    reason: document.getElementById("filterReason").value,
  });
});

document.getElementById("btnNextTrades").addEventListener("click", function() {
  if (!state.currentRunId || !state.tradesCursor) return;
  state.tradesPrevCursors.push(state.tradesCursor);
  loadAndRenderTrades(state.currentRunId, state.tradesCursor, {
    result: document.getElementById("filterResult").value,
    reason: document.getElementById("filterReason").value,
  });
});

document.getElementById("btnPrevTrades").addEventListener("click", function() {
  if (!state.currentRunId || !state.tradesPrevCursors.length) return;
  var prev = state.tradesPrevCursors.pop();
  loadAndRenderTrades(state.currentRunId, prev || null, {
    result: document.getElementById("filterResult").value,
    reason: document.getElementById("filterReason").value,
  });
});

document.getElementById("btnLoadRuns").addEventListener("click", function() {
  state.runsCursor = null;
  state.runsPrevCursors = [];
  loadRuns(null);
});

document.getElementById("btnNextRuns").addEventListener("click", function() {
  if (!state.runsCursor) return;
  state.runsPrevCursors.push(state.runsCursor);
  loadRuns(state.runsCursor);
});

document.getElementById("btnPrevRuns").addEventListener("click", function() {
  if (!state.runsPrevCursors.length) return;
  var prev = state.runsPrevCursors.pop();
  loadRuns(prev || null);
});

document.getElementById("btnReportJson").addEventListener("click", function() {
  if (!state.currentRunId) return;
  loadReport(state.currentRunId, "json");
});

document.getElementById("btnReportMarkdown").addEventListener("click", function() {
  if (!state.currentRunId) return;
  loadReport(state.currentRunId, "markdown");
});

// Initialize default dates
(function() {
  var now = new Date();
  var to = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  var from = new Date(to);
  from.setMonth(from.getMonth() - 1);
  document.getElementById("prepFromDate").value = from.toISOString().slice(0, 10);
  document.getElementById("prepToDate").value = to.toISOString().slice(0, 10);
  loadRuns(null);
})();
