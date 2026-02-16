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

    def detect_break_of_structure(self, df, pip_value=None):
        """
        Detect Break of Structure (BOS) - price breaks previous swing highs/lows.
        Bullish BOS: Price breaks above previous swing high
        Bearish BOS: Price breaks below previous swing low
        """
        pv = pip_value or self.config.PIP_VALUE
        
        if len(df) < 10:
            return None
        
        # Find last 3 swing highs and lows
        highs = []
        lows = []
        
        for i in range(2, len(df) - 2):
            # Swing high: bar with higher high on both sides
            if df['high'].iloc[i] > df['high'].iloc[i-1] and df['high'].iloc[i] > df['high'].iloc[i+1]:
                highs.append({'price': df['high'].iloc[i], 'idx': i, 'time': df.index[i]})
            
            # Swing low: bar with lower low on both sides
            if df['low'].iloc[i] < df['low'].iloc[i-1] and df['low'].iloc[i] < df['low'].iloc[i+1]:
                lows.append({'price': df['low'].iloc[i], 'idx': i, 'time': df.index[i]})
        
        if len(highs) < 2 or len(lows) < 2:
            return None
        
        current_price = df['close'].iloc[-1]
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        
        # Get last two swings
        last_high = highs[-1]['price']
        last_low = lows[-1]['price']
        prev_high = highs[-2]['price'] if len(highs) >= 2 else 0
        prev_low = lows[-2]['price'] if len(lows) >= 2 else float('inf')
        
        bos = None
        
        # Bullish BOS: Price breaks above previous swing high
        if current_high > last_high and last_high > prev_high:
            bos = {
                "type": "bullish",
                "level": last_high,
                "price": current_high,
                "strength": (current_high - last_high) / pv,
                "time": df.index[-1],
            }
        
        # Bearish BOS: Price breaks below previous swing low
        elif current_low < last_low and last_low < prev_low:
            bos = {
                "type": "bearish",
                "level": last_low,
                "price": current_low,
                "strength": (last_low - current_low) / pv,
                "time": df.index[-1],
            }
        
        return bos

    def detect_change_of_character(self, df, pip_value=None):
        """
        Detect Change of Character (ChoCH) - shift in market behavior.
        Indicates potential trend reversal or significant volatility shift.
        """
        pv = pip_value or self.config.PIP_VALUE
        
        if len(df) < 20:
            return None
        
        recent = df.tail(10)
        historical = df.tail(50)
        
        # Calculate ATR for volatility comparison
        recent_atr = talib.ATR(recent['high'], recent['low'], recent['close'], timeperiod=9)
        historical_atr = talib.ATR(historical['high'], historical['low'], historical['close'], timeperiod=14)
        
        if len(recent_atr) == 0 or len(historical_atr) == 0:
            return None
        
        recent_vol = recent_atr.iloc[-1]
        historical_vol = historical_atr.iloc[-1]
        
        if historical_vol == 0:
            return None
        
        volatility_ratio = recent_vol / historical_vol
        
        # Detect structure change in price action
        recent_highs = recent['high'].values
        recent_lows = recent['low'].values
        historical_highs = historical['high'].values
        historical_lows = historical['low'].values
        
        recent_range = recent_highs.max() - recent_lows.min()
        historical_range = historical_highs.max() - historical_lows.min()
        
        choch = None
        
        # Significant volatility increase + structure change
        if volatility_ratio > 1.4:
            # Check if price is extending higher or lower
            if recent['close'].iloc[-1] > recent['close'].iloc[-5]:
                if recent_range > historical_range * 0.7:
                    choch = {
                        "type": "bullish",
                        "reason": "increased_volatility_bullish",
                        "volatility_ratio": volatility_ratio,
                        "time": df.index[-1],
                    }
            else:
                if recent_range > historical_range * 0.7:
                    choch = {
                        "type": "bearish",
                        "reason": "increased_volatility_bearish",
                        "volatility_ratio": volatility_ratio,
                        "time": df.index[-1],
                    }
        
        return choch

    def identify_liquidity_pools(self, df, direction='buy', pip_value=None):
        """
        Identify liquidity pools where retail trader stops cluster.
        Buy-side liquidity: Above recent highs (where short stops sit)
        Sell-side liquidity: Below recent lows (where long stops sit)
        """
        pv = pip_value or self.config.PIP_VALUE
        
        if len(df) < 20:
            return []
        
        recent = df.tail(50)
        liquidity_zones = []
        
        if direction == 'buy':
            # Find recent swing highs (sell-side liquidity above)
            highs = []
            for i in range(2, len(recent) - 2):
                if recent['high'].iloc[i] > recent['high'].iloc[i-1] and recent['high'].iloc[i] > recent['high'].iloc[i+1]:
                    highs.append({
                        'level': recent['high'].iloc[i],
                        'volume': recent['tick_volume'].iloc[i],
                        'idx': i
                    })
            
            # Get top 3 liquidity zones
            if highs:
                highs.sort(key=lambda x: x['volume'], reverse=True)
                for hi in highs[:3]:
                    liquidity_zones.append({
                        "type": "sell_side_liquidity",
                        "level": hi['level'],
                        "distance": (hi['level'] - recent['close'].iloc[-1]) / pv,
                        "strength": hi['volume']
                    })
        
        else:  # direction == 'sell'
            # Find recent swing lows (buy-side liquidity below)
            lows = []
            for i in range(2, len(recent) - 2):
                if recent['low'].iloc[i] < recent['low'].iloc[i-1] and recent['low'].iloc[i] < recent['low'].iloc[i+1]:
                    lows.append({
                        'level': recent['low'].iloc[i],
                        'volume': recent['tick_volume'].iloc[i],
                        'idx': i
                    })
            
            # Get top 3 liquidity zones
            if lows:
                lows.sort(key=lambda x: x['volume'], reverse=True)
                for lo in lows[:3]:
                    liquidity_zones.append({
                        "type": "buy_side_liquidity",
                        "level": lo['level'],
                        "distance": (recent['close'].iloc[-1] - lo['level']) / pv,
                        "strength": lo['volume']
                    })
        
        return liquidity_zones

    def identify_breaker_blocks(self, df, pip_value=None):
        """
        Identify Breaker Blocks - failed support/resistance zones.
        These are levels where price breaks through but then reverses,
        indicating strong rejection by smart money.
        """
        pv = pip_value or self.config.PIP_VALUE
        breaker_blocks = []
        
        if len(df) < 15:
            return []
        
        recent = df.tail(30)
        
        for i in range(5, len(recent) - 2):
            # Bullish breaker: Major support broken but closes above it
            support_level = recent['low'].iloc[i-5:i].min()
            if recent['low'].iloc[i] < support_level and recent['close'].iloc[i] > support_level:
                breaker_blocks.append({
                    "type": "bullish_breaker",
                    "level": support_level,
                    "current_price": recent['close'].iloc[-1],
                    "distance": (recent['close'].iloc[-1] - support_level) / pv,
                    "strength": (recent['close'].iloc[i] - recent['low'].iloc[i]) / pv
                })
            
            # Bearish breaker: Major resistance broken but closes below it
            resistance_level = recent['high'].iloc[i-5:i].max()
            if recent['high'].iloc[i] > resistance_level and recent['close'].iloc[i] < resistance_level:
                breaker_blocks.append({
                    "type": "bearish_breaker",
                    "level": resistance_level,
                    "current_price": recent['close'].iloc[-1],
                    "distance": (resistance_level - recent['close'].iloc[-1]) / pv,
                    "strength": (recent['high'].iloc[i] - recent['close'].iloc[i]) / pv
                })
        
        return breaker_blocks[-4:]

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
