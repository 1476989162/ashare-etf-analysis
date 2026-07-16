# GBM 买卖点概率分析 (闭式解, 区别于蒙特卡洛路径触发)

场景: 用户问"XX 的买入点/卖出点,给出概率"(如 2026-07-10 用户要求固化 161226 买卖点概率)。
这类"T日内价格是否触及某价位 / 落入某区间"问题,用**几何布朗运动闭式解**比蒙特卡洛更快、可复现。

## 与技能内蒙特卡洛方法的区别
- 技能已有 `N天内是否会触达X价(GBM 最小价蒙特卡洛)` —— 适用**日内剩余时段路径**(分钟级,取路径 min/max)。
- 本文件方法 —— 适用**日尺度 T 日**(T=5/10/20),闭式 first-passage / 收盘落区概率,无需随机种子。
- 两者互补: 日内触达用蒙特卡洛; 跨日买卖点概率用本闭式法。

## 方法 (基于真实日K线)
1. 拉腾讯K线 ~120日 → 对数收益率 `ret = log(close[i]/close[i-1])`
2. `mu = mean(ret)` (日漂移), `sigma = stdev(ret)` (日波动)
3. 闭式公式:
```python
import math
def cdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
def p_hit_upper(S0, H, mu, sigma, T):   # T日内盘中曾触及 H(>S0)
    x0, b = math.log(S0), math.log(H)
    d1 = (mu*T + x0 - b) / (sigma*math.sqrt(T))
    d2 = (mu*T - x0 + b) / (sigma*math.sqrt(T))
    return cdf(d1) + math.exp(2*mu*(b-x0)/sigma**2) * cdf(d2)
def p_hit_lower(S0, L, mu, sigma, T):   # T日内盘中曾触及 L(<S0)
    x0, a = math.log(S0), math.log(L)
    d1 = (mu*T + x0 - a) / (sigma*math.sqrt(T))
    d2 = (mu*T - x0 + a) / (sigma*math.sqrt(T))
    return cdf(d1) + math.exp(2*mu*(a-x0)/sigma**2) * cdf(d2)
def p_close_in(S0, Lo, Hi, mu, sigma, T):  # T日内收盘价落入 [Lo,Hi]
    mT, sT = mu*T, sigma*math.sqrt(T)
    return (cdf((math.log(Hi/S0) - mT)/sT) - cdf((math.log(Lo/S0) - mT)/sT)) * 100
```

## 两种口径的区别 (关键! 易踩坑)
- **触 barrier (p_hit_*)**: "T日内盘中曾到过该价"。对高波动品种(σ~5%/日, 如 161226) **几乎必然(1周~98%)**, 数值虚高、不实用, 只说明"迟早会到"。
- **收盘落区 (p_close_in)**: "T日内收盘价稳定落在买/卖区"。白银这类高波动品种只有 **3-8%**, 才是真实可操作概率。
- **报告规则**: 默认报 **p_close_in(收盘落区)**; 触 barrier 仅作"挂条件单能否盘中触发"的参照(高波动下盘中触发概率高 → 挂单比等收盘实用)。
- 若闭式算出触 barrier = 100%/99%, 不要当成"一定能成交在买区", 要改报收盘落区概率。

## 161226 固化买卖点 (2026-07-10 用户明确要求"固化")
```python
DEFAULT_POINTS = {
  '161226': {
    'buys':  {'B1 理想区 1.67-1.72': (1.67, 1.72), 'B3 次买 1.78-1.80': (1.78, 1.80)},
    'sells': {'S1 第一卖 1.89-1.92': (1.89, 1.92), 'S2 压力 2.05-2.10': (2.05, 2.10)},
  },
}
```
实测(现价 1.859, σ=4.91%/日, μ=-0.203%/日, 120交易日):
- 收盘落区: 买区 1周8% / 1月5%; 卖区 1周5% / 1月3%
- 触 barrier: 买区 1周98% / 1月92%; 卖区 1周83% / 1月75%

## 已固化进 scripts/fund_tool.py
- 子命令 `python scripts/fund_tool.py pts 161226` → 波动统计 + 收盘落区 + 触 barrier 双口径表
- 新增函数: `volatility(code)` / `analyze_points(code)` / `DEFAULT_POINTS`
- 加新标的买卖点: 在 `DEFAULT_POINTS` 加一行; 留空则自动用 `levels()` 支撑/压力生成买卖区
- 用法: `pts` 后接代码, 默认 161226; 全池扫描仍用无参 `python scripts/fund_tool.py`

## 局限 (报告必须标注)
- 正态/对数正态假设, 忽略肥尾 → 白银暴涨暴跌实际比模型多, 极端行情概率被低估
- μ 用历史均值, 不含基本面/商品周期
- "概率"是统计口径, 非预测; 跨境/商品 LOF 还叠加溢价收敛风险
