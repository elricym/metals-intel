# Metals-Intel: 贵金属归因与回测系统

> **可迁移知识文档** — 任何 AI agent 读完本文件即可理解、使用和维护此系统。

---

## 一、系统定位

一套基于 SQLite 的本地金融数据系统，覆盖贵金属（金/银/铜）从 2015 年至今的多维度数据，核心能力：

1. **快速归因**：金价大幅波动时，自动扫描同期宏观指标、事件、持仓变化，给出多因子归因
2. **历史回测**：任意事件/信号条件 → 后续 N 天价格表现统计
3. **信号监控**：COT 极值、金银比异常、VIX 飙升、美元突破等
4. **增量更新**：每 2 小时拉取最新数据，自动归因

## 二、技术架构

```
metals-intel/
├── db/metals.db           # SQLite 单文件数据库（约 1.4MB）
├── ingest/                # 数据采集模块
│   ├── prices.py          # 金银铜日线 (yfinance: GC=F, SI=F, HG=F)
│   ├── macro.py           # 宏观指标 (yfinance: DX-Y.NYB, ^TNX, ^VIX, ^GVZ)
│   ├── cot.py             # CFTC COT 持仓 (年度 zip 下载解析)
│   ├── etf.py             # ETF 数据 (yfinance: GLD, SLV)
│   └── events.py          # 宏观事件 (FOMC 利率决议自动抓取)
├── engine/                # 分析引擎
│   ├── attribution.py     # 归因引擎
│   ├── backtest.py        # 回测引擎
│   └── signals.py         # 信号库
├── query.py               # CLI 查询入口
├── cron_update.py         # 定时增量更新
├── init_db.py             # 建表脚本
└── backfill.py            # 历史数据回填（首次使用）
```

### 依赖

```bash
pip install yfinance pandas numpy
```

## 三、数据库 Schema

### `daily_prices` — 日线价格
| 字段 | 类型 | 说明 |
|------|------|------|
| date | TEXT | 日期 YYYY-MM-DD |
| ticker | TEXT | GC=F(金) / SI=F(银) / HG=F(铜) |
| open, high, low, close | REAL | OHLC |
| volume | INTEGER | 成交量 |
| oi | INTEGER | 未平仓量 |
| **PK** | | (date, ticker) |

### `macro_daily` — 宏观日频指标
| 字段 | 类型 | 说明 |
|------|------|------|
| date | TEXT PK | 日期 |
| dxy | REAL | 美元指数 (DX-Y.NYB) |
| us2y | REAL | 2年期美债收益率（数据不完整） |
| us10y | REAL | 10年期美债收益率 (^TNX) |
| us10y_real | REAL | 10年实际利率（需 FRED API 补全） |
| vix | REAL | 恐慌指数 (^VIX) |
| gvz | REAL | 黄金波动率 (^GVZ) |

### `cot_weekly` — CFTC 持仓周报
| 字段 | 类型 | 说明 |
|------|------|------|
| report_date | TEXT | 报告日期 |
| ticker | TEXT | Gold / Silver / Copper |
| mm_long, mm_short, mm_net | INTEGER | 管理基金多/空/净 |
| pm_long, pm_short, pm_net | INTEGER | 产业持仓多/空/净 |
| oi | INTEGER | 未平仓量 |
| **PK** | | (report_date, ticker) |

### `etf_holdings` — ETF 数据
| 字段 | 类型 | 说明 |
|------|------|------|
| date | TEXT | 日期 |
| ticker | TEXT | GLD / SLV |
| close | REAL | ETF 收盘价 |
| volume | INTEGER | 成交量 |
| shares_outstanding | REAL | 流通份额 |
| **PK** | | (date, ticker) |

### `macro_events` — 宏观事件
| 字段 | 类型 | 说明 |
|------|------|------|
| date | TEXT | 日期 |
| event_type | TEXT | FOMC / NFP / CPI / PMI / GEOPOLITICAL / HOLIDAY 等 |
| actual | REAL | 实际值 |
| forecast | REAL | 预期值 |
| previous | REAL | 前值 |
| surprise | REAL | 意外值 (actual - forecast) |
| notes | TEXT | 中文描述 |
| **PK** | | (date, event_type) |

### `attributions` — 归因结果
| 字段 | 类型 | 说明 |
|------|------|------|
| date | TEXT | 日期 |
| ticker | TEXT | GC=F / SI=F / HG=F |
| price_chg_pct | REAL | 当日涨跌幅 % |
| factors_json | TEXT | JSON 数组，每个因子含 factor/value/impact/score/desc |
| notes | TEXT | 中文归因摘要 |
| **PK** | | (date, ticker) |

