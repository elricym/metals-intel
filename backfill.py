#!/usr/bin/env python3
"""One-time historical backfill orchestrator."""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

def main():
    start = time.time()
    
    print("=" * 60)
    print("Metals-Intel Backfill")
    print("=" * 60)
    
    # 1. Init DB
    print("\n[1/6] Initializing database...")
    from init_db import init_db
    init_db()
    
    # 2. Prices
    print("\n[2/6] Backfilling prices (GC=F, SI=F, HG=F)...")
    from ingest.prices import fetch_prices
    fetch_prices()
    
    # 3. Macro
    print("\n[3/6] Backfilling macro data...")
    from ingest.macro import fetch_macro
    fetch_macro()
    
    # 4. ETF
    print("\n[4/6] Backfilling ETF data (GLD, SLV)...")
    from ingest.etf import fetch_etf
    fetch_etf()
    
    # 5. Events
    print("\n[5/6] Loading macro events...")
    from ingest.events import load_events
    load_events()
    
    # 6. COT
    print("\n[6/6] Backfilling COT data (this may take a while)...")
    from ingest.cot import fetch_cot
    fetch_cot()
    
    # 7. Run attribution on recent data
    print("\n[Bonus] Running attribution engine on last 30 days...")
    from engine.attribution import run_attribution_range
    from datetime import datetime, timedelta
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    run_attribution_range(start_date)
    
    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"Backfill complete in {elapsed:.0f} seconds")
    
    # Print stats
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), 'db', 'metals.db')
    conn = sqlite3.connect(DB_PATH)
    print(f"\nDatabase: {DB_PATH}")
    db_size = os.path.getsize(DB_PATH)
    print(f"Size: {db_size / 1024 / 1024:.1f} MB")
    for table in ['daily_prices', 'macro_daily', 'cot_weekly', 'etf_holdings', 'macro_events', 'attributions']:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")
    conn.close()

if __name__ == '__main__':
    main()
