# akshare 库在本机的使用实测（2026-07-10）

用户指定东方财富为数据源，akshare 是封装东财的现成库。本机实测结果如下，**核心价值是能拿到 ETF 的折价率（溢价率）字段**，但受环境代理限制，不能全依赖它。

## 安装
```
pip install akshare     # 实测 1.18.64
```
仅依赖 pandas/requests，装完即用。

## ⚠️ 环境代理（关键前提）
本机环境变量挂着代理：
```
http_proxy  = http://127.0.0.1:7897
https_proxy = http://127.0.0.1:7897
```
该代理**放行 `qt.gtimg.cn`（腾讯），但掐断 `*.eastmoney.com`（东财）**。
- `unset` 代理后东财仍 `Connection aborted` → 不是代理残留，是东财该端点本机不可达。
- 后果：凡 akshare 走东财 `push2*.eastmoney.com` 的接口，全挂 `ProxyError`；腾讯接口不受影响。

## 各接口实测结果（6 只标的：513310/160140/513730/164701/518800/159934）

| 接口 | 用途 | 结果 | 备注 |
|------|------|------|------|
| `ak.fund_etf_spot_em()` | ETF 实时行情 | ✅ 4 只 ETF 跑通 | 含 **`基金折价率`** 列（即溢价率！负值=折价）✅ 这是核心卖点 |
| `ak.fund_lof_spot_em()` | LOF 实时行情 | ❌ ProxyError | 走 `88.push2.eastmoney.com` 被代理挡 → 用腾讯接口补 |
| `ak.fund_etf_hist_em(...)` | 东财历史 K 线 | ❌ ProxyError | 走 `push2his.eastmoney.com` 被挡 → **继续用腾讯 K 线接口** |
| `fund_lof_premium_em` | （猜测的 LOF 溢价函数） | ❌ 不存在 | akshare 无此函数名，别猜 |

### `fund_etf_spot_em()` 关键列
`代码, 名称, 最新价, IOPV实时估值, 基金折价率, 涨跌额, 涨跌幅, 成交量, 成交额, 开盘价, 最高价, 最低价, 昨收, ...`
- **`基金折价率`（负值=折价，正值=溢价）** 是用户要的溢价数据，来源东财，符合偏好。
- 实测折价率：518800 黄金国泰 +0.32%、159934 黄金易方达 +0.31%、513730 东南亚科技 -1.22%、513310 中韩半导体 **NaN**（该东财节点对 513310 半成品，需腾讯兜底）。

## 推荐混合架构（本机最稳）
1. **溢价/折价率** → `ak.fund_etf_spot_em()` 的 `基金折价率`（东财源，用户指定）✅ akshare 真正加分项
2. **历史 K 线复盘** → 腾讯 K 线接口 `https://proxy.finance.qq.com/ifzqgtimg/appstock/app/kline/kline?param={sh/sz}{code},day,,,400`（代理挡不住，2026-07-10 验证 6 只全成功）
3. **LOF 实时（160140/164701）** → 腾讯 `qt.gtimg.cn`，akshare 的 LOF 被代理挡
4. **513310 半导体** akshare 返回 NaN → 始终用腾讯接口兜底

## 前缀坑（再次确认）
- **513730 东南亚科技 = `sh` 不是 `sz`**（51 开头必 sh，见 SKILL.md ETF前缀映射）。
- 用错前缀（sz513730）时代理端点可能**静默返回数据**；交叉校验用 `qt.gtimg.cn`：sz 前缀返回 `v_pv_none_match="1"` 即揪出前缀错误。

## 一句话结论
akshare 在本机**只能稳定取到 ETF 折价率（溢价）**，其余（东财K线、LOF行情）被代理挡，必须用腾讯接口补。封装时溢价走 akshare、K线/LOF 走腾讯，二者各取所长。
