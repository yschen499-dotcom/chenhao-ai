# test_dingding

内部测试用的钉钉 Stream 机器人，用于逐步搭建 CS2 盯盘助手。

当前仓库主要聚焦在第一阶段内部测试版：

- 保留钉钉作为管理和测试入口
- 使用 SQLite 保存本地状态
- 通过聊天命令管理监控列表和测试链路
- 已接入 SteamDT 第一版多平台价格采集能力
- 为后续策略、监控调度和提醒模块继续预留结构

## 文件说明

- `dingtalk_agent.py`: DingTalk Stream entrypoint
- `app/`: 内部测试业务模块
- `scripts/init_db.py`: 初始化 SQLite 数据库
- `CS2_MVP_Checklist.md`: 产品 MVP 规划文档
- `Internal_Test_Architecture.md`: 内部测试架构草案
- `.env.dingtalk_agent`: 本地凭证与配置文件（不提交）

## 环境准备

1. 创建并激活 Python 环境。
2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 在项目根目录创建 `.env.dingtalk_agent`：

```env
DINGTALK_STREAM_CLIENT_ID=你的AppKey
DINGTALK_STREAM_CLIENT_SECRET=你的AppSecret
AGENT_STEAMDT_API_KEY=你的SteamDT开放平台API_KEY

# 可选
# DINGTALK_AGENT_LOG_LEVEL=DEBUG
# AGENT_DB_PATH=data/app.db
# AGENT_SCAN_INTERVAL_SECONDS=60
# AGENT_MAX_REPLY_CHARS=3000
# AGENT_STEAMDT_PRICE_PLATFORM=BUFF
# AGENT_STEAMDT_REQUEST_TIMEOUT_SECONDS=15
```

你也可以使用 `DINGTALK_APP_KEY` 和 `DINGTALK_APP_SECRET` 这组变量名。

## 初始化本地存储

```bash
python3 scripts/init_db.py
```

## 运行

```bash
python3 dingtalk_agent.py
```

## 内部测试命令

- `帮助`
- `状态`
- `监控列表`
- `添加监控 AK-47 | 红线 (久经沙场)`
- `删除监控 AK-47 | 红线 (久经沙场)`
- `立即扫描`
- `测试提醒`

## 说明

- 当前版本仍然是内部测试版，不包含对外售卖逻辑。
- `立即扫描` 已经会调用 SteamDT 接口抓取监控饰品价格，并把结果写入本地 SQLite。
- 当前扫描结果会优先展示 BUFF、悠悠、C5 的在售价与求购价。
- 第一次扫描某个中文饰品名时，会尝试从 SteamDT 基础信息接口刷新名称映射缓存。
- 当前还没有接入自动异动判断和定时后台轮询，重点是先跑通真实数据采集链路。