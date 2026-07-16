# A股宽基指数量化参数计算

> 生成日期：2026-07-15。数据源：腾讯实时行情 qt.gtimg.cn + 腾讯K线 web.ifzq.gtimg.cn（前复权）。
> 用途：当用户要求"量化参数分析"/"技术指标"时，批量计算六大宽基指数的趋势/动量/波动/资金面信号。

## 数据获取（已验证可用）

```python
import urllib.request, json, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

# 1) 实时行情（字段见下方"实时字段映射"）
url = f'https://qt.gtimg.cn/q=sh000300'   # 逗号可并列多只
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
data = urllib.request.urlopen(req, timeout=15, context=ctx).read().decode('gbk', errors='ignore')
# 解析：v_sh000300="1~名称~代码~现价~昨收~今开..."; 用 ~ 分隔

# 2) K线（前复权，250交易日，足够算 MA120/MA250）
url = f'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000300,day,,,250,qfq'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
data = urllib.request.urlopen(req, timeout=20, context=ctx).read().decode('utf-8', errors='ignore')
j = json.loads(data)
days = j['data']['sh000300']['day']   # [[日期,开,收,高,低,量], ...]
```

**端点注意**：K线用 `web.ifzq.gtimg.cn/appstock/app/fqkline/get`（本会话 2026-07-15 实测可用），不是 proxy.finance.qq.com。K 线为前复权（qfq）。

### 实时字段映射（qt.gtimg.cn 的 ~ 分隔）
| 索引 | 含义 |
|------|------|
| [3] | 现价 |
| [4] | 昨收 |
| [32] | 涨跌幅% |
| [33]/[34] | 高/低 |
| [77] | 溢价率（指数通常为空） |
| [80]/[81] | 年高/年低（宽基指数） |
| [30] | 交易日时间戳 |

**指数代码前缀**：sh000300(沪深300)、sh000001(上证指数)、sh000905(中证500)、sh000852(中证1000)、sh000016(上证50)、sz399006(创业板指)。

## 标准量化指标计算（纯Python，无numpy依赖）

所有指标基于 closes = [close, ...] 序列（按时间升序，[-1]为最新）。

### 1. 移动平均线 MA
```python
def ma(closes, n):
    return sum(closes[-n:])/n if len(closes) >= n else None
```
计算 MA5 / MA10 / MA20 / MA60 / MA120。

### 2. EMA 序列（MACD 基础）
```python
def ema_series(values, n):
    alpha = 2/(n+1); result = values[:n]; e = sum(values[:n])/n
    for v in values[n:]:
        e = v*alpha + e*(1-alpha); result.append(e)
    return result
```

### 3. MACD
```python
def calc_macd(closes):
    ema12 = ema_series(closes, 12); ema26 = ema_series(closes, 26)
    dif = [e12-e26 for e12,e26 in zip(ema12, ema26)]
    dea = ema_series(dif, 9)
    macd = [2*(d-d2) for d,d2 in zip(dif, dea)]
    return dif[-1], dea[-1], macd[-1]   # DIF, DEA, MACD柱
```
- 金叉 = DIF > DEA；死叉 = DIF < DEA
- MACD柱 为正值且扩大 → 多头动能增强

### 4. RSI(14) — 平滑型（Wilder RMA）
```python
def calc_rsi(closes, n=14):
    if len(closes) < n+1: return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        c = closes[i]-closes[i-1]; gains.append(max(c,0)); losses.append(max(-c,0))
    avg_gain = sum(gains[:n])/n; avg_loss = sum(losses[:n])/n
    for g,l in zip(gains[n:], losses[n:]):
        avg_gain = (avg_gain*(n-1)+g)/n; avg_loss = (avg_loss*(n-1)+l)/n
    if avg_loss == 0: return 100
    rs = avg_gain/avg_loss; return 100 - 100/(1+rs)
```
> 70 = 超买；30 = 超卖；40-60 = 中性

### 5. Bollinger Bands (20, 2σ)
```python
def calc_boll(closes, n=20, k=2):
    if len(closes) < n: return None, None, None
    m = sum(closes[-n:])/n
    var = sum((c-m)**2 for c in closes[-n:])/n
    std = (var ** 0.5)
    return m-k*std, m, m+k*std   # 下轨, 中轨(MA20), 上轨
```

### 6. ATR(14) — 平均真实波动幅度
```python
def calc_atr(klines, n=14):
    trs = []
    for i in range(1, len(klines)):
        h,l,pc = klines[i]['high'], klines[i]['low'], klines[i-1]['close']
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    return sum(trs[-n:])/n
```
> ATR/current 即当前波动率（%），用于止损/止盈幅度设置

