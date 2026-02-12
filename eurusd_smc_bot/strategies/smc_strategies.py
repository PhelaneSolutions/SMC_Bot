# smc_strategies.py
import pandas as pd
import numpy as np
import talib
from config import Config


class SMCStrategies:
    """Smart Money Concepts - Multi-Symbol"""

    def __init__(self):
        self.config = Config

    def calculate_atr_pips(self, df, pip_value=None):
        """Calculate ATR in pips"""
        pv = pip_value or self.config.PIP_VALUE
        atr = talib.ATR(df["high"], df["low"], df["close"], timeperiod=14)
        return atr.iloc[-1] / pv

    def identify_order_blocks(self, df, pip_value=None):
        """Find institutional order blocks"""
        pv = pip_value or self.config.PIP_VALUE
        order_blocks = []
        atr_pips = self.calculate_atr_pips(df, pv)

        for i in range(2, len(df) - 2):
            candle = df.iloc[i]
            next_candle = df.iloc[i + 1]

            if (candle["close"] > candle["open"]
                    and next_candle["close"] > candle["high"]):
                ob_size = (candle["high"] - candle["low"]) / pv
                if ob_size >= self.config.MIN_OB_SIZE_PIPS:
                    order_blocks.append({
                        "type": "bullish",
                        "price": candle["low"],
                        "stop": candle["low"] - (atr_pips * 0.4 * pv),
                        "strength": candle["tick_volume"] / df.iloc[i - 1]["tick_volume"],
                        "time": candle.name,
                    })

            if (candle["close"] < candle["open"]
                    and next_candle["close"] < candle["low"]):
                ob_size = (candle["high"] - candle["low"]) / pv
                if ob_size >= self.config.MIN_OB_SIZE_PIPS:
                    order_blocks.append({
                        "type": "bearish",
                        "price": candle["high"],
                        "stop": candle["high"] + (atr_pips * 0.4 * pv),
                        "strength": candle["tick_volume"] / df.iloc[i - 1]["tick_volume"],
                        "time": candle.name,
                    })

        return order_blocks[-8:]

    def identify_fair_value_gaps(self, df, pip_value=None):
        """Find Fair Value Gaps"""
        pv = pip_value or self.config.PIP_VALUE
        fvgs = []

        for i in range(1, len(df) - 1):
            if df.iloc[i + 1]["low"] > df.iloc[i - 1]["high"]:
                gap_pips = (df.iloc[i + 1]["low"] - df.iloc[i - 1]["high"]) / pv
                if self.config.MIN_FVG_PIPS <= gap_pips <= self.config.MAX_FVG_PIPS:
                    fvgs.append({
                        "type": "bullish",
                        "top": df.iloc[i + 1]["low"],
                        "bottom": df.iloc[i - 1]["high"],
                        "mid": (df.iloc[i + 1]["low"] + df.iloc[i - 1]["high"]) / 2,
                        "size": gap_pips,
                        "time": df.iloc[i].name,
                    })

            if df.iloc[i + 1]["high"] < df.iloc[i - 1]["low"]:
                gap_pips = (df.iloc[i - 1]["low"] - df.iloc[i + 1]["high"]) / pv
                if self.config.MIN_FVG_PIPS <= gap_pips <= self.config.MAX_FVG_PIPS:
                    fvgs.append({
                        "type": "bearish",
                        "top": df.iloc[i - 1]["low"],
                        "bottom": df.iloc[i + 1]["high"],
                        "mid": (df.iloc[i - 1]["low"] + df.iloc[i + 1]["high"]) / 2,
                        "size": gap_pips,
                        "time": df.iloc[i].name,
                    })

        return fvgs[-12:]

    def analyze_trend(self, df):
        """Determine market structure"""
        ema_8 = talib.EMA(df["close"], timeperiod=8)
        ema_21 = talib.EMA(df["close"], timeperiod=21)
        ema_55 = talib.EMA(df["close"], timeperiod=55)

        current_price = df["close"].iloc[-1]

        score = 0
        if current_price > ema_8.iloc[-1]:
            score += 1
        if ema_8.iloc[-1] > ema_21.iloc[-1]:
            score += 1
        if ema_21.iloc[-1] > ema_55.iloc[-1]:
            score += 1
        if df["close"].iloc[-1] > df["close"].iloc[-5]:
            score += 1

        if score >= 3:
            trend = "bullish"
        elif score <= 1:
            trend = "bearish"
        else:
            trend = "ranging"

        return {"trend": trend, "score": score}

    # ── Swing-specific helpers (wider params) ──

    def identify_order_blocks_swing(self, df, pip_value=None):
        """Find order blocks with swing-width filters."""
        pv = pip_value or self.config.PIP_VALUE
        order_blocks = []
        atr_pips = self.calculate_atr_pips(df, pv)

        for i in range(2, len(df) - 2):
            candle = df.iloc[i]
            next_candle = df.iloc[i + 1]

            if (candle["close"] > candle["open"]
                    and next_candle["close"] > candle["high"]):
                ob_size = (candle["high"] - candle["low"]) / pv
                if ob_size >= self.config.SWING_MIN_OB_SIZE_PIPS:
                    order_blocks.append({
                        "type": "bullish",
                        "price": candle["low"],
                        "stop": candle["low"] - (atr_pips * 0.5 * pv),
                        "strength": candle["tick_volume"] / df.iloc[i - 1]["tick_volume"],
                        "time": candle.name,
                    })

            if (candle["close"] < candle["open"]
                    and next_candle["close"] < candle["low"]):
                ob_size = (candle["high"] - candle["low"]) / pv
                if ob_size >= self.config.SWING_MIN_OB_SIZE_PIPS:
                    order_blocks.append({
                        "type": "bearish",
                        "price": candle["high"],
                        "stop": candle["high"] + (atr_pips * 0.5 * pv),
                        "strength": candle["tick_volume"] / df.iloc[i - 1]["tick_volume"],
                        "time": candle.name,
                    })

        return order_blocks[-6:]

    def identify_fair_value_gaps_swing(self, df, pip_value=None):
        """Find FVGs with swing-width filters."""
        pv = pip_value or self.config.PIP_VALUE
        fvgs = []

        for i in range(1, len(df) - 1):
            if df.iloc[i + 1]["low"] > df.iloc[i - 1]["high"]:
                gap_pips = (df.iloc[i + 1]["low"] - df.iloc[i - 1]["high"]) / pv
                if self.config.SWING_MIN_FVG_PIPS <= gap_pips <= self.config.SWING_MAX_FVG_PIPS:
                    fvgs.append({
                        "type": "bullish",
                        "top": df.iloc[i + 1]["low"],
                        "bottom": df.iloc[i - 1]["high"],
                        "mid": (df.iloc[i + 1]["low"] + df.iloc[i - 1]["high"]) / 2,
                        "size": gap_pips,
                        "time": df.iloc[i].name,
                    })

            if df.iloc[i + 1]["high"] < df.iloc[i - 1]["low"]:
                gap_pips = (df.iloc[i - 1]["low"] - df.iloc[i + 1]["high"]) / pv
                if self.config.SWING_MIN_FVG_PIPS <= gap_pips <= self.config.SWING_MAX_FVG_PIPS:
                    fvgs.append({
                        "type": "bearish",
                        "top": df.iloc[i - 1]["low"],
                        "bottom": df.iloc[i + 1]["high"],
                        "mid": (df.iloc[i - 1]["low"] + df.iloc[i + 1]["high"]) / 2,
                        "size": gap_pips,
                        "time": df.iloc[i].name,
                    })

        return fvgs[-8:]
