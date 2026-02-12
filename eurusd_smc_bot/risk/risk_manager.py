# risk_manager.py
import MetaTrader5 as mt5
from config import Config


class RiskManager:
    def __init__(self):
        self.config = Config

    def get_account_balance(self):
        """Get current account balance"""
        account_info = mt5.account_info()
        return account_info.balance if account_info else 10000

    def calculate_position_size(self, stop_loss_pips, pip_value=None):
        """Calculate lot size.

        If FIXED_LOT_SIZE is set (> 0), always use that.
        Otherwise fall back to risk-based sizing.
        """

        # Fixed lot size mode (e.g. 0.02 lots every trade)
        if getattr(self.config, "FIXED_LOT_SIZE", 0) and self.config.FIXED_LOT_SIZE > 0:
            return round(self.config.FIXED_LOT_SIZE, 2)

        # Risk-based sizing fallback
        pv = pip_value or self.config.PIP_VALUE
        balance = self.get_account_balance()
        risk_amount = balance * self.config.RISK_PERCENT

        # Approximate pip value per standard lot
        # For EURUSD/AUDUSD (pip=0.0001): ~$10 per pip per lot
        # For GBPJPY (pip=0.01): ~$6.50 per pip per lot (varies with JPY rate)
        pip_value_per_lot = 6.5 if pv == 0.01 else 10.0
        position_size = risk_amount / (stop_loss_pips * pip_value_per_lot)

        # Round to valid lot size (0.01 minimum)
        return round(max(position_size, 0.01), 2)

    def calculate_tp_levels(self, entry, stop_loss, direction, pip_value=None):
        """Calculate 3 take profit levels"""
        pv = pip_value or self.config.PIP_VALUE
        decimals = 3 if pv == 0.01 else 5

        if direction == "buy":
            risk = entry - stop_loss
            tp1 = entry + (risk * self.config.TP1_MULTIPLIER)
            tp2 = entry + (risk * self.config.TP2_MULTIPLIER)
            tp3 = entry + (risk * self.config.TP3_MULTIPLIER)
        else:
            risk = stop_loss - entry
            tp1 = entry - (risk * self.config.TP1_MULTIPLIER)
            tp2 = entry - (risk * self.config.TP2_MULTIPLIER)
            tp3 = entry - (risk * self.config.TP3_MULTIPLIER)

        return {
            "tp1": round(tp1, decimals),
            "tp2": round(tp2, decimals),
            "tp3": round(tp3, decimals),
        }

    def check_daily_limit(self, daily_trades):
        """Check if daily trade limit reached"""
        return daily_trades < self.config.MAX_DAILY_TRADES
