#!/usr/bin/env python3
"""
Phoenix Core Skill Marketplace - 技能市场

功能:
1. 浏览远程技能
2. 一键安装/卸载
3. 技能评分和评论
4. 来源可信度验证

Usage:
    python3 skill_marketplace.py browse        # 浏览技能
    python3 skill_marketplace.py install <id>  # 安装技能
    python3 skill_marketplace.py remove <id>   # 卸载技能
    python3 skill_marketplace.py search <query> # 搜索技能
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from skill_whitelist import SkillWhitelistManager, TRUSTED_SOURCES

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 技能市场配置
MARKETPLACE_CONFIG = {
    "sources": [
        {
            "id": "phoenix-official",
            "name": "Phoenix Core 官方技能",
            "url": "https://api.example.com/phoenix-skills",
            "trust_level": "official",
            "local_file": Path(__file__).parent / ".skills" / "sample_skills.json"
        },
        {
            "id": "phoenix-community",
            "name": "Phoenix Community 社区技能",
            "url": "https://api.example.com/phoenix-community-skills",
            "trust_level": "verified"
        },
        {
            "id": "voltagent",
            "name": "VoltAgent 技能库",
            "url": "https://raw.githubusercontent.com/VoltAgent/awesome-phoenix-skills/main/skills.json",
            "trust_level": "community"
        }
    ],
    "cache_file": Path(__file__).parent / ".skills_cache.json",
    "cache_ttl": 3600  # 1 小时
}


class SkillMarketplace:
    """技能市场管理器"""

    def __init__(self, workspace_dir: Path = None):
        self.workspace_dir = workspace_dir or Path(__file__).parent / "workspaces"
        self.whitelist_manager = SkillWhitelistManager()
        self._cache: Dict[str, Any] = {}
        self._load_cache()

    def _load_cache(self):
        """加载缓存"""
        if MARKETPLACE_CONFIG["cache_file"].exists():
            try:
                with open(MARKETPLACE_CONFIG["cache_file"], "r") as f:
                    self._cache = json.load(f)
                logger.info(f"Loaded skills cache")
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")

    def _save_cache(self):
        """保存缓存"""
        try:
            MARKETPLACE_CONFIG["cache_file"].parent.mkdir(parents=True, exist_ok=True)
            with open(MARKETPLACE_CONFIG["cache_file"], "w") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _fetch_skills(self, source_id: str) -> List[Dict]:
        """从指定来源获取技能列表"""
        source = next(
            (s for s in MARKETPLACE_CONFIG["sources"] if s["id"] == source_id),
            None
        )
        if not source:
            return []

        # 检查是否有本地文件
        local_file = source.get("local_file")
        if local_file and local_file.exists():
            try:
                with open(local_file, "r", encoding="utf-8") as f:
                    skills = json.load(f)
                logger.info(f"Loaded skills from local file: {source_id}")
                return skills
            except Exception as e:
                logger.error(f"Failed to load local skills: {e}")

        # 检查缓存
        cache_key = f"skills_{source_id}"
        cached = self._cache.get(cache_key, {})
        cached_at = cached.get("cached_at", 0)
        if datetime.now().timestamp() - cached_at < MARKETPLACE_CONFIG["cache_ttl"]:
            return cached.get("skills", [])

        # 从网络获取
        try:
            response = requests.get(source["url"], timeout=10)
            response.raise_for_status()
            skills = response.json()

            # 更新缓存
            self._cache[cache_key] = {
                "skills": skills,
                "cached_at": datetime.now().timestamp()
            }
            self._save_cache()

            return skills
        except Exception as e:
            logger.error(f"Failed to fetch skills from {source_id}: {e}")
            return cached.get("skills", [])

    def browse(self, category: Optional[str] = None) -> List[Dict]:
        """
        浏览技能市场

        Args:
            category: 分类过滤

        Returns:
            技能列表
        """
        all_skills = []

        for source in MARKETPLACE_CONFIG["sources"]:
            skills = self._fetch_skills(source["id"])
            for skill in skills:
                skill["source"] = source["id"]
                skill["source_name"] = source["name"]
                skill["trust_level"] = source["trust_level"]

                if category and skill.get("category") != category:
                    continue

                all_skills.append(skill)

        return all_skills

    def search(self, query: str) -> List[Dict]:
        """
        搜索技能

        Args:
            query: 搜索关键词

        Returns:
            匹配的技能列表
        """
        all_skills = self.browse()
        query_lower = query.lower()

        results = []
        for skill in all_skills:
            # 搜索标题、描述、标签
            searchable = " ".join([
                skill.get("name", ""),
                skill.get("description", ""),
                " ".join(skill.get("tags", []))
            ]).lower()

            if query_lower in searchable:
                results.append(skill)

        return results

    def install(self, skill_id: str, target_bot: Optional[str] = None) -> Dict:
        """
        安装技能

        Args:
            skill_id: 技能 ID
            target_bot: 目标 Bot (可选，默认所有 Bot)

        Returns:
            安装结果
        """
        result = {
            "success": False,
            "skill_id": skill_id,
            "message": "",
            "installed_to": []
        }

        # 查找技能
        skill_data = None
        for source in MARKETPLACE_CONFIG["sources"]:
            skills = self._fetch_skills(source["id"])
            for skill in skills:
                if skill.get("id") == skill_id:
                    skill_data = skill
                    skill_data["source"] = source["id"]
                    break

        if not skill_data:
            result["message"] = f"技能未找到：{skill_id}"
            return result

        # 检查白名单
        if not self.whitelist_manager.is_skill_allowed(skill_id):
            result["message"] = f"技能已被封禁：{skill_id}"
            return result

        # 下载技能内容
        skill_content = skill_data.get("content", "")
        if not skill_content and skill_data.get("download_url"):
            try:
                response = requests.get(skill_data["download_url"], timeout=10)
                skill_content = response.text
            except Exception as e:
                result["message"] = f"下载失败：{e}"
                return result

        # 安装到目标 Bot
        bots = [target_bot] if target_bot else ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]

        for bot_name in bots:
            skills_dir = self.workspace_dir / bot_name / "DYNAMIC" / "skills"
            skills_dir.mkdir(parents=True, exist_ok=True)

            skill_file = skills_dir / f"{skill_id}.md"
            skill_file.write_text(skill_content, encoding="utf-8")

            result["installed_to"].append(bot_name)

        # 添加到白名单
        self.whitelist_manager.add_skill(
            skill_id,
            {"name": skill_data.get("name", skill_id), "content": skill_content},
            source=skill_data.get("source", "marketplace")
        )

        result["success"] = True
        result["message"] = f"已安装到 {len(result['installed_to'])} 个 Bot"
        logger.info(f"Installed skill {skill_id} to {len(result['installed_to'])} bots")

        return result

    def remove(self, skill_id: str) -> Dict:
        """
        卸载技能

        Args:
            skill_id: 技能 ID

        Returns:
            卸载结果
        """
        result = {
            "success": False,
            "skill_id": skill_id,
            "removed_from": []
        }

        for bot_name in ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]:
            skills_dir = self.workspace_dir / bot_name / "DYNAMIC" / "skills"
            skill_file = skills_dir / f"{skill_id}.md"

            if skill_file.exists():
                skill_file.unlink()
                result["removed_from"].append(bot_name)

        result["success"] = True
        logger.info(f"Removed skill {skill_id} from {len(result['removed_from'])} bots")

        return result

    def rate_skill(self, skill_id: str, rating: int, comment: str = "") -> Dict:
        """
        评分技能

        Args:
            skill_id: 技能 ID
            rating: 评分 (1-5)
            comment: 评论

        Returns:
            评分结果
        """
        if rating < 1 or rating > 5:
            return {"success": False, "message": "评分必须是 1-5"}

        # 这里可以保存到本地或提交到远程
        ratings_file = Path(__file__).parent / ".skill_ratings.json"

        if ratings_file.exists():
            with open(ratings_file, "r") as f:
                ratings = json.load(f)
        else:
            ratings = {}

        if skill_id not in ratings:
            ratings[skill_id] = {"ratings": [], "comments": []}

        ratings[skill_id]["ratings"].append({
            "rating": rating,
            "comment": comment,
            "timestamp": datetime.now().isoformat()
        })

        with open(ratings_file, "w") as f:
            json.dump(ratings, f, indent=2)

        return {"success": True, "message": "评分已提交"}


def print_skills_table(skills: List[Dict]):
    """打印技能表格"""
    if not skills:
        print("暂无技能")
        return

    print(f"\n{'名称':<30} {'来源':<20} {'信任等级':<12} {'分类':<15}")
    print("-" * 80)

    for skill in skills[:20]:  # 最多显示 20 个
        name = skill.get("name", skill.get("id", "unknown"))[:28]
        source = skill.get("source_name", skill.get("source", "unknown"))[:18]
        trust = skill.get("trust_level", "unknown")[:10]
        category = skill.get("category", "general")[:13]

        print(f"{name:<30} {source:<20} {trust:<12} {category:<15}")

    if len(skills) > 20:
        print(f"... 还有 {len(skills) - 20} 个技能")


def main():
    import sys

    if len(sys.argv) < 2:
        print("Phoenix Core Skill Marketplace")
        print("\nUsage:")
        print("  python3 skill_marketplace.py browse [category]  # 浏览技能")
        print("  python3 skill_marketplace.py search <query>     # 搜索技能")
        print("  python3 skill_marketplace.py install <id>       # 安装技能")
        print("  python3 skill_marketplace.py remove <id>        # 卸载技能")
        print("  python3 skill_marketplace.py rate <id> <rating> [comment]  # 评分")
        sys.exit(1)

    marketplace = SkillMarketplace()
    command = sys.argv[1]

    if command == "browse":
        category = sys.argv[2] if len(sys.argv) > 2 else None
        skills = marketplace.browse(category)
        print(f"\n📚 技能市场{' - 分类：' + category if category else ''}")
        print_skills_table(skills)

    elif command == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        skills = marketplace.search(query)
        print(f"\n🔍 搜索结果：{query}")
        print_skills_table(skills)

    elif command == "install" and len(sys.argv) > 2:
        skill_id = sys.argv[2]
        target = sys.argv[3] if len(sys.argv) > 3 else None
        result = marketplace.install(skill_id, target)
        print(f"\n安装结果：{result['message']}")
        if result["success"]:
            print(f"已安装到：{', '.join(result['installed_to'])}")

    elif command == "remove" and len(sys.argv) > 2:
        skill_id = sys.argv[2]
        result = marketplace.remove(skill_id)
        print(f"\n卸载结果：已从 {', '.join(result['removed_from'])} 移除")

    elif command == "rate" and len(sys.argv) > 3:
        skill_id = sys.argv[2]
        rating = int(sys.argv[3])
        comment = sys.argv[4] if len(sys.argv) > 4 else ""
        result = marketplace.rate_skill(skill_id, rating, comment)
        print(f"\n评分结果：{result['message']}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
