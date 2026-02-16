# trade_history.py
import json
import os
from datetime import datetime
from pathlib import Path

class TradeHistory:
    """Manages persistent trade history storage and retrieval."""
    
    def __init__(self):
        self.history_dir = Path("logs/trade_history")
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.master_file = self.history_dir / "all_trades.json"
        self.daily_file = self.history_dir / f"trades_{datetime.now().strftime('%Y%m%d')}.json"
        
    def save_executed_trade(self, trade_data):
        """Save a newly executed trade to history."""
        trade_record = {
            "ticket": trade_data.get("ticket"),
            "symbol": trade_data.get("symbol"),
            "direction": trade_data.get("direction"),
            "entry_price": trade_data.get("entry_price"),
            "entry_time": datetime.now().isoformat(),
            "volume": trade_data.get("volume"),
            "stop_loss": trade_data.get("stop_loss"),
            "tp1": trade_data.get("tp1"),
            "tp2": trade_data.get("tp2"),
            "tp3": trade_data.get("tp3"),
            "stop_pips": trade_data.get("stop_pips"),
            "confidence": trade_data.get("confidence"),
            "trade_type": trade_data.get("trade_type"),  # SCALP or SWING
            "bos_confirmed": trade_data.get("bos_confirmed", False),
            "status": "OPEN",
            "exit_price": None,
            "exit_time": None,
            "profit_loss": None,
            "pips_gained": None,
            "close_reason": None,
        }
        
        self._append_to_file(self.master_file, trade_record)
        self._append_to_file(self.daily_file, trade_record)
        
        return trade_record
    
    def save_closed_trade(self, ticket, exit_price, profit_loss, pips_gained, close_reason):
        """Update trade history when a position is closed."""
        trades = self.load_all_trades()
        
        for trade in trades:
            if trade["ticket"] == ticket:
                trade["status"] = "CLOSED"
                trade["exit_price"] = exit_price
                trade["exit_time"] = datetime.now().isoformat()
                trade["profit_loss"] = profit_loss
                trade["pips_gained"] = pips_gained
                trade["close_reason"] = close_reason  # WIN, LOSS, TP1, TP2, SL, MANUAL
                break
        
        # Rewrite master file with updated trade
        self._write_all_trades(trades)
        
    def load_all_trades(self):
        """Load all trades from master history file."""
        if not self.master_file.exists():
            return []
        
        try:
            with open(self.master_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def load_daily_trades(self):
        """Load today's trades."""
        if not self.daily_file.exists():
            return []
        
        try:
            with open(self.daily_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def get_trade_stats(self):
        """Calculate statistics from trade history."""
        trades = self.load_all_trades()
        closed_trades = [t for t in trades if t["status"] == "CLOSED"]
        
        if not closed_trades:
            return {
                "total_trades": len(trades),
                "closed_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "total_pips": 0,
                "total_profit": 0,
                "avg_profit_per_trade": 0,
                "best_trade": None,
                "worst_trade": None,
            }
        
        wins = [t for t in closed_trades if t.get("profit_loss", 0) >= 0]
        losses = [t for t in closed_trades if t.get("profit_loss", 0) < 0]
        
        total_profit = sum(t.get("profit_loss", 0) for t in closed_trades)
        total_pips = sum(t.get("pips_gained", 0) for t in closed_trades)
        
        best_trade = max(closed_trades, key=lambda t: t.get("profit_loss", 0)) if closed_trades else None
        worst_trade = min(closed_trades, key=lambda t: t.get("profit_loss", 0)) if closed_trades else None
        
        return {
            "total_trades": len(trades),
            "closed_trades": len(closed_trades),
            "open_trades": len(trades) - len(closed_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round((len(wins) / len(closed_trades) * 100), 2) if closed_trades else 0,
            "total_pips": round(total_pips, 2),
            "total_profit": round(total_profit, 2),
            "avg_profit_per_trade": round(total_profit / len(closed_trades), 2) if closed_trades else 0,
            "best_trade": {
                "symbol": best_trade.get("symbol"),
                "profit": best_trade.get("profit_loss"),
                "pips": best_trade.get("pips_gained"),
            } if best_trade else None,
            "worst_trade": {
                "symbol": worst_trade.get("symbol"),
                "profit": worst_trade.get("profit_loss"),
                "pips": worst_trade.get("pips_gained"),
            } if worst_trade else None,
        }
    
    def _append_to_file(self, filepath, trade_record):
        """Append trade to JSON file."""
        trades = []
        if filepath.exists():
            try:
                with open(filepath, 'r') as f:
                    trades = json.load(f)
            except:
                trades = []
        
        trades.append(trade_record)
        
        with open(filepath, 'w') as f:
            json.dump(trades, f, indent=2)
    
    def _write_all_trades(self, trades):
        """Write all trades to master file."""
        with open(self.master_file, 'w') as f:
            json.dump(trades, f, indent=2)
