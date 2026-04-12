# 🦅 Phoenix Core

> 下一代 AI Agent 协作系统 · 8 个专业化 Bot · 6 阶段自进化学习闭环

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Coverage 82%](https://img.shields.io/badge/coverage-82%-green.svg)](tests/)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-ready-blue.svg)](.github/workflows/)

> 💡 **项目起源**: Phoenix Core 基于 [OpenClaw](https://github.com/OpenClaw) 开发，在原有架构基础上进行了全面升级，增加了多 Bot 协作、6 阶段学习闭环、智能记忆系统等核心功能。

[快速开始](#-快速开始) · [文档](docs/) · [示例](#-使用示例) · [社区](#-社区)

---

## 🚀 快速开始

### 15 分钟完成配置

```bash
# 1. 克隆仓库
git clone https://github.com/phoenix-core/phoenix-core.git
cd phoenix-core

# 2. 安装依赖
pip3 install -r requirements.txt

# 3. 运行初始化向导（推荐）
python3 init_wizard.py

# 4. 使用统一 CLI 工具
python3 phoenix.py status    # 检查系统状态
python3 phoenix.py doctor    # 诊断工具
python3 phoenix.py bots start  # 启动所有 Bot
```

### 详细文档

- 📖 [快速入门指南](docs/QUICKSTART.md) - 15 分钟上手
- 📖 [API 参考](docs/API_REFERENCE.md) - 完整 API 文档
- 📖 [最佳实践](docs/BEST_PRACTICES.md) - 配置、性能、安全建议
- 📖 [故障排除](docs/TROUBLESHOOTING.md) - 常见问题和解决方案

---

## ✨ 核心特性

### 多 Bot 协作

预设 8 个专业化 Bot，覆盖完整业务流程：

| Bot | 角色 | 典型用途 |
|-----|------|---------|
| 🎬 编导 | 内容策划 | 直播方案设计、内容策划 |
| ✂️ 剪辑 | 视频编辑 | 视频剪辑、后期制作 |
| 🎨 设计 | 平面设计 | 海报设计、视觉素材 |
| 🎮 场控 | 直播控制 | 直播流程、数据监控 |
| 💬 客服 | 客户支持 | 问题解答、投诉处理 |
| 📊 运营 | 数据分析 | 数据报表、运营策略 |
| 📝 文案 | 内容创作 | 文案撰写、内容优化 |
| 🤖 助理 | 总协调 | 任务分发、跨 Bot 协作 |

### 6 阶段学习闭环

```
任务执行 → AI 评估 → 记忆提取 → 技能进化 → 版本管理 → 自动部署
   ↓                                                                  ↑
   └─────────────────── 持续优化 ────────────────────────────┘
```

- **自动评估**：每次对话后 AI 自动评估任务价值（1-5 星）
- **技能提取**：高分任务自动沉淀为技能
- **版本控制**：技能 v1→v2→v3，支持回滚和谱系追溯
- **跨 Bot 共享**：团队记忆与专业知识共享

---

## 📋 配置方式

### 方式一：初始化向导（推荐）

```bash
python3 init_wizard.py
```

向导会引导你完成：
1. ✅ 配置 LLM Provider API Key
2. ✅ 选择 Bot 团队模板
3. ✅ 配置通信渠道
4. ✅ 高级选项设置

### 方式二：手动配置

```bash
# 复制模板
cp config.template.json config.json
cp .env.example .env

# 编辑配置文件
vim config.json
vim .env

# 启动系统
python3 bot_manager.py start
```

---

## 🛠️ 常用命令

### 使用统一 CLI 工具 (`phoenix.py`)

```bash
# 系统状态
python3 phoenix.py status         # 查看系统状态
python3 phoenix.py doctor         # 诊断工具
python3 phoenix.py doctor --fix   # 自动修复问题

# Bot 管理
python3 phoenix.py bots start     # 启动所有 Bot
python3 phoenix.py bots start --bot 编导    # 启动指定 Bot
python3 phoenix.py bots status    # 查看 Bot 状态
python3 phoenix.py bots stop      # 停止所有 Bot
python3 phoenix.py bots restart   # 重启所有 Bot

# 技能管理
python3 phoenix.py skills list           # 列出所有技能
python3 phoenix.py skills info --name 直播开场白  # 查看技能详情
python3 phoenix.py skills export --output skills_backup.zip  # 导出技能

# 缓存管理
python3 phoenix.py cache stats      # 查看缓存统计
python3 phoenix.py cache clear      # 清空缓存

# 配置管理
python3 phoenix.py config show      # 查看配置
python3 phoenix.py config validate  # 验证配置

# 版本信息
python3 phoenix.py version          # 查看版本号
```

---

## 📁 项目结构

```
phoenix-core/
├── phoenix.py                  # 统一 CLI 工具入口
├── phoenix_core_gateway.py     # API 网关
├── bot_manager.py              # Bot 管理器
├── memory_manager.py           # 记忆管理
├── skill_extractor.py          # 技能提取
├── skill_evolution.py          # 技能进化
├── task_queue.py               # 任务队列
├── init_wizard.py              # 初始化向导
├── .env.example                # 环境变量模板
├── config.template.json        # 配置模板
├── LICENSE                     # Apache 2.0 许可证
├── LEGAL.md                    # 法律声明
├── PRIVACY.md                  # 隐私政策
├── CONTRIBUTING.md             # 贡献指南
├── CHANGELOG.md                # 变更日志
├── workspaces/                 # Bot 工作空间
│   ├── 编导/
│   ├── 场控/
│   └── ...
├── skills/                     # 技能库
├── shared_memory/              # 共享记忆
├── dashboard/                  # Web 仪表板
├── docs/                       # 文档
│   ├── API_REFERENCE.md
│   ├── SKILL_DEVELOPMENT.md
│   ├── BEST_PRACTICES.md
│   └── TROUBLESHOOTING.md
└── tests/                      # 测试套件
```

---

## 🔐 安全建议

### 保护 API Key

```bash
# 设置文件权限
chmod 600 .env
chmod 600 config.json

# 不要提交到 Git
# .gitignore 已包含敏感文件
```

### 遥测配置

Phoenix Core 可选收集匿名使用数据：

```bash
# 在 .env 中设置
PHOENIX_TELEMETRY_OPT_IN=false  # 默认关闭
```

收集内容：
- ✅ 功能使用频率（脱敏）
- ✅ 技能类型分布（哈希）
- ✅ 成功率统计（分桶）

绝不收集：
- ❌ API Key
- ❌ 业务数据
- ❌ 技能内容
- ❌ 用户信息

---

## 🌟 Phoenix Core 优势

| 优势 | 说明 |
|------|------|
| 🤖 **多 Bot 协作** | 原生支持 8 Bot 团队协作，跨 Bot 记忆共享 |
| 🔄 **6 阶段闭环** | 执行→评估→提取→进化，自动优化技能 |
| 📦 **开箱即用** | 3 种预设团队模板，15 分钟配置完成 |
| 📊 **技能版本控制** | v1→v2→v3，支持回滚和谱系追溯 |
| 🔒 **隐私优先** | 数据本地存储，零收集默认 |
| 📖 **中文友好** | 完整中文文档和本地化支持 |

---

## 📊 路线图

### v2.0 (当前版本) - 2026-04

- ✅ 8 个专业化 Bot
- ✅ 6 阶段学习闭环
- ✅ 统一 CLI 工具
- ✅ 完整的文档和测试 (82% 覆盖)

### v2.1 (计划中) - 2026-05

- [ ] Web 仪表板
- [ ] 遥测系统 (Opt-in)
- [ ] 技能市场
- [ ] 更多 AI 模型支持

### v3.0 (规划中) - 2026-Q3

- [ ] 分布式部署
- [ ] 插件系统
- [ ] 企业版功能

---

## 📈 发布准备状态

| 维度 | 状态 | 评分 |
|------|------|------|
| 技术准备度 | ✅ 完成 | 92% |
| 法律合规 | ✅ 完成 | 100% |
| 用户体验 | ✅ 完成 | 85% |
| 文档完整度 | ✅ 完成 | 90% |
| 测试覆盖 | ✅ 完成 | 82% |

详见 [发布准备评估报告](LAUNCH_READINESS_ASSESSMENT.md)

---

## 📚 文档索引

### 入门
- [快速入门](docs/QUICKSTART.md)
- [配置指南](docs/CONFIG_GUIDE.md)
- [常见问题](docs/FAQ.md)

### 开发
- [API 参考](docs/API_REFERENCE.md)
- [技能开发指南](docs/SKILL_DEVELOPMENT.md)
- [最佳实践](docs/BEST_PRACTICES.md)
- [故障排除](docs/TROUBLESHOOTING.md)
- [文档索引](DOCUMENTATION_INDEX.md)

### 法律与合规
- [许可证](LICENSE) - Apache 2.0
- [法律声明](LEGAL.md)
- [隐私政策](PRIVACY.md)
- [贡献指南](CONTRIBUTING.md)

### 项目
- [变更日志](CHANGELOG.md)
- [测试报告](TEST_COVERAGE_REPORT.md)
- [发布评估](LAUNCH_READINESS_ASSESSMENT.md)

---

## 🤝 贡献

欢迎贡献代码、文档或最佳实践！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交变更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

Apache License 2.0 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

- 感谢开源社区提供的灵感
- 感谢所有贡献者和社区成员

---

**🎉 开始使用 Phoenix Core，打造你的多 Bot 协作系统！**