### 7. ADX(14) — 趋势强度
```python
def calc_adx(klines, n=14):
    trs=[]; dm_pos=[]; dm_neg=[]
    for i in range(1, len(klines)):
        h,l,ph,pl = klines[i]['high'],klines[i]['low'],klines[i-1]['high'],klines[i-1]['low']
        trs.append(max(h-l,abs(h-ph),abs(l-pl)))
        pui=h-ph; nui=pl-l
        dm_pos.append(max(0,pui) if pui>nui else 0)
        dm_neg.append(max(0,nui) if nui>pui else 0)
    def sm(arr,m):
        s=sum(arr[:m]); res=[s]
        for i in range(m,len(arr)): s=s+arr[i]-arr[i-m]; res.append(s)
        return res
    smtr=sm(trs,n); sp=sm(dm_pos,n); sn=sm(dm_neg,n)
    di_p=[100*sp[i]/smtr[i] if smtr[i]>0 else 0 for i in range(len(sp))]
    di_n=[100*sn[i]/smtr[i] if smtr[i]>0 else 0 for i in range(len(sn))]
    dx=[100*abs(di_p[i]-di_n[i])/(di_p[i]+di_n[i]) if (di_p[i]+di_n[i])>0 else 0 for i in range(len(di_p))]
    adx=sum(dx[-n:])/n
    return adx, di_p[-1], di_n[-1]
```
> ADX>25 = 趋势强；DI+>DI- = 多头主导；反之空头主导

### 8. 动量（Momentum）
```python
def calc_momentum(closes, n):
    return (closes[-1]-closes[-1-n])/closes[-1-n]*100   # n日动量%
```
计算 mom5 / mom10 / mom20。

### 9. 成交量比（量比简化版）
```python
avg_vol7 = sum(vols[-7:])/7
vol_ratio = vols[-1]/avg_vol7   # >1.5 放量; <0.7 缩量; 0.7-1.5 平量
```

## 综合判断规则

| 指标组合 | 信号 |
|----------|------|
| MA5>MA10>MA20>MA60 | 多头均线排列 |
| MA5<MA10<MA20<MA60 | 空头均线排列 |
| 金价位 > MA20 且 MACD金叉 | 偏多 |
| 金价位 < MA20 且 MACD死叉 | 偏空 |
| ADX<25 且均线乱序 | 横盘震荡（无明确方向） |
| RSI<30 + 空头排列 | 超卖，警惕反弹（但勿盲目抄底） |
| RSI>70 + 多头排列 | 超买，警惕回调（顺势持有多头趋势仍优先） |

## 信号解读优先级（与趋势优先铁律一致）
1. **趋势/动量是第一筛选因子**（ADX+MACD+动量+均线排列）
2. **位置（RSI/BOLL偏离）是辅助**，不与趋势矛盾时参考
3. **ADX<25 的横盘信号**：此时不宜给明确买卖方向，只给区间参考

## 输出模板
```
{指数} | 最新收盘: {C} | 今日涨跌幅: {X}%
  均线: MA5={m5} MA10={m10} MA20={m20} MA60={m60} MA120={m120}
  现价偏离: vsMA20={Y}%  vsMA60={Z}%
  均线排列: 多头/空头/其他
  MACD: DIF={d} DEA={e} MACD柱={v}  金叉/死叉
  RSI14={r}  [超买>70/超卖<30/中性]
  BOLL20: 下轨/中轨/上轨  现价vs中轨={P}%
  ATR14={a} ({p}%)
  ADX={ad}  DI+={dp}  DI-={dn}  [趋势强>25/趋势弱]
  动量: 5日={p5}  10日={p10}  20日={p20}
  成交量比(7日均)={vr}  [放量/缩量/平量]
```

## 2026-07-15 实测结果（收盘）
| 指数 | 收盘 | 涨% | MA20偏 | MA60偏 | MACD | RSI14 | ADX | DI-/DI+ | 20日动量 |
|------|------|-----|--------|--------|------|-------|-----|---------|----------|
| 沪深300 | 4786.78 | -0.20% | -1.84% | -1.41% | 死叉 | 46.7 | 20.8 | 26.6/14.0 | -2.00% |
| 上证指数 | 3955.58 | -0.29% | -2.27% | -3.14% | 死叉 | 42.0 | 28.5 | 37.7/11.5 | -3.33% |
| 中证500 | 8147.58 | -1.55% | -5.77% | -4.15% | 死叉 | 40.9 | 33.0 | 36.7/14.7 | -4.24% |
| 中证1000 | 7817.83 | -1.35% | -7.86% | -8.02% | 死叉 | 35.4 | 36.1 | 46.5/12.0 | -9.58% |
| 创业板指 | 3804.70 | -1.21% | -6.74% | -3.66% | 死叉 | 43.0 | 28.9 | 30.5/10.5 | -7.27% |
| 上证50 | 2967.07 | +0.39% | +0.53% | +0.81% | 金叉 | 52.8 | 28.1 | 23.5/18.4 | +1.82% |

> 结论：除上证50外五大指数一致 MACD死叉+跌破MA20+动量负值，量化信号偏空；上证50唯一金叉红盘，大蓝筹相对抗跌。