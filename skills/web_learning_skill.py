#!/usr/bin/env python3
"""
Web Learning Skill - 从网页学习内容并转化为 Bot 技能

功能:
1. 抓取网页内容
2. AI 分析提取知识点
3. 转化为可复用技能
4. 保存到知识库和技能库

Usage:
    from skills.web_learning_skill import WebLearningSkill
    skill = WebLearningSkill()
    result = skill.learn_from_url("https://example.com/article", "直播运营技巧")
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from urllib.parse import urlparse

# Discord bot 内置 WebFetch
import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class WebLearningSkill:
    """从网页学习内容并转化为技能"""

    def __init__(self, bot_name: str = "运营"):
        self.bot_name = bot_name
        self.workspace_dir = Path(f"workspaces/{bot_name}")
        self.memory_dir = self.workspace_dir / "memory"
        self.skills_dir = self.workspace_dir / "DYNAMIC" / "skills"

        # 确保目录存在
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        # 从 .env 文件读取 API Key
        self.api_key = self._load_api_key()
        self.model = "qwen3.6-plus"  # 使用最新的 qwen3.6-plus 模型
        self.api_url = "https://coding.dashscope.aliyuncs.com/v1/chat/completions"
        self.proxy_url = "http://127.0.0.1:7897"  # 默认代理

    def _load_api_key(self) -> str:
        """从.env 文件加载 API Key"""
        # 先尝试从环境变量读取
        api_key = os.environ.get("CODING_PLAN_API_KEY", "")
        if api_key:
            return api_key

        # 从.env 文件读取
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("CODING_PLAN_API_KEY="):
                        return line.split("=", 1)[1].strip()

        return ""

    def fetch_url(self, url: str) -> str:
        """
        抓取网页内容

        Args:
            url: 网页 URL

        Returns:
            网页文本内容
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')

            # 简单清理 HTML 标签
            text = re.sub(r'<[^>]+>', '', html)
            text = re.sub(r'\s+', ' ', text).strip()

            logger.info(f"成功抓取网页：{url} ({len(text)} 字符)")
            return text[:50000]  # 限制长度

        except Exception as e:
            logger.error(f"抓取失败：{e}")
            return f"无法获取网页内容：{e}"

    def analyze_with_ai(self, content: str, topic: str) -> Dict:
        """
        使用 AI 分析内容并提取知识点

        Args:
            content: 网页内容
            topic: 主题

        Returns:
            分析结果字典
        """
        # API 配置 - 使用 coding-plan 端点
        api_key = os.environ.get("CODING_PLAN_API_KEY", "")
        model = "qwen3.5-plus"
        api_url = "https://coding.dashscope.aliyuncs.com/v1/chat/completions"

        prompt = f"""
你是一个专业的知识提取助手。请从以下内容中提取有价值的知识点，并组织成可复用的技能。

【学习主题】{topic}

【内容来源】网页文章

【待分析内容】
{content[:8000]}  # 限制长度

请按以下格式输出（JSON 格式）：

{{
    "knowledge_points": [
        {{
            "title": "知识点标题",
            "description": "详细描述",
            "key_points": ["要点 1", "要点 2", "要点 3"],
            "how_to_apply": "如何应用到实际工作中",
            "tags": ["标签 1", "标签 2"]
        }}
    ],
    "is_skillworthy": true,  // 是否值得转化为技能（可复用的方法论）
    "skill_draft": {{  // 如果值得转化，提供技能草案
        "name": "技能名称",
        "trigger": "什么情况下触发这个技能",
        "steps": ["步骤 1", "步骤 2", "步骤 3"],
        "tools_needed": ["需要的工具/资源"]
    }}
}}

如果内容不值得转化为技能，is_skillworthy 设为 false。
只输出 JSON，不要其他内容。
"""

        try:
            # 设置代理（每次调用时设置，确保生效）
            proxy = urllib.request.ProxyHandler({'https': self.proxy_url})
            opener = urllib.request.build_opener(proxy)
            old_opener = urllib.request._opener
            urllib.request._opener = opener

            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是一个专业的知识提取助手，擅长从文章中发现可复用的方法论。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.2
            }

            req = urllib.request.Request(
                self.api_url,
                data=json.dumps(data).encode('utf-8'),
                headers=headers,
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=90) as response:
                result = json.loads(response.read().decode('utf-8'))

            # 恢复旧的 opener
            urllib.request._opener = old_opener

            ai_response = result['choices'][0]['message']['content']

            # 解析 JSON
            analysis = json.loads(ai_response)
            logger.info(f"AI 分析完成，提取 {len(analysis.get('knowledge_points', []))} 个知识点")
            return analysis

        except Exception as e:
            logger.error(f"AI 分析失败：{e}")
            # 降级处理：返回基础格式
            return {
                "knowledge_points": [{
                    "title": topic,
                    "description": content[:500],
                    "key_points": [],
                    "how_to_apply": "",
                    "tags": []
                }],
                "is_skillworthy": False,
                "skill_draft": None
            }

    def save_to_knowledge_base(self, analysis: Dict, topic: str):
        """保存到知识库"""
        knowledge_file = self.memory_dir / "知识库.md"

        # 读取现有内容
        existing = ""
        if knowledge_file.exists():
            with open(knowledge_file, "r", encoding="utf-8") as f:
                existing = f.read()

        # 构建新内容
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_content = f"\n\n## 📚 [网络学习] {topic} - {timestamp}\n\n"

        for point in analysis.get("knowledge_points", []):
            new_content += f"### {point.get('title', '知识点')}\n"
            new_content += f"{point.get('description', '')}\n\n"

            if point.get('key_points'):
                new_content += "**要点**:\n"
                for i, kp in enumerate(point['key_points'], 1):
                    new_content += f"{i}. {kp}\n"
                new_content += "\n"

            if point.get('how_to_apply'):
                new_content += f"**应用方法**: {point['how_to_apply']}\n\n"

            if point.get('tags'):
                new_content += f"**标签**: {' '.join(point['tags'])}\n\n"

        new_content += "---\n"

        # 追加写入
        with open(knowledge_file, "a", encoding="utf-8") as f:
            f.write(new_content)

        logger.info(f"知识已保存到：{knowledge_file}")

    def save_as_skill(self, skill_draft: Dict) -> str:
        """保存为技能文件（先到沙盒）"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        skill_name = skill_draft.get("name", "新技能").replace(" ", "_").replace("/", "_")
        skill_id = f"skill_{timestamp}_{skill_name}"

        # 导入沙盒和注册表
        from skill_sandbox import get_sandbox
        from skill_registry import get_registry

        sandbox = get_sandbox(self.bot_name)
        registry = get_registry(self.bot_name)

        skill_content = f"""---
