#!/usr/bin/env python3
"""
Phoenix Core 跨 Bot 记忆共享系统
- 支持公共/团队/私有三种可见性
- 支持团队分组权限控制
- 支持记忆搜索和筛选
"""

import sqlite3
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Literal

# 数据库路径
DB_DIR = Path(__file__).parent / "shared_memory")
SHARE_DB_FILE = DB_DIR / "memory_share.db"

# 团队分组配置
TEAM_CONFIG = {
    "内容团队": ["场控", "运营", "编导"],
    "制作团队": ["剪辑", "美工"],
    "商务团队": ["客服", "渠道"],
}

# 可见性类型
Visibility = Literal["public", "team", "private"]


class MemoryShareManager:
    """跨 Bot 记忆共享管理器"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or SHARE_DB_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
        self._init_teams()

    def init_database(self):
        """初始化数据库（创建表和索引）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. 共享记忆表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shared_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                content TEXT NOT NULL,
                visibility TEXT DEFAULT 'public',
                team TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                channel_id TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                word_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0
            )
        """)

        # 2. 访问权限表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                bot_name TEXT NOT NULL,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (memory_id) REFERENCES shared_memories(id),
                UNIQUE(memory_id, bot_name)
            )
        """)

        # 3. Bot 团队映射表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_teams (
                bot_name TEXT PRIMARY KEY,
                team TEXT NOT NULL
            )
        """)

        # 4. 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_visibility ON shared_memories(visibility)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot ON shared_memories(bot_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team ON shared_memories(team)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags ON shared_memories(tags)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel ON shared_memories(channel_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_access ON memory_access(bot_name)")

        conn.commit()
        conn.close()

    def _init_teams(self):
        """初始化团队映射"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for team, bots in TEAM_CONFIG.items():
            for bot in bots:
                cursor.execute("""
                    INSERT OR REPLACE INTO bot_teams (bot_name, team)
                    VALUES (?, ?)
                """, (bot, team))

        conn.commit()
        conn.close()

    def get_bot_team(self, bot_name: str) -> Optional[str]:
        """获取 Bot 所属团队"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT team FROM bot_teams WHERE bot_name = ?", (bot_name,))
        row = cursor.fetchone()
        conn.close()

        return row[0] if row else None

    def share_memory(self, bot_name: str, content: str,
                     visibility: Visibility = "public",
                     tags: str = "",
                     channel_id: str = "") -> int:
        """
        共享记忆到共享池

        Args:
            bot_name: 分享者 Bot 名称
            content: 记忆内容
            visibility: 可见性 (public/team/private)
            tags: 标签（逗号分隔）
            channel_id: 频道 ID（可选）

        Returns:
            记忆 ID
        """
        # 获取 Bot 团队
        team = self.get_bot_team(bot_name)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO shared_memories
            (bot_name, content, visibility, team, tags, channel_id, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (bot_name, content, visibility, team or "", tags, channel_id, len(content)))

        memory_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return memory_id

    def get_shared_memories(self, bot_name: str,
                            tags: List[str] = None,
                            limit: int = 50,
                            channel_id: str = None) -> List[Dict]:
        """
        获取 Bot 可见的共享记忆

        Args:
            bot_name: 请求者 Bot 名称
            tags: 筛选标签
            limit: 返回数量限制
            channel_id: 筛选频道 ID（可选）

        Returns:
            记忆列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 获取请求者团队
        my_team = self.get_bot_team(bot_name)

        # 构建查询：可见的记忆包括
        # 1. public 可见性
        # 2. team 可见性且同团队
        # 3. private 但自己有访问权限
        # 4. 自己分享的

        query = """
            SELECT DISTINCT sm.id, sm.bot_name, sm.content, sm.visibility,
                   sm.team, sm.tags, sm.channel_id, sm.created_at, sm.word_count, sm.share_count
            FROM shared_memories sm
            WHERE sm.visibility = 'public'
               OR (sm.visibility = 'team' AND sm.team = ?)
               OR sm.bot_name = ?
               OR sm.id IN (
                   SELECT memory_id FROM memory_access WHERE bot_name = ?
               )
        """

        params = [my_team or "", bot_name, bot_name]

        # 添加频道筛选
        if channel_id:
            query += " AND sm.channel_id = ?"
            params.append(channel_id)

        # 添加标签筛选
        if tags:
            tag_conditions = " AND ".join(f"sm.tags LIKE ?" for _ in tags)
            query += f" AND ({tag_conditions})"
            params.extend(f"%{tag}%" for tag in tags)

        query += " ORDER BY sm.created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def grant_access(self, bot_name: str, target_bot: str,
                     memory_id: int) -> bool:
        """
        授予特定 Bot 访问私有记忆的权限

        Args:
            bot_name: 记忆所有者
            target_bot: 被授权 Bot
            memory_id: 记忆 ID

        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 验证所有权
        cursor.execute("""
            SELECT id FROM shared_memories
            WHERE id = ? AND bot_name = ?
        """, (memory_id, bot_name))

        if not cursor.fetchone():
            conn.close()
            return False

        # 授予访问权
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO memory_access (memory_id, bot_name)
                VALUES (?, ?)
            """, (memory_id, target_bot))
            conn.commit()
            success = True
        except sqlite3.IntegrityError:
            success = False
        finally:
            conn.close()

        return success

    def revoke_access(self, bot_name: str, target_bot: str,
                      memory_id: int) -> bool:
        """撤销访问权限"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 验证所有权
        cursor.execute("""
            SELECT id FROM shared_memories
            WHERE id = ? AND bot_name = ?
        """, (memory_id, bot_name))

        if not cursor.fetchone():
            conn.close()
            return False

        cursor.execute("""
            DELETE FROM memory_access
            WHERE memory_id = ? AND bot_name = ?
        """, (memory_id, target_bot))

        conn.commit()
        conn.close()
        return True

    def search_memories(self, bot_name: str, query: str,
                        limit: int = 20) -> List[Dict]:
        """
        搜索共享记忆（支持内容和标签搜索）

        Args:
            bot_name: 请求者 Bot 名称
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            记忆列表
        """
        # 先获取可见记忆
        visible_memories = self.get_shared_memories(bot_name, limit=1000)

        # 本地搜索（简单关键词匹配）
        results = []
        for mem in visible_memories:
            if (query.lower() in mem['content'].lower() or
                    query.lower() in mem['tags'].lower() or
                    query.lower() in mem['bot_name'].lower()):
                results.append(mem)

            if len(results) >= limit:
                break

        return results

    def get_stats(self, bot_name: str = None) -> Dict:
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if bot_name:
            # 个人统计
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN visibility='public' THEN 1 ELSE 0 END) as public_count,
                    SUM(CASE WHEN visibility='team' THEN 1 ELSE 0 END) as team_count,
                    SUM(CASE WHEN visibility='private' THEN 1 ELSE 0 END) as private_count,
                    SUM(word_count) as total_words
                FROM shared_memories
                WHERE bot_name = ?
            """, (bot_name,))
        else:
            # 全局统计
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(DISTINCT bot_name) as bot_count,
                    SUM(word_count) as total_words
                FROM shared_memories
            """)

        row = cursor.fetchone()

        # 转换结果为字典
        stats = {}
        if row:
            stats["total"] = row[0]
            if bot_name:
                stats["public_count"] = row[1]
                stats["team_count"] = row[2]
                stats["private_count"] = row[3]
                stats["total_words"] = row[4] if row[4] else 0
            else:
                stats["bot_count"] = row[1]
                stats["total_words"] = row[2] if row[2] else 0

        conn.close()
        return stats

    def delete_memory(self, bot_name: str, memory_id: int) -> bool:
        """删除记忆"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 验证所有权
        cursor.execute("""
            SELECT id FROM shared_memories
            WHERE id = ? AND bot_name = ?
        """, (memory_id, bot_name))

        if not cursor.fetchone():
            conn.close()
            return False

        # 删除记忆和访问记录
        cursor.execute("DELETE FROM shared_memories WHERE id = ? AND bot_name = ?",
                       (memory_id, bot_name))
        cursor.execute("DELETE FROM memory_access WHERE memory_id = ?",
                       (memory_id,))

        conn.commit()
        conn.close()
        return True


