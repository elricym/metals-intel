#!/usr/bin/env python3
"""Ingest daily OHLCV for Gold, Silver, Copper futures from yfinance."""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from ingest import get_db
import time

TICKERS = ['GC=F', 'SI=F', 'HG=F']

def fetch_prices(start='2015-01-01', end=None, tickers=None):
    if end is None:
        end = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    if tickers is None:
        tickers = TICKERS
    
    conn = get_db()
    for ticker in tickers:
        print(f"  Fetching {ticker} prices...")
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
            if df.empty:
                print(f"    WARNING: No data for {ticker}")
                continue
            # Handle multi-level columns from yfinance
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            count = 0
            for date, row in df.iterrows():
                date_str = date.strftime('%Y-%m-%d')
                conn.execute(
                    "INSERT OR REPLACE INTO daily_prices (date, ticker, open, high, low, close, volume, oi) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
                    (date_str, ticker,
                     float(row['Open']) if pd.notna(row['Open']) else None,
                     float(row['High']) if pd.notna(row['High']) else None,
                     float(row['Low']) if pd.notna(row['Low']) else None,
                     float(row['Close']) if pd.notna(row['Close']) else None,
                     int(row['Volume']) if pd.notna(row['Volume']) else None)
                )
                count += 1
            conn.commit()
            print(f"    Inserted {count} rows for {ticker}")
        except Exception as e:
            print(f"    ERROR fetching {ticker}: {e}")
        time.sleep(1)
    conn.close()

if __name__ == '__main__':
    fetch_prices()
