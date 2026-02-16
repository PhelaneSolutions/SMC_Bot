# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # JustMarkets Credentials
    MT5_LOGIN = int(os.getenv('MT5_LOGIN', 0))
    MT5_PASSWORD = os.getenv('MT5_PASSWORD', '')
    MT5_SERVER = os.getenv('MT5_SERVER', 'JustMarkets-Live')
    
    # ── Symbols to trade ──
    SYMBOLS = {
        "EURUSD.ecn": {"pip_value": 0.0001, "max_spread": 2.0, "swing_max_spread": 3.0},
        "GBPJPY.ecn": {"pip_value": 0.01,   "max_spread": 3.0, "swing_max_spread": 4.0},
        "AUDUSD.ecn": {"pip_value": 0.0001, "max_spread": 2.0, "swing_max_spread": 3.0},
    }

    # Legacy single-symbol fallback (kept for compatibility)
    SYMBOL = "EURUSD.ecn"
    PIP_VALUE = 0.0001
    
    # SMC Parameters
    MIN_FVG_PIPS = 3
    MAX_FVG_PIPS = 20
    MIN_OB_SIZE_PIPS = 8
    MAX_OB_AGE = 30  # candles
    MAX_OB_DISTANCE_PIPS = 8   # max distance from OB for entry
    MIN_OB_STRENGTH = 1.2      # volume ratio threshold for OBs
    
    # Risk Management
    RISK_PERCENT = 0.25  # risk-based sizing (ignored if FIXED_LOT_SIZE > 0)
    FIXED_LOT_SIZE = 0.02  # use fixed 0.02 lots per trade for now
    MAX_DAILY_TRADES = 5        # per symbol
    MIN_STOP_PIPS = 5
    MAX_STOP_PIPS = 25
    
    # Trade Management
    BREAKEVEN_PIPS = 8
    TP1_MULTIPLIER = 1.5
    TP2_MULTIPLIER = 2.0
    TP3_MULTIPLIER = 2.5
    
    # Timeframes
    ENTRY_TIMEFRAME = 15  # M15
    BIAS_TIMEFRAME = 60   # H1

    # Session / Market Filters
    SESSION_START_HOUR = 7   # 07:00 server time
    SESSION_END_HOUR = 17    # 17:00 server time
    MAX_SPREAD_PIPS = 2.0

    # ── Swing Trade Parameters ──
    SWING_ENABLED = True
    SWING_FIXED_LOT_SIZE = 0.02       # smaller size for longer holds
    SWING_MAX_DAILY_TRADES = 2
    SWING_MIN_FVG_PIPS = 8
    SWING_MAX_FVG_PIPS = 60
    SWING_MIN_OB_SIZE_PIPS = 15
    SWING_MAX_OB_DISTANCE_PIPS = 20
    SWING_MIN_OB_STRENGTH = 1.1
    SWING_MIN_STOP_PIPS = 15
    SWING_MAX_STOP_PIPS = 60
    SWING_BREAKEVEN_PIPS = 25
    SWING_TP1_MULTIPLIER = 2.0
    SWING_TP2_MULTIPLIER = 3.0
    SWING_TP3_MULTIPLIER = 4.0
    SWING_MAX_SPREAD_PIPS = 3.0
    SWING_COOLDOWN_SECONDS = 3600     # 1 hour between swing signals