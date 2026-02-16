from datetime import datetime
from threading import Thread, Lock
from typing import Optional
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import os
import traceback

try:
    from main import EURUSD_SMC_Bot
except ImportError:
    from .main import EURUSD_SMC_Bot

os.makedirs('logs', exist_ok=True)

# Setup basic logging for the API
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/webapp.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('webapp')
logger.info("Starting EURUSD SMC Bot WebApp")

app = FastAPI(title="EURUSD SMC Bot Dashboard")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes slideIn{from{opacity:0;transform:translateX(-20px)}to{opacity:1;transform:translateX(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
@keyframes shimmer{0%{background-position:-1000px 0}100%{background-position:1000px 0}}
@keyframes float{0%,100%{transform:translateY(0px)}50%{transform:translateY(-3px)}}

*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',sans-serif;background:linear-gradient(135deg,#0f172a 0%,#1a1f3a 50%,#0f172a 100%);color:#e5e7eb;margin:0;padding:0;min-height:100vh}

.container{max-width:1100px;margin:0 auto;padding:24px;animation:fadeIn .6s ease-out}

header{text-align:center;margin-bottom:36px;animation:fadeIn .8s ease-out}
h1{margin:0;font-size:2.5rem;font-weight:700;background:linear-gradient(135deg,#4ade80,#38bdf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;letter-spacing:-1px}
header>p{color:#9ca3af;margin:8px 0 0;font-size:.95rem}

.controls{display:flex;gap:16px;margin-bottom:32px;align-items:center;justify-content:center;flex-wrap:wrap;animation:slideIn .8s ease-out}

.btn{padding:12px 28px;border-radius:8px;border:none;cursor:pointer;font-weight:600;font-size:.95rem;transition:all .3s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,.1)}
.btn::before{content:'';position:absolute;top:0;left:-100%;width:100%;height:100%;background:rgba(255,255,255,.1);transition:.5s;z-index:1}
.btn:hover::before{left:100%}
.btn span{position:relative;z-index:2}

.btn-start{background:linear-gradient(135deg,#22c55e,#16a34a);color:#fff;box-shadow:0 8px 15px rgba(34,197,94,.3)}
.btn-start:hover{transform:translateY(-2px);box-shadow:0 12px 20px rgba(34,197,94,.4)}
.btn-start:active{transform:translateY(0)}

.btn-stop{background:linear-gradient(135deg,#ef4444,#dc2626);color:#fff;box-shadow:0 8px 15px rgba(239,68,68,.3)}
.btn-stop:hover{transform:translateY(-2px);box-shadow:0 12px 20px rgba(239,68,68,.4)}
.btn-stop:active{transform:translateY(0)}

.btn[disabled]{opacity:.5;cursor:not-allowed;transform:none !important}

.badge{display:inline-flex;align-items:center;gap:8px;padding:8px 16px;border-radius:999px;font-size:.85rem;font-weight:600;animation:fadeIn 1s ease-out;position:relative}
.badge::before{content:'';width:8px;height:8px;background:currentColor;border-radius:50%;animation:pulse 2s infinite}
.badge.on{background:rgba(34,197,94,.15);color:#4ade80;border:1.5px solid rgba(34,197,94,.4)}
.badge.off{background:rgba(239,68,68,.15);color:#fca5a5;border:1.5px solid rgba(239,68,68,.5)}

#msg{margin:16px 0;padding:12px 16px;border-radius:8px;font-size:.9rem;min-height:1.5em;animation:slideIn .4s ease-out;display:none}
#msg.show{display:block}
#msg.success{background:rgba(34,197,94,.1);color:#4ade80;border-left:3px solid #22c55e}
#msg.error{background:rgba(239,68,68,.1);color:#fca5a5;border-left:3px solid #ef4444}

.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:32px}
.stat-card{padding:18px;border-radius:12px;background:linear-gradient(135deg,rgba(30,41,59,.6),rgba(15,23,42,.4));border:1px solid rgba(148,163,184,.1);transition:all .3s ease;animation:fadeIn .6s ease-out;backdrop-filter:blur(10px)}
.stat-card:hover{transform:translateY(-4px);border-color:rgba(148,163,184,.3);box-shadow:0 8px 16px rgba(0,0,0,.2)}

.stat-label{color:#9ca3af;display:block;margin-bottom:6px;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}
.stat-value{font-size:1.6rem;font-weight:700}

.sym-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:32px}
.sym-card{padding:14px;border-radius:10px;background:rgba(30,41,59,.5);border:1px solid rgba(148,163,184,.1);transition:all .3s ease;animation:fadeIn .6s ease-out;cursor:pointer}
.sym-card:hover{border-color:rgba(148,163,184,.3);background:rgba(30,41,59,.8);transform:translateY(-2px)}
.sym-name{font-weight:700;color:#f59e0b;margin-bottom:8px;font-size:.95rem}
.sym-stat{color:#9ca3af;font-size:.8rem;display:flex;justify-content:space-between;margin-bottom:4px}
.sym-stat-val{color:#e5e7eb;font-weight:600}

.section-title{font-size:.9rem;color:#9ca3af;margin-bottom:16px;text-transform:uppercase;letter-spacing:.05em;padding-left:4px;font-weight:600}

.trades-section{margin-bottom:32px;animation:fadeIn .8s ease-out}
.trades-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.trade-card{padding:16px;border-radius:10px;background:linear-gradient(135deg,rgba(30,41,59,.7),rgba(15,23,42,.5));border:1px solid rgba(148,163,184,.2);transition:all .3s ease;animation:fadeIn .6s ease-out;position:relative;overflow:hidden}
.trade-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,#4ade80,transparent);opacity:0;transition:.3s}
.trade-card:hover{border-color:rgba(148,163,184,.4);box-shadow:0 8px 16px rgba(0,0,0,.3);transform:translateY(-2px)}
.trade-card:hover::before{opacity:1}

.trade-header{font-weight:700;color:#f59e0b;margin-bottom:10px;font-size:.95rem;display:flex;justify-content:space-between}
.trade-badge{font-size:.7rem;padding:3px 8px;background:rgba(74,222,128,.2);color:#4ade80;border-radius:4px}

.trade-row{color:#9ca3af;font-size:.85rem;margin-bottom:6px;display:flex;justify-content:space-between}
.trade-row-label{color:#9ca3af}
.trade-row-value{color:#e5e7eb;font-weight:500}

.trade-divider{border-top:1px solid rgba(148,163,184,.1);margin:8px 0}
.trade-pnl{padding-top:8px;font-weight:600;font-size:.9rem;display:flex;justify-content:space-between;align-items:center}

.stats-section{margin-bottom:32px;animation:fadeIn .8s ease-out}
.stats-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px}
.stats-card{padding:14px;border-radius:10px;background:rgba(30,41,59,.5);border:1px solid rgba(148,163,184,.1);text-align:center;transition:all .3s ease;animation:fadeIn .6s ease-out}
.stats-card:hover{border-color:rgba(148,163,184,.3);transform:scale(1.05)}
.stats-label{color:#9ca3af;font-size:.75rem;margin-bottom:6px;text-transform:uppercase}
.stats-value{font-weight:700;font-size:1.2rem;color:#e5e7eb}

.log-section{margin-top:32px;animation:fadeIn 1s ease-out}
.log-box{font-family:'Fira Code','Courier New',monospace;font-size:.75rem;background:rgba(15,23,42,.8);border-radius:10px;border:1px solid rgba(148,163,184,.1);padding:12px;max-height:300px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;line-height:1.5;color:#9ca3af}
.log-box::-webkit-scrollbar{width:6px}
.log-box::-webkit-scrollbar-track{background:rgba(255,255,255,.05)}
.log-box::-webkit-scrollbar-thumb{background:rgba(255,255,255,.2);border-radius:3px}
.log-box::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,.3)}

.loading{display:inline-block;animation:pulse 1.5s infinite}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Samidolla SMC Bot</h1>
    <p>Professional Trading Automation</p>
  </header>

  <div class="controls">
    <button class="btn btn-start" id="startBtn" onclick="doStart()"><span>▶ Start Bot</span></button>
    <button class="btn btn-stop" id="stopBtn" onclick="doStop()"><span>⏹ Stop Bot</span></button>
    <span class="badge off" id="badge">Stopped</span>
  </div>
  
  <div id="msg"></div>

  <div class="stats-grid">
    <div class="stat-card"><span class="stat-label">Total Scalp</span><span class="stat-value" id="dt">-</span></div>
    <div class="stat-card"><span class="stat-label">Open Positions</span><span class="stat-value" id="op">-</span></div>
    <div class="stat-card"><span class="stat-label">Total Swing</span><span class="stat-value" id="sw" style="color:#38bdf8">0</span></div>
    <div class="stat-card"><span class="stat-label">Wins</span><span class="stat-value" id="wi" style="color:#4ade80">0</span></div>
    <div class="stat-card"><span class="stat-label">Losses</span><span class="stat-value" id="lo" style="color:#f87171">0</span></div>
    <div class="stat-card"><span class="stat-label">Live P&L</span><span class="stat-value" id="pnl" style="color:#fbbf24">R0.00</span></div>
  </div>

  <div id="symGrid" class="sym-grid"></div>

  <div id="tradesSection" class="trades-section" style="display:none">
    <div class="section-title">📊 Running Trades</div>
    <div id="tradesGrid" class="trades-grid"></div>
  </div>

  <div id="statsSection" class="stats-section" style="display:none">
    <div class="section-title">📈 All-Time Statistics</div>
    <div id="statsGrid" class="stats-cards"></div>
  </div>

  <div class="log-section">
    <div class="section-title">📝 Recent Activity</div>
    <div id="logBox" class="log-box">Loading...</div>
  </div>
</div>

<script>
var msg = document.getElementById('msg');

function flash(text, ok) {
  msg.textContent = text;
  msg.className = ok ? 'show success' : 'show error';
  setTimeout(function(){ msg.className = ''; }, 4000);
}

function doStart() {
  var btn = document.getElementById('startBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="loading">⟳ Starting...</span>';
  fetch('/start', {method:'POST'})
    .then(function(r){ 
      if (!r.ok) throw new Error('HTTP ' + r.status + ': ' + r.statusText);
      return r.json(); 
    })
    .then(function(d){
      if (d.status === 'error') {
        flash('✗ ' + (d.message || 'Start failed'), false);
        btn.disabled = false;
        btn.innerHTML = '<span>▶ Start Bot</span>';
      } else {
        flash('✓ Bot started successfully', true);
        setTimeout(function(){ poll(); getLogs(); }, 500);
      }
    })
    .catch(function(e){
      flash('✗ Start failed: ' + e.message, false);
      btn.disabled = false;
      btn.innerHTML = '<span>▶ Start Bot</span>';
    });
}

function doStop() {
  var btn = document.getElementById('stopBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="loading">⟳ Stopping...</span>';
  fetch('/stop', {method:'POST'})
    .then(function(r){ 
      if (!r.ok) throw new Error('HTTP ' + r.status + ': ' + r.statusText);
      return r.json(); 
    })
    .then(function(d){
      if (d.status === 'error') {
        flash('✗ ' + (d.message || 'Stop failed'), false);
        btn.disabled = false;
        btn.innerHTML = '<span>⏹ Stop Bot</span>';
      } else {
        flash('✓ Stop requested successfully', true);
        setTimeout(poll, 2000);
      }
    })
    .catch(function(e){
      flash('✗ Stop failed: ' + e.message, false);
      btn.disabled = false;
      btn.innerHTML = '<span>⏹ Stop Bot</span>';
    });
}

function setUI(data) {
  var running = !!(data && data.running);
  document.getElementById('dt').textContent = running && data.daily_trades != null ? data.daily_trades : '-';
  document.getElementById('op').textContent = running && data.open_positions != null ? data.open_positions : '-';
  document.getElementById('sw').textContent = running ? (data.swing_trades || 0) : '0';
  document.getElementById('wi').textContent = running ? (data.wins || 0) : '0';
  document.getElementById('lo').textContent = running ? (data.losses || 0) : '0';
  
  // Per-symbol cards
  var sg = document.getElementById('symGrid');
  sg.innerHTML = '';
  if (running && data.per_symbol) {
    var syms = Object.keys(data.per_symbol);
    for (var i = 0; i < syms.length; i++) {
      var s = syms[i];
      var info = data.per_symbol[s];
      var card = document.createElement('div');
      card.className = 'sym-card';
      card.innerHTML = '<div class="sym-name">' + s + '</div>' +
        '<div class="sym-stat"><span>Scalp:</span> <span class="sym-stat-val">' + (info.daily_trades || 0) + '</span></div>' +
        '<div class="sym-stat"><span>Swing:</span> <span class="sym-stat-val" style="color:#38bdf8">' + (info.swing_trades || 0) + '</span></div>';
      sg.appendChild(card);
    }
  }
  
  var badge = document.getElementById('badge');
  var startBtn = document.getElementById('startBtn');
  var stopBtn  = document.getElementById('stopBtn');
  if (running) {
    badge.textContent = 'Running';
    badge.className = 'badge on';
    startBtn.disabled = true;  startBtn.innerHTML = '<span>▶ Start Bot</span>';
    stopBtn.disabled  = false; stopBtn.innerHTML  = '<span>⏹ Stop Bot</span>';
  } else {
    badge.textContent = 'Stopped';
    badge.className = 'badge off';
    startBtn.disabled = false; startBtn.innerHTML = '<span>▶ Start Bot</span>';
    stopBtn.disabled  = true;  stopBtn.innerHTML  = '<span>⏹ Stop Bot</span>';
  }
}

function displayTrades(tradeData) {
  var tradesSection = document.getElementById('tradesSection');
  var tradesGrid = document.getElementById('tradesGrid');
  var pnlElem = document.getElementById('pnl');
  
  if (!tradeData.running || tradeData.trade_count === 0) {
    tradesSection.style.display = 'none';
    pnlElem.textContent = 'R0.00';
    pnlElem.style.color = '#fbbf24';
    return;
  }
  
  tradesSection.style.display = 'block';
  tradesGrid.innerHTML = '';
  
  // Update P&L color
  var pnlValue = tradeData.total_profit >= 0 ? '+' : '';
  pnlElem.textContent = pnlValue + 'R' + tradeData.total_profit.toFixed(2);
  pnlElem.style.color = tradeData.total_profit >= 0 ? '#4ade80' : '#f87171';
  
  // Display each trade
  for (var i = 0; i < tradeData.trades.length; i++) {
    var trade = tradeData.trades[i];
    var profitColor = trade.profit_r >= 0 ? '#4ade80' : '#f87171';
    var card = document.createElement('div');
    card.className = 'trade-card';
    
    var statusBadge = trade.tp2_hit ? '✓ TP2' : (trade.tp1_hit ? '✓ TP1' : (trade.be_moved ? 'BE' : 'OPEN'));
    var dirColor = trade.direction === 'BUY' ? '#4ade80' : '#f87171';
    
    card.innerHTML = 
      '<div class="trade-header">' + trade.symbol + ' <span style="color:' + dirColor + '">' + trade.direction + '</span><span class="trade-badge">' + statusBadge + '</span></div>' +
      '<div class="trade-row"><span>Ticket:</span> <span class="trade-row-value">' + trade.ticket + '</span></div>' +
      '<div class="trade-row"><span>Entry:</span> <span class="trade-row-value">' + trade.entry_price.toFixed(5) + '</span></div>' +
      '<div class="trade-row"><span>Current:</span> <span class="trade-row-value">' + trade.current_price.toFixed(5) + '</span></div>' +
      '<div class="trade-row"><span>SL:</span> <span class="trade-row-value">' + trade.sl.toFixed(5) + '</span></div>' +
      '<div class="trade-row"><span>Pips:</span> <span class="trade-row-value" style="color:' + dirColor + '">' + (trade.pips >= 0 ? '+' : '') + trade.pips.toFixed(1) + '</span></div>' +
      '<div class="trade-divider"></div>' +
      '<div class="trade-pnl"><span>P&L:</span> <span style="color:' + profitColor + '">R' + (trade.profit_r >= 0 ? '+' : '') + trade.profit_r.toFixed(2) + '</span></div>';
    
    tradesGrid.appendChild(card);
  }
}

function getTrades() {
  fetch('/trades')
    .then(function(r){ return r.json(); })
    .then(displayTrades)
    .catch(function(){ });
}

function getStats() {
  fetch('/trade-stats')
    .then(function(r){ return r.json(); })
    .then(function(d){
      var statsSection = document.getElementById('statsSection');
      var statsGrid = document.getElementById('statsGrid');
      if (d && d.stats && d.stats.closed_trades > 0) {
        statsSection.style.display = 'block';
        statsGrid.innerHTML = '';
        var stats = d.stats;
        var statItems = [
          {label: 'Total Trades', value: stats.total_trades},
          {label: 'Closed', value: stats.closed_trades},
          {label: 'Open', value: stats.open_trades},
          {label: 'Wins', value: stats.wins, color: '#4ade80'},
          {label: 'Losses', value: stats.losses, color: '#f87171'},
          {label: 'Win Rate', value: stats.win_rate + '%'},
          {label: 'Total Pips', value: stats.total_pips.toFixed(1)},
          {label: 'Total P&L', value: 'R' + (stats.total_profit >= 0 ? '+' : '') + stats.total_profit.toFixed(2), color: stats.total_profit >= 0 ? '#4ade80' : '#f87171'},
        ];
        for (var i = 0; i < statItems.length; i++) {
          var item = statItems[i];
          var card = document.createElement('div');
          card.className = 'stats-card';
          var valColor = item.color || '#e5e7eb';
          card.innerHTML = '<div class="stats-label">' + item.label + '</div><div class="stats-value" style="color:' + valColor + '">' + item.value + '</div>';
          statsGrid.appendChild(card);
        }
      } else {
        statsSection.style.display = 'none';
      }
    })
    .catch(function(){ });
}

function poll() {
  fetch('/status')
    .then(function(r){ return r.json(); })
    .then(setUI)
    .catch(function(){ });
}

function colorLine(line) {
  var span = document.createElement('span');
  span.textContent = line + '\n';
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
getTrades();
getStats();
setInterval(poll, 5000);
setInterval(getLogs, 7000);
setInterval(getTrades, 3000);
setInterval(getStats, 10000);
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


@app.get("/trades")
async def get_open_trades():
    """Return details of open positions with live profit/loss."""
    import MetaTrader5 as mt5
    
    with _lock:
        running = _is_running()
        if not running or _bot is None:
            return {"running": False, "trades": []}
        
        trades = []
        total_profit = 0
        
        for position in _bot.positions:
            if position['status'] != 'open':
                continue
            
            sym = position.get('symbol', _bot.config.SYMBOL)
            pv = _bot.config.SYMBOLS.get(sym, {}).get('pip_value', _bot.config.PIP_VALUE)
            
            # Get current position data from MT5
            pos = mt5.positions_get(ticket=position['ticket'])
            if not pos or len(pos) == 0:
                continue
            
            pos = pos[0]
            current_price = pos.price_current
            
            # Calculate profit/loss
            profit = pos.profit + pos.swap + pos.commission
            total_profit += profit
            
            # Calculate pips
            if position['direction'] == 'buy':
                pips = (current_price - position['price']) / pv
            else:
                pips = (position['price'] - current_price) / pv
            
            trades.append({
                "ticket": position['ticket'],
                "symbol": sym,
                "direction": position['direction'].upper(),
                "entry_price": round(position['price'], 5),
                "current_price": round(current_price, 5),
                "volume": position['volume'],
                "pips": round(pips, 2),
                "profit_r": round(profit, 2),
                "profit_percent": round((profit / _bot.config.FIXED_LOT_SIZE) * 100, 2) if _bot.config.FIXED_LOT_SIZE else 0,
                "tp1": round(position['tp1'], 5),
                "tp2": round(position['tp2'], 5),
                "sl": round(position['sl'], 5),
                "tp1_hit": position.get('tp1_hit', False),
                "tp2_hit": position.get('tp2_hit', False),
                "be_moved": position.get('be_moved', False),
            })
        
        return {
            "running": True,
            "trades": trades,
            "total_profit": round(total_profit, 2),
            "trade_count": len(trades),
        }


@app.post("/start")
async def start_bot():
    """Start the trading bot in a background thread."""
    global _bot, _bot_thread

    with _lock:
        if _is_running():
            return JSONResponse({"status": "already_running"})

        try:
            logger.info("Creating bot instance...")
            _bot = EURUSD_SMC_Bot()
            logger.info("Starting bot thread...")
            _bot_thread = Thread(target=_bot.run, daemon=True)
            _bot_thread.start()
            logger.info("Bot thread started successfully")
            return JSONResponse({"status": "started"})
        except Exception as e:
            error_msg = f"Failed to start bot: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return JSONResponse({"status": "error", "message": error_msg}, status_code=500)


@app.post("/stop")
async def stop_bot():
    """Stop the trading bot loop if it is running."""
    global _bot, _bot_thread

    with _lock:
        if not _is_running():
            return JSONResponse({"status": "not_running"})

        try:
            logger.info("Stopping bot...")
            if _bot is not None:
                _bot.stop()
            logger.info("Bot stop signal sent")
            return JSONResponse({"status": "stopping"})
        except Exception as e:
            error_msg = f"Failed to stop bot: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return JSONResponse({"status": "error", "message": error_msg}, status_code=500)


@app.get("/logs")
async def get_logs():
    """Return the last N lines from the current log file."""
    lines = _tail_log_lines(200)
    return JSONResponse({"lines": lines})


@app.get("/trade-stats")
async def get_trade_stats():
    """Return trade statistics and history."""
    with _lock:
        if _bot is None:
            return {"stats": None, "trades": []}
        
        stats = _bot.trade_history.get_trade_stats()
        all_trades = _bot.trade_history.load_all_trades()
        
        return {
            "stats": stats,
            "trades": all_trades,
            "generated_at": datetime.now().isoformat(),
        }


@app.get("/debug")
async def debug_info():
    """Return diagnostic information for debugging."""
    import sys
    import MetaTrader5 as mt5
    
    return {
        "bot_running": _is_running(),
        "bot_instance": _bot is not None,
        "python_version": sys.version,
        "mt5_version": mt5.version() if mt5 else "Not available",
        "logs_path": str(Path("logs").absolute()),
        "timestamp": datetime.now().isoformat(),
    }


# Optional: make `python webapp.py` start uvicorn automatically
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("webapp:app", host="0.0.0.0", port=8000)
