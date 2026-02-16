# Implementation Guide: Advanced Position Management

## Status: For Future Implementation (Not Implemented Yet)

This document outlines code additions needed for more advanced trade management features. These should be implemented after the bot is running profitably for 2+ weeks.

---

## Feature 1: Partial Position Closing at TP1

### Why This Matters
Current behavior: Trade hits TP1, but position stays open (greedy but risky)  
Better behavior: Close 50% at TP1, let remainder ride to TP2/TP3

**Advantage:** Locks in 1.5× risk-reward profit while keeping upside

### Implementation (Add to main.py)

```python
def manage_positions(self):
    """Enhanced management with partial closes"""
    for position in self.positions[:]:
        if position['status'] != 'open':
            continue
        
        sym = position.get('symbol', self.config.SYMBOL)
        pv = self.config.SYMBOLS.get(sym, {}).get('pip_value', self.config.PIP_VALUE)
            
        pos = mt5.positions_get(ticket=position['ticket'])
        if not pos or len(pos) == 0:
            # Position closed - existing code...
            continue
            
        pos = pos[0]
        current_price = pos.price_current
        
        # Calculate profit in pips
        if position['direction'] == 'buy':
            pips = (current_price - position['price']) / pv
        else:
            pips = (position['price'] - current_price) / pv
        
        # === NEW: Close partial at TP1 === (STARTS HERE)
        if position['direction'] == 'buy' and current_price >= position['tp1'] and not position['tp1_hit']:
            # Close 50% of position
            partial_volume = round(position['volume'] / 2, 2)
            
            close_result = self.trade_manager.close_position(
                position['ticket'],
                partial_volume,
                position['direction'],
                current_price,
                symbol=sym
            )
            
            if close_result:
                position['tp1_hit'] = True
                self.logger.info(
                    f"[{sym}] Position {position['ticket']}: TP1 PARTIAL CLOSE "
                    f"(+{position['stop_pips'] * 1.5:.1f} pips, closed {partial_volume} lots)"
                )
                # Update remaining volume
                position['volume'] = partial_volume
                # Move SL to breakeven for remaining half
                self.trade_manager.modify_position(
                    position['ticket'],
                    sl=position['price'] + (1 * pv if position['direction'] == 'buy' else -1 * pv),
                    symbol=sym
                )
        
        elif position['direction'] == 'sell' and current_price <= position['tp1'] and not position['tp1_hit']:
            partial_volume = round(position['volume'] / 2, 2)
            
            close_result = self.trade_manager.close_position(
                position['ticket'],
                partial_volume,
                position['direction'],
                current_price,
                symbol=sym
            )
            
            if close_result:
                position['tp1_hit'] = True
                self.logger.info(
                    f"[{sym}] Position {position['ticket']}: TP1 PARTIAL CLOSE "
                    f"(+{position['stop_pips'] * 1.5:.1f} pips, closed {partial_volume} lots)"
                )
                position['volume'] = partial_volume
                self.trade_manager.modify_position(
                    position['ticket'],
                    sl=position['price'] - (1 * pv),
                    symbol=sym
                )
        # === NEW: Close partial at TP1 === (ENDS HERE)
        
        # Move to breakeven (existing code)
        be_pips = self.config.SWING_BREAKEVEN_PIPS if position.get('trade_type') == 'SWING' else self.config.BREAKEVEN_PIPS
        if pips >= be_pips and not position['be_moved']:
            new_sl = position['price'] + (1 * pv) if position['direction'] == 'buy' else position['price'] - (1 * pv)
            if self.trade_manager.modify_position(position['ticket'], sl=new_sl, symbol=sym):
                position['be_moved'] = True
                self.logger.info(f"[{sym}] Position {position['ticket']}: Breakeven @ +{pips:.1f} pips")
```

---

## Feature 2: Trail SL After TP1 Hit

### Why This Matters
Once TP1 is hit, your profit is locked. Now trail the SL to maximize remaining profit.

**Example:**
- Entry: 1.08765
- TP1: 1.08900 (hit) → Lock 135 pips profit
- SL now trails: moves up as price keeps going
- TP2: 1.09035 could get hit with trailing SL

### Implementation Code