## 四、归因引擎原理

### 触发条件
日涨跌幅 ≥ 1%（可调，`run_attribution(date, threshold=1.0)`）

### 扫描维度（按 score 排序输出）

| 因子 | 数据源 | 触发阈值 | 影响方向 |
|------|--------|----------|----------|
| DXY 美元指数 | macro_daily.dxy | 日变动 > 0.3% | 美元涨→利空金价 |
| 10Y 国债收益率 | macro_daily.us10y | 日变动 > 3bp | 收益率涨→利空金价 |
| 实际利率 | macro_daily.us10y_real | 日变动 > 3bp | 实际利率涨→利空金价（核心定价因子）|
| VIX 恐慌指数 | macro_daily.vix | 日变动 > 10% | VIX 飙升→避险买盘 |
| 宏观事件 | macro_events | 当日有事件 | 事件驱动，score=2.5 |
| 金银比 | daily_prices 交叉 | >85 或 <65 | 均值回归信号（仅白银）|

### 归因输出格式

```
黄金 2026-02-12 变动 -2.92%
主要因素:
  • NFP: 1月非农大幅超预期 (事件驱动)
  • GEOPOLITICAL: Netanyahu确认Trump倾向与伊朗达成协议 (事件驱动)
  • VIX变动 +18.0% (避险)
  • 10Y收益率变动 -0.068 (利多)
```

### 手动归因补充

自动归因无法捕捉的因素（地缘事件、流动性因素等），应手动录入：

```python
import sqlite3, json
conn = sqlite3.connect('db/metals.db')

# 1. 录入事件
conn.execute('''INSERT OR REPLACE INTO macro_events 
    (date, event_type, actual, forecast, previous, surprise, notes)
    VALUES ('2026-02-12', 'NFP', 130, 70, NULL, 60, '非农大幅超预期')''')

# 2. 更新归因（带权重因子）
factors = [
    {'factor': '地缘风险溢价骤降', 'detail': '...', 'impact': 'bearish', 'weight': 0.4},
    {'factor': 'NFP超预期', 'detail': '...', 'impact': 'bearish', 'weight': 0.3},
]
conn.execute('''INSERT OR REPLACE INTO attributions 
    (date, ticker, price_chg_pct, factors_json, notes)
    VALUES ('2026-02-12', 'GC=F', -2.92, ?, '...')''',
    [json.dumps(factors, ensure_ascii=False)])
conn.commit()
```

## 五、回测引擎

### 事件回测

```python
from engine.backtest import backtest_event
# FOMC 后黄金表现
result = backtest_event('FOMC', 'GC=F')
# CPI 超预期后黄金表现
result = backtest_event('CPI', 'GC=F', surprise_filter='positive')
```

返回结构：
```python
{
    'count': 82,                    # 样本数
    'stats': {
        '1d': {'mean': 0.12, 'median': 0.05, 'win_rate': 52.3, 'std': 1.2, ...},
        '5d': {...},
        '20d': {...},
    },
    'results': [{'date': '...', '1d': 0.5, '5d': 1.2, '20d': -0.3, ...}, ...]
}
```

### 信号回测

```python
from engine.backtest import backtest_signal
# COT 极端值后表现
result = backtest_signal('cot_extreme', 'GC=F')
# 金银比 >85 后黄金表现
result = backtest_signal('gold_silver_ratio', 'GC=F', threshold=85)
```

## 六、信号库

| 信号 | 函数 | 判定标准 | 含义 |
|------|------|----------|------|
| COT 分位数 | `cot_percentile(ticker)` | >90% 或 <10%（3年窗口）| 多/空头极端，可能反转 |
| 金银比 | `gold_silver_ratio()` | >85 或 <65 | 均值回归信号 |
| 铜金比 | `copper_gold_ratio()` | 低值 | 经济衰退前兆 |
| VIX 飙升 | `vix_spike()` | 日变动 >20% | 恐慌/避险 |
| DXY 突破 | `dxy_breakout()` | 接近52周高/低点(1%) | 美元趋势信号 |

```python
from engine.signals import all_signals
for s in all_signals():
    if s.get('extreme') or s.get('spike') or s.get('at_high') or s.get('at_low'):
        print(f"⚠️ {s['signal']}: {s['direction']}")
```

