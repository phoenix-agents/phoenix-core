# 贡献者指南

感谢你对 Phoenix Core 的兴趣！本指南说明如何参与项目贡献。

## 🚀 快速开始

### 1. Fork 项目

在 GitHub 上 Fork 本仓库，然后克隆到本地：

```bash
git clone https://github.com/YOUR_USERNAME/phoenix-core.git
cd phoenix-core
```

### 2. 创建分支

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/issue-123
```

### 3. 开发并测试

确保你的代码：
- ✅ 通过现有测试
- ✅ 添加新测试（如适用）
- ✅ 遵循代码风格（PEP 8）

### 4. 提交 Pull Request

```bash
git commit -m "feat: 添加新功能"
git push origin feature/your-feature-name
```

然后在 GitHub 上创建 Pull Request。

## 📋 代码风格

### Python 规范

- 遵循 PEP 8
- 使用 4 空格缩进
- 函数/类添加文档字符串
- 类型注解（推荐）

```python
def calculate_score(
    reusability: float,
    complexity: float,
    effectiveness: float,
    generality: float
) -> float:
    """
    计算任务价值分数（4 维评估）
    
    Args:
        reusability: 可复用性 (0-1)
        complexity: 复杂度 (0-1)
        effectiveness: 有效性 (0-1)
        generality: 通用性 (0-1)
    
    Returns:
        综合分数 (0-1)
    """
    return (reusability + complexity + effectiveness + generality) / 4
```

### 提交信息规范

遵循 Conventional Commits：

```
feat: 添加新功能
fix: 修复 bug
docs: 文档更新
style: 代码格式（不影响功能）
refactor: 重构（不是新功能也不是修复）
test: 添加/修复测试
chore: 构建过程或辅助工具变动
```

## 📝 贡献者协议（CLA）

通过向本项目提交代码，你同意：

1. **版权许可**
   - 你拥有提交内容的版权或有权授权
   - 你同意以 Apache 2.0 许可证发布你的贡献

2. **原创声明**
   - 你的贡献是原创的，或你有权提交
   - 不侵犯任何第三方知识产权

3. **专利授权**
   - 你授予用户专利许可（Apache 2.0 第 3 条）

4. **无额外限制**
   - 你的贡献不添加额外限制

## 🔍 审查流程

1. **自动检查**
   - CI 测试运行
   - 代码风格检查
   - 测试覆盖率检查

2. **人工审查**
   - 核心维护者审查代码
   - 通常 3-5 个工作日内反馈

3. **合并**
   - 审查通过后合并到主分支
   - 自动关闭关联 Issue

## 📚 贡献类型

### 代码贡献
- 新功能
- Bug 修复
- 性能优化
- 重构

### 文档贡献
- 错别字修正
- 示例代码改进
- 新增文档
- 翻译

### 社区贡献
- 问题报告
- 功能建议
- 帮助他人解决问题
- 分享使用案例

## 🎯 待贡献领域

查看 [Issues](https://github.com/phoenix-core/phoenix-core/issues) 寻找可贡献的任务：

- `good first issue` - 适合新手
- `help wanted` - 需要帮助
- `bug` - Bug 修复
- `enhancement` - 功能增强

## ❓ 常见问题

**Q: 我的 PR 多久会被审查？**
A: 通常 3-5 个工作日。如超过一周，可在 PR 中礼貌提醒。

**Q: 我可以提交破坏性变更吗？**
A: 请先创建 Issue 讨论，获得核心维护者同意后再实施。

**Q: 贡献后我能获得什么？**
A: 你的名字将出现在贡献者列表中。更重要的是，你为全球开源社区做出了贡献！🎉

## 📞 联系方式

- 问题反馈：[GitHub Issues](https://github.com/phoenix-core/phoenix-core/issues)
- 讨论：[GitHub Discussions](https://github.com/phoenix-core/phoenix-core/discussions)

---

感谢你的贡献！🙏
