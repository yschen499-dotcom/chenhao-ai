# 内部测试版目录结构草案

## 一、设计原则

当前阶段的目标不是对外售卖，而是先做一个只给自己使用的内部测试版。

核心原则如下：

1. 保留当前已经跑通的 `dingtalk_agent.py`
2. 把它定位成钉钉入口层，而不是业务中心
3. 新增的核心业务逻辑尽量拆到独立模块中
4. 先做最小可用的盯盘闭环，不做会员系统和售卖逻辑

一句话总结：

> 保留现有 `dingtalk_agent` 作为内部管理和测试入口，新增采集、策略、存储和提醒模块，形成一个只给自己使用的内部测试系统。

## 二、推荐目录结构

```text
project_root/
├─ dingtalk_agent.py
├─ requirements.txt
├─ .env.dingtalk_agent
├─ README.md
├─ CS2_MVP_Checklist.md
├─ Internal_Test_Architecture.md
│
├─ app/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ router.py
│  ├─ commands.py
│  ├─ monitor.py
│  ├─ collector.py
│  ├─ strategies.py
│  ├─ alerts.py
│  ├─ storage.py
│  ├─ models.py
│  └─ utils.py
│
├─ data/
│  ├─ app.db
│  ├─ watchlist.json
│  └─ logs/
│
├─ scripts/
│  ├─ init_db.py
│  ├─ run_monitor_once.py
│  └─ seed_watchlist.py
│
└─ docs/
   ├─ INTERNAL_ARCHITECTURE.md
   ├─ COMMANDS.md
   └─ ALERT_RULES.md
```

## 三、各目录与文件职责说明

### 1. 根目录文件

#### `dingtalk_agent.py`

这是当前已经跑通的钉钉机器人入口。

未来只负责：

- 连接钉钉 Stream
- 接收你发来的管理命令
- 调用命令路由
- 返回处理结果
- 调用提醒推送

不建议它继续直接负责：

- 市场数据抓取
- 波动计算
- 数据库存储
- 复杂业务规则

它的定位应该是：

> 入口层 / 适配层

#### `requirements.txt`

继续保留，用来管理项目依赖。

#### `.env.dingtalk_agent`

继续保留，存放：

- 钉钉凭证
- 日志级别
- 扫描间隔
- 管理员 ID
- 其他测试配置

### 2. `app/` 目录

这是后续业务逻辑的核心目录。

#### `app/config.py`

负责统一读取配置。

建议集中管理：

- DingTalk 配置
- 数据库路径
- 监控间隔
- 大盘阈值
- 单品阈值
- 日志设置

#### `app/router.py`

负责消息路由。

将钉钉收到的文本分发到不同命令处理逻辑，比如：

- `help`
- `status`
- `scan`
- `watchlist`
- `add xxx`
- `remove xxx`
- `summary`
- `test alert`

#### `app/commands.py`

负责实现具体命令逻辑。

例如：

- 查看帮助
- 查看系统状态
- 查询监控列表
- 添加监控项
- 删除监控项
- 触发一次扫描
- 发送测试提醒

#### `app/monitor.py`

负责监控调度。

建议在这里实现：

- 定时拉取数据
- 定时运行策略
- 定时生成摘要
- 定时发送提醒

内部测试版先做成最简单的循环调度即可。

#### `app/collector.py`

负责数据采集。

它只做一件事：

> 从数据源获取盯盘所需的原始数据

例如：

- 饰品名称
- 当前价格
- 时间戳
- 成交量或活跃度（如果有）

不负责提醒，也不负责判断信号。

#### `app/strategies.py`

负责策略判断。

它接收采集后的市场数据，产出“提醒事件”。

建议先做三类判断：

1. 大盘异动
2. 单品短期异动
3. 自选监控触发

#### `app/alerts.py`

负责提醒推送。

建议封装：

- 提醒文案格式化
- 去重
- 限频
- 调用钉钉发送消息

后续如果要加其他通知渠道，优先扩展这里。

#### `app/storage.py`

负责所有存储访问。

建议统一封装：

- 写入价格快照
- 读取监控列表
- 写入提醒记录
- 查询系统状态

内部测试版建议优先使用 SQLite。

#### `app/models.py`

可选，用于定义统一的数据结构。

