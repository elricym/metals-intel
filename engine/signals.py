#!/usr/bin/env python3
"""Signal library: COT extremes, volatility spikes, ratio anomalies."""
import sqlite3
import os
import json
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'metals.db')

def get_db():
    return sqlite3.connect(DB_PATH)

def cot_percentile(ticker='Gold', lookback_weeks=156):
    """COT mm_net percentile vs trailing N weeks (default 3 years)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT report_date, mm_net FROM cot_weekly WHERE ticker=? ORDER BY report_date DESC LIMIT ?",
        (ticker, lookback_weeks)
    ).fetchall()
    conn.close()
    if len(rows) < 10:
        return None
    
    current = rows[0][1]
    values = [r[1] for r in rows]
    rank = sum(1 for v in values if v <= current)
    pct = round(rank / len(values) * 100, 1)
    return {
        'signal': 'cot_percentile',
        'ticker': ticker,
        'date': rows[0][0],
        'mm_net': current,
        'percentile': pct,
        'lookback': len(values),
        'extreme': pct > 90 or pct < 10,
        'direction': '多头极端' if pct > 90 else ('空头极端' if pct < 10 else '正常')
    }

def gold_silver_ratio():
    """Gold/Silver ratio - extremes at >85 or <65."""
    conn = get_db()
    gold = conn.execute(
        "SELECT date, close FROM daily_prices WHERE ticker='GC=F' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    silver = conn.execute(
        "SELECT date, close FROM daily_prices WHERE ticker='SI=F' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not gold or not silver or not gold[1] or not silver[1]:
        return None
    
    ratio = round(gold[1] / silver[1], 2)
    return {
        'signal': 'gold_silver_ratio',
        'date': gold[0],
        'ratio': ratio,
        'extreme': ratio > 85 or ratio < 65,
        'direction': '白银相对便宜' if ratio > 85 else ('白银相对贵' if ratio < 65 else '正常')
    }

def copper_gold_ratio():
    """Copper/Gold ratio - recession indicator."""
    conn = get_db()
    gold = conn.execute(
        "SELECT date, close FROM daily_prices WHERE ticker='GC=F' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    copper = conn.execute(
        "SELECT date, close FROM daily_prices WHERE ticker='HG=F' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not gold or not copper or not gold[1] or not copper[1]:
        return None
    
    # Copper is per pound, gold per oz - ratio * 1000 for readability
    ratio = round(copper[1] / gold[1] * 1000, 4)
    return {
        'signal': 'copper_gold_ratio',
        'date': gold[0],
        'ratio': ratio,
        'note': '低比值暗示经济衰退风险'
    }

def vix_spike():
    """VIX daily spike >20%."""
    conn = get_db()
    rows = conn.execute(
        "SELECT date, vix FROM macro_daily WHERE vix IS NOT NULL ORDER BY date DESC LIMIT 5"
    ).fetchall()
    conn.close()
    if len(rows) < 2:
        return None
    
    current = rows[0][1]
    prev = rows[1][1]
    if prev == 0:
        return None
    chg = round((current - prev) / prev * 100, 1)
    return {
        'signal': 'vix_spike',
        'date': rows[0][0],
        'vix': current,
        'change_pct': chg,
        'spike': abs(chg) > 20,
        'direction': 'VIX飙升' if chg > 20 else ('VIX暴跌' if chg < -20 else '正常')
    }

def dxy_breakout():
    """DXY 52-week high/low breakout."""
    conn = get_db()
    rows = conn.execute(
        "SELECT date, dxy FROM macro_daily WHERE dxy IS NOT NULL ORDER BY date DESC LIMIT 252"
    ).fetchall()
    conn.close()
    if len(rows) < 20:
        return None
    
    current = rows[0][1]
    values = [r[1] for r in rows if r[1] is not None]
    high52 = max(values)
    low52 = min(values)
    
    return {
        'signal': 'dxy_breakout',
        'date': rows[0][0],
        'dxy': current,
        'high_52w': round(high52, 2),
        'low_52w': round(low52, 2),
        'at_high': current >= high52 * 0.99,
        'at_low': current <= low52 * 1.01,
        'direction': '美元52周新高' if current >= high52 * 0.99 else ('美元52周新低' if current <= low52 * 1.01 else '正常')
    }

def all_signals():
    """Run all signals and return active ones."""
    signals = []
    
    for metal in ['Gold', 'Silver', 'Copper']:
        s = cot_percentile(metal)
        if s:
            signals.append(s)
    
    for fn in [gold_silver_ratio, copper_gold_ratio, vix_spike, dxy_breakout]:
        s = fn()
        if s:
            signals.append(s)
    
    return signals

if __name__ == '__main__':
    for s in all_signals():
        print(json.dumps(s, ensure_ascii=False, indent=2))
