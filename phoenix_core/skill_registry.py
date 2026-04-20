#!/usr/bin/env python3
"""
Phoenix Core - Skill Registry (技能注册表)

管理所有 Bot 的技能索引，支持语义匹配。

功能:
1. Bot 注册/注销技能
2. 基于任务描述匹配最合适的 Bot
3. 追踪技能执行成功率
4. 持久化存储到 SQLite

Usage:
    registry = SkillRegistry()
    registry.register("运营", "活动策划", "可以策划直播活动和互动流程")
    bot = registry.find_bot_for_task("帮我设计一个直播互动方案")
"""

import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class SkillRegistry:
    """技能注册表 (单例模式)"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True

        # 数据库路径
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path(__file__).parent.parent / "shared_memory" / "memory_share.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_connection()

        # 技能注册表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skill_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                skill_name TEXT NOT NULL,
                description TEXT,
                capabilities TEXT DEFAULT '[]',
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                UNIQUE(bot_name, skill_name)
            )
        """)

        # 创建索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_bot ON skill_registry(bot_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_name ON skill_registry(skill_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_active ON skill_registry(is_active)")

        conn.commit()
        logger.info("SkillRegistry 数据库初始化完成")

    def register(self, bot_name: str, skill_name: str, description: str,
                 capabilities: List[str] = None) -> bool:
        """
        注册或更新 Bot 的技能

        Args:
            bot_name: Bot 名称
            skill_name: 技能名称
            description: 技能描述
            capabilities: 能力标签列表

        Returns:
            是否成功
        """
        conn = self._get_connection()
        capabilities_json = json.dumps(capabilities or [])

        try:
            conn.execute("""
                INSERT INTO skill_registry (bot_name, skill_name, description, capabilities)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(bot_name, skill_name) DO UPDATE SET
                    description = excluded.description,
                    capabilities = excluded.capabilities,
                    updated_at = CURRENT_TIMESTAMP
            """, (bot_name, skill_name, description, capabilities_json))

            conn.commit()
            logger.info(f"技能注册：{bot_name} - {skill_name}")
            return True

        except Exception as e:
            logger.error(f"技能注册失败：{e}")
            conn.rollback()
            return False

        finally:
            conn.close()

    def unregister(self, bot_name: str, skill_name: str) -> bool:
        """注销 Bot 的技能"""
        conn = self._get_connection()

        try:
            conn.execute("""
                UPDATE skill_registry SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE bot_name = ? AND skill_name = ?
            """, (bot_name, skill_name))

            conn.commit()
            logger.info(f"技能注销：{bot_name} - {skill_name}")
            return True

        except Exception as e:
            logger.error(f"技能注销失败：{e}")
            conn.rollback()
            return False

        finally:
            conn.close()

    def get_skills(self, bot_name: str) -> List[Dict]:
        """获取 Bot 的所有技能"""
        conn = self._get_connection()

        cursor = conn.execute("""
            SELECT skill_name, description, capabilities, success_count, fail_count
            FROM skill_registry
            WHERE bot_name = ? AND is_active = 1
        """, (bot_name,))

        skills = []
        for row in cursor.fetchall():
            skills.append({
                "name": row["skill_name"],
                "description": row["description"],
                "capabilities": json.loads(row["capabilities"]),
                "success_count": row["success_count"],
                "fail_count": row["fail_count"]
            })

        conn.close()
        return skills

    def find_bot_for_task(self, task_description: str) -> Optional[str]:
        """
        基于任务描述，匹配最合适的 Bot

        Args:
            task_description: 任务描述

        Returns:
            最合适的 Bot 名称，如果没有匹配则返回 None
        """
        conn = self._get_connection()

        # 获取所有活跃技能
        cursor = conn.execute("""
            SELECT bot_name, skill_name, description, capabilities
            FROM skill_registry
            WHERE is_active = 1
        """)

        scores = {}
        task_lower = task_description.lower()

        for row in cursor.fetchall():
            bot_name = row["bot_name"]
            skill_name = row["skill_name"]
            description = row["description"].lower()
            capabilities = json.loads(row["capabilities"])

            score = 0

            # 1. 关键词匹配 - 技能描述
            for word in task_lower.split():
                if len(word) > 1:  # 忽略单字
                    if word in description:
                        score += 2

            # 2. 能力标签匹配
            for cap in capabilities:
                if cap.lower() in task_lower:
                    score += 5

            # 3. 成功率加权
            total = dict(row).get("success_count", 0) + dict(row).get("fail_count", 0)
            if total > 0:
                success_rate = dict(row)["success_count"] / total
                score *= (0.5 + 0.5 * success_rate)  # 成功率影响 50% 权重

            if score > 0:
                if bot_name not in scores:
                    scores[bot_name] = 0
                scores[bot_name] += score

        conn.close()

        if scores:
            best_bot = max(scores, key=scores.get)
            logger.info(f"技能匹配：'{task_description[:30]}...' → {best_bot}")
            return best_bot

        return None

    def find_bots_for_task(self, task_description: str, limit: int = 5) -> List[Dict]:
        """
        找到多个能处理任务的 Bot，按匹配度排序

        Args:
            task_description: 任务描述
            limit: 返回数量限制

        Returns:
            Bot 列表，包含匹配分数
        """
        conn = self._get_connection()

        cursor = conn.execute("""
            SELECT bot_name, skill_name, description, capabilities, success_count, fail_count
            FROM skill_registry
            WHERE is_active = 1
        """)

        bot_scores = {}
        task_lower = task_description.lower()

        for row in cursor.fetchall():
            bot_name = row["bot_name"]
            description = row["description"].lower()
            capabilities = json.loads(row["capabilities"])

            score = 0

            # 关键词匹配
            for word in task_lower.split():
                if len(word) > 1 and word in description:
                    score += 2

            # 能力标签匹配
            for cap in capabilities:
                if cap.lower() in task_lower:
                    score += 5

            if score > 0:
                if bot_name not in bot_scores:
                    bot_scores[bot_name] = {
                        "bot_name": bot_name,
                        "score": 0,
                        "matched_skills": []
                    }
                bot_scores[bot_name]["score"] += score
                bot_scores[bot_name]["matched_skills"].append(row["skill_name"])

        conn.close()

        # 排序并返回
        sorted_bots = sorted(bot_scores.values(), key=lambda x: x["score"], reverse=True)
        return sorted_bots[:limit]

    def record_success(self, bot_name: str, skill_name: str) -> bool:
        """记录技能成功执行"""
        return self._update_count(bot_name, skill_name, "success")

    def record_failure(self, bot_name: str, skill_name: str) -> bool:
        """记录技能执行失败"""
        return self._update_count(bot_name, skill_name, "fail")

    def _update_count(self, bot_name: str, skill_name: str, count_type: str) -> bool:
        """更新技能计数"""
        conn = self._get_connection()

        try:
            if count_type == "success":
                conn.execute("""
                    UPDATE skill_registry
                    SET success_count = success_count + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE bot_name = ? AND skill_name = ?
                """, (bot_name, skill_name))
            else:
                conn.execute("""
                    UPDATE skill_registry
                    SET fail_count = fail_count + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE bot_name = ? AND skill_name = ?
                """, (bot_name, skill_name))

            conn.commit()
            return True

        except Exception as e:
            logger.error(f"更新技能计数失败：{e}")
            conn.rollback()
            return False

        finally:
            conn.close()

    def get_all_skills(self) -> List[Dict]:
        """获取所有技能"""
        conn = self._get_connection()

        cursor = conn.execute("""
            SELECT bot_name, skill_name, description, capabilities, success_count, fail_count
            FROM skill_registry
            WHERE is_active = 1
        """)

        skills = []
        for row in cursor.fetchall():
            skills.append({
                "bot_name": row["bot_name"],
                "skill_name": row["skill_name"],
                "description": row["description"],
                "capabilities": json.loads(row["capabilities"]),
                "success_count": row["success_count"],
                "fail_count": row["fail_count"]
            })

        conn.close()
        return skills

    def get_stats(self) -> Dict:
        """获取技能统计信息"""
        conn = self._get_connection()

        # Bot 数量
        cursor = conn.execute("""
            SELECT COUNT(DISTINCT bot_name) FROM skill_registry WHERE is_active = 1
        """)
        bot_count = cursor.fetchone()[0]

        # 技能总数
        cursor = conn.execute("""
            SELECT COUNT(*) FROM skill_registry WHERE is_active = 1
        """)
        skill_count = cursor.fetchone()[0]

        # 总成功/失败次数
        cursor = conn.execute("""
            SELECT SUM(success_count), SUM(fail_count) FROM skill_registry WHERE is_active = 1
        """)
        row = cursor.fetchone()
        total_success = row[0] or 0
        total_fail = row[1] or 0

        conn.close()

        return {
            "bot_count": bot_count,
            "skill_count": skill_count,
            "total_success": total_success,
            "total_fail": total_fail,
            "success_rate": total_success / (total_success + total_fail) if (total_success + total_fail) > 0 else 0
        }


