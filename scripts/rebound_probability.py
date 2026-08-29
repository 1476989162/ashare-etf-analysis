#!/usr/bin/env python3
"""
rebound_probability.py — 计算 N 交易日内某基金从当前价反弹 X 元的概率

方法: 取近 ~120 日日K线, 用对数收益率正态模型:
  - 收盘达概率 (p_close): N日累计收益 >= need 的正态概率
  - 盘中达概率 (p_any_high): N日内任一日最高价触及目标的概率 = 1 - P(单日未达)^N

依赖: curl (腾讯K线API web.ifzq.gtimg.cn), Python 3.8+ (statistics.NormalDist)

用法 (单只):
  python scripts/rebound_probability.py sh518880 8.597 0.30 15
  python scripts/rebound_probability.py sz161226 1.872 0.30 15

输出 JSON:
  {"sym":"sh518880","cur":8.597,"target":8.897,"need_pct":3.49,
   "mu_daily_pct":-0.095,"sigma_daily_pct":2.361,
   "p_close":29.6,"p_any_high":59.0}

批量 (逗号分隔 code:price:target[:days]):
  python scripts/rebound_probability.py --batch "sh518880:8.597:0.30:15,sz161226:1.872:0.30:15"

注: 代码前缀 sh/sz 必须正确 (51x/56x/58x→sh, 15x/16x/50x→sz)。
     模型为历史波动率正态近似, 非价格预测, 仅供参考。
"""
import subprocess, json, math, sys
from statistics import NormalDist

API = "https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={},day,,,120"

def fetch_kline(sym):
    url = API.format(sym)
    out = subprocess.run(["curl", "-s", url, "-H", "User-Agent: Mozilla/5.0"],
                         capture_output=True, text=True, timeout=30).stdout
    data = json.loads(out)
    node = data["data"][sym]
    rows = node.get("day") or node.get("qfqday") or []
    if not rows:
        raise ValueError(f"{sym}: K线数据为空")
    closes = [float(r[2]) for r in rows]
    highs = [float(r[3]) for r in rows]
    return closes, highs

def analyze(sym, cur, target_abs, days=15):
    closes, highs = fetch_kline(sym)
    n = len(closes)
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, n)]
    mu = sum(rets) / len(rets)
    sigma = math.sqrt(sum((r - mu) ** 2 for r in rets) / len(rets))
    need = math.log((cur + target_abs) / cur)
    muD = mu * days
    sigD = sigma * math.sqrt(days)
    p_close = 1 - NormalDist(muD, sigD).cdf(need)
    hr = [math.log(highs[i] / closes[i - 1]) for i in range(1, n)]
    hmu = sum(hr) / len(hr)
    hsig = math.sqrt(sum((r - hmu) ** 2 for r in hr) / len(hr))
    z = (need - hmu) / hsig
    p_day = NormalDist(0, 1).cdf(z)
    p_any = 1 - (p_day ** days)
    return dict(sym=sym, cur=cur, target=round(cur + target_abs, 4),
                need_pct=round(need * 100, 2),
                mu_daily_pct=round(mu * 100, 3),
                sigma_daily_pct=round(sigma * 100, 3),
                p_close=round(p_close * 100, 1),
                p_any_high=round(p_any * 100, 1))

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--batch":
        for item in sys.argv[2].split(","):
            parts = item.split(":")
            sym, cur, tgt = parts[0], float(parts[1]), float(parts[2])
            days = int(parts[3]) if len(parts) > 3 else 15
            print(json.dumps(analyze(sym, cur, tgt, days), ensure_ascii=False))
    elif len(sys.argv) >= 4:
        sym = sys.argv[1]
        cur = float(sys.argv[2])
        tgt = float(sys.argv[3])
        days = int(sys.argv[4]) if len(sys.argv) > 4 else 15
        print(json.dumps(analyze(sym, cur, tgt, days), ensure_ascii=False))
    else:
        print("usage: rebound_probability.py <sh/szCODE> <price> <abs_target> [days]")
        print("   or: rebound_probability.py --batch \"sh518880:8.597:0.30:15,...\"")
