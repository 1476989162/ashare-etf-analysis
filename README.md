# ashare-etf-analysis

A股ETF/指数基金分析框架 — 自动优化的活技能

## 特性

- 🔍 实时行情查询（腾讯财经API，一次30+只批量）
- 📊 K线/均线/支撑压力位/买卖五档盘口
- 💰 成分股/费率/规模/资金面分析
- 🎯 做T精确操作方案（买入点/卖出点/止损点）
- ⚡ T+0 ETF自动识别
- 📈 批量分析模式（10-40只全部分类输出）

## 架构

```
SKILL.md              # 技能定义（Hermes自动加载）
references/           # 实战笔记
  api-reliability-notes.md
  order-book-analysis.md
  etf-case-studies-2026-06.md
  t0-etf-trading-guide.md
  2026-06-25-etf-trading-session.md
.github/
  ISSUE_TEMPLATE/
    improvement.md    # 功能改进模板
    bug.md            # Bug报告模板
CHANGELOG.md
.hermes/improvement-queue/  # 本地改进队列（离线时使用）
```

## 自动优化机制

1. **定时扫描**（每48小时）：回顾对话历史，发现常见模式/错误/缺失功能
2. **自动建 Issue**：在 GitHub 创建改进任务
3. **版本管理**：每次正式更新产生新版本号

## 数据源优先级

1. 腾讯财经 HTTP API（qt.gtimg.cn）— 首选，不封IP
2. 腾讯K线 API（web.ifzimg.cn）— 前复权K线
3. 百度股市通 — 仅个股K线
4. 东方财富 — 需限流（QPS≤2），仅用于独有数据

## 使用方式

在 Hermes 中直接说：
- "分析 518880 513600 159819"
- "做T方案 518880 成本8.97"
- "T+0 ETF推荐"

技能自动激活并给出精确价位分析。

## License

MIT
