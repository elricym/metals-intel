#!/usr/bin/env python3
"""Ingest macro indicators: DXY, US2Y, US10Y, VIX, GVZ, breakeven for real rates."""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from ingest import get_db
import time

# Tickers: DXY, 10Y yield, VIX, GVZ, 2Y proxy, 10Y breakeven
MACRO_TICKERS = {
    'dxy': 'DX-Y.NYB',
    'us10y': '^TNX',
    'vix': '^VIX',
    'gvz': '^GVZ',
    'us2y': '^TWO',      # 2Y treasury ETF as proxy; will try ^IRX too
    'breakeven': '^T10YIE',  # 10Y breakeven inflation
}

def fetch_macro(start='2015-01-01', end=None):
    if end is None:
        end = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    data = {}
    for key, ticker in MACRO_TICKERS.items():
        print(f"  Fetching {key} ({ticker})...")
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if not df.empty:
                data[key] = df['Close'].dropna()
                print(f"    Got {len(data[key])} rows")
            else:
                print(f"    WARNING: No data for {key}")
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(1)
    
    # Try ^IRX for short-term rates if ^TWO failed
    if 'us2y' not in data or len(data.get('us2y', [])) == 0:
        print("  Trying ^IRX for short rates...")
        try:
            df = yf.download('^IRX', start=start, end=end, progress=False, auto_adjust=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if not df.empty:
                data['us2y'] = df['Close'].dropna()
                print(f"    Got {len(data['us2y'])} rows from ^IRX")
        except Exception as e:
            print(f"    ^IRX also failed: {e}")
    
    # Build combined dataframe
    all_dates = set()
    for key in ['dxy', 'us10y', 'vix', 'gvz', 'us2y', 'breakeven']:
        if key in data:
            all_dates.update(data[key].index)
    
    conn = get_db()
    count = 0
    for date in sorted(all_dates):
        date_str = date.strftime('%Y-%m-%d')
        dxy = float(data['dxy'].get(date)) if 'dxy' in data and date in data['dxy'].index else None
        us10y = float(data['us10y'].get(date)) if 'us10y' in data and date in data['us10y'].index else None
        vix = float(data['vix'].get(date)) if 'vix' in data and date in data['vix'].index else None
        gvz = float(data['gvz'].get(date)) if 'gvz' in data and date in data['gvz'].index else None
        us2y = float(data['us2y'].get(date)) if 'us2y' in data and date in data['us2y'].index else None
        breakeven = float(data['breakeven'].get(date)) if 'breakeven' in data and date in data['breakeven'].index else None
        
        us10y_real = None
        if us10y is not None and breakeven is not None:
            us10y_real = round(us10y - breakeven, 4)
        
        conn.execute(
            "INSERT OR REPLACE INTO macro_daily (date, dxy, us2y, us10y, us10y_real, vix, gvz) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (date_str, dxy, us2y, us10y, us10y_real, vix, gvz)
        )
        count += 1
    conn.commit()
    conn.close()
    print(f"  Inserted {count} macro_daily rows")

if __name__ == '__main__':
    fetch_macro()
