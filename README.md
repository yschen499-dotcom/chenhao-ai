# test_dingding

内部测试用的钉钉 Stream 机器人，用于逐步搭建 CS2 盯盘助手。

当前仓库主要聚焦在第一阶段内部测试骨架：

- 保留钉钉作为管理和测试入口
- 使用 SQLite 保存本地状态
- 通过聊天命令管理监控列表和测试链路
- 为后续采集器、策略、监控调度和提醒模块预留结构

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

# 可选
# DINGTALK_AGENT_LOG_LEVEL=DEBUG
# AGENT_DB_PATH=data/app.db
# AGENT_SCAN_INTERVAL_SECONDS=60
# AGENT_MAX_REPLY_CHARS=3000
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

- 当前版本仍然是内部测试骨架。
- 真实 CS2 市场采集与策略逻辑还没有正式接入。
- `立即扫描` 当前主要用于验证命令、状态和存储链路。