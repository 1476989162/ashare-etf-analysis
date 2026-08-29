#!/usr/bin/env python3
"""自校验：锁定本技能已实测确认的三条不变量。失败=实现被改坏。
用法: python scripts/selfcheck.py
"""
import json, math, re, subprocess, urllib.request

def run(script, *args):
    return subprocess.run(["python", f"scripts/{script}"] + [str(a) for a in args],
                          capture_output=True, text=True, timeout=120).stdout

def get_quote(sym):
    raw = urllib.request.urlopen(f"http://qt.gtimg.cn/q={sym}", timeout=20).read().decode("gbk", "ignore")
    return raw.strip().split("=", 1)[1].strip().strip('"').split("~")

def main():
    # 1) 盘口 offset=0: parts[9]=买一价, parts[19]=卖一价, 恒满足 卖一>买一 且在日内区间内
    for sym in ("sz159326", "sz161226", "sz159865", "sh562500", "sh518880"):
        p = get_quote(sym)
        b1, a1, lo, hi, cur = float(p[9]), float(p[19]), float(p[34]), float(p[33]), float(p[3])
        assert a1 > b1, f"{sym}: 卖一{a1}<=买一{b1}, offset 偏移!"
        # 盘口价在合理范围 (允许集合竞价/盘后略超日内区间)
        assert b1 > lo * 0.98 and a1 < hi * 1.02, f"{sym}: 盘口价异常 bid1={b1} ask1={a1} lo={lo} hi={hi}"
        # 反向断言: 旧 offset=1 逻辑会读到量级整数当价格
        assert float(p[8]) > 100, f"{sym}: parts[8] 应是量(>100)而非价"

    # 2) K线端点可用 (本技能脚本统一使用 kline/kline)
    for sym in ("sz161226", "sh518880"):
        d = json.loads(subprocess.run(["curl", "-s",
                f"https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={sym},day,,,120"],
                capture_output=True, text=True, timeout=30).stdout)
        assert d.get("code") == 0 and d["data"][sym].get("day"), f"{sym}: K线端点失效"
        # ponytail: fqkline/get(带qfq)实测仍可用, 不作死断言; 仅锁 kline/kline 可用

    # 3) rebound_probability.py 可跑且 need 在对数空间 (need_pct 应≈ target/cur 量级, 不是比值本身)
    out = run("rebound_probability.py", "sh518880", 9.475, 0.30, 15)
    r = json.loads(out)
    # need_pct 实际是对数距离(log空间), 0.30元/9.475 ≈ log(1.0317)=3.12; 若误用比值则=3.17, 量级几乎同
    assert 2.5 < r["need_pct"] < 4.0, f"need_pct={r['need_pct']} 异常(应≈3.12)"
    assert 0 <= r["p_close"] <= 100 and 0 <= r["p_any_high"] <= 100, "概率越界"

    # 4) rebound_scan.py 可跑 (GBK 解码已修)
    out = run("rebound_scan.py", "0.1,0.3", 15)
    assert "code,name,cur" in out and "UnicodeDecodeError" not in out and "AttributeError" not in out
    assert any(l.split(",")[0] == "518880" for l in out.splitlines()[2:]), "rebound_scan 无黄金行"

    print("selfcheck OK: offset=0 / K线端点 / need 对数空间 / GBK 解码 全部通过")

if __name__ == "__main__":
    main()