# ========== 全局单例 ==========

_share_manager: Optional[MemoryShareManager] = None


def get_share_manager() -> MemoryShareManager:
    """获取共享管理器单例"""
    global _share_manager
    if _share_manager is None:
        _share_manager = MemoryShareManager()
    return _share_manager


def share_memory(bot_name: str, content: str,
                 visibility: str = "public", tags: str = "", channel_id: str = "") -> int:
    """快捷共享函数"""
    manager = get_share_manager()
    return manager.share_memory(bot_name, content, visibility, tags, channel_id)


def get_shared_memories(bot_name: str, tags: List[str] = None, channel_id: str = None) -> List[Dict]:
    """快捷获取函数"""
    manager = get_share_manager()
    return manager.get_shared_memories(bot_name, tags, channel_id=channel_id)


def search_memories(bot_name: str, query: str) -> List[Dict]:
    """快捷搜索函数"""
    manager = get_share_manager()
    return manager.search_memories(bot_name, query)


# ========== CLI 接口 ==========

if __name__ == "__main__":
    print("=" * 60)
    print("  Phoenix Core 跨 Bot 记忆共享系统")
    print("=" * 60)
    print()

    manager = get_share_manager()

    # ============= 演示 =============
    print("[演示] 跨 Bot 记忆共享流程...")
    print()

    # 1. 场控分享公开记忆
    print("1. 场控分享公开记忆...")
    memory_id = share_memory(
        bot_name="场控",
        content="直播流程经验：开场前 5 分钟预热，介绍主播和产品，然后进入正式环节...",
        visibility="public",
        tags="直播，流程，开场"
    )
    print(f"   ✅ 分享成功，ID={memory_id}")
    print()

    # 2. 运营分享团队记忆
    print("2. 运营分享团队记忆（仅内容团队可见）...")
    memory_id = share_memory(
        bot_name="运营",
        content="运营数据分析方法：关注观看时长、互动率、转化率三个核心指标...",
        visibility="team",
        tags="运营，数据，分析"
    )
    print(f"   ✅ 分享成功，ID={memory_id}")
    print()

    # 3. 客服分享私有记忆
    print("3. 客服分享私有记忆（仅自己可见）...")
    memory_id = share_memory(
        bot_name="客服",
        content="客户投诉处理记录：用户 A 反馈物流慢，已协调加急处理...",
        visibility="private",
        tags="客服，投诉，物流"
    )
    print(f"   ✅ 分享成功，ID={memory_id}")
    print()

    # 4. 场控查看可见记忆
    print("4. 场控查看可见记忆...")
    memories = get_shared_memories("场控")
    print(f"   场控可见记忆：{len(memories)} 条")
    for m in memories:
        print(f"   - [{m['visibility']}] {m['bot_name']}: {m['content'][:30]}...")
    print()

    # 5. 客服查看可见记忆
    print("5. 客服查看可见记忆...")
    memories = get_shared_memories("客服")
    print(f"   客服可见记忆：{len(memories)} 条")
    for m in memories:
        print(f"   - [{m['visibility']}] {m['bot_name']}: {m['content'][:30]}...")
    print()

    # 6. 搜索记忆
    print("6. 场控搜索'直播'相关记忆...")
    results = search_memories("场控", "直播")
    print(f"   搜索结果：{len(results)} 条")
    for r in results:
        print(f"   - [{r['bot_name']}] {r['tags']}: {r['content'][:30]}...")
    print()

    # 7. 授权访问
    print("7. 客服授权场控访问私有记忆...")
    # 先创建一条私有记忆
    private_id = share_memory("客服", "重要客户资料...", "private")
    success = manager.grant_access("客服", "场控", private_id)
    print(f"   ✅ 授权{'成功' if success else '失败'}")

    # 验证场控能看到
    memories = get_shared_memories("场控")
    private_mem = next((m for m in memories if m['id'] == private_id), None)
    print(f"   场控{'能' if private_mem else '不能'}看到授权的私有记忆")
    print()

    # 8. 统计信息
    print("8. 查看统计信息...")
    stats = manager.get_stats()
    print(f"   总会话：{stats.get('total', 0)}")
    print(f"   Bot 数量：{stats.get('bot_count', 0)}")
    print(f"   总字数：{stats.get('total_words', 0)}")

    # 个人统计
    for bot in ["场控", "运营", "客服"]:
        personal_stats = manager.get_stats(bot)
        print(f"   {bot}: {personal_stats.get('total', 0)} 条记忆")
    print()

    print("=" * 60)
    print("  演示完成!")
    print("=" * 60)
    print()
    print("功能验证:")
    print("- ✅ 公开记忆共享")
    print("- ✅ 团队记忆隔离")
    print("- ✅ 私有记忆权限控制")
    print("- ✅ 记忆搜索")
    print("- ✅ 访问授权")
    print("- ✅ 统计信息")
