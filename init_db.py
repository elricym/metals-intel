#!/usr/bin/env python3
"""Create/reset the SQLite database schema."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'db', 'metals.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_prices (
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER, oi INTEGER,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS macro_daily (
    date TEXT PRIMARY KEY,
    dxy REAL, us2y REAL, us10y REAL, us10y_real REAL,
    vix REAL, gvz REAL
);

CREATE TABLE IF NOT EXISTS cot_weekly (
    report_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    mm_long INTEGER, mm_short INTEGER, mm_net INTEGER,
    pm_long INTEGER, pm_short INTEGER, pm_net INTEGER,
    oi INTEGER,
    PRIMARY KEY (report_date, ticker)
);

CREATE TABLE IF NOT EXISTS etf_holdings (
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    close REAL, volume INTEGER, shares_outstanding REAL,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS macro_events (
    date TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actual REAL, forecast REAL, previous REAL,
    surprise REAL, notes TEXT,
    PRIMARY KEY (date, event_type)
);

CREATE TABLE IF NOT EXISTS attributions (
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    price_chg_pct REAL,
    factors_json TEXT,
    notes TEXT,
    PRIMARY KEY (date, ticker)
);
"""

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == '__main__':
    init_db()
