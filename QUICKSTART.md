# Phoenix Core 快速启动指南

> 零配置启动，5 分钟体验多 Bot 协作

## 🚀 新用户三步启动

### 第一步：创建你的第一个 Bot

```bash
# 创建工作区目录
mkdir -p workspaces/我的助手

# 创建 .env 文件
cat > workspaces/我的助手/.env << EOF
# Bot 基本信息
BOT_NAME=我的助手
BOT_MODEL=qwen3.6-plus
BOT_PROVIDER=coding-plan

# Discord 配置（替换为你的 Bot Token）
DISCORD_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
DISCORD_CHANNEL_ID=YOUR_CHANNEL_ID
DISCORD_SERVER_ID=YOUR_SERVER_ID

# 标记为协调者 Bot（可选，默认第一个就是）
IS_CONTROLLER=true
EOF

# 创建 Bot 人设（可选）
echo "你是一个乐于助人的 AI 助手，擅长协调多 Bot 协作完成任务。" > workspaces/我的助手/SOUL.md
```

### 第二步：启动系统

```bash
# 直接运行 Gateway（自动识别第一个 Bot 为协调者）
python3 phoenix_core_gateway_v2.py --workspace workspaces/我的助手
```

### 第三步：访问 Dashboard

系统启动后，打开浏览器访问：

```
http://localhost:8001
```

### 第四步：测试协作

在 Dashboard 聊天框输入：

```
安排下明天的直播方案
```

系统会自动：
1. 拆解任务给运营、编导、场控 Bot
2. 通过 Discord 发送协议消息
3. 等待各 Bot 响应
4. 汇总结果返回给你

---

## 📐 架构说明

### 自动协调者识别

系统启动时会自动扫描 `workspaces/` 目录：

1. **优先查找** `.env` 中 `IS_CONTROLLER=true` 的 Bot
2. **如果没有**，选择字母序第一个 Bot 作为协调者
3. **协调者 Bot** 会：
   - 创建大脑实例
   - 注入 Gateway 引用
   - 启动 Dashboard API

### 单一进程架构

```
┌─────────────────────────────────────────────────────────┐
│  Phoenix Core Gateway (协调者 Bot)                       │
│  ├── Discord 连接（唯一）                               │
│  ├── CoreBrain（唯一大脑实例）                          │
│  ├── Dashboard HTTP API（端口 8001）                    │
│  └── Worker Bot 管理                                    │
└─────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
    Discord @协调者                  Dashboard 网页
```

**优势**：
- ✅ 大脑实例唯一，状态自然共享
- ✅ Discord 连接唯一，避免 Token 冲突
- ✅ 部署简化，只需启动一个进程
- ✅ 新用户零配置，开箱即用

---

## 🔧 高级配置

### 添加 Worker Bot

创建更多 Bot 作为 Worker：

```bash
mkdir -p workspaces/运营
cat > workspaces/运营/.env << EOF
BOT_NAME=运营
DISCORD_BOT_TOKEN=YOUR_BOT_TOKEN
EOF

mkdir -p workspaces/编导
cat > workspaces/编导/.env << EOF
BOT_NAME=编导
DISCORD_BOT_TOKEN=YOUR_BOT_TOKEN
EOF
```

### 多 Bot 协作流程

1. 用户在 Dashboard 或 Discord 发送请求
2. 大脑拆解任务，识别需要的 Bot
3. 通过 Discord 发送 `[ASK|request_id|brain|300]` 协议消息
4. Worker Bot 收到后处理并回复 `[RESPONSE|request_id|BotName]`
5. 大脑汇总结果返回用户

### 命令行选项

```bash
# 指定工作区
python3 phoenix_core_gateway_v2.py --workspace workspaces/我的助手

# 禁用 Dashboard API（节省资源）
python3 phoenix_core_gateway_v2.py --workspace workspaces/我的助手 --no-dashboard

# 查看所有选项
python3 phoenix_core_gateway_v2.py --help
```

---

## 🔍 故障排查

### Dashboard 无法访问

```bash
# 检查端口是否被占用
lsof -i :8001

# 检查 Gateway 是否正常启动
tail -f logs/gateway.log
```

### Discord 连接失败

检查 `.env` 文件配置：
- `DISCORD_BOT_TOKEN` 是否正确
- `DISCORD_CHANNEL_ID` 是否填写
- Bot 是否已邀请到 Discord 服务器

### 查看 Bot 列表

```bash
curl http://localhost:8001/api/bots
```

### 查看任务历史

```bash
curl http://localhost:8001/api/tasks
```

---

## 📚 下一步

- [ ] 配置 Discord Bot Token
- [ ] 邀请 Bot 到 Discord 服务器
- [ ] 测试多 Bot 协作
- [ ] 查看审计日志 `/api/audit/logs`
- [ ] 配置 GitHub 监控

**完整文档**: https://github.com/phoenix-core/docs
