# Phoenix Core 安全设计文档

**版本**: v2026.4.9
**日期**: 2026-04-09

---

## 🛡️ 整体安全设计：纵深防御

Phoenix Core 继承并扩展了 Phoenix Core 的安全设计理念，通过多层安全机制防止误修改和恶意操作。

### 设计原则与实现

| 设计原则 | 具体实现 | 作用与好处 |
|----------|----------|------------|
| **配置文件隔离** | 支持项目级配置文件 (`~/.openclaw/configs/<project>/`) | 不同项目记忆和技能物理隔离，避免项目间"串味" |
| **本地存储为主** | 所有记忆保存在本地 `~/.openclaw/` 目录 | 100% 本地控制，无云端泄露风险 |
| **RBAC 权限控制** | 技能风险分级 + 执行前评估 | 精细化权限管理，敏感操作需确认 |
| **技能守卫** | `skill_risk_assessor.py` + `skill_executor.py` | 双重检查，防止危险技能执行 |

---

## 🔬 记忆生命周期管理

### 1. "冻结"读取，过程可预期

```
会话开始 → 加载 MEMORY.md/USER.md/SKILL.md → 冻结为系统提示词快照
              ↓
     会话期间记忆上下文保持不变
              ↓
     执行完毕后才可能写入新记忆
```

**保证**: 任务执行期间，Agent 的"记忆"稳定且可预测。

### 2. "主动写入"，过程受控

| 写入方式 | 触发条件 | 用户控制 |
|----------|----------|----------|
| **TaskEvaluator 自动评估** | 任务完成后自动判断是否值得保存 | 可通过 `_auto_extract_skills` 开关控制 |
| **用户显式命令** | `memory add ...` | 完全由用户发起 |
| **技能优化** | 执行失败率过高时触发 | 可配置为手动确认模式 |

---

## 🛡️ 深度防御：防误改的多重保障

### 1. 技能执行风险评估

```python
# skill_risk_assessor.py
ACTION_RISK = {
    # 只读操作 - 低风险
    "check": 0.1, "verify": 0.1, "read": 0.1, "list": 0.1,
    # 修改操作 - 中风险
    "update": 0.4, "modify": 0.4, "create": 0.5,
    # 删除操作 - 高风险
    "delete": 0.8, "drop": 0.9, "remove": 0.8,
}
```

**执行流程**:
```
技能激活 → 风险评估 → [高风险时询问用户] → 沙盒模拟 → 实际执行
```

### 2. 沙盒模拟 (Sandbox)

```python
# 执行前模拟
result = manager.execute_skill(
    skill_name="Deploy Bot",
    sandbox=True  # 沙盒模式
)
# 输出：预测的副作用、风险等级、建议
```

**模拟内容**:
- 文件系统变更预测
- 网络请求影响评估
- 命令执行副作用分析

### 3. 记忆容量限制

| 文件 | 限制 | 目的 |
|------|------|------|
| MEMORY.md | 10,000 字符 | 防止单条记忆臃肿 |
| USER.md | 5,000 字符 | 控制个人偏好条目数量 |
| SKILL.md | 10,000 字符 | 限制技能总数 |

### 4. 技能被动加载

- 技能创建后**被动等待调用**
- Agent **不会随意修改**已有技能
- 技能优化需要**执行失败数据支撑**

---

## 🔀 数据隔离：项目级"安全屋"

### 物理隔离结构

```
~/.openclaw/
├── configs/
│   ├── project-a/
│   │   ├── MEMORY.md
│   │   ├── USER.md
│   │   └── SKILL.md
│   └── project-b/
│       ├── MEMORY.md
│       ├── USER.md
│       └── SKILL.md
├── sessions/
│   └── <project>/
│       └── session.db
└── logs/
```

### 隔离保证

- ✅ 项目 A 的记忆**不会**应用到项目 B
- ✅ 项目 A 的技能**不会**在项目 B 中激活
- ✅ 项目 A 的会话历史**独立存储**

---

## 🧰 保险丝：备份与恢复

### 文件位置

| 类型 | 路径 | 备份建议 |
|------|------|----------|
| 记忆 | `~/.openclaw/configs/<project>/MEMORY.md` | 每日备份 |
| 用户偏好 | `~/.openclaw/configs/<project>/USER.md` | 每周备份 |
| 技能 | `~/.openclaw/configs/<project>/SKILL.md` | 变更后备份 |
| 会话 | `~/.openclaw/sessions/<project>/session.db` | 可选 |

### 恢复命令

```bash
# 查看当前记忆
cat ~/.openclaw/configs/default/MEMORY.md

# 手动编辑修正
vim ~/.openclaw/configs/default/MEMORY.md

# 从备份恢复
cp ~/.openclaw/backups/MEMORY.md.bak ~/.openclaw/configs/default/MEMORY.md
```

---

## 🔒 已实现的安全机制清单

### ✅ 已实现

| 机制 | 文件 | 状态 |
|------|------|------|
| 技能风险评估 | `skill_risk_assessor.py` | ✅ |
| 沙盒执行模拟 | `skill_executor.py` | ✅ |
| 记忆容量限制 | `memory_store.py`, `skill_store.py` | ✅ |
| 本地存储 | SQLite + Markdown 文件 | ✅ |
| 项目隔离 | 配置目录结构 | ✅ |
| 执行结果学习 | `skill_optimizer.py` | ✅ |
| 自动优化阈值控制 | `auto_optimizer.py` | ✅ |
| RBAC 权限控制 | `skills_guard.py` | ✅ |
| 内容安全扫描 | `skills_guard.py` | ✅ |
| 审计日志 | `skills_guard.py` | ✅ |
| 确认机制 | `skills_guard.py` | ✅ |

### 🚧 待实现

| 机制 | 优先级 | 说明 |
|------|--------|------|
| 优化回滚 | 低 | A/B 测试后自动回退 |
| 角色持久化 | 低 | 将角色配置保存到配置文件 |

---

## 🤔 常见疑虑与解答

| 用户问题 | 解决方案 |
|----------|----------|
| 项目 A 的习惯会应用到项目 B 吗？ | 使用项目级配置隔离，`--config project-b` 启动 |
| Agent 会自己修改技能吗？ | 不会，技能优化需要执行失败数据 + 阈值触发 |
| 如何确认 Agent 没乱记东西？ | 所有记忆文件为纯文本，随时 `cat` 查看 |
| 记错了能改回来吗？ | 直接编辑 `.md` 文件或从备份恢复 |
| 自动优化会乱改技能吗？ | 可设置 `dry_run=True` 预览，或调高阈值 |

---

## 📋 安全配置建议

### 开发环境

```python
# 关闭自动优化，手动审查
manager.set_auto_optimize_enabled(False)

# 沙盒模式强制开启
result = manager.execute_skill(..., sandbox=True)

# 低阈值触发询问
manager.set_auto_optimize_threshold(0.7)
```

### 生产环境

```python
# 启用自动优化，但限制在安全阈值内
manager.set_auto_optimize_threshold(0.5)

# 后台服务间隔拉长
manager.start_auto_optimization(interval_minutes=60)

# 定期查看优化历史
history = manager.get_optimization_history()
```

---

## 🔍 安全检查清单

执行敏感操作前，Agent 应自检：

- [ ] 已进行风险评估
- [ ] 已确认项目配置隔离
- [ ] 已检查技能来源
- [ ] 已记录执行日志
- [ ] 已准备回滚方案

---

**状态**: ✅ 安全机制文档化
**下次审查**: 2026-05-09
