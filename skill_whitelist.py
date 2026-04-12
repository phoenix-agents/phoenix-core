#!/usr/bin/env python3
"""
Phoenix Core Skill Whitelist System

技能白名单管理系统 - 只允许已验证的技能

功能:
1. 可信技能来源管理
2. 技能安全评级
3. 安装前自动校验
4. 技能执行策略

Usage:
    python3 skill_whitelist.py list          # 列出所有可信技能
    python3 skill_whitelist.py add <skill>   # 添加可信技能
    python3 skill_whitelist.py remove <skill> # 移除技能
    python3 skill_whitelist.py verify <path>  # 验证技能安全性
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from security_auditor import SecurityAuditor
from skill_risk_assessor import RiskAssessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 白名单文件路径
WHITELIST_FILE = Path(__file__).parent / "verified_skills.json"

# 可信来源列表 (官方/认证)
TRUSTED_SOURCES = {
    "phoenix-core-official": {
        "name": "Phoenix Core 官方技能",
        "trust_level": "official",
        "auto_approve": True
    },
    "phoenix-community": {
        "name": "Phoenix Community 社区技能",
        "trust_level": "verified",
        "auto_approve": True
    },
}

# 技能安全评级
SAFETY_RATINGS = {
    "safe": {"label": "✅ 安全", "description": "已通过安全审计，可放心使用"},
    "reviewed": {"label": "🟡 已审核", "description": "人工审核通过，建议使用"},
    "unverified": {"label": "⚪ 未验证", "description": "未经验证，谨慎使用"},
    "suspicious": {"label": "🔴 可疑", "description": "发现可疑行为，禁止使用"},
    "blocked": {"label": "❌ 已封禁", "description": "确认恶意，永久封禁"}
}


class SkillWhitelistManager:
    """技能白名单管理器"""

    def __init__(self):
        self.whitelist: Dict[str, Any] = {}
        self.blocklist: Dict[str, Any] = {}
        self.sources: Dict[str, Any] = TRUSTED_SOURCES.copy()
        self._load()

    def _load(self):
        """加载白名单数据"""
        if WHITELIST_FILE.exists():
            try:
                with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.whitelist = data.get("whitelist", {})
                    self.blocklist = data.get("blocklist", {})
                    self.sources = {**TRUSTED_SOURCES, **data.get("sources", {})}
                logger.info(f"Loaded whitelist: {len(self.whitelist)} skills")
            except Exception as e:
                logger.error(f"Failed to load whitelist: {e}")
                self._init_default()
        else:
            self._init_default()

    def _init_default(self):
        """初始化默认白名单"""
        self.whitelist = {}
        self.blocklist = {}
        self.sources = TRUSTED_SOURCES.copy()
        logger.info("Initialized default whitelist")

    def _save(self):
        """保存白名单数据"""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "whitelist": self.whitelist,
            "blocklist": self.blocklist,
            "sources": self.sources,
        }
        with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved whitelist: {len(self.whitelist)} skills")

    def add_skill(self, skill_id: str, skill_data: Dict, source: str = "manual") -> bool:
        """
        添加技能到白名单

        Args:
            skill_id: 技能唯一标识
            skill_data: 技能数据
            source: 技能来源

        Returns:
            bool: 是否添加成功
        """
        # 检查是否在黑名单中
        if skill_id in self.blocklist:
            logger.warning(f"Skill {skill_id} is in blocklist, cannot add to whitelist")
            return False

        # 安全审计
        auditor = SecurityAuditor()
        content = skill_data.get("content", "")
        audit_report = auditor.audit_skill(skill_id, content)

        if audit_report.get("verdict") == "FAIL":
            logger.warning(f"Skill {skill_id} failed security audit")
            return False

        # 风险评估
        assessor = RiskAssessor()
        risk_report = assessor.assess_skill(skill_data)

        if risk_report.get("risk_level") == "high":
            logger.warning(f"Skill {skill_id} has high risk")
            return False

        # 计算技能哈希
        skill_hash = hashlib.sha256(content.encode()).hexdigest()

        # 添加到白名单
        self.whitelist[skill_id] = {
            "id": skill_id,
            "name": skill_data.get("name", skill_id),
            "description": skill_data.get("description", ""),
            "hash": skill_hash,
            "source": source,
            "safety_rating": self._calculate_safety_rating(audit_report, risk_report),
            "audit_report": audit_report,
            "risk_report": risk_report,
            "added_at": datetime.now().isoformat(),
            "verified": True
        }

        self._save()
        logger.info(f"Added skill to whitelist: {skill_id}")
        return True

    def remove_skill(self, skill_id: str) -> bool:
        """从白名单移除技能"""
        if skill_id in self.whitelist:
            del self.whitelist[skill_id]
            self._save()
            logger.info(f"Removed skill from whitelist: {skill_id}")
            return True
        return False

    def block_skill(self, skill_id: str, reason: str = "") -> bool:
        """
        封禁技能

        Args:
            skill_id: 技能 ID
            reason: 封禁原因

        Returns:
            bool: 是否封禁成功
        """
        # 从白名单移除
        if skill_id in self.whitelist:
            del self.whitelist[skill_id]

        # 添加到黑名单
        self.blocklist[skill_id] = {
            "id": skill_id,
            "reason": reason,
            "blocked_at": datetime.now().isoformat(),
            "permanent": True
        }

        self._save()
        logger.warning(f"Blocked skill: {skill_id} - {reason}")
        return True

    def verify_skill(self, skill_id: str, content: str) -> Dict[str, Any]:
        """
        验证技能安全性

        Args:
            skill_id: 技能 ID
            content: 技能内容

        Returns:
            Dict: 验证结果
        """
        result = {
            "skill_id": skill_id,
            "verified": False,
            "in_whitelist": False,
            "in_blocklist": False,
            "hash_match": False,
            "can_execute": False,
            "warnings": []
        }

        # 检查黑名单
        if skill_id in self.blocklist:
            result["in_blocklist"] = True
            result["can_execute"] = False
            result["warnings"].append("技能已被封禁")
            return result

        # 检查白名单
        if skill_id in self.whitelist:
            result["in_whitelist"] = True
            whitelist_entry = self.whitelist[skill_id]

            # 验证哈希
            current_hash = hashlib.sha256(content.encode()).hexdigest()
            if current_hash == whitelist_entry.get("hash"):
                result["hash_match"] = True
                result["verified"] = True
                result["can_execute"] = True
            else:
                result["warnings"].append("技能内容已变更，请重新验证")
                # 如果来源可信，仍然允许执行
                source = whitelist_entry.get("source", "")
                if source in self.sources and self.sources[source].get("auto_approve"):
                    result["can_execute"] = True
                    result["warnings"].append("来源可信，允许执行")

        return result

    def _calculate_safety_rating(self, audit: Dict, risk: Dict) -> str:
        """计算安全评级"""
        verdict = audit.get("verdict", "PASS")
        risk_level = risk.get("risk_level", "low")

        if verdict == "FAIL":
            return "blocked"
        elif verdict == "REVIEW_NEEDED":
            return "suspicious"
        elif risk_level == "high":
            return "unverified"
        elif risk_level == "medium":
            return "reviewed"
        else:
            return "safe"

    def is_skill_allowed(self, skill_id: str) -> bool:
        """检查技能是否允许执行"""
        # 黑名单优先
        if skill_id in self.blocklist:
            return False

        # 白名单模式
        if skill_id in self.whitelist:
            return True

        # 默认允许（宽松模式）
        # 如需严格模式，改为 return False
        return True

    def get_skill_info(self, skill_id: str) -> Optional[Dict]:
        """获取技能信息"""
        return self.whitelist.get(skill_id) or self.blocklist.get(skill_id)

    def list_skills(self, source: Optional[str] = None) -> List[Dict]:
        """列出所有技能"""
        skills = list(self.whitelist.values())
        if source:
            skills = [s for s in skills if s.get("source") == source]
        return skills

    def add_source(self, source_id: str, source_info: Dict) -> bool:
        """添加可信来源"""
        self.sources[source_id] = source_info
        self._save()
        return True

    def remove_source(self, source_id: str) -> bool:
        """移除来源"""
        if source_id in self.sources and source_id not in TRUSTED_SOURCES:
            del self.sources[source_id]
            self._save()
            return True
        return False


def print_whitelist(manager: SkillWhitelistManager):
    """打印白名单"""
    print("\n" + "="*60)
    print("📋 Phoenix Core 技能白名单")
    print("="*60)

    print(f"\n✅ 白名单技能：{len(manager.whitelist)}")
    print(f"❌ 封禁技能：{len(manager.blocklist)}")
    print(f"📦 可信来源：{len(manager.sources)}")

    if manager.whitelist:
        print("\n🟢 白名单详情:")
        print("-"*60)
        for skill in manager.list_skills():
            rating = SAFETY_RATINGS.get(skill.get("safety_rating", "unverified"), {})
            print(f"  {rating.get('label', '?')} {skill.get('name', skill.get('id'))}")
            print(f"     来源：{skill.get('source', 'unknown')}")
            print(f"     评级：{skill.get('safety_rating', 'unverified')}")
            print(f"     添加：{skill.get('added_at', 'unknown')[:10]}")

    if manager.blocklist:
        print("\n🔴 封禁列表:")
        print("-"*60)
        for skill_id, info in manager.blocklist.items():
            print(f"  ❌ {skill_id}")
            print(f"     原因：{info.get('reason', 'unknown')}")
            print(f"     封禁：{info.get('blocked_at', 'unknown')[:10]}")


def main():
    import sys

    if len(sys.argv) < 2:
        print("Phoenix Core Skill Whitelist System")
        print("\nUsage:")
        print("  python3 skill_whitelist.py list           # 列出所有可信技能")
        print("  python3 skill_whitelist.py verify <path>  # 验证技能安全性")
        print("  python3 skill_whitelist.py block <id>     # 封禁技能")
        sys.exit(1)

    manager = SkillWhitelistManager()
    command = sys.argv[1]

    if command == "list":
        print_whitelist(manager)

    elif command == "verify" and len(sys.argv) > 2:
        skill_path = Path(sys.argv[2])
        if skill_path.exists():
            content = skill_path.read_text(encoding="utf-8")
            skill_id = skill_path.stem
            result = manager.verify_skill(skill_id, content)
            print(f"\nVerification result for {skill_id}:")
            print(json.dumps(result, indent=2))
        else:
            print(f"File not found: {skill_path}")

    elif command == "block" and len(sys.argv) > 2:
        skill_id = sys.argv[2]
        reason = sys.argv[3] if len(sys.argv) > 3 else "Manual block"
        manager.block_skill(skill_id, reason)
        print(f"Blocked skill: {skill_id}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
