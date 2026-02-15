#!/usr/bin/env python3
"""CLI query interface for metals-intel."""
import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

DB_PATH = os.path.join(os.path.dirname(__file__), 'db', 'metals.db')

def get_db():
    return sqlite3.connect(DB_PATH)

def cmd_attribution(args):
    """Show attribution for a date."""
    date = args[0] if args else 'today'
    if date == 'today':
        date = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_db()
    rows = conn.execute(
        "SELECT ticker, price_chg_pct, notes, factors_json FROM attributions WHERE date=?", (date,)
    ).fetchall()
    
    if not rows:
        # Try running attribution
        from engine.attribution import run_attribution
        results = run_attribution(date, threshold=0.5)
        if results:
            for r in results:
                print(r['notes'])
                print()
        else:
            # Show prices for that day anyway
            prices = conn.execute(
                "SELECT ticker, close FROM daily_prices WHERE date=?", (date,)
            ).fetchall()
            if prices:
                print(f"📊 {date} 无显著波动 (< 0.5%)")
                for ticker, close in prices:
                    name = {'GC=F': '黄金', 'SI=F': '白银', 'HG=F': '铜'}.get(ticker, ticker)
                    if close:
                        print(f"  {name}: ${close:.2f}")
            else:
                print(f"无 {date} 数据")
    else:
        for ticker, chg, notes, factors_json in rows:
            print(notes)
            print()
    conn.close()

def cmd_summary(args):
    """Current state summary."""
    conn = get_db()
    
    print("=" * 60)
    print("📊 贵金属市场概览")
    print("=" * 60)
    
    # Latest prices
    for ticker, name in [('GC=F', '黄金'), ('SI=F', '白银'), ('HG=F', '铜')]:
        row = conn.execute(
            "SELECT date, close FROM daily_prices WHERE ticker=? AND close IS NOT NULL ORDER BY date DESC LIMIT 1",
            (ticker,)
        ).fetchone()
        prev = conn.execute(
            "SELECT close FROM daily_prices WHERE ticker=? AND close IS NOT NULL ORDER BY date DESC LIMIT 1 OFFSET 1",
            (ticker,)
        ).fetchone()
        if row:
            chg = ''
            if prev and prev[0]:
                pct = (row[1] - prev[0]) / prev[0] * 100
                chg = f' ({pct:+.2f}%)'
            print(f"  {name}: ${row[1]:.2f}{chg}  [{row[0]}]")
    
    # Macro
    print()
    macro = conn.execute("SELECT * FROM macro_daily ORDER BY date DESC LIMIT 1").fetchone()
    if macro:
        print(f"📈 宏观指标 [{macro[0]}]")
        labels = ['DXY', 'US2Y', 'US10Y', '实际利率', 'VIX', 'GVZ']
        for i, label in enumerate(labels):
            val = macro[i+1]
            if val is not None:
                print(f"  {label}: {val:.2f}")
    
    # Signals
    print()
    print("🔔 信号状态")
    from engine.signals import all_signals
    signals = all_signals()
    active = [s for s in signals if s.get('extreme') or s.get('spike') or s.get('at_high') or s.get('at_low')]
    if active:
        for s in active:
            print(f"  ⚠️  {s['signal']}: {s.get('direction', '')} ({json.dumps({k:v for k,v in s.items() if k not in ['signal','direction','extreme','spike','at_high','at_low']}, ensure_ascii=False)})")
    else:
        for s in signals:
            print(f"  ✅ {s['signal']}: {s.get('direction', s.get('note', ''))}")
    
    # Recent attributions
    print()
    print("📝 近期归因")
    attrs = conn.execute(
        "SELECT date, ticker, price_chg_pct, notes FROM attributions ORDER BY date DESC LIMIT 5"
    ).fetchall()
    if attrs:
        for date, ticker, chg, notes in attrs:
            name = {'GC=F': '黄金', 'SI=F': '白银', 'HG=F': '铜'}.get(ticker, ticker)
            print(f"  {date} {name} {chg:+.2f}%")
    else:
        print("  暂无归因记录")
    
    # Table stats
    print()
    print("📦 数据库统计")
    for table in ['daily_prices', 'macro_daily', 'cot_weekly', 'etf_holdings', 'macro_events', 'attributions']:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")
    
    conn.close()