例如可以抽象：

- WatchItem
- PriceSnapshot
- AlertEvent
- SystemStatus

#### `app/utils.py`

放通用工具函数，例如：

- 时间处理
- 文本格式化
- 百分比计算
- 安全类型转换
- 去重 key 生成

### 3. `data/` 目录

存放运行时数据。

#### `data/app.db`

SQLite 数据库文件。

建议内部测试版直接使用它。

#### `data/watchlist.json`

可作为初始监控标的的种子文件。

在还没完全实现动态命令管理前，这个文件很方便。

#### `data/logs/`

日志目录，后续如果要写文件日志可以使用。

### 4. `scripts/` 目录

用于放辅助脚本和一次性脚本。

#### `scripts/init_db.py`

初始化数据库表结构。

#### `scripts/run_monitor_once.py`

手动运行一次监控逻辑。

这对调试非常有帮助，不需要每次都等定时器触发。

#### `scripts/seed_watchlist.py`

将一批核心监控标的写入数据库或配置文件。

### 5. `docs/` 目录

用于放内部文档。

#### `docs/INTERNAL_ARCHITECTURE.md`

记录内部架构说明。

#### `docs/COMMANDS.md`

记录支持的钉钉命令与格式。

#### `docs/ALERT_RULES.md`

记录提醒规则，例如：

- 大盘异动怎么定义
- 单品异动怎么定义
- 自选触发怎么定义

## 四、内部测试版的最小数据模型建议

建议先只建 4 张表。

### 1. `watchlists`

存储监控标的。

建议字段：

- id
- item_name
- enabled
- category
- target_price
- upper_threshold
- lower_threshold
- created_at
- updated_at

### 2. `price_snapshots`

存储价格快照。

建议字段：

- id
- item_name
- price
- volume
- source
- captured_at

### 3. `alert_events`

存储提醒历史，防止重复推送。

建议字段：

- id
- alert_type
- item_name
- alert_key
- message
- created_at

### 4. `system_state`

存储系统状态。

建议字段：

- key
- value
- updated_at

例如：

- `last_scan_time`
- `last_push_time`
- `last_error`

## 五、内部测试版建议支持的命令

### 第一批命令

建议先做以下命令：

- `help`
- `status`
- `watchlist`
- `scan`
- `test alert`

### 第二批命令

在第一批稳定后再做：

- `add xxx`
- `remove xxx`
- `summary`

### 暂时不做

内部测试阶段先不做：

- 会员系统
- 续费逻辑
- 白名单售卖逻辑
- 多用户权限区分

## 六、推荐开发顺序

### 第 1 步：保留 `dingtalk_agent.py`，改成命令路由入口

先支持：

- `help`
- `status`
- `scan`
- `test alert`

### 第 2 步：新增 `storage.py` 和 SQLite

先把这些表落地：

- `watchlists`
- `price_snapshots`
- `alert_events`
- `system_state`

### 第 3 步：新增 `collector.py`

先采一小批固定标的，不要做全市场。

### 第 4 步：新增 `strategies.py`

先只实现两个最简单的策略：

1. 单品短期涨跌幅提醒
2. 大盘简单异动提醒

### 第 5 步：新增 `alerts.py`

把策略产出的提醒事件推送到你的钉钉。

### 第 6 步：新增 `monitor.py`

让系统自动定时运行。

### 第 7 步：最后再做 `add/remove/watchlist`

这时再通过钉钉动态维护监控标的。

## 七、内部测试版明确不做的内容

当前只给自己测试，建议不做：

- 收费系统
- 会员系统
- 白名单逻辑
- 多渠道通知
- 稀有属性监控
- 自动下单
- 高级图表分析

## 八、最终目标

内部测试版最终应该实现：

你作为管理员可以通过钉钉：

- 查看系统状态
- 触发一次扫描
- 查看监控列表
- 添加或删除监控项
- 接收异动提醒
- 接收每日简报

系统自动完成：

- 定时抓数据
- 判断异动
- 生成提醒
- 主动推送

## 九、一句话建议

> 保留现有 `dingtalk_agent` 作为钉钉入口层，新开发重点放在采集层、策略层、存储层和提醒层。

这样既不会浪费你已经跑通的部分，也不会把业务逻辑继续堆进一个入口文件里。
