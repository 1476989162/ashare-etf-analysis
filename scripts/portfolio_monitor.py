#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF Portfolio Batch Monitor — Cron-ready script for real-time portfolio tracking.

Usage:
    python portfolio_monitor.py                          # use default portfolio below
    python portfolio_monitor.py --portfolio my_etf.json  # load custom portfolio

Output: Full monitoring report matching user's 6-item format:
    1. Current price, change%, P&L%
    2. Bid1/Ask1
    3. Suggestion (buy/sell/做T/hold)
    4. Buy point → Sell point (paired)
    5. Stop loss (unconditional liquidation line)
    6. Most-likely-to-fill sell price

Strategy: 不认亏卖，做T降本为主.

Compatible with Hermes cron jobs where execute_code is blocked.
Run via: terminal("python C:/Users/Administrator/ashare-etf-analysis/scripts/portfolio_monitor.py")
"""

import json
import re
import sys
import urllib.request
from datetime import datetime

# ── Default portfolio (user's actual positions) ──────────────────────────
DEFAULT_PORTFOLIO = {
    "562500": {"name": "机器人ETF华夏", "cost": 1.139, "shares": 7000, "t_type": "T+1"},
    "159326": {"name": "电网设备ETF华夏", "cost": 2.180, "shares": 5000, "t_type": "T+1"},
    "513730": {"name": "东南亚科技ETF", "cost": 1.144, "shares": 5000, "t_type": "T+0"},
    "513520": {"name": "日经ETF华夏", "cost": 2.517, "shares": 5000, "t_type": "T+0"},
    "513500": {"name": "标普500ETF博时", "cost": 2.499, "shares": 2000, "t_type": "T+0"},
    "159865": {"name": "养殖ETF国泰", "cost": 0.499, "shares": 2000, "t_type": "T+1"},
    "512400": {"name": "有色金属ETF南方", "cost": 2.2107, "shares": 25300, "t_type": "T+1"},
    "518880": {"name": "黄金ETF华安", "cost": 9.6332, "shares": 3800, "t_type": "T+0"},
    "161226": {"name": "国投白银LOF", "cost": 2.8397, "shares": 33800, "t_type": "T+1"},
    "159126": {"name": "港股通50ETF南方", "cost": None, "shares": 0, "t_type": "观望"},
}

# ── Tencent API field parsing ─────────────────────────────────────────────
def parse_tencent_quote(line):
    """Parse a single Tencent API response line. Returns dict or None."""
    m = re.match(r'v_(\w+)="(.+)"', line.strip())
    if not m:
        return None
    code = re.sub(r'^sh|^sz', '', m.group(1))
    parts = m.group(2).split('~')
    # ponytail: qt.gtimg.cn 2026-08-27 实测确认 — 所有 sz/sh 前缀ETF,
    # parts[9]=买一价, parts[19]=卖一价, 无需 parts[0] 偏移.
    # 旧版 offset 逻辑(offset=1 if parts[0] in ('51','0'))会偏到 [8]/[18]=量级整数,
    # 导致 sz15/16/50 系列全部报"ask1<=bid1"被丢弃 (159326/161226/159865/159126).
    # 升级路径: 若腾讯改API字段顺序, 恢复偏移检测; 当前 offset=0 是唯一正确值.

    try:
        current = float(parts[3])
        prev_close = float(parts[4])
        high = float(parts[33])
        low = float(parts[34])
        change_pct = float(parts[32])
        bid1 = float(parts[9])
        ask1 = float(parts[19])
        bid1_qty = int(float(parts[8]))
        ask1_qty = int(float(parts[18]))

        # Cross-validation
        if not (low <= current <= high):
            raise AssertionError(f"current {current} not in [{low}, {high}]")
        if not (ask1 > bid1):
            raise AssertionError(f"ask1 {ask1} <= bid1 {bid1}")

        return {
            'code': code,
            'name': parts[1],
            'current': current,
            'prev_close': prev_close,
            'high': high,
            'low': low,
            'change_pct': change_pct,
            'bid1': bid1,
            'ask1': ask1,
            'bid1_qty': bid1_qty,
            'ask1_qty': ask1_qty,
        }
    except (ValueError, IndexError, AssertionError) as e:
        print(f"WARN: Parse error for {code}: {e}", file=sys.stderr)
        return None


def fetch_quotes(codes_str):
    """Fetch real-time quotes from Tencent API. Returns dict keyed by code."""
    url = f"https://qt.gtimg.cn/q={codes_str}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode('gbk', 'ignore')

    result = {}
    for line in raw.strip().split(';'):
        line = line.strip()
        if not line:
            continue
        q = parse_tencent_quote(line)
        if q:
            result[q['code']] = q
    return result


def compute_analysis(code, quote, portfolio):
    """Compute trading analysis for a single ETF."""
    p = portfolio[code]
    cost = p['cost']
    shares = p['shares']
    t_type = p['t_type']
    cur = quote['current']
    bid1 = quote['bid1']
    ask1 = quote['ask1']
    low = quote['low']
    high = quote['high']

    analysis = {
        'code': code,
        'name': p['name'],
        't_type': t_type,
        'cost': cost,
        'shares': shares,
        'current': cur,
        'change_pct': quote['change_pct'],
        'bid1': bid1,
        'ask1': ask1,
        'high': high,
        'low': low,
    }

    if cost and shares > 0:
        pnl_pct = (cur - cost) / cost * 100
        pnl_amt = (cur - cost) * shares
        analysis['pnl_pct'] = pnl_pct
        analysis['pnl_amt'] = pnl_amt
        analysis['pnl_per_share'] = cur - cost
    else:
        analysis['pnl_pct'] = None
        analysis['pnl_amt'] = None

    # Suggestion logic: 不认亏卖，做T降本
    if t_type == '观望':
        analysis['suggestion'] = '观望'
        analysis['action'] = '等待企稳信号'
    elif pnl_pct is not None and pnl_pct >= 3:
        analysis['suggestion'] = '持有/部分止盈'
        analysis['action'] = '可出一部分锁利'
    elif pnl_pct is not None and pnl_pct >= -1:
        analysis['suggestion'] = '做T' if t_type == 'T+0' else '持有'
        analysis['action'] = '微盈微亏，做T降本' if t_type == 'T+0' else '持有不动'
    elif pnl_pct is not None and pnl_pct >= -3:
        analysis['suggestion'] = '做T' if t_type == 'T+0' else '持有'
        analysis['action'] = '轻套做T' if t_type == 'T+0' else '持有等反弹'
    else:
        analysis['suggestion'] = '做T' if t_type == 'T+0' else '持有'
        analysis['action'] = '深套做T降本' if t_type == 'T+0' else '持有不动(不割肉)'

    # Buy/sell points — paired (买→卖), sell ≥ break-even (用户铁律)
    if t_type == '观望':
        analysis['buy_point'] = f"{bid1:.3f}-{bid1 + 0.005:.3f}"
        analysis['sell_point'] = f"{ask1:.3f}-{ask1 + 0.005:.3f}"
    elif cost is not None and pnl_pct is not None and pnl_pct < -10:
        # Deep trapped: cost×1.0015 = 保本价; 卖点必须≥保本价（用户铁律）
        break_even = cost * 1.0015
        analysis['buy_point'] = f"{low:.3f}-{low + 0.005:.3f}"
        if break_even > high:
            # 保本价超出今日高点 → 日内无法保本，只给做T降本区间，标注保本价
            t_buy = low + 0.002
            t_sell = min(high, cur * 1.03)
            analysis['sell_point'] = f"{t_buy:.3f}→{t_sell:.3f}(做T降本)"
            analysis['break_even'] = break_even
            analysis['break_even_note'] = f"保本价{break_even:.4f}超出今日高点{high}，日内难以保本，建议分批做T降本"
        else:
            # 保本价今日可达 → 卖点锚定保本价，卖出即保本（不高于现价+5%）
            analysis['sell_point'] = f"{break_even:.3f}-{min(break_even + 0.005, cur * 1.05):.3f}"
    elif t_type == 'T+0':
        analysis['buy_point'] = f"{bid1:.3f}-{bid1 + 0.003:.3f}"
        analysis['sell_point'] = f"{ask1:.3f}-{ask1 + 0.003:.3f}"
    else:
        analysis['buy_point'] = f"{bid1:.3f}-{bid1 + 0.005:.3f}"
        analysis['sell_point'] = f"{ask1:.3f}-{ask1 + 0.005:.3f}"

    # Stop loss: 成本 × 0.95（用户铁律: 5%无条件清仓线，统一用 0.95 不漂移）
    if cost:
        analysis['stop_loss'] = round(cost * 0.95, 4)
    else:
        analysis['stop_loss'] = None

    # Most-likely-to-fill sell price — anchored to ASK1 (卖一价), not bid1
    # ponytail: portfolio-monitoring-template.md 明确纠正: "卖出点=卖一价上方0.001~0.005,旧模板写买一价上方是错的"
    analysis['immediate_sell'] = f"{ask1:.3f}"
    analysis['likely_sell'] = f"{ask1 + 0.001:.3f} ~ {ask1 + 0.003:.3f}"

    return analysis


def generate_report(analyses, total_pnl, timestamp):
    """Generate the full monitoring report."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"  ETF持仓实时监控分析 | {timestamp}")
    lines.append("=" * 70)

    for a in analyses:
        lines.append(f"\n{'─' * 60}")
        lines.append(f"【{a['code']} {a['name']}】({a['t_type']})")
        lines.append(f"{'─' * 60}")

        if a['pnl_pct'] is not None:
            sign = '+' if a['pnl_pct'] >= 0 else ''
            lines.append(f"  成本: {a['cost']}  持仓: {a['shares']:,}份")
            lines.append(f"  现价: {a['current']}  涨跌: {a['change_pct']:+.2f}%")
            lines.append(f"  浮盈亏: {sign}{a['pnl_pct']:.2f}% ({a['pnl_amt']:+,.0f}元)")
        else:
            lines.append(f"  现价: {a['current']}  涨跌: {a['change_pct']:+.2f}%")
            lines.append(f"  无持仓，观望")

        lines.append(f"  买一: {a['bid1']}  卖一: {a['ask1']}")
        lines.append(f"  今日区间: {a['low']} ~ {a['high']}")
        lines.append(f"  ─────────────────────────────────")
        lines.append(f"  ★ 建议: {a['suggestion']}")
        lines.append(f"  ★ 操作: {a['action']}")
        lines.append(f"  ★ 买入点: {a['buy_point']} → 卖出点: {a['sell_point']}")
        if a['stop_loss']:
            lines.append(f"  ★ 止损价: {a['stop_loss']}  ← 无条件清仓线")
        lines.append(f"  ★ 大概率卖价: {a['likely_sell']} (卖一上方+0.001~0.003)")

    lines.append(f"\n{'=' * 70}")
    lines.append(f"汇总:")
    lines.append(f"{'=' * 70}")
    lines.append(f"  总浮盈亏: {total_pnl:+,.0f}元")
    lines.append(f"  策略: 不认亏卖 | 做T降本 | 严格止损")
    lines.append(f"")
    lines.append(f"⚠️ 风险提示：以上建议基于技术面分析，不构成投资建议。")
    lines.append(f"⚠️ 止损价是底线，跌破无条件清仓，不认亏卖是策略不是死扛。")

    return '\n'.join(lines)


def main():
    # Load portfolio
    portfolio = DEFAULT_PORTFOLIO
    if len(sys.argv) > 2 and sys.argv[1] == '--portfolio':
        with open(sys.argv[2], 'r', encoding='utf-8') as f:
            portfolio = json.load(f)

    # Build codes string (sh for 51/56/58, sz for 15/16/50)
    codes_parts = []
    for code in portfolio:
        if code.startswith(('51', '56', '58')):
            codes_parts.append(f"sh{code}")
        else:
            codes_parts.append(f"sz{code}")
    codes_str = ','.join(codes_parts)

    # Fetch quotes
    quotes = fetch_quotes(codes_str)

    # Analyze each
    analyses = []
    total_pnl = 0.0
    for code in portfolio:
        if code not in quotes:
            print(f"WARN: No quote for {code}", file=sys.stderr)
            continue
        a = compute_analysis(code, quotes[code], portfolio)
        analyses.append(a)
        if a['pnl_amt']:
            total_pnl += a['pnl_amt']

    # Sort: worst loss first
    analyses.sort(key=lambda x: x['pnl_amt'] if x['pnl_amt'] is not None else 0)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    report = generate_report(analyses, total_pnl, timestamp)
    print(report)


if __name__ == '__main__':
    main()
