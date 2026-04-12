# Phoenix Core API 参考

**版本**: 2.0.0  
**更新日期**: 2026-04-12

---

## 📦 核心模块

### MemoryManager

记忆系统核心管理器，提供会话管理、记忆注入和学习循环。

```python
from phoenix_core import MemoryManager

manager = MemoryManager()
manager.load(session_id="abc123")

# 获取记忆上下文
context = manager.build_memory_context()

# 同步对话
manager.sync_turn(user_msg, assistant_msg, tool_iterations=3)

# 处理工具调用
result = manager.handle_tool_call("memory", {
    "action": "add",
    "target": "memory",
    "content": "..."
})
```

**主要方法**:

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `load(session_id)` | session_id: str | None | 加载会话记忆 |
| `build_memory_context()` | - | str | 构建系统提示上下文 |
| `sync_turn(user, assistant, iterations)` | user: str, assistant: str, iterations: int | None | 同步对话 |
| `handle_tool_call(tool, params)` | tool: str, params: dict | Any | 处理工具调用 |

---

### MemoryStore

记忆存储层，管理 MEMORY.md 和 USER.md 文件。

```python
from memory_store import MemoryStore

store = MemoryStore(memory_char_limit=5000, user_char_limit=2000)

# 添加记忆
result = store.add("test_bot", "记忆内容")

# 读取记忆
data = store.read("MEMORY")

# 保存学习总结
store.save_learning_summary("测试总结")
```

**主要方法**:

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `add(bot_name, content)` | bot_name: str, content: str | dict | 添加记忆 |
| `read(target)` | target: str (MEMORY/USER) | dict | 读取记忆 |
| `remove(target, bot_name)` | target: str, bot_name: str | dict | 移除记忆 |
| `replace(target, bot_name, content)` | target, bot_name, content | dict | 替换记忆 |
| `save_learning_summary(summary)` | summary: str | None | 保存学习总结 |

---

### SessionStore

SQLite 会话存储，支持 FTS5 全文搜索。

```python
from session_store import SessionStore

store = SessionStore(db_path="./sessions.db")

# 保存会话
store.save_session(
    session_id="abc123",
    user_msg="你好",
    assistant_msg="你好！有什么可以帮助你的？"
)

# 搜索会话
results = store.search_sessions("直播方案")
```

**主要方法**:

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `save_session(session_id, user_msg, assistant_msg)` | session_id, user_msg, assistant_msg | dict | 保存会话 |
| `search_sessions(query)` | query: str | list | 搜索会话 |
| `get_recent_sessions(limit)` | limit: int | list | 获取最近会话 |

---

### SkillStore

技能存储，支持技能版本控制。

```python
from skill_store import SkillStore

store = SkillStore(skill_char_limit=10000)

# 添加技能
store.add("skill_name", "[SKILL] 技能内容")

# 读取技能
data = store.read("skill_name")

# 搜索技能
results = store.search("关键词")
```

**主要方法**:

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `add(skill_name, content)` | skill_name: str, content: str | dict | 添加技能 |
| `read(skill_name)` | skill_name: str | dict | 读取技能 |
| `search(query)` | query: str | list | 搜索技能 |
| `remove(skill_name)` | skill_name: str | dict | 移除技能 |

---

### TaskQueue

任务队列，支持优先级和分配。

```python
from task_queue import TaskQueue, TaskPriority

queue = TaskQueue()

# 添加任务
task_id = queue.add_task(
    assigned_to="编导",
    title="直播方案设计",
    description="设计双 11 直播活动方案",
    priority=TaskPriority.HIGH
)

# 获取统计
stats = queue.get_stats()

# 获取任务
task = queue.get_task(task_id)
```

**任务优先级**:

```python
class TaskPriority(Enum):
    CRITICAL = "critical"  # 紧急
    HIGH = "high"          # 高
    NORMAL = "normal"      # 普通
    LOW = "low"            # 低
```

---

### BotMemoryAdapter

Bot 记忆适配器，为每个 Bot 提供记忆能力。

```python
from bot_memory_adapter import BotMemoryStore

adapter = BotMemoryStore(bot_name="编导")

# 添加记忆
adapter.add_memory("直播方案要点")

# 获取记忆上下文
context = adapter.get_memory_context()

# 添加用户偏好
adapter.add_user_preference("喜欢简洁的方案")
```

