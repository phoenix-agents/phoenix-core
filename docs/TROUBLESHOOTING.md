# Phoenix Core 故障排除指南

**版本**: 2.0.0  
**更新日期**: 2026-04-12

---

## 🔍 诊断工具

### 1. 健康检查

```bash
# 完整检查
phoenix doctor

# 快速检查
phoenix doctor --quick

# 自动修复
phoenix doctor --fix
```

### 2. 日志查看

```bash
# 查看最近的日志
tail -100 logs/phoenix.log

# 搜索错误
grep "ERROR" logs/phoenix.log
```

### 3. 状态检查

```bash
# 系统状态
phoenix status

# Bot 状态
phoenix bots status

# 缓存统计
phoenix cache stats
```

---

## ❌ 常见问题

### 1. API Key 问题

**错误**: `API key not found`

**原因**: 环境变量未设置

**解决**:
```bash
# 检查.env 文件
cat .env

# 设置 API Key
export DASHSCOPE_API_KEY="your_key"

# 重新运行
python3 bot_manager.py start
```

### 2. Bot 无法启动

**错误**: `Failed to start bot`

**排查步骤**:
```bash
# 1. 检查配置文件
cat config.json

# 2. 查看 Bot 日志
tail -100 workspaces/编导/logs/latest.log

# 3. 检查端口占用
lsof -i :8080
```

**解决**:
```bash
# 重新配置
python3 init_wizard.py

# 重启 Bot
phoenix bots restart
```

### 3. 记忆丢失

**错误**: `Memory not found`

**原因**: 文件路径错误或权限问题

**解决**:
```bash
# 1. 检查记忆文件
ls -la workspaces/编导/memory/

# 2. 检查权限
chmod 644 workspaces/编导/memory/*.md

# 3. 恢复备份
cp workspaces/编导/memory/backup/MEMORY.md workspaces/编导/memory/
```

### 4. 技能执行失败

**错误**: `Skill execution failed`

**排查**:
```python
from skill_executor import SkillExecutor

executor = SkillExecutor()
result = executor.execute_skill("skill_name")
print(result)  # 查看详细错误
```

**解决**:
```bash
# 1. 检查技能文件
cat skills/skill_name.md

# 2. 验证技能
phoenix skills info --name skill_name

# 3. 重新生成
python3 skill_extractor.py
```

### 5. 任务队列堵塞

**错误**: `Task queue full`

**解决**:
```bash
# 查看任务统计
phoenix tasks list

# 清理已完成任务
python3 task_queue.py cleanup

# 增加队列容量
# config.json: "task_queue_max_size": 1000
```

### 6. 跨 Bot 通信失败

**错误**: `Failed to share memory`

**排查**:
```python
from memory_share import share_memory

result = share_memory(
    from_bot="编导",
    to_bots=["场控"],
    content="测试"
)
print(result)
```

**解决**:
```bash
# 1. 检查共享目录
ls -la shared_memory/

# 2. 重启 Bot
phoenix bots restart

# 3. 检查配置
cat config.json | grep shared_memory
```

---

## 🔧 高级故障排除

### 1. 内存泄漏

**症状**: 系统运行变慢，内存占用高

**诊断**:
```bash
# 查看内存使用
ps aux | grep python

# 使用 memory_profiler
python3 -m memory_profiler phoenix_core.py
```

**解决**:
```python
# 定期清理缓存
from phoenix_memory_cache import get_memory_optimizer

optimizer = get_memory_optimizer()
optimizer.clear()
```

### 2. 数据库损坏

**症状**: SQLite 查询失败

**诊断**:
```bash
# 检查数据库完整性
sqlite3 sessions.db "PRAGMA integrity_check;"
```

**解决**:
```bash
# 备份当前数据库
cp sessions.db sessions.db.bak

# 导出并重建
sqlite3 sessions.db .dump | sqlite3 sessions_new.db
mv sessions_new.db sessions.db
```

### 3. 性能下降

**症状**: 响应变慢

**诊断**:
```bash
# 性能分析
python3 -m cProfile -o profile.stats phoenix_core.py

# 查看分析结果
python3 -m pstats profile.stats
```

**解决**:
```bash
# 清理缓存
phoenix cache clear

# 优化数据库
sqlite3 sessions.db "VACUUM;"
```

---

## 🆘 紧急恢复

### 1. 系统回滚

```bash
# 1. 停止所有 Bot
phoenix bots stop

# 2. 回滚代码
git checkout <previous_version>

# 3. 恢复配置
cp config.json.bak config.json

# 4. 重启系统
phoenix bots start
```

### 2. 数据恢复

```bash
# 1. 找到最近的备份
ls -la backups/

# 2. 恢复数据
cp -r backups/2026-04-11/* workspaces/

# 3. 验证恢复
phoenix doctor
```

### 3. 联系支持

如果以上方法都无法解决问题：

1. 收集日志文件
2. 记录复现步骤
3. 提交 GitHub Issue
4. 联系技术支持

---

## 📞 获取帮助

### 1. 文档资源

- [API 参考](API_REFERENCE.md)
- [最佳实践](BEST_PRACTICES.md)
- [技能开发指南](SKILL_DEVELOPMENT.md)

### 2. 社区支持

- GitHub Issues
- Discord 社区
- 技术博客

### 3. 提交 Bug

**Bug 报告模板**:
```markdown
**问题描述**: 
[简短描述问题]

**复现步骤**:
1. ...
2. ...
3. ...

**期望行为**:
[描述期望的结果]

**实际行为**:
[描述实际发生的情况]

**环境信息**:
- Phoenix Core 版本：v2.0.0
- Python 版本：3.10
- 操作系统：macOS/Windows/Linux

**日志**:
[粘贴相关日志]
```

---

*本文由技术文档工程师 D 撰写*
