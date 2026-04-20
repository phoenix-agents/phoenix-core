# 📦 Phoenix Core v1.3 - 安装指南

> 完整安装包，包含 Web Dashboard 交互式界面

---

## 🚀 快速开始（推荐）

### 方式一：交互式安装（5 分钟）

```bash
# 解压
tar -xzf phoenix-core-clean-v1.3.tar.gz
cd phoenix-core

# 运行交互式安装向导
bash install.sh
```

安装向导会引导你完成：
1. ✅ 选择平台（Discord/飞书/微信/WhatsApp）
2. ✅ 配置 API Key
3. ✅ 配置 Bot 信息
4. ✅ 启用远程调试
5. ✅ 自动安装依赖

### 方式二：手动配置

```bash
# 解压
tar -xzf phoenix-core-clean-v1.3.tar.gz
cd phoenix-core

# 配置环境
cp .env.example .env
vim .env

# 安装依赖
pip install -r requirements.txt

# 启动
bash start.sh 客服
```

---

## 📡 远程调试说明

### 架构

```
新用户设备                          技术支持设备
┌──────────────────┐               ┌──────────────────┐
│ Bot + Dashboard  │               │  调试服务器       │
│ remote_integration.py │           │  debug_master.py │
└────────┬─────────┘               └────────┬─────────┘
         │                                  │
         └────────────── WebSocket ─────────┘
              ws://技术支持 IP:9000/ws/debug/{device_id}
```

### 使用场景

| 场景 | 配置方式 |
|------|------|
| **自己调试** | 不需要远程调试 |
| **接受远程协助** | 配置 `DEBUG_MASTER_URL` 指向技术支持的服务器 |
| **提供技术支持** | 运行 `python3 debug_master.py --port 9000` |

### 配置远程调试

在安装向导的【5/5】选择启用远程调试，或手动编辑 `.env`：

```ini
# 远程调试配置（可选）
DEBUG_MASTER_URL=技术支持 IP:9000
DEBUG_DEVICE_ID=客服 -001  # 留空自动生成
DEBUG_AUTH_TOKEN=xxx  # 可选
```

### 启动远程调试

Bot 启动时会自动连接调试服务器（如果配置了）：

```bash
bash start.sh 客服
# 看到 "📡 远程调试客户端已启动" 表示成功
```

### 技术支持操作

```bash
# 1. 启动调试服务器
python3 debug_master.py --port 9000

# 2. 查看在线设备
# 在 Dashboard 访问 http://localhost:9000

# 3. 发送调试命令
# 见 REMOTE_DEBUG_SETUP.md
```

---

## 📋 支持的平台

| 平台 | 说明 | 配置项 |
|------|------|--------|
| **Discord** | 游戏/社区机器人 | `DISCORD_BOT_TOKEN` |
| **飞书** | 企业协作平台 | `FEISHU_APP_ID`, `FEISHU_APP_SECRET` |
| **微信企业版** | 企业内部使用 | `WECOM_CORP_ID`, `WECOM_SECRET` |
| **钉钉** | 阿里巴巴办公平台 | `DINGTALK_APP_KEY`, `DINGTALK_APP_SECRET` |
| **WhatsApp** | 国际通用 | `WHATSAPP_TOKEN` |

---

## 🤖 支持的 AI 模型

| 提供商 | 推荐模型 | 配置项 |
|--------|----------|--------|
| **Anthropic** | claude-sonnet-4-6 | `ANTHROPIC_API_KEY` |
| **OpenAI** | gpt-4o | `OPENAI_API_KEY` |
| **智谱 AI** | glm-4 | `ZHIPU_API_KEY` |
| **自定义** | 任意 | `API_BASE_URL`, `API_KEY` |

---

## 🖥️ Dashboard 功能

访问 `http://localhost:8000` 后可以看到：

| 功能 | 说明 |
|------|------|
| 📊 **系统状态** | 内存使用、运行时间、消息统计 |
| 🤖 **Bot 列表** | 所有 Bot 的在线状态和活跃度 |
| 💬 **消息记录** | 实时消息流和对话历史 |
| 📈 **性能图表** | 响应时间、成功率趋势 |
| 🧠 **记忆管理** | 查看和编辑 Bot 记忆 |
| 🔧 **技能配置** | 管理 Bot 技能和工具 |
| 📡 **远程调试** | 设备列表和日志推送 |

---

## 📁 目录结构

```
phoenix-core/
├── phoenix_core/          # 核心模块
├── channels/              # 渠道适配器
├── config/                # 配置加载
├── shared_memory/         # 共享记忆
├── skills/                # 技能管理
├── teams/                 # 团队配置
├── dashboard/             # Web Dashboard
│   ├── static/            # 静态资源
│   └── templates/         # HTML 模板
├── workspaces/            # Bot 工作区
│   └── 客服/
│       ├── BOT_CONFIG.yaml
│       └── .env
├── install.sh             # 交互式安装脚本
├── start.sh               # 一键启动脚本
├── phoenix_core_gateway_v2.py
├── api_server.py
└── requirements.txt
```

---

## ❓ 常见问题

### Q: 安装完成后如何修改配置？
A: 编辑 `.env` 文件，然后重启 Bot

### Q: 如何添加新的 Bot?
A: 运行 `bash install.sh` 再次配置，或手动创建 `workspaces/新 Bot` 目录

### Q: Dashboard 打不开？
A: 确认 `api_server.py` 已启动，检查端口 8000 是否被占用

### Q: 如何禁用远程调试？
A: 在 `.env` 中删除 `DEBUG_*` 开头的变量

---

## 📖 更多文档

- [QUICKSTART.md](QUICKSTART.md) - 快速入门
- [REMOTE_DEBUG_QUICKSTART.md](REMOTE_DEBUG_QUICKSTART.md) - 远程调试配置
- [REMOTE_DEBUG_SETUP.md](REMOTE_DEBUG_SETUP.md) - 远程调试完整指南

---

**版本**: v1.3 (2026-04-20)  
**包含**: Dashboard + Bot + 远程调试 + 多平台支持
