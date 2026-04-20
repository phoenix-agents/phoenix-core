# 📦 Phoenix Core 安装包 - 带 Dashboard 交互界面

> 完整安装包，包含 Web Dashboard 交互式界面

---

## 🎯 5 分钟快速启动

### 1️⃣ 解压安装包

```bash
tar -xzf phoenix-core-clean-v1.3.tar.gz
cd phoenix-core
```

### 2️⃣ 配置环境

```bash
cp .env.example .env
vim .env
```

**必填配置：**
```ini
# Discord Bot
DISCORD_BOT_TOKEN=你的_Token
DISCORD_CHANNEL_ID=你的频道_ID

# LLM API
ANTHROPIC_API_KEY=你的_API_Key
DEFAULT_MODEL=claude-sonnet-4-6

# Bot 名称
BOT_NAME=客服
```

### 3️⃣ 一键启动（Dashboard + Bot）

```bash
# 创建工作区
mkdir -p workspaces/客服

# 一键启动
bash start.sh 客服
```

**启动后访问：**
- **Dashboard**: http://localhost:8000
- **API**: http://localhost:8000/api

---

## 🖥️ Dashboard 界面功能

访问 `http://localhost:8000` 后可以看到：

| 功能 | 说明 |
|------|------|
| 📊 **系统状态** | 内存使用、运行时间、消息统计 |
| 🤖 **Bot 列表** | 所有 Bot 的在线状态和活跃度 |
| 💬 **消息记录** | 实时消息流和对话历史 |
| 📈 **性能图表** | 响应时间、成功率趋势 |
| 🧠 **记忆管理** | 查看和编辑 Bot 记忆 |
| 🔧 **技能配置** | 管理 Bot 技能和工具 |
| 📡 **远程调试** | 设备列表和日志推送（如果配置） |

---

## 🚀 手动启动方式

如果想分别启动服务：

```bash
# 启动 API Server + Dashboard (端口 8000)
python3 api_server.py --port 8000

# 另开终端启动 Bot
python3 phoenix_core_gateway_v2.py --workspace workspaces/客服
```

或只启动 Bot（无 Dashboard）：

```bash
python3 phoenix_core_gateway_v2.py --workspace workspaces/客服
```

---

## 📋 完整文档

| 文档 | 说明 |
|------|------|
| [INSTALL_GUIDE.md](INSTALL_GUIDE.md) | 完整安装指南 |
| [INSTALLATION_QUICKSTART.md](INSTALLATION_QUICKSTART.md) | 10 分钟快速上手 |
| [QUICKSTART.md](QUICKSTART.md) | 快速入门 |
| [REMOTE_DEBUG_QUICKSTART.md](REMOTE_DEBUG_QUICKSTART.md) | 远程调试配置 |

---

## ❓ 常见问题

### Q: Dashboard 打不开？
**解决：** 确认 `api_server.py` 已启动，检查端口 8000 是否被占用

### Q: Bot 没有响应？
**解决：** 检查 `.env` 中的 `DISCORD_BOT_TOKEN` 是否正确

### Q: 如何停止服务？
**解决：** 按 `Ctrl+C` 或在 Dashboard 点击"停止"按钮

---

**版本**: v1.3 (2026-04-20)  
**包含**: Dashboard + Bot + 远程调试
