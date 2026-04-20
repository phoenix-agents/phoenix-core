# find-skills

🔍 **Phoenix Core 技能发现工具** - 从 CocoHub 安全技能商店查找和安装技能

## 功能

- 🔎 搜索 CocoHub 的 5000+ 技能
- 🔒 集成 Phoenix Core 安全审计系统
- 📊 显示技能安全评级 (S/A/B/C/D)
- ✅ 安装前自动 vet 检查
- 📥 一键安装已验证技能

## 安装

```bash
# 在 Phoenix Core 工作目录中运行
cd /Users/wangsai/phoenix-core

# 技能已内置，直接使用
```

## 使用方法

### 在对话中使用

```
@场控 帮我查找文档生成相关的技能
@场控 搜索 office 技能
@场控 安装 pls-office-docs 技能
@场控 检查 excel-skill 的安全性
```

### 命令行使用

```bash
# 列出所有可用技能
python3 cocoloop_hub.py list

# 按分类列出
python3 cocoloop_hub.py list --category=document

# 搜索技能
python3 cocoloop_hub.py search "word document"

# 检查技能安全性
python3 cocoloop_hub.py vet pls-office-docs

# 安装技能
python3 cocoloop_hub.py install pls-office-docs

# 查看技能详情
python3 cocoloop_hub.py info pls-office-docs
```

## 安全机制

本技能集成了 Phoenix Core 的安全体系：

1. **白名单检查** - 只允许已验证的技能
2. **安全审计** - 使用 SecurityAuditor 检查代码风险
3. **CocoHub 评级** - 显示 S/A/B/C/D 安全评级
4. **安装前 vet** - 所有技能安装前必须通过 vet 检查

### 安全评级说明

| 评级 | 含义 | 建议 |
|-----|------|-----|
| ✅ safe | 已通过安全审计 | 可放心安装 |
| 🟡 reviewed | 人工审核通过 | 建议使用 |
| ⚪ unverified | 未经验证 | 谨慎使用 |
| 🔴 suspicious | 发现可疑行为 | 禁止使用 |
| ❌ blocked | 确认恶意 | 永久封禁 |

## 推荐技能

### 文档处理
- `pls-office-docs` - Office 文档处理 (PDF/DOCX/XLSX/PPTX)
- `ai-documentation-generator` - AI 文档生成
- `docx-skill` - Word 文档生成
- `markitdown` - 文档转换为 Markdown

###  productivity
- `advanced-calendar` - 日历管理
- `cron-task` - 定时任务
- `browser-control` - 浏览器自动化

## 技能来源

- **CocoHub** (hub.cocoloop.cn) - 国内最大 AI 技能商店
- **ClawHub** - 官方技能市场
- **Phoenix Core 官方** - 已验证技能

## 注意事项

⚠️ **安全提醒**:
- 安装任何技能前请先运行 `vet` 检查
- 不要安装评级为 C 或 D 的技能
- 避免连接金融/个人账户
- 建议在隔离环境中测试新技能

## 故障排除

### 无法连接 CocoHub
```bash
# 检查网络连接
curl https://hub.cocoloop.cn

# 如果无法访问，可能是网络问题
```

### 技能安装失败
```bash
# 先 vet 检查
python3 cocoloop_hub.py vet <skill-name>

# 查看详细错误日志
tail -50 logs/场控.log
```

## 更新日志

- **v1.0.0** (2026-04-11) - 初始版本，集成 CocoHub 技能商店
