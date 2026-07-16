#!/usr/bin/env python3
# rebound_scan.py - 批量计算"N天内反弹X元、概率≥Y%"的ETF候选
# 用法: python rebound_scan.py [targets逗号分隔] [days]
# 例:   python rebound_scan.py 0.1,0.3 15
# 依赖: curl (terminal), 腾讯K线/实时接口, statistics
import json, math, re, subprocess, sys
from statistics import NormalDist

# === ETF池（按需扩展；sh=上海 51/56/58开头, sz=深圳 15/16/50开头）===
SYMS = {
 "sh518880":("518880","黄金ETF华安"), "sh518660":("518660","黄金ETF工银"),
 "sh518850":("518850","黄金ETF华夏"), "sh518800":("518800","黄金ETF国泰"),
 "sz159830":("159830","金ETF天弘"), "sh164701":("164701","黄金LOF"),
 "sh513500":("513500","标普500博时"), "sh513600":("513600","恒生指数"),
 "sh513520":("513520","日经ETF"), "sh513730":("513730","东南亚科技"),
 "sh513330":("513330","恒生互联网"), "sh513100":("513100","纳指ETF国泰"),
 "sh513180":("513180","恒生科技"), "sh513310":("513310","中韩半导体"),
 "sz161125":("161125","标普500LOF"), "sh160140":("160140","美国REIT"),
 "sh501312":("501312","海外科技LOF"), "sz161226":("161226","国投白银LOF"),
 "sh512400":("512400","有色金属"), "sz159819":("159819","人工智能"),
 "sh513000":("513000","日经225易方达"),
}

def fetch_realtime():
    syms = ",".join(SYMS.keys())
    out = subprocess.run(["curl","-s",f"https://qt.gtimg.cn/q={syms}","-H","User-Agent: Mozilla/5.0"],
                         capture_output=True, text=True, timeout=30).stdout
    cur = {}
    for line in out.split(";"):
        m = re.search(r'v_(\w+)="(.*)"', line)
        if not m: continue
        parts = m.group(2).split("~")
        if len(parts) < 4: continue
        try: cur[m.group(1)] = float(parts[3])
        except: pass
    return cur

def fetch_kline(sym):
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={sym},day,,,120,qfq"
    out = subprocess.run(["curl","-s",url,"-H","User-Agent: Mozilla/5.0"],
                         capture_output=True, text=True, timeout=30).stdout
    d = json.loads(out)
    node = d["data"][sym]
    key = "qfqday" if "qfqday" in node else "day"
    rows = node[key]
    closes = [float(r[2]) for r in rows]
    highs = [float(r[3]) for r in rows]
    return closes, highs

def analyze(sym, cur, targets, N):
    code, name = SYMS[sym]
    try: closes, highs = fetch_kline(sym)
    except Exception: return None
    if len(closes) < 30: return None
    rets = [math.log(closes[i]/closes[i-1]) for i in range(1,len(closes))]
    mu = sum(rets)/len(rets); var = sum((r-mu)**2 for r in rets)/len(rets); sigma=math.sqrt(var)
    hr = [math.log(highs[i]/closes[i-1]) for i in range(1,len(closes))]
    hmu = sum(hr)/len(hr); hvar=sum((r-hmu)**2 for r in hr)/len(hr); hsig=math.sqrt(hvar)
    res = {"code":code,"name":name,"cur":round(cur,4),"mu":round(mu*100,3),"sig":round(sigma*100,3)}
    for t in targets:
        need = t/cur
        pc = 1 - NormalDist(mu*N, sigma*math.sqrt(N)).cdf(need)
        z = (need - hmu)/hsig; pdh = NormalDist(0,1).cdf(z); pah = 1 - (pdh**N)
        res[f"close_{t}"] = round(pc*100,1)
        res[f"high_{t}"] = round(pah*100,1)
    return res

def main():
    targets = [float(x) for x in (sys.argv[1] if len(sys.argv)>1 else "0.1,0.3").split(",")]
    N = int(sys.argv[2]) if len(sys.argv)>2 else 15
    cur = fetch_realtime()
    print(f"# N={N}天 | 目标={targets}元 | 数据源:腾讯120日K线+实时价")
    print("code,name,cur,mu%,sig%, " + ", ".join(f"close_{t}/high_{t}" for t in targets))
    for sym in SYMS:
        if sym not in cur: continue
        r = analyze(sym, cur[sym], targets, N)
        if not r: continue
        cols = [str(r["code"]), r["name"], str(r["cur"]), str(r["mu"]), str(r["sig"])]
        for t in targets:
            cols.append(f"{r[f'close_{t}']}/{r[f'high_{t}']}")
        print(",".join(cols))

if __name__ == "__main__":
    main()
