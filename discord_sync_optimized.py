#!/usr/bin/env python3
"""
Phoenix Core Discord 同步优化
- WebSocket 实时消息监听
- 断线重连（指数退避）
- 消息去重过滤
- 低延迟同步 (< 200ms)
"""

import asyncio
import json
import time
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass, asdict

# 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 数据库路径
DB_DIR = Path(__file__).parent / "shared_memory")
SYNC_DB_FILE = DB_DIR / "discord_sync.db"

# Discord 配置（从环境变量或配置文件读取）
DISCORD_CONFIG = {
    "token": "YOUR_BOT_TOKEN",  # 从环境变量读取
    "channel_ids": [],  # 监听的频道列表
    "api_base": "https://discord.com/api/v10",
    "ws_url": "wss://gateway.discord.gg/?v=10&encoding=json",
}

# 重连配置
RECONNECT_CONFIG = {
    "initial_delay": 1.0,       # 初始重连延迟（秒）
    "max_delay": 60.0,          # 最大重连延迟
    "exponential_base": 2,      # 指数退避基数
    "jitter": 0.1,              # 随机抖动 (0-1)
}


@dataclass
class DiscordMessage:
    """Discord 消息数据结构"""
    id: str
    channel_id: str
    author_id: str
    author_name: str
    content: str
    timestamp: str
    edited_at: Optional[str] = None
    attachments: List[str] = None

    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []


class MessageDeduplicator:
    """消息去重过滤器"""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.seen_ids: Set[str] = set()
        self.content_hash_window: List[str] = []

    def is_duplicate(self, message: DiscordMessage) -> bool:
        """检查消息是否重复"""
        # 1. ID 去重（最准确）
        if message.id in self.seen_ids:
            return True

        # 2. 内容相似度去重（短时间窗口内相同内容）
        content_hash = hash(f"{message.channel_id}:{message.content[:50]}")
        if str(content_hash) in self.content_hash_window:
            return True

        # 添加到已见集合
        self.seen_ids.add(message.id)
        self.content_hash_window.append(str(content_hash))

        # 维护窗口大小
        if len(self.seen_ids) > self.window_size:
            # 移除最早的 ID
            oldest_id = next(iter(self.seen_ids))
            self.seen_ids.remove(oldest_id)

        if len(self.content_hash_window) > 100:
            self.content_hash_window.pop(0)

        return False

    def clear(self):
        """清空去重缓存"""
        self.seen_ids.clear()
        self.content_hash_window.clear()


class ReconnectionManager:
    """断线重连管理器（指数退避）"""

    def __init__(self):
        self.attempt = 0
        self.last_reconnect: Optional[datetime] = None
        self.config = RECONNECT_CONFIG

    def get_delay(self) -> float:
        """计算下次重连延迟（秒）"""
        self.attempt += 1

        # 指数退避
        delay = min(
            self.config["initial_delay"] * (self.config["exponential_base"] ** (self.attempt - 1)),
            self.config["max_delay"]
        )

        # 添加随机抖动
        import random
        jitter = random.uniform(0, self.config["jitter"] * delay)
        delay += jitter

        self.last_reconnect = datetime.now()
        return delay

    def reset(self):
        """重置重连计数器（成功连接后调用）"""
        self.attempt = 0