# 全局实例
_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """获取全局 SkillRegistry 实例"""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def register_skill(bot_name: str, skill_name: str, description: str,
                   capabilities: List[str] = None) -> bool:
    """便捷函数：注册技能"""
    return get_skill_registry().register(bot_name, skill_name, description, capabilities)


def find_bot_for_task(task_description: str) -> Optional[str]:
    """便捷函数：为任务匹配 Bot"""
    return get_skill_registry().find_bot_for_task(task_description)


def get_bot_skills(bot_name: str) -> List[Dict]:
    """便捷函数：获取 Bot 技能"""
    return get_skill_registry().get_skills(bot_name)


def find_bots_for_task(task_description: str, limit: int = 5, min_score: float = 0.1) -> List[tuple]:
    """
    便捷函数：为任务匹配多个 Bot（增强版）

    Returns:
        [(bot_name, score), ...] 按分数降序排列
    """
    return get_skill_registry().find_bots_for_task_v2(task_description, limit, min_score)


# ========== 增强方法（文档分析后新增） ==========

def import_from_soul_md(registry: SkillRegistry, bot_name: str, soul_md_path: Path) -> bool:
    """
    从 SOUL.md 文件自动导入技能描述

    解析 SOUL.md 中的角色定位、职责、技能相关段落，自动注册为技能

    Args:
        registry: SkillRegistry 实例
        bot_name: Bot 名称
        soul_md_path: SOUL.md 文件路径

    Returns:
        是否成功导入
    """
    import re

    if not soul_md_path.exists():
        logger.warning(f"SOUL.md 不存在：{soul_md_path}")
        return False

    content = soul_md_path.read_text(encoding='utf-8')

    # 解析模式：查找技能/能力/职责相关段落
    patterns = [
        (r'##\s*技能\s*\n(.*?)(?=\n##|\Z)', '技能'),
        (r'##\s*能力\s*\n(.*?)(?=\n##|\Z)', '能力'),
        (r'##\s*擅长\s*\n(.*?)(?=\n##|\Z)', '擅长'),
        (r'##\s*职责\s*\n(.*?)(?=\n##|\Z)', '职责'),
        (r'##\s*角色定位\s*\n(.*?)(?=\n##|\Z)', '角色定位'),
        (r'##\s*职责\s*\n([\s\S]*?)(?=##|$$)', '职责'),  # 多行职责
    ]

    for pattern, section_name in patterns:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        if matches:
            description = matches[0].strip()[:300]  # 限制长度
            # 清理markdown 格式
            description = re.sub(r'^\d+\.\s*', '', description, flags=re.MULTILINE)
            description = re.sub(r'^-\s*', '', description, flags=re.MULTILINE)

            # 提取中文关键词（2 字以上）
            keywords = list(set(re.findall(r'[\u4e00-\u9fa5]{2,}', description)))[:15]

            # 注册技能
            skill_name = f"{bot_name}_{section_name}"
            registry.register(
                bot_name=bot_name,
                skill_name=skill_name,
                description=description,
                capabilities=keywords
            )
            logger.info(f"从 SOUL.md 导入技能：{bot_name} - {skill_name}")
            return True

    # 如果以上都没匹配到，尝试提取整个文件的关键信息
    logger.info(f"使用降级模式解析 SOUL.md: {soul_md_path}")

    # 提取角色定位
    role_match = re.search(r'##\s*角色定位\s*\n(.*?)(?=##|\Z)', content, re.DOTALL)
    if role_match:
        description = role_match.group(1).strip()[:300]
        keywords = list(set(re.findall(r'[\u4e00-\u9fa5]{2,}', description)))[:15]
        registry.register(
            bot_name=bot_name,
            skill_name=f"{bot_name}_角色定位",
            description=description,
            capabilities=keywords
        )
        logger.info(f"从 SOUL.md 导入角色定位：{bot_name}")
        return True

    logger.warning(f"未从 SOUL.md 解析到技能：{soul_md_path}")
    return False


