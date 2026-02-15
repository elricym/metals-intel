#!/usr/bin/env python3
"""Incremental update script for cron (every 2 hours)."""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

def main():
    # Only update last 5 days
    start = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    
    from ingest.prices import fetch_prices
    from ingest.macro import fetch_macro
    from ingest.etf import fetch_etf
    from engine.attribution import run_attribution
    
    fetch_prices(start=start)
    fetch_macro(start=start)
    fetch_etf(start=start)
    
    # Run attribution for today
    today = datetime.now().strftime('%Y-%m-%d')
    run_attribution(today, threshold=1.0)

if __name__ == '__main__':
    main()
