"""
trend_scan.py —— 趋势主导无偏基金扫描
用途: 用户要"找趋势好的基金/重新推荐/抛弃历史指导"时, 纯按数据排名, 不被位置/溢价/历史偏好带偏。
依赖: 同目录 fund_tool.py (提供 tx_quote / tx_kline / levels / volatility / p_hit_* / p_close_in)
数据源: 腾讯实时+K线 (经 fund_tool, 代理挡不住)

铁律(来自 2026-07-10 用户纠正'你是光看溢价的吗？不看趋势？'):
  - 趋势/动量是主导因子, 位置/溢价仅辅助
  - 趋势向下(尤其MA空头排列)的品种, 即使位置低也不能推为买点
  - GBM触barrier概率需 min(100,...) 截断

用法:
  python trend_scan.py                # 用下面 TECH 默认科技池
  python trend_scan.py 513310 159599  # 指定代码
  python trend_scan.py --all          # 用全市场 UNIVERSE
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fund_tool as ft
from datetime import datetime

TECH = {
 '513310':'中韩半导体','159599':'芯片ETF东财','512760':'芯片ETF','159995':'芯片ETF华夏',
 '588000':'科创50','588080':'科创50ETF','515050':'5GETF','159994':'5G通信ETF',
 '562500':'机器人ETF','515980':'人工智能ETF','159819':'AI智能ETF','159738':'云计算ETF',
 '513180':'恒生科技ETF','513130':'恒生科技ETF','159740':'恒生科技ETF','513870':'纳指ETF',
 '513100':'纳指ETF','159941':'纳指ETF','159915':'创业板ETF','515030':'新能源车ETF',
 '159806':'新能源车ETF','513730':'东南亚科技ETF','159892':'恒生医药','159865':'养殖ETF',
}
UNIVERSE = {**TECH, '513500':'标普500','164701':'黄金LOF','518800':'黄金ETF国泰',
            '159934':'黄金ETF易方达','518880':'黄金ETF华安','161226':'白银LOF',
            '160140':'美国REIT','510300':'沪深300','512400':'有色金属'}

def trend_metrics(kl):
    c = [k['close'] for k in kl]
    mom5  = c[-1]/c[-6]-1 if len(c) > 5 else 0
    mom20 = c[-1]/c[-21]-1 if len(c) > 20 else 0
    ma5, ma20 = sum(c[-5:])/5, sum(c[-20:])/20
    madir = ma5/ma20 - 1
    y = [k['close'] for k in kl if k['date'] >= '2026-01-01']
    pos = (c[-1]-min(y))/(max(y)-min(y)) if max(y) > min(y) else 0.5
    return mom5, mom20, madir, pos

def premium(q):
    if q['nav'] not in (None, '', '0.0000'):
        try: return (q['price']/float(q['nav'])-1)*100
        except: pass
    return q['tx_premium']

def main():
    args = sys.argv[1:]
    use_all = '--all' in args
    codes = [a for a in args if a != '--all']
    pool = UNIVERSE if use_all else TECH
    if codes:
        pool = {c: c for c in codes}
    T = 10
    print(f"分析时间: {datetime.now():%Y-%m-%d %H:%M}  趋势主导扫描(动量+均线主导, 无偏)")
    print("=" * 118)
    rows = []
    for code, name in pool.items():
        try:
            q = ft.tx_quote(code); kl = ft.tx_kline(code)
            lv = ft.levels(kl, 20); vol = ft.volatility(code)
            prem = premium(q)
            S0, sup, res = q['price'], lv['support'], lv['resist']
            m5, m20, mad, pos = trend_metrics(kl)
            trend_score = m20*100*2.0 + m5*100*1.3 + mad*100*1.5
            pos_score   = (1-pos)*15
            prem_score  = -max(0, (prem or 0)-2)*3
            total = trend_score + pos_score + prem_score
            pu = min(100, ft.p_hit_upper(S0, res, vol['mu'], vol['sigma'], T)*100)
            pl = min(100, ft.p_hit_lower(S0, sup, vol['mu'], vol['sigma'], T)*100)
            rows.append((total, code, name, S0, prem, m5*100, m20*100, mad*100, pos*100, sup, res, lv['mdd']*100, pu, pl))
        except Exception as e:
            print(f"{code} 失败: {repr(e)[:50]}")
    rows.sort(reverse=True)
    print(f"{'总分':>5} {'代码':<8} {'名称':<12} {'现价':>7} {'溢价%':>6} {'5日%':>6} {'20日%':>7} {'MA%':>6} {'位置%':>6} {'回撤%':>6}")
    for r in rows:
        tot, code, name, S0, prem, m5, m20, mad, pos, sup, res, mdd, pu, pl = r
        pm = f"{(prem or 0):+.1f}" if prem is not None else "N/A"
        print(f"{tot:5.0f} {code:<8} {name[:12]:<12} {S0:7.3f} {pm:>6} {m5:6.1f} {m20:7.1f} {mad:6.1f} {pos:6.0f} {mdd:6.1f}")
    print("\n== 趋势最强 TOP4 ==")
    for r in rows[:4]:
        tot, code, name, S0, prem, m5, m20, mad, pos, sup, res, mdd, pu, pl = r
        print(f"\n● {name} {code}  现价{S0:.3f} 溢价{(prem or 0):+.1f}% 位置{pos:.0f}%")
        print(f"   5日{m5:+.1f}% 20日{m20:+.1f}% MA排列{mad:+.1f}% 支撑{sup:.3f} 压力{res:.3f} 距高{mdd:.1f}%")
        print(f"   10日上触压力{pu:.0f}% 下触支撑{pl:.0f}%")
        print(f"   建议: 买区{sup:.3f}-{sup*1.03:.3f} 目标{res:.3f} 止损{sup*0.95:.3f}(-5%)")

if __name__ == '__main__':
    main()
