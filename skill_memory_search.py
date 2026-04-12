#!/usr/bin/env python3
"""
Memory Search Skill - Search bot memory for specific content

Usage in Discord:
  @Bot 搜索记忆：生日直播
  @Bot 记忆搜索：福袋
"""

from pathlib import Path
import re
from typing import List, Dict, Any


def search_memory_files(bot_name: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search all memory files for a specific bot.

    Args:
        bot_name: Name of the bot (e.g., '编导', '场控', '运营')
        query: Search term
        limit: Maximum results to return

    Returns:
        List of matching results with file path and content preview
    """
    results = []
    memory_dir = Path(__file__).parent / "workspaces" / {bot_name} / "memory"

    if not memory_dir.exists():
        return [{'error': f'Memory directory not found for {bot_name}'}]

    # Search in each subdirectory
    for subdir in ['知识库', '项目', '学习笔记', '日志']:
        dir_path = memory_dir / subdir
        if not dir_path.exists():
            continue

        for md_file in dir_path.glob('*.md'):
            try:
                content = md_file.read_text(encoding='utf-8')

                # Remove frontmatter
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        content = parts[2]

                # Search for query
                if query in content:
                    # Find context around the match
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if query in line:
                            # Get context (line + 2 lines before and after)
                            start = max(0, i - 2)
                            end = min(len(lines), i + 3)
                            context = '\n'.join(lines[start:end])

                            results.append({
                                'file': f'{subdir}/{md_file.name}',
                                'line': i + 1,
                                'context': context.strip(),
                                'match': line.strip()
                            })

                            if len(results) >= limit:
                                break

            except Exception as e:
                continue

        if len(results) >= limit:
            break

    return results


def format_search_results(results: List[Dict], query: str, bot_name: str) -> str:
    """Format search results as a readable message."""
    if not results:
        return f"🔍 未在 {bot_name} 的记忆中找到 \"{query}\" 相关内容"

    if 'error' in results[0]:
        return f"❌ {results[0]['error']}"

    output = f"🔍 在 {bot_name} 的记忆中找到 {len(results)} 条 \"{query}\" 相关结果：\n\n"

    for i, result in enumerate(results[:5], 1):
        output += f"**{i}. {result['file']}** (第 {result['line']} 行)\n"
        output += f"```\n{result['context']}\n```\n\n"

    if len(results) > 5:
        output += f"_...还有 {len(results) - 5} 条结果_\n"

    return output


# Skill handler
def handle_memory_search(bot_name: str, query: str) -> str:
    """
    Handle memory search request.

    Args:
        bot_name: Bot name
        query: Search query

    Returns:
        Formatted search results
    """
    results = search_memory_files(bot_name, query, limit=10)
    return format_search_results(results, query, bot_name)


# Test
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python3 skill_memory_search.py <bot_name> <query>")
        print("Example: python3 skill_memory_search.py 编导 生日")
        sys.exit(1)

    bot = sys.argv[1]
    query = sys.argv[2]

    result = handle_memory_search(bot, query)
    print(result)
