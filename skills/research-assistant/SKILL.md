---
name: research-assistant
description: 搜索和整理网络信息，生成研究报告
version: 1.0.0
category: research
author: Phoenix Core Team (参考 anthropics/skills)
license: MIT
tags: ["research", "search", "summarization"]
---

# Research Assistant - 研究助理

## 触发条件

当用户需要搜集信息、整理资料、生成报告时触发：
- "帮我查查..."
- "研究一下..."
- "整理...的资料"
- "生成...的研究报告"

## 执行步骤

1. **需求分析** - 理解用户研究主题和需求
2. **关键词提取** - 提取搜索关键词和同义词
3. **多源搜索** - 使用多个搜索引擎获取信息
4. **信息筛选** - 过滤低质量和不相关内容
5. **交叉验证** - 对比多个来源验证准确性
6. **整理归纳** - 按逻辑结构组织信息
7. **生成报告** - 输出结构化研究报告

## 搜索策略

| 策略 | 说明 | 示例 |
|------|------|------|
| **精准搜索** | 使用引号精确匹配 | `"AI Agent 框架"` |
| **排除搜索** | 排除无关内容 | `AI -chatbot` |
| **站点搜索** | 限定特定网站 | `site:github.com AI Agent` |
| **时间范围** | 限定最新信息 | `2025..2026 AI trends` |
| **文件类型** | 特定格式文件 | `filetype:pdf research paper` |

## 输出格式

```markdown
# 研究报告：<主题>

## 执行摘要
200 字以内的核心发现

## 背景介绍
研究主题的背景和重要性

## 主要发现
1. 发现一 + 证据
2. 发现二 + 证据
3. 发现三 + 证据

## 对比分析
| 方案 A | 方案 B | 方案 C |
|--------|--------|--------|
| 优点   | 优点   | 优点   |
| 缺点   | 缺点   | 缺点   |

## 结论与建议
基于研究结果的建议

## 参考资料
[1] 来源名称 - URL
[2] 来源名称 - URL
```

## 示例

### 示例 1：技术调研

用户："帮我调研一下 AI Agent 框架有哪些"

→ 执行搜索
- 搜索关键词：`AI Agent framework 2026 comparison`
- 搜索来源：GitHub、技术博客、官方文档

输出:
```markdown
# 研究报告：AI Agent 框架对比

## 执行摘要
2026 年主流的 AI Agent 框架包括 LangChain、LlamaIndex、CrewAI 等，
各有优劣。LangChain 生态最成熟，CrewAI 在多 Agent 协作方面领先。

## 主要框架对比

| 框架 | Stars | 特点 | 适用场景 |
|------|-------|------|----------|
| LangChain | 80k+ | 工具丰富、文档完善 | 通用 Agent 开发 |
| LlamaIndex | 30k+ | RAG  optimized | 知识库问答 |
| CrewAI | 50k+ | 多 Agent 协作 | 复杂任务编排 |
| AutoGen | 25k+ | 微软出品、对话式 | 对话应用 |

## 建议
- 快速原型 → LangChain
- 企业 RAG → LlamaIndex
- 多 Agent 系统 → CrewAI

## 参考资料
[1] LangChain 官方文档 - https://python.langchain.com
[2] Awesome AI Agents - https://github.com/...
```

### 示例 2：市场研究

用户："研究一下 2026 年 AI 技能市场的情况"

输出:
```markdown
# 研究报告：2026 AI 技能市场分析

## 执行摘要
AI 技能市场在 2026 年快速增长，主要趋势包括 MCP 协议标准化、
安全审核机制完善、跨平台兼容性提升。

## 市场规模
- GitHub 相关项目：440+ MCP 服务器
- 主要平台：Claude Skills、LangChain Skills 等
- 增长率：月均新增 50+ 技能项目

## 热门技能类别
1. 开发工具（代码审查、测试生成）
2. 研究搜索（信息搜集、报告生成）
3.  productivity（文档处理、会议记录）

## 趋势分析
- MCP 协议成为标准
- 安全审核成为必需
- 技能组合编排兴起
```

## 相关技能

- [web-search](../web-search/) - 基础网络搜索
- [web-scraper](../web-scraper/) - 网页内容提取
- [data-analyst](../data-analyst/) - 数据分析
- [documentation-writer](../documentation-writer/) - 文档编写

---

*版本：v1.0*
*参考：anthropics/skills*
