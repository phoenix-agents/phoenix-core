# Phoenix Core 功能特性

## 概述

Phoenix Core 是一个 AI 驱动的直播运营团队系统，包含 8 个独立的 Discord Bot，形成完整的直播运营团队。

## 核心功能

### 1. Bot 团队

8 个专业 Bot 角色：
- **编导** 📝 - 内容策划 (DeepSeek-V3.2)
- **剪辑** 🎬 - 视频剪辑 (GPT-5.1)
- **美工** 🎨 - 视觉设计 (GPT-5.1)
- **场控** 🎮 - 气氛控制 (Claude Haiku 4.5)
- **客服** 💬 - 粉丝运营 (Qwen3.5-Plus)
- **运营** 📊 - 数据分析 (Claude Sonnet 4.6)
- **渠道** 🤝 - 商务合作 (GPT-5.1)
- **小小谦** 🤖 - 系统协调 (Kimi K2.5)

### 2. 技能白名单系统 (`skill_whitelist.py`)

- 可信技能来源管理
- 技能安全评级（安全/已审核/未验证/可疑/已封禁）
- 安装前自动校验
- 技能执行策略

**使用方法:**
```bash
python3 skill_whitelist.py list           # 列出所有可信技能
python3 skill_whitelist.py verify <path>  # 验证技能安全性
python3 skill_whitelist.py block <id>     # 封禁技能
```

### 3. 技能市场 (`skill_marketplace.py`)

- 浏览远程技能
- 一键安装/卸载
- 技能搜索
- 来源可信度验证

**使用方法:**
```bash
python3 skill_marketplace.py browse        # 浏览技能
python3 skill_marketplace.py install <id>  # 安装技能
python3 skill_marketplace.py remove <id>   # 卸载技能
python3 skill_marketplace.py search <query> # 搜索技能
```

### 4. 任务队列系统 (`task_queue.py`)

- 任务优先级调度 (紧急/高/普通/低)
- 跨 Bot 上下文共享
- 任务依赖管理
- 协作状态跟踪
- 自动重试机制

**核心功能:**
```python
from task_queue import get_task_queue, TaskPriority

queue = get_task_queue()
task_id = queue.add_task(
    assigned_to="编导",
    title="策划直播",
    description="下周直播内容",
    priority=TaskPriority.HIGH
)
```

### 5. 记忆缓存优化 (`phoenix_memory_cache.py`)

- LRU 缓存策略
- 批量写入优化
- 异步刷新
- 命中率统计
- 两层缓存 (L1 内存/L2 磁盘)

**使用方法:**
```python
from phoenix_memory_cache import get_memory_optimizer

optimizer = get_memory_optimizer()
memory = optimizer.get_memory("编导", "long_term")
```

### 6. Web Dashboard (`web_ui.py`)

- Bot 状态仪表板
- 任务队列可视化
- 缓存统计
- 健康检查
- 技能市场浏览

**启动方法:**
```bash
python3 web_ui.py --port 8080
# 或
phoenix web --port 8080
# 访问：http://your-server-ip:8080
```

访问：http://your-server-ip:8080

### 7. CLI 工具 (`phoenix_cli.py`)

统一的命令行入口：

```bash
phoenix status          # 查看系统状态
phoenix doctor          # 健康检查
phoenix bots list       # Bot 列表
phoenix skills list     # 技能列表
phoenix cache stats     # 缓存统计
phoenix tasks list      # 任务列表
phoenix web             # 启动 Web UI
```

### 8. 健康检查 (`doctor.py`)

7 大健康检查类别：
- Bots - Bot 运行状态
- Database - 数据库连接
- Workspace - 工作目录
- Config - 配置文件
- Memory - 记忆系统
- Skills - 技能系统
- Discord - Discord 连接

**使用方法:**
```bash
python3 doctor.py --quick    # 快速检查
python3 doctor.py --fix      # 自动修复
python3 doctor.py --category bots  # 检查特定类别
```

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Phoenix Core                          │
├─────────────────────────────────────────────────────────┤
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐│
│  │编导 │ │剪辑 │ │美工 │ │场控 │ │客服 │ │运营 │ │渠道 ││
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘│
│                     │                                     │
│              ┌──────┴──────┐                             │
│              │   小小谦    │ (系统协调)                   │
│              └─────────────┘                             │
│                    │                                     │
│  ┌─────────────────┼─────────────────┐                   │
│  │  任务队列  │  技能系统  │  缓存优化  │                   │
│  └─────────────────┴─────────────────┘                   │
│                    │                                     │
│            ┌───────┴───────┐                             │
│            │  Web Dashboard │                             │
│            └───────────────┘                             │
└─────────────────────────────────────────────────────────┘
```

## 快速开始

1. **查看系统状态:**
   ```bash
   phoenix status
   ```

2. **健康检查:**
   ```bash
   phoenix doctor
   ```

3. **启动 Web UI:**
   ```bash
   phoenix web --port 8080
   ```

4. **浏览技能:**
   ```bash
   python3 skill_marketplace.py browse
   ```

5. **创建任务:**
   ```bash
   phoenix tasks add --bot 编导 --title "新任务" --priority high
   ```

## 文件结构

```
phoenix-core/
├── phoenix_cli.py          # CLI 工具
├── web_ui.py               # Web Dashboard
├── doctor.py               # 健康检查
├── skill_whitelist.py      # 技能白名单
├── skill_marketplace.py    # 技能市场
├── task_queue.py           # 任务队列
├── phoenix_memory_cache.py # 记忆缓存
├── discord_bot.py          # Discord Bot
└── workspaces/             # Bot 工作目录
    ├── 编导/
    ├── 剪辑/
    ├── ...
    └── 小小谦/
```

## 技术栈

- Python 3.8+
- Discord.py
- SQLite (WAL 模式)
- LRU Cache
- RESTful API

## 许可证

MIT License
