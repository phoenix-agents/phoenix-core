---
name: github-pr-helper
description: 协助审查 Pull Request 和 Issue 管理
version: 1.0.0
category: development
author: Phoenix Core Team (参考 awesome-claude-skills)
license: MIT
tags: ["github", "code-review", "pr", "collaboration"]
---

# GitHub PR Helper - GitHub 助手

## 触发条件

当用户需要处理 GitHub 相关任务时触发：
- "审查这个 PR"
- "帮我看看这个 issue"
- "总结这个 commit 的改动"
- "生成 release notes"

## 执行步骤

1. **获取信息** - 从 GitHub API 获取 PR/Issue 详情
2. **代码分析** - 审查代码变更（diff）
3. **上下文理解** - 关联相关 Issue 和讨论
4. **质量评估** - 检查代码质量和规范
5. **生成意见** - 输出审查意见或总结

## 支持的操作

| 操作 | 说明 | 命令示例 |
|------|------|----------|
| **审查 PR** | 分析代码变更并提供意见 | "审查 PR #123" |
| **总结改动** | 概述 commit 或 PR 的变更 | "总结这个 PR 改了什么" |
| **检查 Issue** | 分析 Issue 描述和评论 | "看看 issue #456" |
| **生成 Release** | 基于 PR 列表生成 Release Notes | "生成 v1.0 release notes" |
| **回复评论** | 帮助起草 PR/Issue 回复 | "帮我回复这个评论" |

## 输出格式

### PR 审查报告

```markdown
## PR 审查报告

### 基本信息
- **PR**: #123 - Add user authentication
- **作者**: @username
- **变更**: +500 -200 (8 files)

### 变更概述
1. 新增用户认证模块
2. 添加 JWT token 生成和验证
3. 更新路由中间件

### 代码质量
✅ 测试覆盖充分
⚠️ 缺少密码强度验证
❌ 硬编码的 secret key

### 审查意见
**建议修改后合并**

### 具体建议
1. [安全] 使用环境变量存储 secret key
2. [功能] 添加密码复杂度检查
3. [文档] 补充 API 使用示例
```

## 示例

### 示例 1：PR 审查

用户："帮我审查这个 PR https://github.com/xxx/yyy/pull/123"

输出:
```markdown
## PR 审查报告

### 基本信息
- **PR**: #123 - Add user authentication
- **作者**: @dev123
- **Files**: 8 changed, +500, -200

### 代码变更分析

#### 新增文件
- `auth/jwt_handler.py` - JWT 令牌处理
- `auth/middleware.py` - 认证中间件
- `tests/test_auth.py` - 单元测试

#### 修改文件
- `app.py` - 集成认证路由
- `requirements.txt` - 添加 PyJWT

### 安全性检查
❌ **严重**: `SECRET_KEY` 硬编码在代码中
⚠️ **警告**: 密码未添加复杂度要求
✅ 使用 bcrypt 加密密码

### 代码质量
✅ 单元测试覆盖率达 90%
⚠️ 缺少集成测试
✅ 遵循 PEP8 规范

### 建议
**需要修改后再合并**

必须修复:
1. 将 SECRET_KEY 移到环境变量
2. 添加密码复杂度验证

建议改进:
1. 添加集成测试
2. 补充 API 文档
```

### 示例 2：Release Notes 生成

用户："生成 v1.0 的 release notes"

输出:
```markdown
# Release Notes v1.0

## 新功能
- 用户认证系统 (#120, #123)
- API 速率限制 (#115)
- 管理后台界面 (#118)

## 优化
- 数据库查询性能提升 50% (#112)
- 减少首页加载时间至 1s 以内 (#119)

## Bug 修复
- 修复登录会话过期问题 (#110)
- 修复移动端布局错乱 (#116)

## 技术债务
- 重构用户模块 (#114)
- 升级 Django 到 4.2 (#121)

## 贡献者
感谢以下贡献者：@dev1, @dev2, @dev3

## 升级说明
```bash
pip install -r requirements.txt
python manage.py migrate
```
```

## 相关技能

- [code-reviewer](../code-reviewer/) - 通用代码审查
- [documentation-writer](../documentation-writer/) - 文档编写
- [unit-test-generator](../unit-test-generator/) - 生成测试

---

*版本：v1.0*
*参考：awesome-claude-skills*
