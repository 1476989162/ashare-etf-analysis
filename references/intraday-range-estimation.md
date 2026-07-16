# 今日盘中高低区间估算（基于历史日内振幅分布）

当用户问"今天能到最低/最高多少""今天最高/最低大概多少"时，用**历史日内振幅分布**估算今日可能的高/低区间。与 N 日触达概率（GBM 路径触及）不同，这里直接给出**区间上下界**，适合"今天范围"类问题。

## 方法（实测 161226 白银LOF，2026-07-10）

1. 拉真实日 K 线（腾讯 `proxy.finance.qq.com/.../kline`，~120 日）。
2. 计算每只 K 线的**日内振幅**：`amp = (high - low) / close`。
3. 取 `mean(amp)`、`std(amp)`。
4. 以**当前实时价**为中枢，按 `中枢 × (1 ± k·amp)` 估算高/低：
   - 1σ ≈ mean + 1·std
   - 1.5σ ≈ mean + 1.5·std
   - 2σ / 近20日最大单日振幅 ≈ 极端框

## 实测数据（161226，121 交易日）
- 日内振幅均值 = 4.07%，波动 = 3.13%
- 1σ → ±7.2% → 高≈1.97 / 低≈1.71
- 1.5σ → ±8.8% → 高≈2.00 / 低≈1.68
- 2σ / 近20日最大单日振幅(10.0%) → 高≈2.02 / 低≈1.66

## 代码模板
```python
import json, urllib.request, math
from statistics import mean, stdev

code = 'sz161226'
url = f'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/kline/kline?param={code},day,,,500'
rows = json.loads(urllib.request.urlopen(url, timeout=15).read())['data'][code]['day']
y26 = [r for r in rows if r[0] >= '2026-01-01']
amp = [(float(r[3]) - float(r[4])) / float(r[2]) for r in y26[1:]]
ma, sa = mean(amp), stdev(amp)

# 当前实时价（腾讯 qt.gtimg.cn 字段[3]）
f = urllib.request.urlopen(f'http://qt.gtimg.cn/q={code}', timeout=15).read().decode('gbk', errors='ignore').split('=',1)[1].strip().strip('"').split('~')
cur = float(f[3])

print(f'日内振幅均值={ma*100:.2f}% 波动={sa*100:.2f}%')
for k in [1, 1.5, 2]:
    rng = ma + k * sa
    print(f'  {k}σ: 高≈{cur*(1+rng):.3f} 低≈{cur*(1-rng):.3f}')

# 近20日最大单日振幅（极端框）
mx = max(amp[-20:])
print(f'  极端(近20日最大振幅{mx*100:.1f}%): 高≈{cur*(1+mx):.3f} 低≈{cur*(1-mx):.3f}')
```

## ⚠️ 局限（必须告知用户）
1. **统计区间，不是预测**：白银LOF 年化波动 ~78%，盘中 ±10% 都正常；区间仅表示"大概率范围内"，极端行情会突破。
2. **正态假设 + 振幅独立假设**：真实有肥尾，极端跌/涨概率实际可能更高。
3. **必须标注"不是预测"**：用户容易把区间当目标价。输出时明确"统计概率区间，非预测"。
4. 与 GBM 路径触及（"今天会不会摸到 X"）互补：本方法是"今天的 H/L 大概在哪"，GBM 是"特定价触发概率"。

## 与用户持仓账的结合
算完区间后，若用户有成本（如 161226 成本 1.839、当前 1.841）：
- 当前最低已逼近成本线 → 提示"几乎没有安全垫"
- 区间下界 < 成本 → "今天有 X% 概率名义浮亏"
- 区间上界 > 成本保本价 → "反弹到成本上方是减仓窗口，别等更高"