name: {skill_draft.get('name', '新技能')}
description: 从网络学习提取的技能
auto_generated: true
version: 1.0.0
created_at: {datetime.now().isoformat()}
source: web_learning
---

# {skill_draft.get('name', '新技能')}

**来源**: 网络学习提取
**提取时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

## 触发条件

{skill_draft.get('trigger', '用户明确请求相关知识')}

---

## 执行步骤

"""
        for i, step in enumerate(skill_draft.get('steps', []), 1):
            skill_content += f"{i}. **{step}**\n"

        skill_content += "\n"

        if skill_draft.get('tools_needed'):
            skill_content += "## 所需工具\n\n"
            for tool in skill_draft['tools_needed']:
                skill_content += f"- {tool}\n"

        skill_content += "\n---\n"

        # 保存到沙盒目录
        skill_file = sandbox.save_to_sandbox(skill_id, skill_content)

        # 注册技能
        registry.register_skill(skill_id, {
            "name": skill_draft.get('name'),
            "description": "从网络学习提取的技能",
            "source": "web_learning",
            "version": "1.0.0",
            "trigger": skill_draft.get('trigger', ''),
            "steps": skill_draft.get('steps', []),
            "tools_needed": skill_draft.get('tools_needed', [])
        })

        # 运行沙盒测试
        skill_data = {
            "id": skill_id,
            "name": skill_draft.get('name'),
            "trigger": skill_draft.get('trigger', ''),
            "steps": skill_draft.get('steps', []),
            "tools_needed": skill_draft.get('tools_needed', [])
        }
        test_results = sandbox.run_all_tests(skill_data)

        # 提交审批（从 sandbox 移动到 pending）
        from skill_approval import get_approval_workflow
        approval_workflow = get_approval_workflow(self.bot_name)
        approval_workflow.submit_for_approval(skill_id, test_results)

        logger.info(f"技能已保存到沙盒：{skill_file}")
        logger.info(f"沙盒测试结果：{'通过' if test_results.get('overall_passed') else '未通过'}")

        return str(skill_file)

    def learn_from_url(self, url: str, topic: str = None) -> Dict:
        """
        从 URL 学习并转化为知识/技能

        Args:
            url: 学习网址
            topic: 主题（可选，默认从 URL 推断）

        Returns:
            学习结果
        """
        logger.info(f"开始从 URL 学习：{url}")

        # 步骤 1: 抓取内容
        content = self.fetch_url(url)
        if content.startswith("无法获取"):
            return {"success": False, "error": content}

        # 步骤 2: AI 分析
        if not topic:
            topic = urlparse(url).path.strip('/').split('/')[0] or "未知主题"

        analysis = self.analyze_with_ai(content, topic)

        # 步骤 3: 保存到知识库
        self.save_to_knowledge_base(analysis, topic)

        # 步骤 4: 如果值得，保存为技能
        skill_file = None
        if analysis.get("is_skillworthy") and analysis.get("skill_draft"):
            skill_file = self.save_as_skill(analysis["skill_draft"])

        return {
            "success": True,
            "topic": topic,
            "url": url,
            "knowledge_points": len(analysis.get("knowledge_points", [])),
            "skill_created": skill_file is not None,
            "skill_file": skill_file,
            "summary": analysis
        }

    def learn_from_search(self, query: str, num_results: int = 3) -> Dict:
        """
        从网络搜索结果中学习

        Args:
            query: 搜索关键词
            num_results: 搜索结果数量

        Returns:
            学习结果
        """
        # 步骤 1: 搜索（使用 WebFetch API）
        results = self._search_with_webfetch(query, num_results)

        if not results:
            return {"success": False, "error": "未找到搜索结果"}

        # 步骤 2: 合并内容
        combined_content = ""
        for i, r in enumerate(results, 1):
            combined_content += f"[来源 {i}] {r.get('title', '')} - {r.get('body', '')}\n\n"

        # 步骤 3: AI 分析
        analysis = self.analyze_with_ai(combined_content, query)

        # 步骤 4: 保存
        self.save_to_knowledge_base(analysis, query)

        skill_file = None
        if analysis.get("is_skillworthy") and analysis.get("skill_draft"):
            skill_file = self.save_as_skill(analysis["skill_draft"])

        return {
            "success": True,
            "query": query,
            "sources": len(results),
            "knowledge_points": len(analysis.get("knowledge_points", [])),
            "skill_created": skill_file is not None,
            "skill_file": skill_file
        }

    def _search_with_webfetch(self, query: str, num_results: int = 3) -> List[Dict]:
        """使用 WebFetch API 搜索（不需要 ddgs 库）"""
        # 使用 Bing 搜索 URL
        search_url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"

        try:
            # 这里可以集成 WebFetch 或其他搜索 API
            # 目前返回一个占位结果
            logger.info(f"搜索查询：{query}")
            return [{"title": query, "body": f"关于{query}的搜索结果", "href": ""}]
        except Exception as e:
            logger.error(f"搜索失败：{e}")
            return []


# 技能接口函数
def execute_skill(action: str, params: dict) -> dict:
    """执行学习技能"""
    bot_name = params.get("bot_name", "运营")
    skill = WebLearningSkill(bot_name)

    if action == "learn_from_url":
        result = skill.learn_from_url(
            params.get("url", ""),
            params.get("topic")
        )
        return result

    elif action == "learn_from_search":
        result = skill.learn_from_search(
            params.get("query", ""),
            params.get("num_results", 3)
        )
        return result

    else:
        return {"success": False, "error": f"未知动作：{action}"}


if __name__ == "__main__":
    print("=" * 50)
    print("测试 Web Learning 技能")
    print("=" * 50)

    # 测试示例（需要实际 URL）
    skill = WebLearningSkill(bot_name="运营")

    # 示例：从搜索结果学习
    print("\n【测试】从网络搜索学习：'直播运营技巧 2026'")
    result = skill.learn_from_search("直播运营技巧 2026", num_results=3)

    print(f"\n学习结果:")
    print(f"  主题：{result.get('topic')}")
    print(f"  知识点：{result.get('knowledge_points')} 个")
    print(f"  技能创建：{result.get('skill_created')}")
    print(f"  技能文件：{result.get('skill_file')}")

    print("\n" + "=" * 50)
