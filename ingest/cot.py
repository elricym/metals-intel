#!/usr/bin/env python3
"""Ingest CFTC COT disaggregated futures data for Gold, Silver, Copper."""
import os
import io
import zipfile
import pandas as pd
import requests
from ingest import get_db
import time

# CFTC commodity codes
COMMODITY_CODES = {
    '88': 'Gold',
    '84': 'Silver', 
    '85': 'Copper',
}

def fetch_cot(start_year=2015, end_year=2026):
    conn = get_db()
    total = 0
    
    for year in range(start_year, end_year + 1):
        url = f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
        print(f"  Downloading COT {year}...")
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code != 200:
                print(f"    WARNING: HTTP {resp.status_code} for {year}")
                continue
            
            zf = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = zf.namelist()[0]
            df = pd.read_csv(zf.open(csv_name), low_memory=False)
            
            # Filter for our commodities
            df['CFTC_Commodity_Code'] = df['CFTC_Commodity_Code'].astype(str).str.strip()
            
            count = 0
            for code, name in COMMODITY_CODES.items():
                subset = df[df['CFTC_Commodity_Code'] == code]
                for _, row in subset.iterrows():
                    report_date = pd.to_datetime(row['Report_Date_as_YYYY-MM-DD']).strftime('%Y-%m-%d')
                    try:
                        conn.execute(
                            "INSERT OR REPLACE INTO cot_weekly "
                            "(report_date, ticker, mm_long, mm_short, mm_net, pm_long, pm_short, pm_net, oi) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (report_date, name,
                             int(row.get('M_Money_Positions_Long_All', 0)),
                             int(row.get('M_Money_Positions_Short_All', 0)),
                             int(row.get('M_Money_Positions_Long_All', 0)) - int(row.get('M_Money_Positions_Short_All', 0)),
                             int(row.get('Prod_Merc_Positions_Long_All', 0)),
                             int(row.get('Prod_Merc_Positions_Short_All', 0)),
                             int(row.get('Prod_Merc_Positions_Long_All', 0)) - int(row.get('Prod_Merc_Positions_Short_All', 0)),
                             int(row.get('Open_Interest_All', 0)))
                        )
                        count += 1
                    except Exception as e:
                        pass
            conn.commit()
            total += count
            print(f"    Inserted {count} rows for {year}")
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(2)
    
    conn.close()
    print(f"  Total COT rows: {total}")

if __name__ == '__main__':
    fetch_cot()
