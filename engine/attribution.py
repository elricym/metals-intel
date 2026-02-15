#!/usr/bin/env python3
"""Attribution engine: when daily move >1%, scan all factors and attribute."""
import sqlite3
import os
import json
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'metals.db')

TICKER_NAMES = {'GC=F': '黄金', 'SI=F': '白银', 'HG=F': '铜'}

def get_db():
    return sqlite3.connect(DB_PATH)

def get_price_change(conn, date, ticker):
    """Get price change % for a given date and ticker."""
    row = conn.execute(
        "SELECT close FROM daily_prices WHERE ticker=? AND date<? ORDER BY date DESC LIMIT 1",
        (ticker, date)
    ).fetchone()
    curr = conn.execute(
        "SELECT close FROM daily_prices WHERE ticker=? AND date=?",
        (ticker, date)
    ).fetchone()
    if not row or not curr or not row[0] or not curr[0]:
        return None
    return round((curr[0] - row[0]) / row[0] * 100, 2)

def scan_factors(conn, date, ticker):
    """Scan all factors for a given date."""
    factors = []
    
    # 1. DXY move
    macro = conn.execute("SELECT dxy FROM macro_daily WHERE date=?", (date,)).fetchone()
    prev_macro = conn.execute("SELECT dxy FROM macro_daily WHERE date<? ORDER BY date DESC LIMIT 1", (date,)).fetchone()
    if macro and prev_macro and macro[0] and prev_macro[0]:
        dxy_chg = round((macro[0] - prev_macro[0]) / prev_macro[0] * 100, 2)
        if abs(dxy_chg) > 0.3:
            direction = '走强' if dxy_chg > 0 else '走弱'
            factors.append({
                'factor': 'DXY',
                'value': f'{dxy_chg:+.2f}%',
                'impact': '利空' if dxy_chg > 0 else '利多',
                'score': min(abs(dxy_chg) / 0.5, 3),
                'desc': f'美元{direction} {dxy_chg:+.2f}%'
            })
    
    # 2. Yield changes
    m = conn.execute("SELECT us10y, us10y_real FROM macro_daily WHERE date=?", (date,)).fetchone()
    pm = conn.execute("SELECT us10y, us10y_real FROM macro_daily WHERE date<? ORDER BY date DESC LIMIT 1", (date,)).fetchone()
    if m and pm and m[0] and pm[0]:
        y_chg = round(m[0] - pm[0], 3)
        if abs(y_chg) > 0.03:
            factors.append({
                'factor': '10Y收益率',
                'value': f'{y_chg:+.3f}',
                'impact': '利空' if y_chg > 0 else '利多',
                'score': min(abs(y_chg) / 0.05, 3),
                'desc': f'10Y收益率变动 {y_chg:+.3f}'
            })
    if m and pm and m[1] and pm[1]:
        r_chg = round(m[1] - pm[1], 3)
        if abs(r_chg) > 0.03:
            factors.append({
                'factor': '实际利率',
                'value': f'{r_chg:+.3f}',
                'impact': '利空' if r_chg > 0 else '利多',
                'score': min(abs(r_chg) / 0.05, 3),
                'desc': f'实际利率变动 {r_chg:+.3f}'
            })
    
    # 3. VIX
    v = conn.execute("SELECT vix FROM macro_daily WHERE date=?", (date,)).fetchone()
    pv = conn.execute("SELECT vix FROM macro_daily WHERE date<? ORDER BY date DESC LIMIT 1", (date,)).fetchone()
    if v and pv and v[0] and pv[0] and pv[0] > 0:
        vix_chg = round((v[0] - pv[0]) / pv[0] * 100, 1)
        if abs(vix_chg) > 10:
            factors.append({
                'factor': 'VIX',
                'value': f'{vix_chg:+.1f}%',
                'impact': '避险' if vix_chg > 0 else '风险偏好',
                'score': min(abs(vix_chg) / 15, 3),
                'desc': f'VIX变动 {vix_chg:+.1f}%'
            })
    
    # 4. Macro events
    events = conn.execute(
        "SELECT event_type, actual, forecast, surprise, notes FROM macro_events WHERE date=?", (date,)
    ).fetchall()
    for ev in events:
        factors.append({
            'factor': ev[0],
            'value': f'actual={ev[1]}, forecast={ev[2]}',
            'impact': '事件驱动',
            'score': 2.5,
            'desc': f'{ev[0]}: {ev[4] or ""}'
        })
    
    # 5. Gold/Silver ratio (for silver)
    if ticker == 'SI=F':
        gold = conn.execute("SELECT close FROM daily_prices WHERE ticker='GC=F' AND date=?", (date,)).fetchone()
        silver = conn.execute("SELECT close FROM daily_prices WHERE ticker='SI=F' AND date=?", (date,)).fetchone()
        if gold and silver and gold[0] and silver[0]:
            ratio = gold[0] / silver[0]
            if ratio > 85 or ratio < 65:
                factors.append({
                    'factor': '金银比',
                    'value': f'{ratio:.1f}',
                    'impact': '均值回归压力' if ratio > 85 else '偏低',
                    'score': 1.5,
                    'desc': f'金银比 {ratio:.1f}'
                })
    
    # Sort by score
    factors.sort(key=lambda x: x.get('score', 0), reverse=True)
    return factors

def run_attribution(date=None, threshold=1.0):
    """Run attribution for all metals on a given date."""
    conn = get_db()
    if date is None:
        # Get latest date
        row = conn.execute("SELECT MAX(date) FROM daily_prices").fetchone()
        date = row[0] if row else None
    if not date:
        conn.close()
        return []
    
    results = []
    for ticker in ['GC=F', 'SI=F', 'HG=F']:
        chg = get_price_change(conn, date, ticker)
        if chg is None:
            continue
        
        if abs(chg) >= threshold:
            factors = scan_factors(conn, date, ticker)
            name = TICKER_NAMES.get(ticker, ticker)
            
            # Build notes in Chinese
            if factors:
                notes_parts = [f"{name} {date} 变动 {chg:+.2f}%"]
                notes_parts.append("主要因素:")
                for f in factors[:5]:
                    notes_parts.append(f"  • {f['desc']} ({f['impact']})")
                notes = '\n'.join(notes_parts)
            else:
                notes = f"{name} {date} 变动 {chg:+.2f}%，无明显归因因素"
            
            conn.execute(
                "INSERT OR REPLACE INTO attributions (date, ticker, price_chg_pct, factors_json, notes) "
                "VALUES (?, ?, ?, ?, ?)",
                (date, ticker, chg, json.dumps(factors, ensure_ascii=False), notes)
            )
            results.append({'date': date, 'ticker': ticker, 'change': chg, 'factors': factors, 'notes': notes})
    
    conn.commit()
    conn.close()
    return results

def run_attribution_range(start_date, end_date=None, threshold=1.0):
    """Run attribution for a date range."""
    conn = get_db()
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM daily_prices WHERE date BETWEEN ? AND ? ORDER BY date",
        (start_date, end_date)
    ).fetchall()]
    conn.close()
    
    all_results = []
    for d in dates:
        results = run_attribution(d, threshold)
        all_results.extend(results)
    
    print(f"  Attribution: processed {len(dates)} dates, found {len(all_results)} significant moves")
    return all_results

if __name__ == '__main__':
    results = run_attribution()
    for r in results:
        print(r['notes'])
        print()
