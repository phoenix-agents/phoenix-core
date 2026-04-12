# Phoenix Core 最佳实践

**版本**: 2.0.0  
**更新日期**: 2026-04-12

---

## 🎯 配置最佳实践

### 1. API Key 管理

**推荐做法**:
```bash
# .env 文件权限设置
chmod 600 .env

# 使用环境变量
export DASHSCOPE_API_KEY="your_key"
```

**避免**:
```bash
# ❌ 不要在代码中硬编码
api_key = os.environ.get("API_KEY")

# ❌ 不要提交敏感文件
git add .env
```

### 2. Bot 配置分离

**推荐**:
```json
// config.json
{
  "bots": {
    "编导": {"model": "qwen3-coder-next", "provider": "coding-plan"},
    "剪辑": {"model": "gpt-5.1", "provider": "compshare"}
  }
}
```

**好处**:
- 不同 Bot 使用不同模型
- 成本优化
- 性能最优化

### 3. 记忆限制设置

```bash
# .env
PHOENIX_MEMORY_LIMIT=5000      # 记忆文件字符限制
PHOENIX_USER_LIMIT=2000        # 用户文件字符限制
PHOENIX_SKILL_LIMIT=10000      # 技能文件字符限制
```

---

## 📝 记忆管理最佳实践

### 1. 内容分类

**MEMORY.md** - 代理笔记和观察:
```markdown
## 观察
- 用户偏好简洁的回复
- 直播方案需要包含应急预案
- 双 11 活动需要提前 2 周准备
```

**USER.md** - 用户偏好和期望:
```markdown
## 偏好
- 回复风格：简洁直接
- 方案类型：数据驱动
- 沟通方式：主动汇报
```

### 2. 记忆更新频率

- **每次对话后**: 同步到会话存储
- **每 5 次迭代**: 触发后台反思
- **每天**: 生成学习总结

### 3. 跨 Bot 记忆共享

```python
from memory_share import share_memory

# 共享记忆到其他 Bot
share_memory(
    from_bot="编导",
    to_bots=["场控", "运营"],
    content="直播方案要点"
)
```

---

## 🛠️ 技能开发最佳实践

### 1. 技能设计原则

**SMART 原则**:
- **S**pecific - 具体明确
- **M**easurable - 可衡量
- **A**chievable - 可实现
- **R**elevant - 相关性强
- **T**ime-bound - 有时限

### 2. 技能命名规范

```
[领域]_[功能]_[可选：版本]

例子:
- memory_config          # 记忆配置
- customer_servicefaq    # 客服 FAQ
- live_stream_plan_v2    # 直播方案 v2
```

### 3. 技能测试

```python
# 单元测试
def test_skill_execution():
    result = executor.execute("skill_name")
    assert result["success"] is True

# 集成测试
def test_skill_with_memory():
    manager.load("session_123")
    result = manager.handle_tool_call("skill", {...})
    assert result is not None
```

---

## 🚀 性能优化最佳实践

### 1. 缓存策略

```python
from phoenix_memory_cache import get_memory_optimizer

optimizer = get_memory_optimizer()

# L1 缓存 - 热数据
# L2 缓存 - 持久化数据
```

### 2. 批量操作

```python
# ❌ 避免多次单独写入
for item in items:
    store.add("bot", item)

# ✅ 推荐批量写入
batch_content = "\n".join(items)
store.add("bot", batch_content)
```

### 3. 定期清理

```bash
# 清理缓存
phoenix cache clear

# 清理日志
find logs -name "*.log" -mtime +7 -delete
```

---

## 🔐 安全最佳实践

### 1. 权限控制

```python
from bot_security_guard import get_bot_guard

guard = get_bot_guard("编导")

# 检查权限
if not guard.check_permission("write_file"):
    print("没有写入文件权限")
```

### 2. 沙盒测试

```python
from sandbox_backend import SandboxBackend

sandbox = SandboxBackend()

# 高风险操作在沙盒中测试
result = sandbox.run_risky_operation(...)
```

### 3. 审计日志

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    filename='audit.log'
)
```

---

## 📊 监控最佳实践

### 1. 健康检查

```bash
# 定期检查
phoenix doctor

# 查看状态
phoenix status
```

### 2. 指标收集

- Bot 运行状态
- 任务完成率
- 技能成功率
- 记忆命中率

### 3. 告警设置

```python
# 失败率告警
if failure_rate > 0.3:
    send_alert("技能成功率下降")
```

---

## 🤝 团队协作最佳实践

### 1. 代码审查

- 所有代码变更需经过审查
- 使用 PR 流程
- 至少一人审核

### 2. 文档更新

- 代码变更同步更新文档
- 使用清晰的提交信息
- 标注破坏性变更

### 3. 版本管理

```bash
# 语义化版本
v2.0.0  # 重大变更
v2.1.0  # 新功能
v2.1.1  # Bug 修复
```

---

## 📚 学习资源

- [API 参考](API_REFERENCE.md)
- [技能开发指南](SKILL_DEVELOPMENT.md)
- [故障排除](TROUBLESHOOTING.md)

---

*本文由技术文档工程师 D 撰写*