def get_all_skills_summary(self) -> Dict[str, List[str]]:
    """
    获取所有 Bot 的技能摘要（用于 Dashboard 展示）

    Returns:
        {bot_name: ["技能 1: 描述...", "技能 2: 描述..."], ...}
    """
    summary = {}
    for bot_name in self._get_all_bot_names():
        skills = self.get_skills(bot_name)
        summary[bot_name] = [
            f"{s['name']}: {s['description'][:50]}..." for s in skills
        ]
    return summary


def _get_all_bot_names(self) -> List[str]:
    """获取所有已注册技能的 Bot 名称列表"""
    conn = self._get_connection()
    cursor = conn.execute("SELECT DISTINCT bot_name FROM skill_registry WHERE is_active = 1")
    bot_names = [row[0] for row in cursor.fetchall()]
    conn.close()
    return bot_names


def record_skill_usage(self, bot_name: str, skill_name: str, success: bool, rating: float = 0.0) -> bool:
    """
    记录技能使用结果（用于权重调整和学习）

    Args:
        bot_name: Bot 名称
        skill_name: 技能名称
        success: 是否成功
        rating: 用户评分 (0-5)
    """
    conn = self._get_connection()

    try:
        if success:
            conn.execute("""
                UPDATE skill_registry
                SET success_count = success_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE bot_name = ? AND skill_name = ?
            """, (bot_name, skill_name))
        else:
            conn.execute("""
                UPDATE skill_registry
                SET fail_count = fail_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE bot_name = ? AND skill_name = ?
            """, (bot_name, skill_name))

        conn.commit()
        logger.info(f"记录技能使用：{bot_name} - {skill_name} - {'成功' if success else '失败'}")
        return True

    except Exception as e:
        logger.error(f"记录技能使用失败：{e}")
        conn.rollback()
        return False

    finally:
        conn.close()


# 为类添加新方法
SkillRegistry.get_all_skills_summary = get_all_skills_summary
SkillRegistry._get_all_bot_names = _get_all_bot_names
SkillRegistry.record_skill_usage = record_skill_usage
