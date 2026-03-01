#!/usr/bin/env python3
"""Paper trading simulator for metals-intel strategies."""

import json, os, sys, argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "db" / "paper_portfolio.json"
CST = timezone(timedelta(hours=8))

def _load():
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text())
    return {"cash": 100000, "positions": [], "trades": [], "created": _now()}

def _save(db):
    DB_PATH.parent.mkdir(exist_ok=True)
    DB_PATH.write_text(json.dumps(db, indent=2, ensure_ascii=False))

def _now():
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M")

def _get_price(ticker):
    import yfinance as yf
    return yf.Ticker(ticker).fast_info['lastPrice']

def _find_position(db, ticker):
    for p in db["positions"]:
        if p["ticker"] == ticker:
            return p
    return None

def cmd_init(args):
    db = {"cash": args.cash, "positions": [], "trades": [], "created": _now()}
    _save(db)
    print(f"✅ 模拟盘初始化，初始资金: ${args.cash:,.0f}")

def cmd_buy(args):
    db = _load()
    price = args.price or _get_price(args.ticker)
    cost = price * args.qty
    if cost > db["cash"]:
        print(f"❌ 资金不足: 需要 ${cost:,.2f}，可用 ${db['cash']:,.2f}")
        return
    
    pos = _find_position(db, args.ticker)
    if pos:
        total_qty = pos["qty"] + args.qty
        pos["avg_price"] = (pos["avg_price"] * pos["qty"] + price * args.qty) / total_qty
        pos["qty"] = total_qty
    else:
        db["positions"].append({
            "ticker": args.ticker,
            "qty": args.qty,
            "avg_price": price,
            "opened": _now()
        })
    
    db["cash"] -= cost
    db["trades"].append({
        "time": _now(), "action": "BUY", "ticker": args.ticker,
        "qty": args.qty, "price": price, "note": args.note or ""
    })
    _save(db)
    print(f"✅ 买入 {args.ticker} x{args.qty} @ ${price:,.2f} (花费 ${cost:,.2f})")

def cmd_sell(args):
    db = _load()
    pos = _find_position(db, args.ticker)
    if not pos or pos["qty"] < args.qty:
        print(f"❌ 持仓不足")
        return
    
    price = args.price or _get_price(args.ticker)
    revenue = price * args.qty
    pnl = (price - pos["avg_price"]) * args.qty
    pnl_pct = (price / pos["avg_price"] - 1) * 100
    
    pos["qty"] -= args.qty
    if pos["qty"] == 0:
        db["positions"].remove(pos)
    
    db["cash"] += revenue
    db["trades"].append({
        "time": _now(), "action": "SELL", "ticker": args.ticker,
        "qty": args.qty, "price": price, "pnl": round(pnl, 2),
        "note": args.note or ""
    })
    _save(db)
    sign = "🟢" if pnl >= 0 else "🔴"
    print(f"✅ 卖出 {args.ticker} x{args.qty} @ ${price:,.2f} | {sign} P&L: ${pnl:,.2f} ({pnl_pct:+.1f}%)")

def cmd_status(args):
    db = _load()
    print(f"\n{'='*55}")
    print(f"  📊 模拟盘  (创建: {db['created']})")
    print(f"{'='*55}")
    
    total_value = db["cash"]
    
    if db["positions"]:
        print(f"\n  {'品种':<10} {'数量':>6} {'成本':>10} {'现价':>10} {'盈亏':>12} {'收益率':>8}")
        print(f"  {'-'*58}")
        
        for pos in db["positions"]:
            try:
                cur_price = _get_price(pos["ticker"])
            except:
                cur_price = pos["avg_price"]
            
            mkt_val = cur_price * pos["qty"]
            pnl = (cur_price - pos["avg_price"]) * pos["qty"]
            pnl_pct = (cur_price / pos["avg_price"] - 1) * 100
            total_value += mkt_val
            sign = "🟢" if pnl >= 0 else "🔴"
            
            print(f"  {pos['ticker']:<10} {pos['qty']:>6} ${pos['avg_price']:>9,.2f} ${cur_price:>9,.2f} {sign}${pnl:>+10,.2f} {pnl_pct:>+7.1f}%")
    else:
        print("\n  (无持仓)")
    
    init_cash = 100000  # default
    total_pnl = total_value - init_cash
    total_pct = (total_value / init_cash - 1) * 100
    
    print(f"\n  💰 现金:    ${db['cash']:>12,.2f}")
    print(f"  📈 总市值:  ${total_value:>12,.2f}")
    print(f"  {'🟢' if total_pnl >= 0 else '🔴'} 总盈亏:  ${total_pnl:>+12,.2f} ({total_pct:+.1f}%)")
    print()

def cmd_trades(args):
    db = _load()
    n = args.limit or 20
    trades = db["trades"][-n:]
    if not trades:
        print("(无交易记录)")
        return
    print(f"\n  {'时间':<18} {'操作':>4} {'品种':<8} {'数量':>5} {'价格':>10} {'盈亏':>10} {'备注'}")
    print(f"  {'-'*70}")
    for t in trades:
        pnl_str = f"${t.get('pnl',0):>+,.2f}" if t.get('pnl') else ""
        print(f"  {t['time']:<18} {t['action']:>4} {t['ticker']:<8} {t['qty']:>5} ${t['price']:>9,.2f} {pnl_str:>10} {t.get('note','')}")
    print()

def main():
    p = argparse.ArgumentParser(description="Paper Trading Simulator")
    sub = p.add_subparsers(dest="cmd")
    
    s = sub.add_parser("init", help="初始化模拟盘")
    s.add_argument("--cash", type=float, default=100000)
    
    s = sub.add_parser("buy", help="买入")
    s.add_argument("ticker")
    s.add_argument("qty", type=int)
    s.add_argument("--price", type=float)
    s.add_argument("--note", type=str)
    
    s = sub.add_parser("sell", help="卖出")
    s.add_argument("ticker")
    s.add_argument("qty", type=int)
    s.add_argument("--price", type=float)
    s.add_argument("--note", type=str)
    
    s = sub.add_parser("status", help="查看持仓")
    
    s = sub.add_parser("trades", help="交易记录")
    s.add_argument("--limit", type=int)
    
    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return
    
    {"init": cmd_init, "buy": cmd_buy, "sell": cmd_sell, 
     "status": cmd_status, "trades": cmd_trades}[args.cmd](args)

if __name__ == "__main__":
    main()
