# main.py
import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime
import logging
import sys

from config import Config
from strategies.smc_strategies import SMCStrategies
from risk.risk_manager import RiskManager
from trading.trade_manager import TradeManager

class EURUSD_SMC_Bot:
    """Multi-Symbol SMC Trading Bot - Direct MT5 Connection"""
    
    def __init__(self):
        self.config = Config
        self.strategies = SMCStrategies()
        self.risk = RiskManager()
        
        # Per-symbol state: {symbol: {daily_trades, last_signal_time, swing_trades, last_swing_signal_time}}
        self.symbol_state = {}
        for sym, sym_cfg in self.config.SYMBOLS.items():
            self.symbol_state[sym] = {
                "daily_trades": 0,
                "last_signal_time": None,
                "swing_trades": 0,
                "last_swing_signal_time": None,
                "pip_value": sym_cfg["pip_value"],
            }

        # Global state
        self.daily_trades = 0
        self.daily_pips = 0
        self.positions = []
        self.last_signal_time = None
        self._running = False
        self.wins = 0
        self.losses = 0
        self.swing_trades = 0
        self.last_swing_signal_time = None
        
        # Setup logging
        self.setup_logging()
        self.trade_manager = TradeManager(self.logger)
        
    def setup_logging(self):
        """Configure logging"""
        self.logger = logging.getLogger('SMC_Bot')
        self.logger.setLevel(logging.INFO)
        
        # File handler
        fh = logging.FileHandler(f'logs/bot_{datetime.now().strftime("%Y%m%d")}.log')
        fh.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Format
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        
    def connect(self):
        """Connect to JustMarkets MT5"""
        self.logger.info("=" * 60)
        self.logger.info("CONNECTING TO JUSTMARKETS MT5...")
        
        # Initialize MT5
        if not mt5.initialize():
            self.logger.error(f"MT5 Init Failed: {mt5.last_error()}")
            return False
            
        # Login
        authorized = mt5.login(
            login=self.config.MT5_LOGIN,
            password=self.config.MT5_PASSWORD,
            server=self.config.MT5_SERVER
        )
        
        if authorized:
            account_info = mt5.account_info()
            self.logger.info("CONNECTION SUCCESSFUL - LIVE ACCOUNT")
            self.logger.info(f"   Account: {account_info.login}")
            self.logger.info(f"   Balance: R{account_info.balance:.2f}")
            self.logger.info(f"   Equity: R{account_info.equity:.2f}")
            self.logger.info(f"   Server: {account_info.server}")
            self.logger.info(f"   Leverage: 1:{account_info.leverage}")
            self.logger.info("=" * 60)
            return True
        else:
            self.logger.error(f"Login Failed: {mt5.last_error()}")
            return False
    
    def get_market_data(self, symbol):
        """Fetch M15+H1 data for a symbol"""
        pip_value = self.config.SYMBOLS[symbol]["pip_value"]

        rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 200)
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
        tick = mt5.symbol_info_tick(symbol)
        
        if rates_m15 is None or rates_h1 is None or tick is None:
            return None
            
        df_m15 = pd.DataFrame(rates_m15)
        df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
        df_m15.set_index('time', inplace=True)
        
        df_h1 = pd.DataFrame(rates_h1)
        df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
        df_h1.set_index('time', inplace=True)
        
        return {
            'symbol': symbol,
            'pip_value': pip_value,
            'm15': df_m15,
            'h1': df_h1,
            'bid': tick.bid,
            'ask': tick.ask,
            'spread': (tick.ask - tick.bid) / pip_value
        }

    def get_swing_data(self, symbol):
        """Fetch H1+H4+D1 data for swing trades."""
        pip_value = self.config.SYMBOLS[symbol]["pip_value"]

        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 300)
        rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 200)
        rates_d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 100)
        tick = mt5.symbol_info_tick(symbol)

        if rates_h1 is None or rates_h4 is None or rates_d1 is None or tick is None:
            return None

        df_h1 = pd.DataFrame(rates_h1)
        df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
        df_h1.set_index('time', inplace=True)

        df_h4 = pd.DataFrame(rates_h4)
        df_h4['time'] = pd.to_datetime(df_h4['time'], unit='s')
        df_h4.set_index('time', inplace=True)

        df_d1 = pd.DataFrame(rates_d1)
        df_d1['time'] = pd.to_datetime(df_d1['time'], unit='s')
        df_d1.set_index('time', inplace=True)

        return {
            'symbol': symbol,
            'pip_value': pip_value,
            'h1': df_h1,
            'h4': df_h4,
            'd1': df_d1,
            'bid': tick.bid,
            'ask': tick.ask,
            'spread': (tick.ask - tick.bid) / pip_value
        }
    
    def generate_signal(self, data):
        """Generate trading signal using SMC"""
        df_m15 = data['m15']
        df_h1 = data['h1']
        current_ask = data['ask']
        current_bid = data['bid']
        symbol = data['symbol']
        pv = data['pip_value']
        
        # Get SMC concepts (pass pip_value for correct pip calculation)
        order_blocks = self.strategies.identify_order_blocks(df_m15, pv)
        fvgs = self.strategies.identify_fair_value_gaps(df_m15, pv)
        trend_h1 = self.strategies.analyze_trend(df_h1)
        trend_m15 = self.strategies.analyze_trend(df_m15)
        
        signals = []
        
        # BUY SIGNAL - require strong bullish H1 trend and at least neutral M15
        if trend_h1['trend'] == 'bullish' and trend_h1['score'] >= 3 and trend_m15['trend'] in ['bullish', 'ranging']:
            for ob in order_blocks:
                if ob['type'] == 'bullish':
                    dist_to_ob = (current_ask - ob['price']) / pv
                    if 0 <= dist_to_ob <= self.config.MAX_OB_DISTANCE_PIPS and ob['strength'] >= self.config.MIN_OB_STRENGTH:
                        for fvg in fvgs:
                            if fvg['type'] == 'bullish':
                                if fvg['bottom'] <= current_ask <= fvg['top']:
                                    stop_loss = ob['stop']
                                    stop_pips = (current_ask - stop_loss) / pv
                                    
                                    if self.config.MIN_STOP_PIPS <= stop_pips <= self.config.MAX_STOP_PIPS:
                                        volume = self.risk.calculate_position_size(stop_pips, pv)
                                        tp_levels = self.risk.calculate_tp_levels(
                                            current_ask, stop_loss, 'buy', pv
                                        )
                                        
                                        signals.append({
                                            'direction': 'buy',
                                            'price': current_ask,
                                            'sl': stop_loss,
                                            **tp_levels,
                                            'volume': volume,
                                            'stop_pips': stop_pips,
                                            'ob_price': ob['price'],
                                            'fvg_mid': fvg['mid'],
                                            'confidence': ob['strength'] * fvg['size'],
                                            'symbol': symbol,
                                        })
        
        # SELL SIGNAL - require strong bearish H1 trend and at least neutral M15
        if trend_h1['trend'] == 'bearish' and trend_h1['score'] >= 3 and trend_m15['trend'] in ['bearish', 'ranging']:
            for ob in order_blocks:
                if ob['type'] == 'bearish':
                    dist_to_ob = (ob['price'] - current_bid) / pv
                    if 0 <= dist_to_ob <= self.config.MAX_OB_DISTANCE_PIPS and ob['strength'] >= self.config.MIN_OB_STRENGTH:
                        for fvg in fvgs:
                            if fvg['type'] == 'bearish':
                                if fvg['bottom'] <= current_bid <= fvg['top']:
                                    stop_loss = ob['stop']
                                    stop_pips = (stop_loss - current_bid) / pv
                                    
                                    if self.config.MIN_STOP_PIPS <= stop_pips <= self.config.MAX_STOP_PIPS:
                                        volume = self.risk.calculate_position_size(stop_pips, pv)
                                        tp_levels = self.risk.calculate_tp_levels(
                                            current_bid, stop_loss, 'sell', pv
                                        )
                                        
                                        signals.append({
                                            'direction': 'sell',
                                            'price': current_bid,
                                            'sl': stop_loss,
                                            **tp_levels,
                                            'volume': volume,
                                            'stop_pips': stop_pips,
                                            'ob_price': ob['price'],
                                            'fvg_mid': fvg['mid'],
                                            'confidence': ob['strength'] * fvg['size'],
                                            'symbol': symbol,
                                        })
        
        # Return best signal
        if signals:
            signals.sort(key=lambda x: x['confidence'], reverse=True)
            best = signals[0]
            self.logger.info(
                f"[{symbol}] Signal generated: {best['direction'].upper()} at {best['price']:.5f} "
                f"SL {best['sl']:.5f} ({best['stop_pips']:.1f} pips) "
                f"trend_h1={trend_h1['trend']} ob={best['ob_price']:.5f} fvg_mid={best['fvg_mid']:.5f}"
            )
            return best

        self.logger.info(
            f"[{symbol}] No valid signal (trend_h1={trend_h1['trend']}, "
            f"OBs={len(order_blocks)}, FVGs={len(fvgs)})"
        )
        return None

    def generate_swing_signal(self, data):
        """Generate swing trading signal using H1 entry / H4+D1 bias."""
        df_h1 = data['h1']
        df_h4 = data['h4']
        df_d1 = data['d1']
        current_ask = data['ask']
        current_bid = data['bid']
        symbol = data['symbol']
        pv = data['pip_value']

        # Swing uses H1 OBs/FVGs with wider filters
        order_blocks = self.strategies.identify_order_blocks_swing(df_h1, pv)
        fvgs = self.strategies.identify_fair_value_gaps_swing(df_h1, pv)
        trend_d1 = self.strategies.analyze_trend(df_d1)
        trend_h4 = self.strategies.analyze_trend(df_h4)

        signals = []

        cfg = self.config

        # SWING BUY - D1 bullish, H4 supportive
        if trend_d1['trend'] == 'bullish' and trend_d1['score'] >= 3 and trend_h4['trend'] in ['bullish', 'ranging']:
            for ob in order_blocks:
                if ob['type'] == 'bullish':
                    dist = (current_ask - ob['price']) / pv
                    if 0 <= dist <= cfg.SWING_MAX_OB_DISTANCE_PIPS and ob['strength'] >= cfg.SWING_MIN_OB_STRENGTH:
                        for fvg in fvgs:
                            if fvg['type'] == 'bullish' and fvg['bottom'] <= current_ask <= fvg['top']:
                                stop_loss = ob['stop']
                                stop_pips = (current_ask - stop_loss) / pv
                                if cfg.SWING_MIN_STOP_PIPS <= stop_pips <= cfg.SWING_MAX_STOP_PIPS:
                                    volume = round(max(cfg.SWING_FIXED_LOT_SIZE, 0.01), 2)
                                    risk = current_ask - stop_loss
                                    signals.append({
                                        'direction': 'buy',
                                        'price': current_ask,
                                        'sl': stop_loss,
                                        'tp1': current_ask + risk * cfg.SWING_TP1_MULTIPLIER,
                                        'tp2': current_ask + risk * cfg.SWING_TP2_MULTIPLIER,
                                        'tp3': current_ask + risk * cfg.SWING_TP3_MULTIPLIER,
                                        'volume': volume,
                                        'stop_pips': stop_pips,
                                        'ob_price': ob['price'],
                                        'fvg_mid': fvg['mid'],
                                        'confidence': ob['strength'] * fvg['size'],
                                        'trade_type': 'SWING',
                                        'symbol': symbol,
                                    })

        # SWING SELL - D1 bearish, H4 supportive
        if trend_d1['trend'] == 'bearish' and trend_d1['score'] >= 3 and trend_h4['trend'] in ['bearish', 'ranging']:
            for ob in order_blocks:
                if ob['type'] == 'bearish':
                    dist = (ob['price'] - current_bid) / pv
                    if 0 <= dist <= cfg.SWING_MAX_OB_DISTANCE_PIPS and ob['strength'] >= cfg.SWING_MIN_OB_STRENGTH:
                        for fvg in fvgs:
                            if fvg['type'] == 'bearish' and fvg['bottom'] <= current_bid <= fvg['top']:
                                stop_loss = ob['stop']
                                stop_pips = (stop_loss - current_bid) / pv
                                if cfg.SWING_MIN_STOP_PIPS <= stop_pips <= cfg.SWING_MAX_STOP_PIPS:
                                    volume = round(max(cfg.SWING_FIXED_LOT_SIZE, 0.01), 2)
                                    risk = stop_loss - current_bid
                                    signals.append({
                                        'direction': 'sell',
                                        'price': current_bid,
                                        'sl': stop_loss,
                                        'tp1': current_bid - risk * cfg.SWING_TP1_MULTIPLIER,
                                        'tp2': current_bid - risk * cfg.SWING_TP2_MULTIPLIER,
                                        'tp3': current_bid - risk * cfg.SWING_TP3_MULTIPLIER,
                                        'volume': volume,
                                        'stop_pips': stop_pips,
                                        'ob_price': ob['price'],
                                        'fvg_mid': fvg['mid'],
                                        'confidence': ob['strength'] * fvg['size'],
                                        'trade_type': 'SWING',
                                        'symbol': symbol,
                                    })

        if signals:
            signals.sort(key=lambda x: x['confidence'], reverse=True)
            best = signals[0]
            self.logger.info(
                f"[{symbol}] SWING signal: {best['direction'].upper()} at {best['price']:.5f} "
                f"SL {best['sl']:.5f} ({best['stop_pips']:.1f} pips) "
                f"trend_d1={trend_d1['trend']} trend_h4={trend_h4['trend']}"
            )
            return best

        return None
    
    def execute_signal(self, signal):
        """Execute the trading signal"""
        sym = signal.get('symbol', self.config.SYMBOL)
        sym_state = self.symbol_state.get(sym, {})
        trade_type = signal.get('trade_type', 'SCALP')

        # Per-symbol daily limit check
        if trade_type == 'SWING':
            if sym_state.get('swing_trades', 0) >= self.config.SWING_MAX_DAILY_TRADES:
                self.logger.warning(f"[{sym}] Swing daily limit reached")
                return False
        else:
            if sym_state.get('daily_trades', 0) >= self.config.MAX_DAILY_TRADES:
                self.logger.warning(f"[{sym}] Daily trade limit reached")
                return False
            
        result = self.trade_manager.execute_order(signal)
        
        if result['success']:
            # Update per-symbol state
            if trade_type == 'SWING':
                sym_state['swing_trades'] = sym_state.get('swing_trades', 0) + 1
                sym_state['last_swing_signal_time'] = datetime.now()
                self.swing_trades += 1
            else:
                sym_state['daily_trades'] = sym_state.get('daily_trades', 0) + 1
                sym_state['last_signal_time'] = datetime.now()
                self.daily_trades += 1

            self.last_signal_time = datetime.now()

            position = {
                'ticket': result['ticket'],
                **signal,
                'open_time': datetime.now(),
                'status': 'open',
                'be_moved': False,
                'tp1_hit': False,
                'tp2_hit': False,
                'trade_type': trade_type,
                'symbol': sym,
            }
            self.positions.append(position)
            
            # Log trade
            price_fmt = '.3f' if sym_state.get('pip_value', 0.0001) == 0.01 else '.5f'
            self.logger.info("\n" + "=" * 60)
            self.logger.info(f"TRADE EXECUTED - LIVE ACCOUNT [{trade_type}] {sym}")
            self.logger.info(f"   Ticket: {result['ticket']}")
            self.logger.info(f"   Symbol: {sym}")
            self.logger.info(f"   Direction: {signal['direction'].upper()}")
            self.logger.info(f"   Entry: {signal['price']:{price_fmt}}")
            self.logger.info(f"   SL: {signal['sl']:{price_fmt}} ({signal['stop_pips']:.1f} pips)")
            self.logger.info(f"   TP1: {signal['tp1']:{price_fmt}}")
            self.logger.info(f"   TP2: {signal['tp2']:{price_fmt}}")
            self.logger.info(f"   TP3: {signal['tp3']:{price_fmt}}")
            self.logger.info(f"   Volume: {signal['volume']} lots")
            self.logger.info(f"   OB: {signal['ob_price']:{price_fmt}}")
            self.logger.info(f"   FVG: {signal['fvg_mid']:{price_fmt}}")
            self.logger.info("=" * 60)
            
            return True
        else:
            self.logger.error(f"[{sym}] Order failed: {result['error']}")
            return False
    
    def manage_positions(self):
        """Manage open positions"""
        for position in self.positions[:]:
            if position['status'] != 'open':
                continue
            
            sym = position.get('symbol', self.config.SYMBOL)
            pv = self.config.SYMBOLS.get(sym, {}).get('pip_value', self.config.PIP_VALUE)
                
            # Get current position data
            pos = mt5.positions_get(ticket=position['ticket'])
            if not pos or len(pos) == 0:
                # Position closed by SL/TP -- check history for result
                position['status'] = 'closed'
                try:
                    deals = mt5.history_deals_get(position=position['ticket'])
                    if deals and len(deals) >= 2:
                        close_deal = deals[-1]
                        profit = close_deal.profit + close_deal.swap + close_deal.commission
                    else:
                        profit = 0
                except Exception:
                    profit = 0
                if profit >= 0:
                    self.wins += 1
                    self.logger.info(f"[{sym}] Position {position['ticket']}: CLOSED WIN (R{profit:.2f})")
                else:
                    self.losses += 1
                    self.logger.info(f"[{sym}] Position {position['ticket']}: CLOSED LOSS (R{profit:.2f})")
                self.positions.remove(position)
                continue
                
            pos = pos[0]
            current_price = pos.price_current
            
            # Calculate profit in pips
            if position['direction'] == 'buy':
                pips = (current_price - position['price']) / pv
            else:
                pips = (position['price'] - current_price) / pv
            
            # Move to breakeven
            be_pips = self.config.SWING_BREAKEVEN_PIPS if position.get('trade_type') == 'SWING' else self.config.BREAKEVEN_PIPS
            if pips >= be_pips and not position['be_moved']:
                new_sl = position['price'] + (1 * pv) if position['direction'] == 'buy' else position['price'] - (1 * pv)
                
                if self.trade_manager.modify_position(position['ticket'], sl=new_sl, symbol=sym):
                    position['be_moved'] = True
                    self.logger.info(f"[{sym}] Position {position['ticket']}: Breakeven @ +{pips:.1f} pips")
            
            # Check TP1
            if position['direction'] == 'buy' and current_price >= position['tp1'] and not position['tp1_hit']:
                position['tp1_hit'] = True
                self.logger.info(f"[{sym}] Position {position['ticket']}: TP1 Hit (+{position['stop_pips'] * 1.5:.1f} pips)")
                
            elif position['direction'] == 'sell' and current_price <= position['tp1'] and not position['tp1_hit']:
                position['tp1_hit'] = True
                self.logger.info(f"[{sym}] Position {position['ticket']}: TP1 Hit (+{position['stop_pips'] * 1.5:.1f} pips)")
            
            # Check TP2
            if position['direction'] == 'buy' and current_price >= position['tp2'] and not position['tp2_hit']:
                position['tp2_hit'] = True
                self.logger.info(f"[{sym}] Position {position['ticket']}: TP2 Hit (+{position['stop_pips'] * 2.0:.1f} pips)")
                
            elif position['direction'] == 'sell' and current_price <= position['tp2'] and not position['tp2_hit']:
                position['tp2_hit'] = True
                self.logger.info(f"[{sym}] Position {position['ticket']}: TP2 Hit (+{position['stop_pips'] * 2.0:.1f} pips)")
    
    def print_status(self, symbol_data_list):
        """Print real-time status for all symbols"""
        parts = [f"[{datetime.now().strftime('%H:%M:%S')}]"]
        for sd in symbol_data_list:
            sym = sd['symbol']
            parts.append(f"{sym}: {sd['bid']:.5f}/{sd['ask']:.5f} sp={sd['spread']:.1f}")
        total_scalp = sum(s.get('daily_trades', 0) for s in self.symbol_state.values())
        total_swing = sum(s.get('swing_trades', 0) for s in self.symbol_state.values())
        open_count = len([p for p in self.positions if p['status'] == 'open'])
        parts.append(f"T:{total_scalp} S:{total_swing} O:{open_count} Bal:R{mt5.account_info().balance:.2f}")
        status = "\r" + " | ".join(parts)
        print(status, end="")
    
    def run(self):
        """Main bot execution loop"""
        self._running = True

        # Connect to MT5
        if not self.connect():
            self.logger.error("Failed to connect. Exiting...")
            self._running = False
            return
        
        symbols_list = list(self.config.SYMBOLS.keys())
        self.logger.info(f"\nSTARTING SMC BOT - LIVE TRADING ({', '.join(symbols_list)})")
        self.logger.info("=" * 60)
        
        try:
            while self._running:
                now = datetime.now()
                hour = now.hour

                # Reset daily counters at midnight
                if hour == 0 and now.minute == 0:
                    self.daily_trades = 0
                    self.daily_pips = 0
                    self.wins = 0
                    self.losses = 0
                    self.swing_trades = 0
                    for sym in self.symbol_state:
                        self.symbol_state[sym]['daily_trades'] = 0
                        self.symbol_state[sym]['swing_trades'] = 0
                        self.symbol_state[sym]['last_signal_time'] = None
                        self.symbol_state[sym]['last_swing_signal_time'] = None
                    self.logger.info("\nNew trading day started")
                
                all_data = []

                # ── Iterate over each symbol ──
                for symbol in symbols_list:
                    sym_cfg = self.config.SYMBOLS[symbol]
                    sym_state = self.symbol_state[symbol]

                    # Get market data for this symbol
                    data = self.get_market_data(symbol)
                    if data is None:
                        continue
                    all_data.append(data)

                    # ── Scalp signals (session + spread filter) ──
                    if not (self.config.SESSION_START_HOUR <= hour < self.config.SESSION_END_HOUR):
                        pass  # Outside trading session
                    elif data['spread'] > sym_cfg.get('max_spread', self.config.MAX_SPREAD_PIPS):
                        self.logger.info(f"[{symbol}] Spread too high ({data['spread']:.1f} pips)")
                    elif sym_state.get('daily_trades', 0) < self.config.MAX_DAILY_TRADES:
                        last_sig = sym_state.get('last_signal_time')
                        if last_sig is None or (now - last_sig).seconds > 300:
                            signal = self.generate_signal(data)
                            if signal:
                                self.execute_signal(signal)
                        else:
                            remaining = 300 - (now - last_sig).seconds
                            self.logger.info(f"[{symbol}] Cooldown: {remaining}s")

                    # ── Swing signals (no session filter) ──
                    swing_spread_ok = data['spread'] <= sym_cfg.get('swing_max_spread', self.config.SWING_MAX_SPREAD_PIPS)
                    if self.config.SWING_ENABLED and swing_spread_ok:
                        if sym_state.get('swing_trades', 0) < self.config.SWING_MAX_DAILY_TRADES:
                            last_swing = sym_state.get('last_swing_signal_time')
                            if last_swing is None or (now - last_swing).seconds > self.config.SWING_COOLDOWN_SECONDS:
                                swing_data = self.get_swing_data(symbol)
                                if swing_data:
                                    swing_signal = self.generate_swing_signal(swing_data)
                                    if swing_signal:
                                        self.execute_signal(swing_signal)
                            else:
                                remaining = self.config.SWING_COOLDOWN_SECONDS - (now - last_swing).seconds
                                self.logger.info(f"[{symbol}] Swing cooldown: {remaining}s")
                
                # Manage open positions (all symbols)
                self.manage_positions()
                
                # Print status
                if all_data:
                    self.print_status(all_data)
                
                # Wait
                time.sleep(2)
                
        except KeyboardInterrupt:
            self.logger.info("\nBot stopped by user")
        except Exception as e:
            self.logger.error(f"Bot error: {str(e)}")
        finally:
            mt5.shutdown()
            self.logger.info("MT5 connection closed")

    def stop(self):
        """Signal the bot loop to stop gracefully."""
        self._running = False

# ============================================
# ENTRY POINT
# ============================================
if __name__ == "__main__":
    import os
    os.makedirs('logs', exist_ok=True)
    
    bot = EURUSD_SMC_Bot()
    bot.run()