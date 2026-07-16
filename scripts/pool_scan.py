"""
pool_scan.py — 全池趋势优先扫描 (ashare-etf-analysis 技能配套)

按用户2026-07-13铁律重排「趋势 > 国别」批量扫描ETF池：
  - 拉实时行情(腾讯qt.gtimg.cn,含IOPV[81]算真实溢价)
  - 拉K线(优先 web.ifzq.gtimg.cn, 失败回退 proxy 端点, 双重json.loads解代理二次编码)
  - 算 趋势评分(20日动量权重最高) + RSI + MA排列 + 位置%
  - 趋势强(MA多头+20日动量正)的A股ETF照样给买卖点, 不因"非境外"排除
  - 输出: 趋势排名 + 每只 买点(回踩MA20)/卖点(阶段高)/止损(买点*0.95)

用法: python scripts/pool_scan.py 513310 160140 513730 164701 518800 159934 161226 512400 159599
      (不带参数则用 POOL 默认池)
"""
import json, urllib.request, re, time, sys

POOL = ["513310","160140","513730","164701","518800","159934","161226","512400","159599"]
T0 = {"518800","164701","513310","513730","160140","513600","513500"}  # T+0 权威列表(技能)

def prefix(c):
    return ("sh"+c) if c.startswith(("51","56","58","6","9")) else ("sz"+c)

def qt(code):
    sym=prefix(code)
    for _ in range(4):
        try:
            with urllib.request.urlopen(f"https://qt.gtimg.cn/q={sym}", timeout=15) as r:
                raw=r.read().decode("gbk","ignore")
            return re.search(r'="(.*)";', raw).group(1).split("~")
        except Exception:
            time.sleep(0.7)
    return None

def kline(code, days=120):
    sym=prefix(code)
    urls=[
        f"https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={sym},day,,,{days}",
        f"https://proxy.finance.qq.com/ifzqgtimg/app/kline/kline?param={sym},day,,,{days}",
    ]
    for url in urls:
        for _ in range(4):
            try:
                with urllib.request.urlopen(url, timeout=15) as r:
                    d=json.loads(r.read().decode("utf-8","ignore"))
                data=d["data"]
                if isinstance(data,str): data=json.loads(data)
                sub=data[sym]
                if isinstance(sub,str): sub=json.loads(sub)
                return sub["day"]
            except Exception:
                time.sleep(1)
    return None

def f(p,i):
    try: return float(p[i])
    except Exception: return None

def main():
    codes = sys.argv[1:] or POOL
    rows=[]
    for code in codes:
        p=qt(code); k=kline(code)
        if not p or not k:
            print(f"{code:<7} 行情或K线失败"); continue
        name=p[1]; price=f(p,3); chg=f(p,32); iopv=f(p,81)
        premium=(price/iopv-1)*100 if iopv else None
        ts=p[30]+" "+p[31]
        closes=[float(x[2]) for x in k]; cur=closes[-1]
        m5=sum(closes[-5:])/5; m20=sum(closes[-20:])/20
        madir=(m5/m20-1)*100
        g=[max(c-b,0) for b,c in zip(closes,closes[1:])]
        l=[max(b-c,0) for b,c in zip(closes,closes[1:])]
        ag=sum(g[-14:])/14; al=sum(l[-14:])/14; rs=ag/al; rsi=100-100/(1+rs)
        mom5=(cur/closes[-6]-1)*100; mom20=(cur/closes[-21]-1)*100
        hi=max(closes); lo=min(closes); pos60=(cur-lo)/(hi-lo)*100 if hi>lo else 0
        t1 = "T+0" if code in T0 else "T+1"
        trend = mom20*100*2.0 + mom5*100*1.3 + madir*100*1.5
        pos_s = (1-pos60/100)*15
        prem_s = -max(0,(premium or 0)-2)*3 if premium is not None else 0
        total = trend + pos_s + prem_s
        buy=round(m20,3); sell=round(hi,3); stop=round(buy*0.95,3)
        rows.append(dict(code=code,name=name,price=price,chg=chg,prem=prem,ts=ts,
                         rsi=rsi,pos60=pos60,mom5=mom5,mom20=mom20,madir=madir,
                         t1=t1,total=total,buy=buy,sell=sell,stop=stop))
    rows.sort(key=lambda x:-x["total"])
    print(f"{'代码':<7}{'名称':<14}{'时间':<15}{'机制':<5}{'趋势':>8}{'溢价%':>7}{'现价':>7}{'买(MA20)':>9}{'卖(阶段高)':>11}{'止损':>7}  备注")
    print("-"*120)
    for r in rows:
        trend_word = "🟢多" if r["mom20"]>0 else "🔻空"
        note=[]
        if r["prem"] is not None and r["prem"]>5: note.append(f"⚠溢价+{r['prem']:.1f}%买入即亏")
        if r["pos60"]>75: note.append("位置偏高")
        if r["pos60"]<15: note.append("低位")
        if r["t1"]=="T+1": note.append("非T+0")
        print(f"{r['code']:<7}{r['name']:<14}{r['ts']:<15}{r['t1']:<5}{trend_word}{r['mom20']:>+6.1f}%"
              f"{r['prem']:>7.2f}{r['price']:>7.3f}{r['buy']:>9.3f}{r['sell']:>11.3f}{r['stop']:>7.3f}  {';'.join(note)}")
    print("\n=== 趋势排名(趋势>国别: 强多头A股ETF照给点,不因非境外排除; 原油/能源除外) ===")
    for r in rows:
        tw="🟢多头" if r["mom20"]>0 else "🔻空头"
        print(f"{r['code']} {r['name']:<12} 评分{r['total']:>7.1f} | {tw} MA{r['madir']:+.1f}% 20日{r['mom20']:+.1f}% RSI{r['rsi']:.0f} 溢价{(r['prem'] if r['prem'] is not None else 0):+.1f}% {r['t1']}")

if __name__=="__main__":
    main()
