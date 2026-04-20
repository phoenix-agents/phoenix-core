#!/usr/bin/env python3
"""
Web Search Skill - DuckDuckGo 免费网络搜索

功能:
- 网络搜索（无需 API Key）
- 新闻搜索
- 图片搜索
- 结果摘要

Usage:
    from skills.web_search_skill import WebSearchSkill
    skill = WebSearchSkill()
    results = skill.search("Python 教程")
"""

import logging
from typing import List, Dict
from urllib.parse import urlparse

# 使用 ddgs 库（需要 VPN）
from ddgs import DDGS

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class WebSearchSkill:
    """Web 搜索技能 - 使用 DuckDuckGo API"""

    def __init__(self, max_results: int = 10):
        self.max_results = max_results
        self.ddgs = DDGS()

    def search(self, query: str, max_results: int = None) -> List[Dict[str, str]]:
        """
        搜索网络内容

        Args:
            query: 搜索关键词
            max_results: 返回结果数量

        Returns:
            搜索结果列表，每项包含：title, href, body, source
        """
        max_results = max_results or self.max_results

        try:
            results = []
            for result in self.ddgs.text(query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "href": result.get("href", ""),
                    "body": result.get("body", ""),
                    "source": self._extract_source(result.get("href", ""))
                })

            logger.info(f"搜索 '{query}' 找到 {len(results)} 条结果")
            return results

        except Exception as e:
            logger.error(f"搜索失败：{e}")
            return []

    def news(self, query: str, max_results: int = None) -> List[Dict[str, str]]:
        """
        搜索新闻

        Args:
            query: 搜索关键词
            max_results: 返回结果数量

        Returns:
            新闻结果列表，每项包含：title, href, body, date, source
        """
        max_results = max_results or self.max_results

        try:
            results = []
            for result in self.ddgs.news(query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "href": result.get("url", ""),
                    "body": result.get("body", ""),
                    "date": result.get("date", ""),
                    "source": result.get("source", "")
                })

            logger.info(f"新闻搜索 '{query}' 找到 {len(results)} 条结果")
            return results

        except Exception as e:
            logger.error(f"新闻搜索失败：{e}")
            return []

    def images(self, query: str, max_results: int = None) -> List[Dict[str, str]]:
        """
        搜索图片

        Args:
            query: 搜索关键词
            max_results: 返回结果数量

        Returns:
            图片结果列表，每项包含：title, image, source, url
        """
        max_results = max_results or self.max_results

        try:
            results = []
            for result in self.ddgs.images(query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "image": result.get("image", ""),
                    "source": result.get("source", ""),
                    "url": result.get("url", "")
                })

            logger.info(f"图片搜索 '{query}' 找到 {len(results)} 条结果")
            return results

        except Exception as e:
            logger.error(f"图片搜索失败：{e}")
            return []

    def _extract_source(self, url: str) -> str:
        """从 URL 提取来源域名"""
        try:
            domain = urlparse(url).netloc
            return domain.replace("www.", "")
        except:
            return "unknown"

    def summarize(self, query: str, max_results: int = 5) -> str:
        """
        搜索并生成摘要

        Args:
            query: 搜索关键词

        Returns:
            摘要文本
        """
        results = self.search(query, max_results=max_results)

        if not results:
            return "未找到相关信息"

        # 简单摘要
        summary_parts = []
        for i, r in enumerate(results[:3], 1):
            summary_parts.append(f"{i}. {r['title']} - {r['body'][:80]}...")

        summary = f"关于 '{query}' 的搜索结果：\n\n" + "\n\n".join(summary_parts)
        summary += f"\n\n共找到 {len(results)} 条结果"

        return summary


# 技能接口函数（供 SkillLoader 调用）
def execute_skill(action: str, params: dict) -> dict:
    """执行搜索技能"""
    skill = WebSearchSkill()

    if action == "search":
        results = skill.search(params.get("query", ""), params.get("max_results", 10))
        return {"success": True, "results": results}

    elif action == "news":
        results = skill.news(params.get("query", ""), params.get("max_results", 5))
        return {"success": True, "results": results}

    elif action == "images":
        results = skill.images(params.get("query", ""), params.get("max_results", 5))
        return {"success": True, "results": results}

    elif action == "summarize":
        summary = skill.summarize(params.get("query", ""))
        return {"success": True, "summary": summary}

    else:
        return {"success": False, "error": f"未知动作：{action}"}


# 测试
if __name__ == "__main__":
    print("=" * 50)
    print("测试 Web Search 技能 (DuckDuckGo)")
    print("=" * 50)

    skill = WebSearchSkill()

    # 测试普通搜索
    print("\n【测试 1】普通搜索：'Python 教程 2026'")
    results = skill.search("Python 教程 2026", max_results=5)
    for r in results:
        print(f"\n  📄 {r['title']}")
        print(f"     来源：{r['source']}")
        print(f"     摘要：{r['body'][:60]}...")

    # 测试新闻搜索
    print("\n\n【测试 2】新闻搜索：'AI 人工智能'")
    news = skill.news("AI 人工智能", max_results=3)
    for n in news:
        print(f"\n  📰 {n['title']}")
        print(f"     日期：{n['date']} | 来源：{n['source']}")

    # 测试摘要
    print("\n\n【测试 3】摘要：'直播运营技巧'")
    summary = skill.summarize("直播运营技巧")
    print(summary)

    print("\n" + "=" * 50)
    print("测试完成!")
    print("=" * 50)
