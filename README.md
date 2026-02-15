# Metals-Intel 贵金属归因分析系统

自动化贵金属(黄金/白银/铜)价格归因、信号检测与历史回测系统。

## 功能

- **价格归因**: 当日波动超1%时自动归因(美元、利率、VIX、FOMC等)
- **信号检测**: COT持仓极端、金银比、铜金比、VIX飙升、DXY突破
- **历史回测**: 事件驱动(FOMC/CPI)和信号驱动回测，计算1/5/20日远期收益
- **增量更新**: 每2小时cron更新最新数据

## 安装

```bash
pip install yfinance pandas numpy requests
```

## 使用

### 首次运行 - 历史数据回填
```bash
python3 backfill.py  # ~5-10分钟
```

### 查询
```bash
python3 query.py summary                           # 市场概览
python3 query.py attribution today                  # 今日归因
python3 query.py attribution 2024-09-18             # 指定日期
python3 query.py backtest --event FOMC --ticker GC=F  # FOMC回测
python3 query.py signal --type cot_extreme --ticker Gold  # COT信号
python3 query.py history --ticker GC=F --days 30    # 价格历史
```

### 定时更新 (crontab)
```
0 */2 * * * cd /path/to/metals-intel && python3 cron_update.py
```

## 数据源

| 数据 | 来源 | 频率 |
|------|------|------|
| 期货价格 | yfinance (GC=F/SI=F/HG=F) | 日线 |
| 宏观指标 | yfinance (DXY/TNX/VIX/GVZ) | 日线 |
| COT持仓 | CFTC disaggregated | 周度 |
| ETF | yfinance (GLD/SLV) | 日线 |
| 宏观事件 | 内置FOMC数据库 | 事件 |

## 数据库

SQLite @ `db/metals.db`，6张表：daily_prices, macro_daily, cot_weekly, etf_holdings, macro_events, attributions