def cmd_backtest(args):
    """Run backtest."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--event', default='FOMC')
    parser.add_argument('--surprise', default=None)
    parser.add_argument('--ticker', default='GC=F')
    parser.add_argument('--signal', default=None)
    parsed = parser.parse_args(args)
    
    from engine.backtest import backtest_event, backtest_signal
    
    if parsed.signal:
        result = backtest_signal(parsed.signal, parsed.ticker)
    else:
        result = backtest_event(parsed.event, parsed.ticker, parsed.surprise)
    
    print(f"回测: {parsed.event or parsed.signal} → {parsed.ticker}")
    print(f"样本数: {result['count']}")
    print()
    
    if result['stats']:
        print(f"{'周期':<8} {'均值':>8} {'中位数':>8} {'胜率':>8} {'标准差':>8} {'最小':>8} {'最大':>8}")
        print("-" * 60)
        for period, s in result['stats'].items():
            print(f"{period:<8} {s['mean']:>+7.2f}% {s['median']:>+7.2f}% {s['win_rate']:>7.1f}% {s['std']:>7.2f}% {s['min']:>+7.2f}% {s['max']:>+7.2f}%")
    
    if result['results']:
        print(f"\n最近5次:")
        for r in result['results'][-5:]:
            print(f"  {r['date']}: {r.get('notes', '')} → 1d={r.get('1d', 'N/A')}% 5d={r.get('5d', 'N/A')}% 20d={r.get('20d', 'N/A')}%")

def cmd_signal(args):
    """Show current signals."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', default=None)
    parser.add_argument('--ticker', default=None)
    parsed = parser.parse_args(args)
    
    from engine.signals import all_signals, cot_percentile
    
    if parsed.type == 'cot_extreme' and parsed.ticker:
        s = cot_percentile(parsed.ticker)
        if s:
            print(json.dumps(s, ensure_ascii=False, indent=2))
        else:
            print("无数据")
    else:
        signals = all_signals()
        for s in signals:
            flag = '⚠️' if s.get('extreme') or s.get('spike') or s.get('at_high') or s.get('at_low') else '✅'
            print(f"{flag} {s['signal']}: {s.get('direction', s.get('note', ''))}")
            for k, v in s.items():
                if k not in ['signal', 'direction', 'extreme', 'spike', 'at_high', 'at_low', 'note']:
                    print(f"    {k}: {v}")
            print()

def cmd_history(args):
    """Recent price history."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', default='GC=F')
    parser.add_argument('--days', type=int, default=30)
    parsed = parser.parse_args(args)
    
    conn = get_db()
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume FROM daily_prices WHERE ticker=? ORDER BY date DESC LIMIT ?",
        (parsed.ticker, parsed.days)
    ).fetchall()
    conn.close()
    
    name = {'GC=F': '黄金', 'SI=F': '白银', 'HG=F': '铜'}.get(parsed.ticker, parsed.ticker)
    print(f"📊 {name} ({parsed.ticker}) 最近 {parsed.days} 天")
    print(f"{'日期':<12} {'开盘':>10} {'最高':>10} {'最低':>10} {'收盘':>10} {'成交量':>12}")
    print("-" * 68)
    for row in reversed(rows):
        d, o, h, l, c, v = row
        print(f"{d:<12} {o or 0:>10.2f} {h or 0:>10.2f} {l or 0:>10.2f} {c or 0:>10.2f} {v or 0:>12,}")

COMMANDS = {
    'attribution': cmd_attribution,
    'summary': cmd_summary,
    'backtest': cmd_backtest,
    'signal': cmd_signal,
    'history': cmd_history,
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("用法: python3 query.py <command> [options]")
        print(f"命令: {', '.join(COMMANDS.keys())}")
        sys.exit(1)
    
    COMMANDS[sys.argv[1]](sys.argv[2:])

if __name__ == '__main__':
    main()
