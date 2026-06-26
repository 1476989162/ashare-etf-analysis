# A股数据 API 可靠性实测笔记（2026-06-24）

基于20只ETF的实测数据，记录各API实际表现。

## ETF代码 → 腾讯行情前缀映射规则（2026-06-24 实测修正）

| 前缀 | 交易所 | 代码段 | 示例 |
|------|--------|--------|------|
| `sh` | 上海 | 51xxxx, 56xxxx, 6xxxxx, 9xxxxx | 518880, 562500, 601212 |
| `sz` | 深圳 | 15xxxx, 16xxxx, 50xxxx, 58xxxx, 0xxxxx, 3xxxxx | 159819, 161226, 501018, 589580 |
| `bj` | 北京 | 8xxxxx | 830799 |

⚠️ **56xxxx 是上海（sh），不是深圳！** 562500机器人ETF华夏、561300沪深300增强、562350电力ETF都是上海ETF。

## 实测结果

### ✅ 腾讯财经 HTTP API（qt.gtimg.cn）
- 20/20 ETF全部成功返回实时行情
- 一次请求拿多只（逗号分隔），Keep-Alive复用
- 不封IP，可以放心使用
- 字段：3=现价, 4=昨收, 32=涨跌幅%, 37=成交额(万), 39=PE(TTM), 44=总市值(亿), 46=PB
- 买卖五档：[9][10]=买一价/量, [11][12]=买二, [13][14]=买三, [15][16]=买四, [17][18]=买五
- [19][20]=卖一价/量, [21][22]=卖二, [23][24]=卖三, [25][26]=卖四, [27][28]=卖五
- 踩坑：索引43是振幅%不是PB，PB在索引46

### ✅ 腾讯K线 API（web.ifzq.gtimg.cn）
- 20/20 ETF全部成功返回60日K线
- 返回前复权数据（qfq）
- 格式：date, open, close, high, low, volume

### ⚠️ 百度股市通 K线
- 21只ETF中仅2只返回有效数据，其余空list
- ETF兼容性差，仅用于个股

### ⚠️ 东方财富 API
- 实时行情API 404（FundSearch路径失效）
- push2/datacenter需严格限流（QPS≤2，间隔≥1s）

## 推荐工作流

1. **实时行情 → terminal curl 腾讯财经 HTTP API（首选，最可靠）**
   ```bash
   curl -s "https://qt.gtimg.cn/q=sh518880,sz159819,sh562500" \
     -H "User-Agent: Mozilla/5.0" | iconv -f gbk -t utf-8
   ```
   - 一次可带37+只代码，全部成功
   - 子代理(delegate_task)无terminal权限，无法执行curl
   - execute_code 中 urllib 偶尔被环境封（东方财富必封，腾讯偶封）
   - **所以必须在 terminal 工具中执行 curl，不要在 execute_code 中用 urllib**

2. K线数据 → execute_code 中 urllib 腾讯K线 API（成功率高，单次批量20只）
3. MA均线 → 本地计算
4. 资金流向/龙虎榜 → 东财 datacenter-web（需限流QPS≤2）

## 新安装技能

- **a-stock-data** (v3.2.3): 在 gupiao profile 下 `~/.hermes/skills/a-stock-data/SKILL.md`
  - 七层数据架构，28个端点
  - 内嵌防封限流 `em_get()` helper
  - 作者：Simon 林，项目：https://github.com/simonlin1212/a-stock-data
