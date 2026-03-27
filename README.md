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

# 大模型（深度解析、早报/周报/月报）；OpenAI 兼容接口
#
# 【推荐】通义千问（阿里云百炼 Model Studio → API-KEY）
# 控制台：https://bailian.console.aliyun.com/  创建 API Key 后填入下方。
AGENT_LLM_API_KEY=你的DashScope_API_KEY
AGENT_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
AGENT_LLM_MODEL=qwen-plus
# 其它可选模型示例：qwen-turbo、qwen-max、qwen-flash（以控制台实际可用名为准）
# 国际地域可把 BASE_URL 换成文档中的新加坡/弗吉尼亚等 compatible-mode 地址。
#
# 若用 OpenAI 官方：
# AGENT_LLM_BASE_URL=https://api.openai.com/v1
# AGENT_LLM_MODEL=gpt-4o-mini
# AGENT_LLM_TIMEOUT_SECONDS=120

# 可选
# AGENT_LLM_TIMEOUT_SECONDS=120
# DINGTALK_AGENT_LOG_LEVEL=DEBUG
# AGENT_DB_PATH=data/app.db
# AGENT_SCAN_INTERVAL_SECONDS=300
# AGENT_MAX_REPLY_CHARS=3000
# AGENT_STEAMDT_PRICE_PLATFORM=BUFF
# AGENT_STEAMDT_REQUEST_TIMEOUT_SECONDS=15
# AGENT_ALERT_THRESHOLD_PERCENT=3
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

云服务器部署步骤见 **[DEPLOY.md](DEPLOY.md)**（**Windows 见第三节**；Linux 见第二节）。Windows 可用 **`scripts/run_agent.bat`** 前台启动。

## 命令列表（与机器人内发送「帮助」一致）

**正文唯一来源**：`app/commands.py` 顶部的 **`HELP_TEXT`**（`help_text()` 原样返回）。

`帮助` / `命令` / `功能`：`状态`、`监控列表`、`添加监控`、`删除监控`、`深度解析`、`大盘`、`测试早报`、`测试周报`、`测试月报`、`测试提醒`（已移除「立即扫描」，改为后台定时扫描）。

示例：`添加监控 AK-47 | 红线 (久经沙场)` · `深度解析 AK-47 | 红线 (久经沙场)` · `删除监控 AK-47 | 红线 (久经沙场)`

## 说明

- 当前版本为内部自用，不包含对外售卖逻辑。
- 后台扫描由 `AGENT_ENABLE_BACKGROUND_SCAN` 与 `AGENT_SCAN_INTERVAL_SECONDS` 控制，抓取监控饰品价格并写入 SQLite；面板展示 BUFF、悠悠、C5 的在售价与求购价。
- 主动预警：在售价、求购价、在售量、求购量任一相对上次波动幅度 ≥ `AGENT_ALERT_THRESHOLD_PERCENT`（默认 3%）即推送。
- 首次扫描某中文饰品名时，会尝试从 SteamDT 基础信息接口刷新名称映射缓存。
- 定时早报/周报/月报需配置 Webhook、LLM 与调度相关环境变量，详见 `app/config.py` 与 `app/commands.py` 的 `HELP_TEXT`。