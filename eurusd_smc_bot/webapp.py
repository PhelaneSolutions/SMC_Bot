from datetime import datetime
from threading import Thread, Lock
from typing import Optional
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

import os

from main import EURUSD_SMC_Bot

os.makedirs('logs', exist_ok=True)

app = FastAPI(title="EURUSD SMC Bot Dashboard")

_bot: Optional[EURUSD_SMC_Bot] = None
_bot_thread: Optional[Thread] = None
_lock = Lock()


def _is_running() -> bool:
    return _bot is not None and getattr(_bot, "_running", False)


def _tail_log_lines(max_lines: int = 200) -> list[str]:
    """Return last max_lines from today's log file, if it exists."""
    today = datetime.now().strftime("%Y%m%d")
    log_path = Path("logs") / f"bot_{today}.log"
    if not log_path.exists():
        return []

    try:
        with log_path.open("r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return [line.rstrip("\n") for line in lines[-max_lines:]]
    except Exception:
        return []


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    """Single-page dashboard UI."""
    return HTML_PAGE


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Samidolla SMC Bot</title>
<style>
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#0f172a;color:#e5e7eb;margin:0;padding:0}
.c{max-width:900px;margin:40px auto;padding:24px;background:#020617;border-radius:12px;box-shadow:0 20px 40px rgba(0,0,0,.6)}
h1{margin-top:0;font-size:1.8rem}
.controls{display:flex;gap:12px;margin:16px 0 24px;align-items:center}
.btn{padding:10px 18px;border-radius:9999px;border:none;cursor:pointer;font-weight:600;font-size:.95rem;transition:opacity .15s}
.btn:active{transform:scale(.96)}
.btn-start{background:#22c55e;color:#022c22}
.btn-stop{background:#ef4444;color:#7f1d1d}
.btn[disabled]{opacity:.4;cursor:not-allowed;transform:none}
.badge{display:inline-flex;align-items:center;padding:4px 10px;border-radius:9999px;font-size:.8rem;font-weight:600}
.badge.on{background:rgba(22,163,74,.15);color:#4ade80;border:1px solid rgba(34,197,94,.4)}
.badge.off{background:rgba(248,113,113,.12);color:#fca5a5;border:1px solid rgba(239,68,68,.5)}
.grid{padding:16px;border-radius:10px;background:#020617;border:1px solid #1f2937;display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.lbl{color:#9ca3af;display:block;margin-bottom:4px;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}
.val{font-size:1.05rem}
.log-wrap{margin-top:20px}
.log-title{font-size:.85rem;color:#9ca3af;margin-bottom:4px}
#logBox{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.78rem;background:#0f172a;border-radius:8px;border:1px solid #1f2937;padding:8px 10px;max-height:280px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
#msg{margin-top:8px;font-size:.8rem;min-height:1.2em}
</style>
</head>
<body>
<div class="c">
  <h1>Samidolla SMC Bot</h1>
  <div class="controls">
    <button class="btn btn-start" id="startBtn" onclick="doStart()">Start Bot</button>
    <button class="btn btn-stop"  id="stopBtn"  onclick="doStop()">Stop Bot</button>
    <span class="badge off" id="badge">Stopped</span>
  </div>
  <div id="msg"></div>

  <div class="grid">
    <div><span class="lbl">Total Scalp</span><span class="val" id="dt">-</span></div>
    <div><span class="lbl">Open Positions</span><span class="val" id="op">-</span></div>
    <div><span class="lbl">Total Swing</span><span class="val" id="sw" style="color:#38bdf8">0</span></div>
    <div><span class="lbl">Wins</span><span class="val" id="wi" style="color:#4ade80">0</span></div>
    <div><span class="lbl">Losses</span><span class="val" id="lo" style="color:#f87171">0</span></div>
    <div><span class="lbl">Last Signal</span><span class="val" id="ls">-</span></div>
  </div>

  <div id="symGrid" style="margin-top:12px;display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px"></div>

  <div class="log-wrap">
    <div class="log-title">Recent log output</div>
    <div id="logBox">Loading...</div>
  </div>
</div>

<script>
var msg = document.getElementById('msg');

function flash(text, ok) {
  msg.textContent = text;
  msg.style.color = ok ? '#4ade80' : '#fca5a5';
  setTimeout(function(){ msg.textContent = ''; }, 4000);
}

function doStart() {
  var btn = document.getElementById('startBtn');
  btn.disabled = true;
  btn.textContent = 'Starting...';
  fetch('/start', {method:'POST'})
    .then(function(r){ return r.json(); })
    .then(function(d){
      flash('Bot started: ' + (d.status || 'ok'), true);
      poll();
      getLogs();
    })
    .catch(function(e){
      flash('Start failed: ' + e, false);
      btn.disabled = false;
      btn.textContent = 'Start Bot';
    });
}

function doStop() {
  var btn = document.getElementById('stopBtn');
  btn.disabled = true;
  btn.textContent = 'Stopping...';
  fetch('/stop', {method:'POST'})
    .then(function(r){ return r.json(); })
    .then(function(d){
      flash('Stop requested: ' + (d.status || 'ok'), true);
      setTimeout(poll, 2000);
    })
    .catch(function(e){
      flash('Stop failed: ' + e, false);
      btn.disabled = false;
      btn.textContent = 'Stop Bot';
    });
}

function setUI(data) {
  var running = !!(data && data.running);
  document.getElementById('dt').textContent = running && data.daily_trades != null ? data.daily_trades : '-';
  document.getElementById('op').textContent = running && data.open_positions != null ? data.open_positions : '-';
  document.getElementById('sw').textContent = running ? (data.swing_trades || 0) : '0';
  document.getElementById('wi').textContent = running ? (data.wins || 0) : '0';
  document.getElementById('lo').textContent = running ? (data.losses || 0) : '0';
  document.getElementById('ls').textContent = running && data.last_signal_time ? new Date(data.last_signal_time).toLocaleString() : '-';
  // Per-symbol cards
  var sg = document.getElementById('symGrid');
  sg.innerHTML = '';
  if (running && data.per_symbol) {
    var syms = Object.keys(data.per_symbol);
    for (var i = 0; i < syms.length; i++) {
      var s = syms[i];
      var info = data.per_symbol[s];
      var card = document.createElement('div');
      card.style.cssText = 'padding:10px;border-radius:8px;background:#1e293b;border:1px solid #334155';
      card.innerHTML = '<div style=\"font-weight:700;color:#f59e0b;margin-bottom:4px\">' + s + '</div>' +
        '<span style=\"color:#9ca3af;font-size:.75rem\">Scalp: </span><span>' + (info.daily_trades || 0) + '</span>' +
        '<span style=\"color:#9ca3af;font-size:.75rem;margin-left:8px\">Swing: </span><span style=\"color:#38bdf8\">' + (info.swing_trades || 0) + '</span>';
      sg.appendChild(card);
    }
  }
  var badge = document.getElementById('badge');
  var startBtn = document.getElementById('startBtn');
  var stopBtn  = document.getElementById('stopBtn');
  if (running) {
    badge.textContent = 'Running';
    badge.className = 'badge on';
    startBtn.disabled = true;  startBtn.textContent = 'Start Bot';
    stopBtn.disabled  = false; stopBtn.textContent  = 'Stop Bot';
  } else {
    badge.textContent = 'Stopped';
    badge.className = 'badge off';
    startBtn.disabled = false; startBtn.textContent = 'Start Bot';
    stopBtn.disabled  = true;  stopBtn.textContent  = 'Stop Bot';
  }
}

function poll() {
  fetch('/status')
    .then(function(r){ return r.json(); })
    .then(setUI)
    .catch(function(){ });
}

function colorLine(line) {
  var span = document.createElement('span');
  span.textContent = line + '\\n';
  if (line.indexOf('TRADE EXECUTED') !== -1 || line.indexOf('Signal generated') !== -1 || line.indexOf('Ticket:') !== -1 || line.indexOf('Direction:') !== -1 || line.indexOf('Entry:') !== -1 || line.indexOf('Volume:') !== -1) {
    span.style.color = '#fb923c';
  } else if (line.indexOf('SWING signal') !== -1 || line.indexOf('[SWING]') !== -1 || line.indexOf('Swing cooldown') !== -1) {
    span.style.color = '#38bdf8';
  } else if (line.indexOf('CLOSED WIN') !== -1 || line.indexOf('TP1 Hit') !== -1 || line.indexOf('TP2 Hit') !== -1 || line.indexOf('Breakeven') !== -1) {
    span.style.color = '#4ade80';
  } else if (line.indexOf('CLOSED LOSS') !== -1 || line.indexOf('Order failed') !== -1) {
    span.style.color = '#f87171';
  }
  return span;
}

function getLogs() {
  fetch('/logs')
    .then(function(r){ return r.json(); })
    .then(function(d){
      var box = document.getElementById('logBox');
      if (d && Array.isArray(d.lines) && d.lines.length) {
        box.innerHTML = '';
        for (var i = 0; i < d.lines.length; i++) {
          box.appendChild(colorLine(d.lines[i]));
        }
        box.scrollTop = box.scrollHeight;
      } else {
        box.textContent = 'No logs yet.';
      }
    })
    .catch(function(){ });
}

poll();
getLogs();
setInterval(poll, 5000);
setInterval(getLogs, 7000);
</script>
</body>
</html>"""


@app.get("/status")
async def status():
    """Return basic bot status for the UI."""
    with _lock:
        running = _is_running()
        if not running or _bot is None:
            return {"running": False}

        # Per-symbol breakdown
        per_symbol = {}
        for sym, state in _bot.symbol_state.items():
            per_symbol[sym] = {
                "daily_trades": state.get("daily_trades", 0),
                "swing_trades": state.get("swing_trades", 0),
            }

        return {
            "running": True,
            "daily_trades": _bot.daily_trades,
            "open_positions": len([p for p in _bot.positions if p["status"] == "open"]),
            "last_signal_time": _bot.last_signal_time.isoformat() if _bot.last_signal_time else None,
            "wins": getattr(_bot, "wins", 0),
            "losses": getattr(_bot, "losses", 0),
            "swing_trades": getattr(_bot, "swing_trades", 0),
            "per_symbol": per_symbol,
        }


@app.post("/start")
async def start_bot():
    """Start the trading bot in a background thread."""
    global _bot, _bot_thread

    with _lock:
        if _is_running():
            return {"status": "already_running"}

        _bot = EURUSD_SMC_Bot()
        _bot_thread = Thread(target=_bot.run, daemon=True)
        _bot_thread.start()

        return {"status": "started"}


@app.post("/stop")
async def stop_bot():
    """Stop the trading bot loop if it is running."""
    global _bot, _bot_thread

    with _lock:
        if not _is_running():
            return {"status": "not_running"}

        if _bot is not None:
            _bot.stop()

    return {"status": "stopping"}


@app.get("/logs")
async def get_logs():
    """Return the last N lines from the current log file."""
    lines = _tail_log_lines(200)
    return JSONResponse({"lines": lines})


# Optional: make `python webapp.py` start uvicorn automatically
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("webapp:app", host="0.0.0.0", port=8000)