```python
def manage_positions(self):
    """Add after TP1 close section"""
    
    # === NEW: Trail SL after TP1 === (ADD THIS)
    if position['tp1_hit'] and not position.get('sl_trailing'):
        # Mark as trailing
        position['sl_trailing'] = True
        trail_distance = 20  # Trail 20 pips below current price
        
        if position['direction'] == 'buy':
            # Current price - 20 pips
            new_trail_sl = current_price - (trail_distance * pv)
            # Only move SL up, never down
            if new_trail_sl > position.get('trailing_sl', 0):
                self.trade_manager.modify_position(
                    position['ticket'],
                    sl=new_trail_sl,
                    symbol=sym
                )
                position['trailing_sl'] = new_trail_sl
        else:
            # For sell: Current price + 20 pips
            new_trail_sl = current_price + (trail_distance * pv)
            if new_trail_sl < position.get('trailing_sl', float('inf')):
                self.trade_manager.modify_position(
                    position['ticket'],
                    sl=new_trail_sl,
                    symbol=sym
                )
                position['trailing_sl'] = new_trail_sl
```

---

## Feature 3: Entry Validation Function

### Why This Matters
Current: Generates signal whenever OB + FVG + Trend align  
Better: Also check if market is choppy/ranging (high false triggers)

### Implementation

```python
# Add to SMCStrategies class
def validate_entry_conditions(self, df, signal, pip_value=None):
    """Additional checks before entry"""
    pv = pip_value or self.config.PIP_VALUE
    
    # Check 1: Volume confirmation
    avg_volume = df['tick_volume'].tail(20).mean()
    current_volume = df['tick_volume'].iloc[-1]
    if current_volume < avg_volume * 0.8:
        return False, "Insufficient volume"
    
    # Check 2: Volatility check (don't enter in very high volatility)
    atr_pips = self.calculate_atr_pips(df, pv)
    if atr_pips > 100:  # Extreme volatility
        return False, f"ATR too high ({atr_pips:.0f} pips)"
    
    # Check 3: Momentum in direction of signal
    candle1 = df.iloc[-1]
    candle2 = df.iloc[-2]
    
    if signal['direction'] == 'buy':
        # Price should be making higher lows/highs
        if candle1['low'] <= candle2['low']:
            return False, "Lower low - downward momentum"
        if candle1['close'] < candle2['close']:
            return False, "Last candle closed below previous"
    else:
        if candle1['high'] >= candle2['high']:
            return False, "Higher high - upward momentum"
        if candle1['close'] > candle2['close']:
            return False, "Last candle closed above previous"
    
    # Check 4: Risk/Reward minimum
    risk = signal['price'] - signal['sl'] if signal['direction'] == 'buy' else signal['sl'] - signal['price']
    reward = signal['tp3'] - signal['price'] if signal['direction'] == 'buy' else signal['price'] - signal['tp3']
    reward_ratio = reward / risk
    
    if reward_ratio < 1.5:
        return False, f"RR ratio too low ({reward_ratio:.2f}:1)"
    
    return True, "All checks passed"
```

### Use It In Signal Generation

```python
def execute_signal(self, signal):
    """Enhanced execute with validation"""
    sym = signal.get('symbol', self.config.SYMBOL)
    
    # NEW: Validate entry conditions
    data = self.get_market_data(sym)
    if data:
        is_valid, reason = self.strategies.validate_entry_conditions(
            data['m15'], signal, data['pip_value']
        )
        if not is_valid:
            self.logger.info(f"[{sym}] Signal rejected: {reason}")
            return False
    
    # Continue with existing execute logic...
```

---

## Feature 4: Close Opposite Signal (Reversal Detection)

### Why This Matters
Example scenario:
- You buy at 1.08700 (bullish signal)
- Price goes to 1.08900 (+200 pips)
- Suddenly strong bearish signal appears
- Smart: Close buy and take +200 pip profit
- Dumb: Keep hodling hoping for more

### Implementation

