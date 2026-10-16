# QMT → PTrade 迁移对照表（别硬搬，要重写）

> **先说结论**：QMT 内置 Python 和 PTrade 是**两套完全不同的平台**，函数名、参数、账户模型全不一样。
> **逻辑可以搬，代码必须重写。** 好消息：PTrade 的 API 更简单，我这份已经重写好了 —— `PTrade版_ETF轮动.py`（约 40 行）。

## 一、国金有没有 PTrade？**有，QMT 和 PTrade 可以一起开**

| 项目 | 要求 |
|---|---|
| 资产 | 账户自有资产 **≥ 10 万**（近 20 个交易日日均，现金/股票/基金都算） |
| 风险测评 | **C4 及以上** |
| 交易经验 | **6 个月以上**（模拟盘不算） |
| 申请入口 | **佣金宝 APP → 我的 → 我的业务 → PTrade/QMT/底仓增强权限** → 勾选申请 |
| 审核 | 1~3 个工作日，结果发 APP 消息 / 短信 / 邮箱 |
| 佣金 | 谈判目标：万 2.5 全佣、最低 5 元 |

**⭐ 省钱小技巧**：不用等开户也能先摸 PTrade —— 网上流传一个**国金 PTrade 测试版共享账号**（账号 `55010687` / 密码 `259800`），下载"国金证券-Ptrade测试版"客户端即可登录试用。
> ⚠️ 共享账号人多会卡、且别人能改你的策略，**只用来熟悉界面，别放真数据**。

## 二、两套 API 对照（这是"不能直接搬"的原因）

| 用途 | QMT 内置 Python | PTrade |
|---|---|---|
| 入口函数 | `def init(ContextInfo)` / `def handlebar(ContextInfo)` | `def initialize(context)` / `def handle_data(context, data)` |
| 定时任务 | 自己在 handlebar 里判断时间 | **`run_daily(context, func, time='14:50')`** ⭐ |
| 下单 | `passorder(23, 1101, accID, code, 5, 0, vol, 'name', 1, '', ContextInfo)` | **`order(code, amount)` / `order_target(code, 0)` / `order_target_value(code, 金额)`** ⭐ 极简 |
| 取历史行情 | `get_market_data(fields, [code], end_time=..., count=..., dividend_type='front')` 每只单独取 | **`get_history(count, '1d', 'close', [16只一起传], fq='pre')`** ⭐ 一次拿全部 |
| 查持仓 | `get_trade_detail_data(accID,'STOCK','POSITION')` | **`context.portfolio.positions`** |
| 查资金 | `get_trade_detail_data(accID,'STOCK','ACCOUNT')` | **`context.portfolio.cash` / `.portfolio_value`** |
| 标的代码 | `588000.SH` / `159915.SZ` | **`588000.SS` / `159915.SZ`**（上海变 `.SS`） |
| 状态保存 | 新规禁文件读写 → 必须幂等 | **框架自动 pickle 保存 `g`**，重启自动恢复 |
| 打印 | `print(...)` | `log.info(...)` / `log.warning(...)` |

## 三、PTrade 的三大优势（对你这套策略特别重要）

1. **`order_target_value(code, 金额)`** —— 直接说"我要持有这只值多少钱"，**系统自己算股数**。QMT 里那一堆"自己记账 / 查账户 / 被成交比例截断"的坑，**在 PTrade 里根本不存在**
2. **一次取 16 只的历史数据**（`get_history` 传列表返回 DataFrame），比 QMT 一只一只取快十几倍
3. **跑在券商服务器**：**电脑关机、断网，照样执行**，不用 7×24 挂着

## 四、迁移时要注意的 3 个点

| 点 | 说明 |
|---|---|
| **`set_universe` 必须设** | PTrade **只能操作股票池内的标的**，池子外的下单会被拒 |
| **`include` 参数** | 默认我写成 `include=False`（用上一根K线，**绝对不含未来数据**）。所以信号天然比 QMT 那版慢一天，净值会有差异——这是**更保守、更诚实**的做法 |
| **回测频率选日线** | 回测 15:00 执行、交易默认 14:50，和策略的日线逻辑匹配 |

## 五、建议的上线路线

```
QMT（已验证过一遍，留着当"研究台"）
        ↓  逻辑照搬、API 重写（已给你 PTrade版_ETF轮动.py）
PTrade 回测 → 跑出你自己机器上的成绩单 → 和 QMT 的对比
        ↓
PTrade 模拟盘跑 2 周 → 信号核对无误
        ↓
PTrade 实盘（先 1~2 万）→ 跑满 3 个月 → 再上满仓
```

**QMT 和 PTrade 不是二选一，是分工**：QMT 在你本机、透明可查（今晚这些坑只有在本机才挖得出来）；PTrade 在云端、不睡觉。**两边都开着，互为备份。**
