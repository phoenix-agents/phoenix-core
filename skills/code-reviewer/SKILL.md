---
name: code-reviewer
description: 审查代码质量、安全性和最佳实践
version: 1.0.0
category: development
author: Phoenix Core Team (参考 anthropics/skills)
license: MIT
tags: ["code-review", "quality", "security"]
---

# Code Reviewer - 代码审查员

## 触发条件

当用户需要审查代码时触发：
- "审查这段代码"
- "帮我看看这个函数有什么问题"
- "检查代码安全性"
- "代码是否符合最佳实践"

## 执行步骤

1. **接收代码** - 获取用户提供的代码片段或文件路径
2. **静态分析** - 检查代码语法、格式、命名规范
3. **安全检查** - 识别潜在安全漏洞（SQL 注入、XSS 等）
4. **性能分析** - 查找性能瓶颈和优化点
5. **最佳实践** - 对照语言规范检查最佳实践
6. **生成报告** - 输出结构化审查报告

## 审查维度

| 维度 | 检查项 |
|------|--------|
| **代码质量** | 可读性、可维护性、复杂度 |
| **安全性** | 注入漏洞、敏感信息泄露、权限检查 |
| **性能** | 时间复杂度、空间复杂度、资源使用 |
| **规范** | 命名规范、注释规范、代码格式 |

## 输出格式

```markdown
## 代码审查报告

### 总体评价
⭐⭐⭐⭐ (4/5) - 代码质量良好，存在少量改进空间

### 发现问题
1. **严重** - SQL 注入风险 (第 15 行)
2. **警告** - 未使用的导入语句 (第 3 行)
3. **建议** - 函数过长，建议拆分

### 优化建议
- 使用参数化查询防止 SQL 注入
- 删除未使用的 import
- 将 process_data() 拆分为多个小函数
```

## 示例

### 示例 1：Python 代码审查

用户："审查这段 Python 代码"

```python
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    result = db.execute(query)
    return result is not None
```

→ 执行审查

输出:
```
## 代码审查报告

### 严重问题
1. **SQL 注入漏洞** - 使用 f-string 拼接 SQL 查询，攻击者可绕过认证

### 修复建议
使用参数化查询:
```python
def login(username, password):
    query = "SELECT * FROM users WHERE username=? AND password=?"
    result = db.execute(query, (username, password))
    return result is not None
```
```

### 示例 2：代码优化建议

用户："这段代码怎么优化？"

```python
def process(items):
    result = []
    for i in range(len(items)):
        if items[i] % 2 == 0:
            result.append(items[i] * 2)
    return result
```

输出:
```
### 优化建议

1. 使用列表推导式提高可读性:
```python
def process(items):
    return [item * 2 for item in items if item % 2 == 0]
```

2. 改进函数命名:
   - `process` → `filter_and_double_evens`
```

## 相关技能

- [unit-test-generator](../unit-test-generator/) - 生成单元测试
- [security-analyst](../security-analyst/) - 深度安全分析
- [documentation-writer](../documentation-writer/) - 编写文档

---

*版本：v1.0*
*参考：anthropics/skills*
