# 持仓组合实时监控模板

## 用户偏好（从2026-06-26 session提取）

用户要求每只ETF输出以下6项（简洁）：
1. 现价、涨跌%、浮盈/浮亏%（有持仓的）
2. 买一价/卖一价（Bid/Ask）
3. 建议：买、卖、或做T
4. 精确点位：买入点 → 卖出点（配对）
5. 止损价（无条件清仓线）
6. 卖点：给出大概率能卖的价位（卖一价、买一价上方0.001-0.005）

核心策略：**不认亏卖，做T降本策略为主**。即使浮亏很深（如-37%），也不建议清仓止损，而是通过做T降本、补仓摊薄来"用时间换空间"。只有当确认趋势彻底恶化（如归零风险）时才建议清仓。

## 输出模板

```
# 📊 ETF持仓实时监控分析

**数据时间：YYYY-MM-DD HH:MM（收盘/盘中）** | **总浮盈：±X元**

---

## 🤖 {名称} ({代码}) [{T+0/T+1}]
- 现价：**{price}** | 涨跌：**{change_pct}%** | 今高{high} / 今低{low}
- 买一：**{bid1}** | 卖一：**{ask1}** | 价差{spread}
- 成本{cost} | 持仓{qty}份 | 浮盈：**{pnl_pct}%（{pnl_amt}元）**
- **建议：{操作建议}**
- 买入点：**{buy_low}→{buy_high}** | 卖出点：**{sell_low}→{sell_high}**
- 止损价：**{stop_loss}**（无条件清仓线）

---

## 📋 操作优先级排序

| 优先级 | ETF | 策略 | 理由 |
|:---:|:---|:---|:---|
| 🔴1 | {最大亏损源} | 做T降本 | 浮亏最大，需持续做T |
| 🔴2 | {第二大亏损源} | 做T降本 | 第二大亏损源 |
| 🟡3 | {中等亏损} | T+0做T | 浮亏中等，可借势做T |
| 🟡4 | {微亏/微盈} | 观望 | 等企稳 |
| 🟢5 | {盈利品种} | 小量做T | 亏损小，T+0灵活 |

## ⚠️ 风险提示
- {最大亏损源} + {第二大亏损源}合计浮亏约{total}元，占总亏损{pct}%
- 做T策略：日内低买高卖，**不认亏清仓**，以降本为核心目标
- 止损价仅作为极端情况下的无条件清仓线，非日常操作点
```

## 腾讯API批量解析代码（已验证）

```python
import re

# 字段索引（已验证）：
# [3]=现价 [4]=昨收 [31]=涨跌额 [32]=涨跌幅% [33]=最高 [34]=最低
# [9]=买一价 [8]=买一量 [19]=卖一价 [18]=卖一量
# [37]=成交额(万)

parsed = {}
for line in lines:
    m = re.match(r'v_(\w+)="(.+)"', line)
    if not m: continue
    code = re.sub(r'^sh|^sz', '', m.group(1))  # 去前缀
    parts = m.group(2).split('~')
    parsed[code] = dict(
        current=float(parts[3]),
        change_pct=float(parts[32]),
        bid1=float(parts[9]), bid1_qty=int(float(parts[8])),
        ask1=float(parts[19]), ask1_qty=int(float(parts[18])),
        high=float(parts[33]), low=float(parts[34]),
    )

# 计算浮盈
pnl_pct = (cur - cost) / cost * 100
pnl_amt = (cur - cost) * qty
```

## 关键注意事项

- **code前缀必须strip**：`re.sub(r'^sh|^sz', '', code)`，否则与positions dict不匹配
- **买一价在[9]，买一量在[8]**（腾讯API是量-价对，不是价-量对）
- **卖一价在[19]，卖一量在[18]**
- 止损价 = 成本 × 0.85（深套品种）或 成本 × 0.90（轻度套牢），根据品种波动性调整
- 买入点 = 现价下方0.3%~1.5%（根据波动性）
- 卖出点 = 买一价上方0.001~0.005（大概率成交）

## 相关参考

- `references/api-reliability-notes.md` — 腾讯API字段详解
- `references/t0-etf-trading-guide.md` — 做T降本策略
- `references/order-book-analysis.md` — 盘口分析