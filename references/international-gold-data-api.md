# 国际金价数据源实战笔记

## 背景

用户持有黄金ETF（518880、518660、518850、562500等），所以黄金现货/期货价格直接影响ETF净值。国际金价是全球定价基准，A股黄金ETF跟踪上海金（SHAU），而上海金与COMEX黄金期货（GC=XAU）联动紧密。

## 黄金相关市场

| 市场 | 交易标的 | 交易时间 | 数据可用性 |
|------|---------|---------|-----------|
| 伦敦金 | XAUUSD | 24小时OTC | 实时 |
| COMEX金期货 | GC=F (Aug/Sep等) | 北京时间21:00~次日02:00 | 实时 |
| 上海金 | SHAU | 9:00~15:30 + 21:00~次日02 | 实时 |
| 518880黄金ETF | 受SHAU影响 | 9:30~15:00 A股 | 实时 |

## 可用数据API（已实测）

### 1. 🟢 gold-api.com（免费，推荐）

**金/银现货实时价格：**
```json
// XAU/USD 现货
curl -s "https://api.gold-api.com/price/XAU"

{
  "currency": "USD",
  "name": "Gold",
  "price": 4079.10,
  "symbol": "XAU",
  "updatedAt": "2026-06-26T14:05:13Z"
}
```

**支持币种：**
- `/price/XAU/USD` — 美元金价
- `/price/XAU/GBP` — 英镑金价
- `/price/XAU/EUR` — 欧元金价

**注意事项：**
- 无需API Key
- 实时更新（秒级）
- 50Hz速率限制（足够单人使用）

### 2. 🟢 Yahoo Finance API（含期货、汇率）

**COMEX金期货 (GC=F)：**
```
https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d
```

**关键返回字段：**
- `meta.regularMarketPrice` — 当前价格
- `meta.regularMarketDayHigh` — 当日最高
- `meta.regularMarketDayLow` — 当日最低
- `indicators.quote[0].high[]` — 当日最高价数组
- `indicators.quote[0].close` — 最新收盘价

**汇率数据（用于人民币换算）：**
```
GBP/USD → query2.finance.yahoo.com/v8/finance/chart/GBP=X
USD/CNY → query2.finance.yahoo.com/v8/finance/chart=CNY=X
```

**注意事项：**
- ⚡ `query2.finance.yahoo.com`（比 `query1` 少风控）
- 需指定 `period1`/`period2` 时间戳范围
- execute_code 中 urllib 偶尔报错 "SRE module mismatch"（属环境路径冲突），**用 terminal 执行 Python 脚本应避免 execute_code 调用 urllib**
- `python3` 在 Windows MSYS 环境下需要完整路径 `C:/Python314/python.exe`（但环境损坏则报错 `AssertionError: SRE module mismatch`），推荐用 terminal 的 `which python` 找到的路径

### 3. 🟡 腾讯财经（A股黄金ETF实时行情）

黄金ETF实时价格首选：
```
curl -s "https://qt.gtimg.cn/q=sh518880,sh518660,sz159830,sz518800"
```

## 汇率换算公式

```
人民币金价(元/克) = 国际金价(USD/troy_oz) × USD/CNY ÷ 31.1035
```

**GBP/USD → 人民币：**
```
人民币金价 = GBP金价 × GBP/USD ÷ 31.1035
```

**EUR/USD → 人民币：**
```
人民币金价 = EUR金价 × EUR/USD ÷ 31.1035
```

## 金价对黄金ETF的影响

| 金价变动 | 518880(黄金ETF) | 518660(工银) | 164701(LOF) |
|---------|---------------|-------------|-----------|
| +1% | 净值~+1% | 净值~+1% | 净值~+0.95% |
| -1% | 净值~-1% | 净值~-1% | 净值~-0.95% |

- 跟踪误差主要来自：①汇率波动 ②管理/托管费率 ③溢价/折价 ④现金仓位

## 黑天鹅提醒

**金/银/铜等商品ETF的价格可能在当天大幅波动，分析时需**：
1. 先看黄金现货价格有无异动（gold-api 或 Yahoo Finance GC=F 查5min内最高最低）
2. 再查AUD/USD（澳元）和USD/CHF（瑞郎）确认方向
3. 然后拿到A股黄金ETF实时场内价格，再给出操作建议
4. **金价是领先指标**，黄金ETF价格滞后金价数秒到数分钟

## 常见兑换率速查

```
1 金衡盎司 = 31.1035 克
当前 GBP/USD ≈ 1.32
GBP/CNY ≈ 9.2
```