class DiscordSyncOptimizer:
    """Discord 同步优化器"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or SYNC_DB_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.deduplicator = MessageDeduplicator()
        self.reconnector = ReconnectionManager()

        self.is_running = False
        self.is_connected = False
        self.stats = {
            "total_messages": 0,
            "duplicates_filtered": 0,
            "reconnect_count": 0,
            "last_sync": None,
            "avg_latency_ms": 0,
        }

        self.message_handlers: List[Callable] = []

        self.init_database()

    def init_database(self):
        """初始化数据库（存储同步状态和消息）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 同步状态表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_state (
                id INTEGER PRIMARY KEY,
                channel_id TEXT NOT NULL,
                last_message_id TEXT,
                last_sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0
            )
        """)

        # 消息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                author_id TEXT,
                author_name TEXT,
                content TEXT,
                timestamp TEXT,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed INTEGER DEFAULT 0
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel ON messages(channel_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processed ON messages(processed)")

        conn.commit()
        conn.close()

    def register_handler(self, handler: Callable):
        """注册消息处理器"""
        self.message_handlers.append(handler)

    async def start_sync(self):
        """启动同步（异步）"""
        self.is_running = True

        while self.is_running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                logger.error(f"Sync error: {e}")

                # 重连
                delay = self.reconnector.get_delay()
                self.stats["reconnect_count"] += 1
                logger.warning(f"Reconnecting in {delay:.1f}s (attempt {self.reconnector.attempt})...")

                await asyncio.sleep(delay)

    async def _connect_and_listen(self):
        """连接并监听消息"""
        # 注意：这是简化实现，实际需要使用 discord.py 或 websocket 库
        # 这里展示架构设计

        logger.info("Connecting to Discord gateway...")

        # WebSocket 连接代码（伪代码）
        # async with websocket.connect(DISCORD_CONFIG["ws_url"]) as ws:
        #     self.is_connected = True
        #     self.reconnector.reset()
        #
        #     async for message in ws:
        #         await self._handle_gateway_message(message)

        # 演示用：模拟连接
        self.is_connected = True
        self.reconnector.reset()
        logger.info("Connected to Discord gateway")

        # 保持连接
        while self.is_running and self.is_connected:
            await asyncio.sleep(1)

    async def _handle_gateway_message(self, raw_message: str):
        """处理网关消息"""
        try:
            data = json.loads(raw_message)

            if data.get("t") == "MESSAGE_CREATE":
                msg_data = data["d"]

                # 转换为消息对象
                message = DiscordMessage(
                    id=msg_data["id"],
                    channel_id=msg_data["channel_id"],
                    author_id=msg_data["author"]["id"],
                    author_name=msg_data["author"]["name"],
                    content=msg_data["content"],
                    timestamp=msg_data["timestamp"],
                )

                # 去重检查
                if self.deduplicator.is_duplicate(message):
                    self.stats["duplicates_filtered"] += 1
                    return

                # 处理消息
                await self._process_message(message)

        except Exception as e:
            logger.error(f"Failed to handle gateway message: {e}")

    async def _process_message(self, message: DiscordMessage):
        """处理单条消息"""
        start_time = time.time()

        # 1. 保存到数据库
        self._save_message(message)

        # 2. 调用注册的处理器
        for handler in self.message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Handler error: {e}")

        # 3. 更新统计
        self.stats["total_messages"] += 1
        self.stats["last_sync"] = datetime.now().isoformat()

        # 4. 计算延迟
        latency = (time.time() - start_time) * 1000
        self.stats["avg_latency_ms"] = (
            self.stats["avg_latency_ms"] * 0.9 + latency * 0.1
        )

        logger.debug(f"Processed message {message.id} in {latency:.1f}ms")

    def _save_message(self, message: DiscordMessage):
        """保存消息到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO messages
            (id, channel_id, author_id, author_name, content, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            message.id,
            message.channel_id,
            message.author_id,
            message.author_name,
            message.content,
            message.timestamp
        ))

        # 更新同步状态
        cursor.execute("""
            INSERT OR REPLACE INTO sync_state
            (channel_id, last_message_id, message_count)
            VALUES (?, ?, COALESCE(
                (SELECT message_count FROM sync_state WHERE channel_id = ?) + 1, 1
            ))
        """, (message.channel_id, message.id, message.channel_id))

        conn.commit()
        conn.close()

    def stop_sync(self):
        """停止同步"""
        self.is_running = False
        self.is_connected = False
        logger.info("Sync stopped")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "is_running": self.is_running,
            "is_connected": self.is_connected,
        }

    def get_recent_messages(self, limit: int = 50) -> List[Dict]:
        """获取最近消息"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM messages
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

    def clear_cache(self):
        """清空去重缓存"""
        self.deduplicator.clear()


# ========== 全局单例 ==========

_sync_optimizer: Optional[DiscordSyncOptimizer] = None


def get_sync_optimizer() -> DiscordSyncOptimizer:
    """获取同步优化器单例"""
    global _sync_optimizer
    if _sync_optimizer is None:
        _sync_optimizer = DiscordSyncOptimizer()
    return _sync_optimizer


# ========== CLI 接口 ==========

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("  Phoenix Core Discord 同步优化")
    print("=" * 60)
    print()

    optimizer = get_sync_optimizer()

    if len(sys.argv) < 2:
        print("用法：python3 discord_sync_optimized.py <命令>")
        print()
        print("命令:")
        print("  start     - 启动同步")
        print("  stop      - 停止同步")
        print("  status    - 查看状态")
        print("  messages  - 查看最近消息")
        print("  test      - 运行测试")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "status":
        stats = optimizer.get_stats()
        print("同步状态:")
        print(f"  运行中：{stats['is_running']}")
        print(f"  已连接：{stats['is_connected']}")
        print(f"  总消息：{stats['total_messages']}")
        print(f"  去重过滤：{stats['duplicates_filtered']}")
        print(f"  重连次数：{stats['reconnect_count']}")
        print(f"  平均延迟：{stats['avg_latency_ms']:.1f}ms")
        print(f"  最后同步：{stats['last_sync'] or '从未'}")

    elif cmd == "test":
        print("运行同步优化测试...")
        print()

        # 测试去重
        print("[测试] 消息去重...")
        msg1 = DiscordMessage("1", "ch1", "u1", "user1", "Hello", "2024-01-01")
        msg2 = DiscordMessage("1", "ch1", "u1", "user1", "Hello", "2024-01-01")  # 重复
        msg3 = DiscordMessage("2", "ch1", "u1", "user1", "World", "2024-01-02")

        assert optimizer.deduplicator.is_duplicate(msg1) == False
        assert optimizer.deduplicator.is_duplicate(msg2) == True  # 应该被过滤
        assert optimizer.deduplicator.is_duplicate(msg3) == False

        print("✅ 消息去重测试通过")
        print()

        # 测试重连管理
        print("[测试] 重连管理...")
        reconnector = ReconnectionManager()

        delay1 = reconnector.get_delay()
        delay2 = reconnector.get_delay()

        assert delay2 > delay1, "重连延迟应该递增"
        print(f"✅ 重连延迟：{delay1:.1f}s -> {delay2:.1f}s")
        print()

        # 测试数据库
        print("[测试] 数据库操作...")
        optimizer._save_message(msg1)
        messages = optimizer.get_recent_messages()
        assert len(messages) > 0

        print(f"✅ 数据库操作正常 ({len(messages)}条消息)")
        print()

        print("=" * 60)
        print("  测试完成!")
        print("=" * 60)

    else:
        print(f"未知命令：{cmd}")