**主要方法**:

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `add_memory(content)` | content: str | bool | 添加记忆 |
| `add_user_preference(content)` | content: str | bool | 添加用户偏好 |
| `get_memory_context()` | - | str | 获取记忆上下文 |
| `get_user_context()` | - | str | 获取用户上下文 |
| `search_memory(query)` | query: str | list | 搜索记忆 |

---

### SkillExtractor

技能提取器，从任务执行中提取技能。

```python
from skill_extractor import SkillExtractor

extractor = SkillExtractor(memory_manager)

# 提取技能
result = extractor.extract_skill({
    "worth_preserving": True,
    "task_type": "memory_config",
    "steps_taken": ["步骤 1", "步骤 2"],
    "reasoning": "值得保留的技能"
})
```

**主要方法**:

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `extract_skill(evaluation)` | evaluation: dict | dict | 提取技能 |
| `get_status()` | - | dict | 获取提取状态 |

---

### SkillOptimizer

技能优化器，分析执行结果并优化技能。

```python
from skill_optimizer import SkillOptimizer

optimizer = SkillOptimizer(memory_manager)

# 记录执行结果
optimizer.record_execution({
    "skill_name": "memory_config",
    "success": True,
    "execution_data": {...}
})

# 优化技能
result = optimizer.optimize_skill("memory_config")
```

---

### ReflectionEngine

反思引擎，深度分析和模式发现。

```python
from reflection_engine import ReflectionEngine

engine = ReflectionEngine(memory_manager)

# 执行反思
insights = engine.reflect(
    bot_name="编导",
    time_range="24h"
)
```

---

### KnowledgeGraph

知识图谱，跨 Bot 知识共享。

```python
from knowledge_graph import KnowledgeGraph

graph = KnowledgeGraph()

# 分享学习
graph.share_learning(
    from_bot="编导",
    to_bots=["场控", "运营"],
    knowledge_id="xyz"
)
```

---

## 🔧 工具函数

### memory_tool

记忆工具 Schema：

```python
from memory_store import MEMORY_TOOL_SCHEMA

print(MEMORY_TOOL_SCHEMA)
# 输出工具定义
```

### session_store_tool

会话存储工具 Schema：

```python
from session_store import SESSION_STORE_SCHEMA
```

### skill_tool

技能工具 Schema：

```python
from skill_store import SKILL_TOOL_SCHEMA
```

---

## 🌐 Phoenix CLI

统一命令行接口。

```bash
# 查看状态
phoenix status

# 健康检查
phoenix doctor

# Bot 管理
phoenix bots list
phoenix bots start
phoenix bots stop

# 技能管理
phoenix skills list
phoenix skills info --name skill_name

# 缓存管理
phoenix cache stats
phoenix cache clear

# 配置管理
phoenix config show
phoenix config edit

# 任务管理
phoenix tasks list
phoenix tasks add --bot 编导 --title "新任务"

# 版本信息
phoenix version
```

---

## 📝 配置文件

### .env

```bash
# DashScope API
DASHSCOPE_API_KEY=your_key_here

# DashScope Coding Plan API
DASHSCOPE_CODING_PLAN_API_KEY=your_key_here

# CompShare API
COMPSHARE_API_KEY=your_key_here

# Moonshot API
MOONSHOT_API_KEY=your_key_here

# 可选：调试日志
PHOENIX_LOG_LEVEL=DEBUG
```

### config.json

```json
{
  "llm": {
    "default_provider": "coding-plan",
    "models": {
      "编导": {"model": "qwen3-coder-next", "provider": "coding-plan"},
      "剪辑": {"model": "gpt-5.1", "provider": "compshare"}
    }
  },
  "memory": {
    "shared_memory_dir": "shared_memory",
    "workspaces_dir": "workspaces"
  },
  "learning_loop": {
    "iteration_threshold": 5,
    "auto_reflection": true
  }
}
```

---

## 🔍 错误处理

所有 API 返回统一的错误格式：

```python
{
    "success": False,
    "error": "错误信息",
    "details": {...}  # 可选的详细信息
}
```

**常见错误**:

| 错误 | 说明 | 解决方案 |
|------|------|---------|
| `API key not found` | 缺少 API Key | 检查.env 配置 |
| `Session not found` | 会话不存在 | 检查 session_id |
| `Skill not found` | 技能不存在 | 检查技能名称 |
| `Memory limit exceeded` | 超出记忆限制 | 清理旧记忆 |

---

*本文档由技术文档工程师 D 维护*
