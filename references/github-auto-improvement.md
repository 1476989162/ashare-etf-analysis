# GitHub 自动优化机制

## 仓库信息

- **URL**: https://github.com/1476989162/ashare-etf-analysis.git
- **本地路径**: `~/.hermes/skills/creative/ashare-etf-analysis/`
- **Token**: 环境变量 `GITHUB_TOKEN` 或 `GH_TOKEN`（Windows 用户需在 PowerShell 中设置：`[Environment]::SetEnvironmentVariable("GITHUB_TOKEN", "ghp_...", "User")`，然后重启 Hermes 应用使 bash 会话生效）

> ⚠️ Token 不要写入文件，应通过环境变量注入。当前有效 Token 已设置于 2026-06-28。

## 自动任务

| 任务 | 频率 | Job ID |
|------|------|--------|
| `ashare-etf-auto-improvement` | 每48小时 | `bc0511ad4f97` |
| `a-stock-data-auto-update` | 每24小时 | `9ab6282f1a6b` |

## 改进检测逻辑

扫描对话历史时关注以下信号：

1. **功能缺口**: 用户问了但技能没覆盖的查询
2. **数据错误**: API 返回过时数据、字段索引变化
3. **用户纠正**: 技能返回了方向性建议而非精确价位
4. **T+0误判**: 错误识别了可T+0的ETF
5. **做T公式遗漏**: LOF溢价、分红除息等场景

## Issue 模板

- `.github/ISSUE_TEMPLATE/improvement.md` — 功能改进
- `.github/ISSUE_TEMPLATE/bug.md` — Bug报告

## 手动触发

用户说"改进XXX"时：
1. 建 Issue
2. 修复代码/SKILL.md
3. 推送仓库
4. 更新本地技能
5. 更新 CHANGELOG.md

## 版本规则

- `patch (z+1)` = Bug修复
- `minor (y+1)` = 新功能
- `major (x+1)` = 架构变更
