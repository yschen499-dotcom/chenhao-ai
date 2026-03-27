# 云服务器部署说明（盯盘机器人）

适用：**Linux（推荐 Ubuntu 22.04 / Debian 12）** 或 **Windows Server**。以下为最小可运行流程。

---

## 一、服务器侧准备

1. **安全组 / 防火墙**
   - 放行 **入站 SSH**：`22`（建议仅允许你的办公/家庭 IP）。
   - **出站**一般默认可访问 **HTTPS 443**（访问钉钉、SteamDT、通义等）；若访问不了，检查云厂商安全组是否限制出站。

2. **本机准备**
   - 记录服务器 **公网 IP**、**登录用户**（如 `root` 或 `ubuntu`）、**密钥或密码**。

---

## 二、Linux 部署（推荐）

### 1. SSH 登录

```bash
ssh root@你的服务器IP
# 或
ssh ubuntu@你的服务器IP
```

### 2. 安装依赖（Ubuntu 示例）

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

### 3. 上传代码

任选其一：

- **Git**：仓库推到 GitHub/Gitee 后在服务器 `git clone`。
- **本机打包**：在电脑把项目打成 zip，`scp` 上传后解压。

示例目录：`/opt/dingpan-bot`（可自定）。

```bash
sudo mkdir -p /opt/dingpan-bot
sudo chown $USER:$USER /opt/dingpan-bot
cd /opt/dingpan-bot
# 把项目文件放到此目录，确保有 dingtalk_agent.py、app/、requirements.txt
```

### 4. 虚拟环境与依赖

```bash
cd /opt/dingpan-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

### 5. 环境变量

在服务器创建 **`.env.dingtalk_agent`**（与本地相同，填钉钉、SteamDT、通义等），权限收紧：

```bash
chmod 600 .env.dingtalk_agent
```

### 6. 初始化数据库（可选，程序也会自动建表）

```bash
source .venv/bin/activate
python scripts/init_db.py
```

### 7. 前台试跑（确认无报错）

```bash
source .venv/bin/activate
python dingtalk_agent.py
```

看到日志里 **Starting DingTalk Stream bot**、**LLM warmup**（若已配 key）后，在钉钉里发 **帮助** 测一下。  
确认 OK 后 `Ctrl+C` 退出。

### 8. 后台常驻（systemd）

```bash
sudo nano /etc/systemd/system/dingtalk-agent.service
```

写入（**把路径、用户名改成你的**）：

```ini
[Unit]
Description=DingTalk CS2 盯盘机器人
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/dingpan-bot
EnvironmentFile=-/opt/dingpan-bot/.env.dingtalk_agent
ExecStart=/opt/dingpan-bot/.venv/bin/python /opt/dingpan-bot/dingtalk_agent.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dingtalk-agent
sudo systemctl status dingtalk-agent
```

看日志：

```bash
journalctl -u dingtalk-agent -f
```

---

## 三、Windows Server / Windows 云主机部署

### 1. 远程登录

用云厂商 **远程桌面（RDP）** 登录（安全组放行 **3389**，建议仅允许你的 IP）。

### 2. 安装 Python

1. 打开 https://www.python.org/downloads/windows/ 下载 **Python 3.11 或 3.12**（64-bit）。
2. 安装时勾选 **Add python.exe to PATH**、**Install for all users**（若可选）。
3. 新开一个 **PowerShell** 或 **cmd**，执行：

```bat
python --version
pip --version
```

### 3. 上传项目

任选其一：

- 浏览器下载 zip 解压到固定目录，例如 **`C:\dingpan-bot`**；
- 或安装 **Git for Windows**，在目录里 `git clone` 你的仓库。

确保目录里有 **`dingtalk_agent.py`**、**`app`**、**`requirements.txt`**。

### 4. 虚拟环境与依赖

以 **PowerShell** 为例（路径按你的实际修改）：

```powershell
cd C:\dingpan-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
```

若提示 **无法加载脚本**，先以管理员身份执行一次：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

也可用 **cmd**（无需改执行策略）：

```bat
cd /d C:\dingpan-bot
python -m venv .venv
.venv\Scripts\pip install -U pip
.venv\Scripts\pip install -r requirements.txt
```

### 5. 环境变量

在 **`C:\dingpan-bot`** 下创建 **`.env.dingtalk_agent`**（与本地相同：钉钉、SteamDT、通义等）。不要提交到 Git。

### 6. 初始化数据库（可选）

```powershell
python scripts\init_db.py
```

### 7. 前台试跑

```powershell
python dingtalk_agent.py
```

看到日志里 **Starting DingTalk Stream bot** 后，在钉钉发 **帮助** 测试。确认无误后 **Ctrl+C** 退出。

也可双击运行 **`scripts\run_agent.bat`**（需在项目根目录有 `.venv`）。

### 8. 开机自动运行（任务计划程序）

1. **Win + R** → 输入 `taskschd.msc` → 回车。
2. **创建任务**（不要用「创建基本任务」也可，下面用「创建任务」更全）。
3. **常规**：名称填 `DingTalk盯盘机器人`；勾选 **不管用户是否登录都要运行**（需输入管理员密码）；配置选 **Windows 10/Server 2016** 等。
4. **触发器**：**新建** → `启动时` 或 `登录时`（二选一即可）。
5. **操作**：**新建** → 程序或脚本填：

```text
C:\dingpan-bot\.venv\Scripts\python.exe
```

添加参数：

```text
dingtalk_agent.py
```

起始于（**工作目录**）：

```text
C:\dingpan-bot
```

6. **条件**：可取消勾选「只有在使用交流电源时才启动」（笔记本云主机少见）。
7. **设置**：可勾选 **任务失败后重新启动**，间隔 **1 分钟**，重试 **3 次**。
8. 确定保存，**右键任务 → 运行** 测一次；若失败，在 **任务计划程序** 里该任务 → **历史记录** 查看原因。

### 9. 可选：用 NSSM 注册为 Windows 服务（更「服务化」）

1. 下载 [NSSM](https://nssm.cc/download)，解压后 `nssm install DingTalkBot`。
2. **Application** → Path：`C:\dingpan-bot\.venv\Scripts\python.exe`  
   **Startup directory**：`C:\dingpan-bot`  
   **Arguments**：`dingtalk_agent.py`  
3. 安装后：`nssm start DingTalkBot`。
4. 日志可在 NSSM 的 **I/O** 选项卡重定向到文件。

### 10. 防火墙

一般 **出站 HTTPS** 默认即可。若钉钉/SteamDT 无响应，在 **Windows 防火墙** 中确认 **Python** 未被禁止访问专用/公用网络。

---

## 四、常见问题

| 现象 | 排查 |
|------|------|
| 连不上 SteamDT / 通义 | 服务器 `curl -I https://open.steamdt.com`、换地域或检查安全组出站 |
| 钉钉无回复 | 检查 `.env` 中 AppKey/Secret；企业网络是否拦 `oapi.dingtalk.com` |
| 进程退出 | Linux：`journalctl -u dingtalk-agent -n 100`；Windows：任务计划 **历史记录** 或 NSSM 日志 |

---

## 五、数据与更新

- **SQLite** 默认在 `data/app.db`，升级前请 **备份 `data/`**。
- **Linux**：更新代码后 `sudo systemctl restart dingtalk-agent`。
- **Windows**：覆盖文件后，在任务计划里 **结束再运行** 该任务，或用 NSSM `nssm restart DingTalkBot`。
