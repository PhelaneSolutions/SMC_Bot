# trade_manager.py
import MetaTrader5 as mt5
from datetime import datetime
import time
from config import Config


class TradeManager:
    def __init__(self, logger):
        self.logger = logger
        self.config = Config

    def execute_order(self, signal):
        """Execute market order"""
        symbol = signal.get("symbol", self.config.SYMBOL)

        if signal["direction"] == "buy":
            order_type = mt5.ORDER_TYPE_BUY
            price = signal["price"]
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = signal["price"]

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": signal["volume"],
            "type": order_type,
            "price": price,
            "sl": signal["sl"],
            "tp": signal["tp3"],
            "deviation": 10,
            "magic": 123456,
            "comment": f"SMC_{signal['direction'].upper()}_{symbol}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return {
                "success": True,
                "ticket": result.order,
                "price": result.price,
                "volume": result.volume,
            }
        else:
            return {
                "success": False,
                "error": result.comment if result else "Unknown error",
            }

    def modify_position(self, ticket, symbol=None, sl=None, tp=None):
        """Modify stop loss or take profit"""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol or self.config.SYMBOL,
            "position": ticket,
        }
        if sl:
            request["sl"] = sl
        if tp:
            request["tp"] = tp

        result = mt5.order_send(request)
        return result and result.retcode == mt5.TRADE_RETCODE_DONE

    def close_position(self, ticket, volume, direction, price, symbol=None):
        """Close position"""
        sym = symbol or self.config.SYMBOL
        order_type = (
            mt5.ORDER_TYPE_SELL if direction == "buy" else mt5.ORDER_TYPE_BUY
        )

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": volume,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": 10,
            "magic": 123456,
            "comment": "SMC_CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        return result and result.retcode == mt5.TRADE_RETCODE_DONE
