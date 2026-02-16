# trade_manager.py
import MetaTrader5 as mt5
from datetime import datetime
import time
from config import Config


class TradeManager:
    def __init__(self, logger):
        self.logger = logger
        self.config = Config

    def _get_filling_mode(self, symbol):
        """Auto-detect the correct filling mode for a symbol."""
        info = mt5.symbol_info(symbol)
        if info is None:
            return mt5.ORDER_FILLING_IOC
        filling = info.filling_mode
        # filling_mode bitmask: bit0 (val 1) = FOK, bit1 (val 2) = IOC
        if filling & 1:
            return mt5.ORDER_FILLING_FOK
        elif filling & 2:
            return mt5.ORDER_FILLING_IOC
        else:
            return mt5.ORDER_FILLING_RETURN

    def execute_order(self, signal):
        """Execute market order with detailed diagnostics"""
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
            "type_filling": self._get_filling_mode(symbol),
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
            error_msg = result.comment if result else "Unknown error"
            error_code = result.retcode if result else "N/A"
            
            # Enhanced error messages
            detailed_error = error_msg
            if "AutoTrading" in error_msg:
                detailed_error = f"AutoTrading disabled in MT5. Enable: Tools > Options > Expert Advisors"
            elif "not enough money" in error_msg.lower():
                detailed_error = f"Insufficient funds. Reduce lot size (Volume: {signal['volume']} lots)"
            elif "invalid price" in error_msg.lower():
                detailed_error = f"Invalid price. Market may have moved (Current: {price})"
            
            return {
                "success": False,
                "error": detailed_error,
                "error_code": error_code,
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
            "type_filling": self._get_filling_mode(sym),
        }

        result = mt5.order_send(request)
        return result and result.retcode == mt5.TRADE_RETCODE_DONE
