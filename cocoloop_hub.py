#!/usr/bin/env python3
"""
CocoLoop Hub Integration - 安全技能商店集成

功能:
1. 从 hub.cocoloop.cn 获取技能列表
2. 技能安全评级查询 (S/A/B/C/D)
3. 技能安装前自动 vet 检查
4. 与现有白名单系统集成

Usage:
    python3 cocoloop_hub.py list              # 列出所有可用技能
    python3 cocoloop_hub.py search <query>    # 搜索技能
    python3 cocoloop_hub.py install <skill>   # 安装技能
    python3 cocoloop_hub.py vet <skill>       # 检查技能安全性
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
from datetime import datetime

# 导入现有安全系统
try:
    from skill_whitelist import SkillWhitelistManager
    from security_auditor import SecurityAuditor
except ImportError:
    logger = logging.getLogger(__name__)
    logging.warning("Security modules not found, using basic validation")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# CocoHub API 配置
COCOHUB_API_BASE = "https://hub.cocoloop.cn/api"
# 保存到 Phoenix Core 共享技能目录，所有 bot 都能使用
COCOHUB_SKILLS_DIR = Path(__file__).parent / "skills")
COCOHUB_SKILLS_DIR.mkdir(parents=True, exist_ok=True)


class CocoHubClient:
    """CocoHub API 客户端"""

    def __init__(self):
        self.api_base = COCOHUB_API_BASE
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Phoenix-Core-CocoHub-Client/1.0",
            "Accept": "application/json"
        })

    def get_skills_list(self, category: str = None, limit: int = 100) -> List[Dict]:
        """获取技能列表"""
        try:
            url = f"{self.api_base}/skills"
            params = {"limit": limit}
            if category:
                params["category"] = category

            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("skills", [])
            else:
                logger.error(f"API error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Failed to fetch skills: {e}")
            return []

    def get_skill_detail(self, skill_id: str) -> Optional[Dict]:
        """获取技能详情"""
        try:
            url = f"{self.api_base}/skills/{skill_id}"
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Failed to fetch skill detail: {e}")
            return None

    def search_skills(self, query: str) -> List[Dict]:
        """搜索技能"""
        try:
            url = f"{self.api_base}/skills/search"
            params = {"q": query, "limit": 50}
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            return []
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []


class CocoHubIntegration:
    """CocoHub 技能商店集成"""

    def __init__(self):
        self.client = CocoHubClient()
        self.whitelist_manager = SkillWhitelistManager()
        self.security_auditor = SecurityAuditor()
        COCOHUB_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    def list_skills(self, category: str = None) -> List[Dict]:
        """列出可用技能"""
        logger.info(f"Fetching skills from CocoHub...")
        skills = self.client.get_skills_list(category=category, limit=100)

        # 添加安全评级标注
        for skill in skills:
            skill_name = skill.get("name", "")
            whitelisted = skill_name in self.whitelist_manager.whitelist
            skill["phoenix_verified"] = whitelisted
            if whitelisted:
                skill["safety_rating"] = self.whitelist_manager.whitelist[skill_name].get("rating", "unverified")

        return skills

    def search_skills(self, query: str) -> List[Dict]:
        """搜索技能"""
        logger.info(f"Searching for: {query}")
        results = self.client.search_skills(query)

        for skill in results:
            skill_name = skill.get("name", "")
            whitelisted = skill_name in self.whitelist_manager.whitelist
            skill["phoenix_verified"] = whitelisted

        return results

    def vet_skill(self, skill_name: str, skill_data: Dict) -> Dict:
        """检查技能安全性"""
        logger.info(f"Vetting skill: {skill_name}")

        vet_result = {
            "skill_name": skill_name,
            "safe": False,
            "rating": "unverified",
            "issues": [],
            "recommendation": "review"
        }

        # 1. 检查是否在白名单
        if skill_name in self.whitelist_manager.whitelist:
            entry = self.whitelist_manager.whitelist[skill_name]
            vet_result["safe"] = entry.get("rating") in ["safe", "reviewed"]
            vet_result["rating"] = entry.get("rating", "unverified")
            vet_result["recommendation"] = "install" if vet_result["safe"] else "review"
            return vet_result

        # 2. 检查是否在黑名单
        if skill_name in self.whitelist_manager.blocklist:
            vet_result["safe"] = False
            vet_result["rating"] = "blocked"
            vet_result["recommendation"] = "do_not_install"
            vet_result["issues"].append("Skill is blocklisted")
            return vet_result

        # 3. 使用 SecurityAuditor 检查技能代码
        skill_code = skill_data.get("code", "")
        if skill_code:
            audit_result = self.security_auditor.audit_code(skill_code)
            if audit_result.get("risk_level") == "high":
                vet_result["issues"].append("High risk code detected")
                vet_result["recommendation"] = "do_not_install"
                return vet_result

        # 4. 检查 CocoHub 安全评级
        cocoloop_rating = skill_data.get("safety_rating", "")
        if cocoloop_rating in ["S", "A"]:
            vet_result["rating"] = "reviewed"
            vet_result["recommendation"] = "install_with_caution"
        elif cocoloop_rating == "B":
            vet_result["rating"] = "unverified"
            vet_result["recommendation"] = "manual_review_required"
        elif cocoloop_rating in ["C", "D"]:
            vet_result["issues"].append(f"Low safety rating from CocoHub: {cocoloop_rating}")
            vet_result["recommendation"] = "do_not_install"

        return vet_result

    def install_skill(self, skill_name: str, skill_data: Dict) -> bool:
        """安装技能"""
        # 先 vet 检查
        vet_result = self.vet_skill(skill_name, skill_data)

        if vet_result["recommendation"] == "do_not_install":
            logger.error(f"Skill {skill_name} failed vet check: {vet_result['issues']}")
            return False

        if vet_result["recommendation"] == "manual_review_required":
            logger.warning(f"Skill {skill_name} requires manual review before installation")
            print(f"\n⚠️  技能 {skill_name} 需要人工审核")
            print(f"问题：{vet_result['issues']}")
            response = input("是否继续安装？(y/N): ")
            if response.lower() != 'y':
                return False

        # 保存到技能目录（创建子目录 + SKILL.md 格式）
        skill_dir = COCOHUB_SKILLS_DIR / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        try:
            # 写入 SKILL.md 内容
            content = skill_data.get("content", "") or skill_data.get("readme", "")
            with open(skill_file, "w", encoding="utf-8") as f:
                f.write(content)

            # 添加到白名单
            self.whitelist_manager.add_skill(
                skill_name,
                source="cocoloop",
                rating=vet_result.get("rating", "reviewed"),
                vetted_at=datetime.now().isoformat()
            )

            logger.info(f"Installed skill: {skill_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to install skill: {e}")
            return False

    def get_skill_find_command(self) -> str:
        """获取 find-skills 命令的帮助文本"""
        return """
