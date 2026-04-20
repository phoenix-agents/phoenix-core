# 技能系统说明文档

## 两种技能格式

Phoenix Core 技能系统支持两种格式的技能，它们**不冲突**，bot 都能正确调用。

### 格式 1：目录格式（安装的技能）

**结构**：
```
skills/pls-office-docs/
└── SKILL.md
```

**来源**：
- 从 CocoHub 安装的 навы
- 手动安装的完整技能

**特点**：
- ✅ 包含完整的技能描述
- ✅ 有使用方法说明
- ✅ 可执行具体操作（如创建 Word 文档）
- ✅ 通过 `verified_skills.json` 白名单验证

**示例技能**：
- `pls-office-docs` - Office 文档处理
- `find-skills` - 技能发现工具

---

### 格式 2：单文件格式（bot 自己生成的技能）

**结构**：
```
workspaces/场控/DYNAMIC/skills/
├── skill_20260411_103035.md
├── 生日直播方案.md
└── 流量密码分析.md
```

**来源**：
- bot 在学习循环中自动创建
- 记录 bot 的工作经验和知识

**特点**：
- 📚 是**知识记忆**，不是可执行代码
- 📋 记录历史方案、话术、经验
- 🔍 供 bot 在执行任务时参考
- 📝 自动命名（带时间戳）或用户命名

**示例内容**：
- 生日直播方案细节
- 流量密码分析
- 粉丝互动话术
- 应急预案

---

## 技能加载优先级

技能加载器按以下顺序加载：

```
1. 共享技能 (/Users/wangsai/phoenix-core/skills/)
   └── 目录格式技能（如 pls-office-docs）

2. 私有技能 (workspaces/<bot_name>/DYNAMIC/skills/)
   ├── 目录格式技能（bot 私有安装）
   └── 单文件格式技能（bot 生成的知识）
```

**优先级规则**：
- 私有技能可以覆盖同名共享技能
- 单文件格式技能不能覆盖目录格式技能（因为格式不同）

---

## 技能调用方式

### 可执行技能（目录格式）

用户说：`"把方案保存为 Word 文档"`

```
LLM → <tool_name>create_word_doc</tool_name>
      ↓
SkillExecutor → skill_loader.execute_skill("pls-office-docs")
      ↓
OfficeSkill.create_word_document() → 创建文件
```

### 知识参考技能（单文件格式）

用户说：`"生日方案具体是什么？"`

```
LLM → 搜索已加载的技能内容
      ↓
找到 `生日直播方案.md` → 读取内容作为参考
      ↓
回复用户方案详情
```

---

## 会冲突吗？

**不会冲突！** 两种技能有不同的用途：

| 特性 | 目录格式技能 | 单文件格式技能 |
|------|-------------|--------------|
| 用途 | **执行操作**（创建文件、调用 API 等） | **知识参考**（历史记录、经验总结） |
| 执行 | ✅ 可执行代码 | ❌ 仅作文本参考 |
| 安装方式 | CocoHub/手动安装 | bot 自动生成 |
| 文件数 | 少（几个目录） | 多（随时间增长） |
| 白名单 | ✅ 需要 | ❌ 不需要（bot 自己生成的） |

---

## bot 如何正确调用？

### 对于可执行技能

bot 的 LLM 会生成工具调用格式：
```xml
<tool_name>create_word_doc</tool_name>
<args>
filename: 方案.docx
title: 方案标题
content: 方案内容
</args>
```

`SkillExecutor` 解析并执行。

### 对于知识参考技能

bot 通过 `_search_relevant_skills()` 方法查找相关技能内容，作为上下文参考：

```python
# 在 phoenix_core_gateway.py 中
skill_context = self._search_relevant_skills(user_message)
```

---

## 总结

✅ **两种格式不冲突**
- 目录格式 = 可执行技能
- 单文件格式 = 知识记忆

✅ **bot 都能正确调用**
- 通过 `SkillExecutor` 执行操作
- 通过 `_search_relevant_skills` 查找参考

✅ **各司其职**
- 安装的技能用来**做事**
- 生成的技能用来**参考**

---

更新时间：2026-04-11