## 七、CLI 使用

```bash
# 市场概览（价格 + 宏观 + 信号 + 近期归因）
python3 query.py summary

# 某日归因
python3 query.py attribution 2026-02-12
python3 query.py attribution today

# 回测
python3 query.py backtest --event FOMC --ticker GC=F
python3 query.py backtest --signal cot_extreme --ticker GC=F

# 信号状态
python3 query.py signal

# 价格历史
python3 query.py history --ticker GC=F --days 30
```

## 八、数据采集

### 首次回填（2015年至今）

```bash
python3 backfill.py
```

会按顺序执行：
1. `init_db.py` — 建表
2. `ingest/prices.py` — 金银铜日线 (yfinance)
3. `ingest/macro.py` — DXY/收益率/VIX/GVZ (yfinance)
4. `ingest/cot.py` — CFTC COT 年度数据 (2015-至今)
5. `ingest/etf.py` — GLD/SLV (yfinance)
6. `ingest/events.py` — FOMC 利率决议 (FRED)
7. `engine/attribution.py` — 对近30天大波动做归因

### 增量更新

```bash
python3 cron_update.py
```

拉取最新数据 → upsert → 自动归因新的大波动。适合 cron 每2小时执行。

### 数据源与已知限制

| 数据 | 来源 | 限制 |
|------|------|------|
| 价格 OHLCV | yfinance (Yahoo Finance) | 免费，偶有限流 |
| DXY/VIX/GVZ | yfinance | GVZ 历史可能不完整 |
| 2Y 国债 | yfinance ^TWO | 数据极不完整 |
| 实际利率 | 需 FRED API (^T10YIE 已下架) | **目前缺失** |
| COT | CFTC 年度 zip | 每周五更新，延迟3天 |
| 宏观事件 | 仅 FOMC 自动抓取 | **CPI/NFP/PMI 需手动录入** |

### 补全建议

1. **FRED API Key** → 可补全 2Y 收益率、实际利率、CPI/NFP 历史数据
2. **手动/半自动事件录入** → 重大事件（NFP 大超预期、地缘冲突等）应在发生时录入 macro_events
3. **新闻/推特联动** → 将 AI 新闻摘要存入 attributions.notes 增强归因

## 九、Agent 使用指南

### 作为 AI Agent 如何使用此系统

**日常使用（回答用户关于金价的问题）：**

```bash
# 1. 先看概览
cd /path/to/metals-intel && python3 query.py summary

# 2. 用户问"今天黄金怎么了" → 跑归因
python3 query.py attribution today

# 3. 用户问"NFP 超预期后金价怎么走" → 跑回测
python3 query.py backtest --event NFP --surprise positive --ticker GC=F

# 4. 用户问"现在有什么信号" → 看信号
python3 query.py signal
```

**数据维护：**

- 定时跑 `python3 cron_update.py` 保持数据最新
- 遇到重大事件（NFP/CPI/地缘），手动 INSERT 到 macro_events
- 自动归因不够时，手动补充 attributions 的 factors_json 和 notes

**分析框架（回答"为什么涨/跌"的思路）：**

1. 查当日 macro_events → 有无事件驱动？
2. 查 DXY 变动 → 美元因素？
3. 查 10Y/实际利率 → 利率因素？
4. 查 VIX → 恐慌/风险偏好？
5. 查 COT → 持仓极端？
6. 查 ETF 成交量 → 恐慌抛售 or 追涨？
7. 查金银比/铜金比 → 交叉验证
8. 搜索当日新闻 → 补充非量化因素（地缘、政策等）

**归因质量层级：**
- 🟢 自动归因：数据库指标覆盖的因素，可靠
- 🟡 半自动：事件录入后的归因，需要人工判断因果
- 🔴 需搜索：地缘事件、市场情绪等，需查新闻补充

## 十、扩展方向

1. **接入 FRED API** → 补全 CPI/NFP/PMI 历史事件 + 实际利率
2. **自动事件日历** → 从财经日历网站抓取未来事件预告
3. **多品种扩展** → 原油(CL=F)、铂(PL=F)、钯(PA=F)
4. **Web UI** → 配合 metals-dashboard 展示归因和回测结果
5. **Alerting** → 信号触发时自动通知
6. **ML 增强** → 用历史归因数据训练简单的因子权重模型

---

*最后更新: 2026-02-15*
*数据库大小: ~1.4MB | 总行数: ~16,000+ | 覆盖: 2015-01 至今*
