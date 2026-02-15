#!/usr/bin/env python3
"""Historical backtest: event/signal → N-day forward performance."""
import sqlite3
import os
import json
import numpy as np
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'metals.db')

def get_db():
    return sqlite3.connect(DB_PATH)

def get_forward_returns(conn, ticker, date, horizons=[1, 5, 20]):
    """Get forward returns for N business days after date."""
    rows = conn.execute(
        "SELECT date, close FROM daily_prices WHERE ticker=? AND date>=? ORDER BY date LIMIT ?",
        (ticker, date, max(horizons) + 5)
    ).fetchall()
    
    if len(rows) < 2:
        return {}
    
    base_price = rows[0][1]
    if not base_price:
        return {}
    
    returns = {}
    for h in horizons:
        if h < len(rows) and rows[h][1]:
            returns[f'{h}d'] = round((rows[h][1] - base_price) / base_price * 100, 2)
    return returns

def backtest_event(event_type='FOMC', ticker='GC=F', surprise_filter=None, horizons=[1, 5, 20]):
    """Backtest: find all event dates, calculate forward returns."""
    conn = get_db()
    
    query = "SELECT date, actual, forecast, surprise, notes FROM macro_events WHERE event_type=? ORDER BY date"
    rows = conn.execute(query, (event_type,)).fetchall()
    
    results = []
    for date, actual, forecast, surprise, notes in rows:
        if surprise_filter == 'positive' and (surprise is None or surprise <= 0):
            continue
        if surprise_filter == 'negative' and (surprise is None or surprise >= 0):
            continue
        
        fwd = get_forward_returns(conn, ticker, date, horizons)
        if fwd:
            results.append({
                'date': date,
                'actual': actual,
                'forecast': forecast,
                'surprise': surprise,
                'notes': notes,
                **fwd
            })
    
    conn.close()
    return compute_stats(results, horizons)

def backtest_signal(signal_type, ticker='GC=F', threshold=None, horizons=[1, 5, 20]):
    """Backtest based on signal conditions."""
    conn = get_db()
    results = []
    
    if signal_type == 'cot_extreme':
        cot_ticker = 'Gold' if ticker == 'GC=F' else ('Silver' if ticker == 'SI=F' else 'Copper')
        rows = conn.execute(
            "SELECT report_date, mm_net FROM cot_weekly WHERE ticker=? ORDER BY report_date",
            (cot_ticker,)
        ).fetchall()
        
        for i in range(156, len(rows)):
            window = [r[1] for r in rows[i-156:i]]
            current = rows[i][1]
            pct = sum(1 for v in window if v <= current) / len(window) * 100
            
            if pct > 90 or pct < 10:
                fwd = get_forward_returns(conn, ticker, rows[i][0], horizons)
                if fwd:
                    results.append({
                        'date': rows[i][0],
                        'mm_net': current,
                        'percentile': round(pct, 1),
                        'direction': 'bullish_extreme' if pct > 90 else 'bearish_extreme',
                        **fwd
                    })
    
    elif signal_type == 'gold_silver_ratio':
        th_high = threshold or 85
        rows = conn.execute(
            "SELECT a.date, a.close/b.close as ratio FROM daily_prices a "
            "JOIN daily_prices b ON a.date=b.date AND b.ticker='SI=F' "
            "WHERE a.ticker='GC=F' AND a.close IS NOT NULL AND b.close IS NOT NULL "
            "ORDER BY a.date"
        ).fetchall()
        
        for date, ratio in rows:
            if ratio > th_high:
                fwd = get_forward_returns(conn, ticker, date, horizons)
                if fwd:
                    results.append({'date': date, 'ratio': round(ratio, 2), **fwd})
    
    conn.close()
    return compute_stats(results, horizons)

def compute_stats(results, horizons=[1, 5, 20]):
    """Compute summary statistics from backtest results."""
    if not results:
        return {'count': 0, 'results': [], 'stats': {}}
    
    stats = {}
    for h in horizons:
        key = f'{h}d'
        values = [r[key] for r in results if key in r]
        if values:
            arr = np.array(values)
            stats[key] = {
                'mean': round(float(np.mean(arr)), 2),
                'median': round(float(np.median(arr)), 2),
                'std': round(float(np.std(arr)), 2),
                'win_rate': round(sum(1 for v in values if v > 0) / len(values) * 100, 1),
                'count': len(values),
                'min': round(float(np.min(arr)), 2),
                'max': round(float(np.max(arr)), 2),
            }
    
    return {'count': len(results), 'results': results, 'stats': stats}

if __name__ == '__main__':
    result = backtest_event('FOMC', 'GC=F')
    print(f"FOMC → Gold backtest: {result['count']} events")
    for period, s in result['stats'].items():
        print(f"  {period}: mean={s['mean']:+.2f}% median={s['median']:+.2f}% win={s['win_rate']}%")
