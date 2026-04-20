# 技能安装指南

## 技能目录结构

技能必须按照以下格式保存，才能被技能加载器正确识别：

```
skills/
├── pls-office-docs/          # 技能目录（名称即技能名）
│   └── SKILL.md              # 必须的描述文件
├── find-skills/
│   └── SKILL.md
└── your-new-skill/
    └── SKILL.md
```

## SKILL.md 文件要求

每个技能必须包含 `SKILL.md` 文件，建议包含以下内容：

```markdown
# 技能名称

## 功能描述
简要说明技能的功能

## 依赖安装
如果需要 Python 依赖，说明如何安装

## 使用方法
如何使用这个技能

## Python 代码示例
如果有，提供代码示例

## 安全说明
安全性说明和注意事项
```

## 安装技能的两种方式

### 方式 1：通过 CocoHub 安装（推荐）

```bash
python3 cocoloop_hub.py install <skill_name>
```

**自动完成**：
1. ✅ 安全性 vet 检查
2. ✅ 保存到正确的目录格式
3. ✅ 添加到白名单
4. ✅ 所有 bot 立即可用

### 方式 2：手动安装

1. 在 `skills/` 目录创建技能子目录
2. 编写 `SKILL.md` 文件
3. 在 `verified_skills.json` 添加白名单条目
4. 重启 bot

## 技能加载优先级

技能加载器按以下顺序加载技能：

1. **共享技能** (`/Users/wangsai/phoenix-core/skills/`) - 所有 bot 共用
2. **私有技能** (`workspaces/<bot_name>/DYNAMIC/skills/`) - 仅特定 bot 使用

私有技能可以覆盖同名共享技能（用于自定义版本）。

## 验证技能已加载

```bash
python3 -c "
from skill_loader import SkillLoader
loader = SkillLoader('场控')
print('已加载技能:', list(loader.skills.keys()))
"
```

## 故障排查

### 技能安装了但 bot 用不了？

1. **检查目录格式**：必须是 `skills/技能名/SKILL.md`
2. **检查白名单**：技能必须在 `verified_skills.json` 中
3. **重启 bot**：新技能需要重启才能加载

### 日志中看不到技能？

```bash
# 查看 bot 启动日志，应该有类似：
# [场控] Loaded 17 skills for activation
```

---

更新时间：2026-04-11