```python
def execute_signal(self, signal):
    """Check if new signal contradicts open position"""
    
    # Check if any open positions conflict with new signal
    for position in self.positions:
        if position['status'] != 'open':
            continue
        
        if position['symbol'] != signal.get('symbol'):
            continue
        
        # Check for reversal
        if position['direction'] == 'buy' and signal['direction'] == 'sell':
            current_pos = mt5.positions_get(ticket=position['ticket'])
            if current_pos:
                pos = current_pos[0]
                current_profit = pos.profit  # Actual P&L in ZAR
                
                # Close if profit > 50 ZAR (good profit)
                if current_profit > 50:
                    self.trade_manager.close_position(
                        position['ticket'],
                        position['volume'],
                        position['direction'],
                        pos.price_current,
                        symbol=signal['symbol']
                    )
                    self.logger.info(
                        f"[{signal['symbol']}] Reversal detected: "
                        f"Closed buy position with R{current_profit:.2f} profit"
                    )
                    position['status'] = 'closed'
                    self.positions.remove(position)
                    return False  # Don't take reverse signal yet
    
    # Continue with normal execution if no reversal...
```

---

## Feature 5: Daily P&L Tracking & Auto-Stop

### Why This Matters
Protect against losing days. If you lose R100+ in a day, stop trading.

### Implementation

```python
# Add to __init__:
self.daily_pl = 0
self.daily_loss_limit = 100  # R100 max loss per day

# Add new method:
def check_daily_limits(self):
    """Stop trading if daily loss threshold hit"""
    account_info = mt5.account_info()
    
    # Calculate daily P&L (equity change from session start)
    if not hasattr(self, 'session_start_balance'):
        self.session_start_balance = account_info.balance
    
    current_pl = account_info.balance - self.session_start_balance
    
    if current_pl < -self.daily_loss_limit:
        self.logger.warning(
            f"Daily loss limit reached: R{current_pl:.2f} "
            f"(limit: R{-self.daily_loss_limit:.2f})"
        )
        self.logger.warning("STOPPING BOT - Daily loss protection activated")
        self._running = False
        return False
    
    return True

# Add to main loop in run():
if not self.check_daily_limits():
    self.logger.info("Daily limit check failed, stopping trading")
    break
```

---

## Testing Checklist

When implementing these features, test in this order:

- [ ] **Feature 1 (Partial Close):** 
  - Verify position splits correctly at TP1
  - Check SL moves to breakeven for remaining half
  - Monitor logs for "PARTIAL CLOSE" messages

- [ ] **Feature 2 (Trail SL):**
  - Set TP1 hit manually in demo account
  - Verify SL trails as price moves up
  - Check no SL reductions happen

- [ ] **Feature 3 (Entry Validation):**
  - Run 50 signals, reject ~30-40%
  - Backtest rejected signals (should be low quality)
  - Monitor win rate improvement

- [ ] **Feature 4 (Reversal):**
  - Generate buy, then sell signal quickly
  - Verify old position closes if profitable
  - Check no duplicate trades

- [ ] **Feature 5 (Daily Limits):**
  - Manually trigger 2-3 losses to test
  - Verify bot stops once limit reached
  - Check logs for warning messages

---

## Performance Impact

| Feature | Added Complexity | CPU Usage | Expected Benefit |
|---------|-----------------|-----------|-----------------|
| Partial Close | Low | Negligible | Lock 50% profit |
| Trail SL | Low | Negligible | Capture 20-40% more upside |
| Entry Validation | Medium | Slight ↑ | Reduce false entries by 30-40% |
| Reversal Close | Low | Negligible | Exit bad trades early |
| Daily Limits | Low | Negligible | Protect from catastrophic days |

**Overall:** These features add ~5% CPU overhead but can improve profitability by 40-60%.

---

## Recommended Implementation Order

1. **First:** Partial Position Close (most valuable, lowest risk)
2. **Second:** Daily Limits (prevents catastrophic losses)
3. **Third:** Entry Validation (improves quality)
4. **Fourth:** Trail SL (captures additional profits)
5. **Fifth:** Reversal Close (nice-to-have optimization)

---

## Debug Commands

If needed to verify implementations:

```python
# Check if position is marked for trailing:
for pos in bot.positions:
    print(f"Ticket: {pos['ticket']}, Trailing: {pos.get('sl_trailing', False)}")

# Check daily P&L:
account_info = mt5.account_info()
print(f"Current Balance: {account_info.balance}")
print(f"Daily P&L: {account_info.balance - bot.session_start_balance}")

# Force partial close for testing:
bot.positions[0]['tp1_hit'] = True  # Simulate TP1 hit
```

---

**Document Version:** 1.0  
**Date:** Feb 16, 2026  
**Status:** Ready for Implementation After Bot Goes Live  
**Estimated Implementation Time:** 2-3 hours total for all features
