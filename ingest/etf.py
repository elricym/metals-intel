#!/usr/bin/env python3
"""Ingest ETF data for GLD/SLV from yfinance."""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from ingest import get_db
import time

ETF_TICKERS = ['GLD', 'SLV']

def fetch_etf(start='2015-01-01', end=None):
    if end is None:
        end = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    conn = get_db()
    for ticker in ETF_TICKERS:
        print(f"  Fetching {ticker} ETF data...")
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df.empty:
                print(f"    WARNING: No data for {ticker}")
                continue
            
            # Try to get shares outstanding from info
            shares = None
            try:
                info = yf.Ticker(ticker).info
                shares = info.get('sharesOutstanding')
            except:
                pass
            
            count = 0
            for date, row in df.iterrows():
                conn.execute(
                    "INSERT OR REPLACE INTO etf_holdings (date, ticker, close, volume, shares_outstanding) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (date.strftime('%Y-%m-%d'), ticker,
                     float(row['Close']) if pd.notna(row['Close']) else None,
                     int(row['Volume']) if pd.notna(row['Volume']) else None,
                     shares)
                )
                count += 1
            conn.commit()
            print(f"    Inserted {count} rows for {ticker}")
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(1)
    conn.close()

if __name__ == '__main__':
    fetch_etf()
