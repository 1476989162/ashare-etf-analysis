"""
fund_tool.py —— ETF/LOF 统一分析工具（ashare-etf-analysis 技能配套，2026-07-10 实战验证）
设计原则(基于实测):
  - 历史K线 / LOF行情: 走腾讯 qt.gtimg.cn / 腾讯K线接口 (环境代理挡不住 *.eastmoney.com)
  - 溢价率(最准确): 自己算 (现价-IOPV)/IOPV*100% , 腾讯 f[81]=IOPV(ETF) / 净值(LOF)
  - 兜底: akshare fund_etf_spot_em 的 [基金折价率] (东财源, 排除NaN) ; 再兜底 腾讯 f[77]
  - 止损: 统一 5% (用户铁律 不认亏卖, 但给5%清仓线)  — 注意早期版本误用 -3%, 已改 -5%
  - 优先级评分: 溢价合规(<5%) + 趋势向上(距阶段高>-15%) + 回调至买区附近
用法:
  python fund_tool.py            # 分析默认池(含用户持仓 161226白银LOF)
  python fund_tool.py 513310 164701   # 分析指定代码(支持 sh/sz 前缀)
"""
import sys, json, urllib.request, math
from datetime import datetime

# 默认池: 用户关注的6只 + 持仓161226白银LOF
DEFAULT = ['513310', '160140', '513730', '164701', '518800', '159934', '161226']

# 腾讯 sh/sz 前缀规则: 51/56/58/6/9->sh, 15/16/50->sz (51开头必为sh)
def tprefix(code: str) -> str:
    if code.startswith(('51', '56', '58', '6', '9')):
        return 'sh' + code
    return 'sz' + code

def http_get(url, timeout=15):
    return urllib.request.urlopen(url, timeout=timeout).read()

def tx_quote(code: str):
    tc = tprefix(code)
    raw = http_get(f"http://qt.gtimg.cn/q={tc}").decode('gbk', errors='ignore')
    f = raw.strip().split('=', 1)[1].strip().strip('"').split('~')
    return {
        'code': code, 'tc': tc, 'name': f[1],
        'price': float(f[3]), 'prev_close': float(f[4]),
        'open': float(f[5]), 'high': float(f[33]), 'low': float(f[34]),
        'pct': float(f[32]), 'nav': f[81] if len(f) > 81 and f[81] else None,
        'tx_premium': float(f[77]) if len(f) > 77 and f[77] not in ('', None) else None,
        'ts': f[30] if len(f) > 30 else '',
    }

def tx_kline(code: str, start='2026-01-01', end='2027-12-31', count=1200):
    tc = tprefix(code)
    url = f"https://proxy.finance.qq.com/ifzqgtimg/appstock/app/kline/kline?param={tc},day,{start},{end},{count}"
    d = json.loads(http_get(url))
    rows = d['data'][tc].get('day') or []
    return [{'date': r[0], 'open': float(r[1]), 'close': float(r[2]),
             'high': float(r[3]), 'low': float(r[4])} for r in rows]

def ak_etf_premium():
    """返回 {code: 折价率%} 仅ETF; 失败返回空dict。NaN 跳过(513310东财节点半成品)。"""
    try:
        import akshare as ak
        df = ak.fund_etf_spot_em()
        m = {}
        for _, row in df.iterrows():
            try:
                v = row['基金折价率']
                if v == v:  # not NaN
                    m[str(row['代码'])] = float(v)
            except Exception:
                pass
        return m
    except Exception:
        return {}

def levels(klines, n=20):
    if not klines:
        return None
    recent = klines[-n:]
    closes = [k['close'] for k in recent]
    support = min(k['low'] for k in recent)
    resist = max(k['high'] for k in recent)
    peak = max(closes)
    mdd = min(c / peak - 1 for c in closes)
    return {'support': support, 'resist': resist, 'peak': peak, 'mdd': mdd,
            'start': closes[0], 'end': closes[-1]}

def analyze(codes):
    ak_prem = ak_etf_premium()
    results = []
    for code in codes:
        q = tx_quote(code)
        kl = tx_kline(code)
        lv = levels(kl, 20)
        # 溢价率优先级: ①(现价-IOPV)/IOPV ②akshare东财(排除NaN) ③腾讯f[77]
        prem = None
        if q['nav'] not in (None, '', '0.0000'):
            try:
                iopv = float(q['nav'])
                if iopv > 0:
                    prem = (q['price'] / iopv - 1) * 100
            except Exception:
                pass
        if prem is None:
            av = ak_prem.get(code)
            if av is not None:
                prem = av
        if prem is None and q['tx_premium'] is not None:
            prem = q['tx_premium']
        results.append({'q': q, 'lv': lv, 'premium': prem, 'kl_count': len(kl)})
    return results

def report(results):
    print(f"分析时间: {datetime.now():%Y-%m-%d %H:%M}  数据源: 腾讯实时+K线 / 溢价(现价-IOPV)")
    print("=" * 92)
    ranked = []
    for r in results:
        q, lv, prem = r['q'], r['lv'], r['premium']
        pm = f"{prem:+.2f}%" if prem is not None else "N/A"
        print(f"{q['code']} {q['name'][:12]:<12} | 现价{q['price']:.3f} "
              f"涨跌{q['pct']:+.2f}% | 溢价{pm} | 昨收{q['prev_close']:.3f}")
        score = None
        if lv:
            buy_lo = lv['support']
            buy_hi = round(lv['support'] * 1.02, 3)
            target = lv['resist']
            stop = round(lv['support'] * 0.95, 3)   # 止损统一 5%
            print(f"   近20日 支撑{buy_lo:.3f} 压力{target:.3f} 距阶段高{lv['mdd']*100:.1f}%")
            print(f"   买区 {buy_lo:.3f}-{buy_hi:.3f} | 目标 {target:.3f} | 止损 {stop:.3f} (-5%)")
            prem_ok = (prem is not None) and (prem < 5.0)
            trend_ok = lv['mdd'] > -15.0
            near_buy = q['price'] <= buy_hi * 1.01
            score = (1 if prem_ok else 0) + (1 if trend_ok else 0) + (1 if near_buy else 0)
            ranked.append((score, q['code'], q['name'], q['price'], prem, buy_lo, buy_hi, target, stop))
        print("-" * 92)
    ranked.sort(key=lambda x: x[0], reverse=True)
    print("\n【今日买入优先级】 评分=溢价合规(<5%)+趋势向上(距高>-15%)+回调至买区 (满分3)")
    for sc, code, name, price, prem, blo, bhi, tgt, stop in ranked:
        pm = f"{prem:+.2f}%" if prem is not None else "N/A"
        flag = "✅可买" if sc == 3 else ("⚠️观望" if sc >= 1 else "❌回避")
        print(f"  {flag} [{sc}/3] {code} {name[:10]:<10} 现价{price:.3f} 溢价{pm} "
              f"买区{blo:.3f}-{bhi:.3f} 目标{tgt:.3f} 止损{stop:.3f}")
    print("\n注: 溢价>5%一律回避(跨境/商品LOF盘中溢价=买入即亏); 黄金优先低单价(164701); 港股/原油已剔除")

if __name__ == '__main__':
    codes = sys.argv[1:] or DEFAULT
    codes = [c[2:] if c[:2] in ('sh', 'sz') else c for c in codes]
    report(analyze(codes))