📋 CocoHub 技能查找命令:

  python3 cocoloop_hub.py list              # 列出所有可用技能
  python3 cocoloop_hub.py list --category=<category>  # 按分类列出
  python3 cocoloop_hub.py search <query>    # 搜索技能
  python3 cocoloop_hub.py vet <skill_name>  # 检查技能安全性
  python3 cocoloop_hub.py install <skill_name>  # 安装技能
  python3 cocoloop_hub.py info <skill_name> # 查看技能详情

分类示例:
  - document (文档处理)
  - office (Office 工具)
  - productivity (生产力)
  - coding (编程)
  - search (搜索)
        """


def main():
    """主函数"""
    hub = CocoHubIntegration()

    if len(sys.argv) < 2:
        print(hub.get_skill_find_command())
        return

    command = sys.argv[1]

    if command == "list":
        category = None
        for arg in sys.argv[2:]:
            if arg.startswith("--category="):
                category = arg.split("=")[1]

        skills = hub.list_skills(category)
        print(f"\n📦 CocoHub 技能列表{' - ' + category if category else ''}:\n")
        for i, skill in enumerate(skills[:20], 1):
            verified = "✅" if skill.get("phoenix_verified") else "⚪"
            rating = skill.get("safety_rating", "?")
            print(f"{i}. {verified} {skill.get('name', 'Unknown')} [{rating}] - {skill.get('description', '')[:50]}...")
        if len(skills) > 20:
            print(f"... 还有 {len(skills) - 20} 个技能")

    elif command == "search":
        if len(sys.argv) < 3:
            print("用法：python3 cocoloop_hub.py search <query>")
            return
        query = " ".join(sys.argv[2:])
        results = hub.search_skills(query)
        print(f"\n🔍 搜索结果 '{query}':\n")
        for i, skill in enumerate(results[:10], 1):
            verified = "✅" if skill.get("phoenix_verified") else "⚪"
            print(f"{i}. {verified} {skill.get('name', 'Unknown')} - {skill.get('description', '')[:60]}...")

    elif command == "vet":
        if len(sys.argv) < 3:
            print("用法：python3 cocoloop_hub.py vet <skill_name>")
            return
        skill_name = sys.argv[2]
        skill_detail = hub.client.get_skill_detail(skill_name)
        if skill_detail:
            result = hub.vet_skill(skill_name, skill_detail)
            print(f"\n🔒 技能安全评估：{skill_name}")
            print(f"   安全：{'是' if result['safe'] else '否'}")
            print(f"   评级：{result['rating']}")
            print(f"   建议：{result['recommendation']}")
            if result['issues']:
                print(f"   问题：{', '.join(result['issues'])}")
        else:
            print(f"未找到技能：{skill_name}")

    elif command == "install":
        if len(sys.argv) < 3:
            print("用法：python3 cocoloop_hub.py install <skill_name>")
            return
        skill_name = sys.argv[2]
        skill_detail = hub.client.get_skill_detail(skill_name)
        if skill_detail:
            success = hub.install_skill(skill_name, skill_detail)
            if success:
                print(f"✅ 技能已安装：{skill_name}")
            else:
                print(f"❌ 安装失败：{skill_name}")
        else:
            print(f"未找到技能：{skill_name}")

    elif command == "info":
        if len(sys.argv) < 3:
            print("用法：python3 cocoloop_hub.py info <skill_name>")
            return
        skill_name = sys.argv[2]
        skill_detail = hub.client.get_skill_detail(skill_name)
        if skill_detail:
            print(f"\n📋 技能信息：{skill_name}")
            print(f"   描述：{skill_detail.get('description', 'N/A')}")
            print(f"   作者：{skill_detail.get('author', 'N/A')}")
            print(f"   评级：{skill_detail.get('safety_rating', 'N/A')}")
            print(f"   分类：{skill_detail.get('category', 'N/A')}")
            print(f"   版本：{skill_detail.get('version', 'N/A')}")
        else:
            print(f"未找到技能：{skill_name}")

    else:
        print(hub.get_skill_find_command())


if __name__ == "__main__":
    main()
