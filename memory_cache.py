#!/usr/bin/env python3
"""
Memory Cache - LRU cache for bot memory

Features:
1. LRU eviction (Least Recently Used)
2. TTL expiration (Time To Live)
3. Incremental loading (only changed files)
4. Async loading for large files

Usage:
    from memory_cache import MemoryCache

    cache = MemoryCache(bot_name="编导", ttl_seconds=300, max_entries=100)
    content = cache.get("memory_key")
    cache.set("memory_key", "content")
"""

import logging
import hashlib
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from collections import OrderedDict
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class CacheEntry:
    """单个缓存条目"""

    def __init__(self, key: str, value: Any, ttl_seconds: int = 300):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.ttl_seconds = ttl_seconds
        self.size = len(str(value)) if value else 0

    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.last_accessed > self.ttl_seconds

    def touch(self):
        """更新访问时间"""
        self.last_accessed = time.time()


class MemoryCache:
    """
    LRU 记忆缓存

    用于加速 Bot 记忆加载，减少磁盘 I/O
    """

    def __init__(self, bot_name: str, ttl_seconds: int = 300,
                 max_entries: int = 100, max_memory_mb: int = 50):
        self.bot_name = bot_name
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.max_memory_bytes = max_memory_mb * 1024 * 1024

        # LRU 缓存 (OrderedDict 保持插入顺序)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # 文件指纹缓存 (用于增量加载)
        self._file_fingerprints: Dict[str, str] = {}

        # 异步加载队列
        self._pending_loads: Dict[str, asyncio.Future] = {}

        # 线程池用于异步文件加载
        self._executor = ThreadPoolExecutor(max_workers=4)

        logger.info(f"[{bot_name}] Memory cache initialized: "
                   f"TTL={ttl_seconds}s, max_entries={max_entries}, "
                   f"max_memory={max_memory_mb}MB")

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期则返回 None
        """
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # 检查是否过期
            if entry.is_expired():
                del self._cache[key]
                logger.debug(f"[{self.bot_name}] Cache entry expired: {key}")
                return None

            # 移动到末尾 (LRU)
            self._cache.move_to_end(key)
            entry.touch()

            logger.debug(f"[{self.bot_name}] Cache hit: {key} ({entry.size} bytes)")
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int = None):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl_seconds: 自定义 TTL (可选)
        """
        with self._lock:
            # 如果已存在，先删除旧条目
            if key in self._cache:
                del self._cache[key]

            # 使用自定义 TTL 或默认 TTL
            ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds

            # 创建新条目
            entry = CacheEntry(key, value, ttl)

            # 检查内存限制
            current_memory = sum(e.size for e in self._cache.values())
            while current_memory + entry.size > self.max_memory_bytes and self._cache:
                # 删除最旧的条目 (LRU)
                oldest_key = next(iter(self._cache))
                oldest_entry = self._cache[oldest_key]
                current_memory -= oldest_entry.size
                del self._cache[oldest_key]
                logger.debug(f"[{self.bot_name}] Evicted cache entry: {oldest_key}")

            # 检查条目数限制
            while len(self._cache) >= self.max_entries and self._cache:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"[{self.bot_name}] Evicted cache entry (max entries): {oldest_key}")

            # 添加到缓存末尾
            self._cache[key] = entry
            logger.debug(f"[{self.bot_name}] Cache set: {key} ({entry.size} bytes)")

    def delete(self, key: str) -> bool:
        """
        删除缓存条目

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"[{self.bot_name}] Cache delete: {key}")
                return True
            return False

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            logger.info(f"[{self.bot_name}] Cache cleared")

    def get_stats(self) -> Dict:
        """获取缓存统计"""
        with self._lock:
            total_size = sum(e.size for e in self._cache.values())
            expired_count = sum(1 for e in self._cache.values() if e.is_expired())

            return {
                "bot_name": self.bot_name,
                "entries": len(self._cache),
                "total_size_bytes": total_size,
                "total_size_mb": total_size / 1024 / 1024,
                "expired_entries": expired_count,
                "max_entries": self.max_entries,
                "max_memory_mb": self.max_memory_bytes / 1024 / 1024,
                "ttl_seconds": self.ttl_seconds
            }

    def compute_file_fingerprint(self, file_path: Path) -> str:
        """
        计算文件指纹 (用于增量加载)

        Args:
            file_path: 文件路径

        Returns:
            文件 MD5 哈希值
        """
        try:
            mtime = file_path.stat().st_mtime
            size = file_path.stat().st_size
            content_hash = hashlib.md5(f"{mtime}:{size}".encode()).hexdigest()
            return content_hash
        except Exception as e:
            logger.error(f"Failed to compute fingerprint for {file_path}: {e}")
            return ""

    def should_reload_file(self, file_path: Path) -> bool:
        """
        检查文件是否需要重新加载

        Args:
            file_path: 文件路径

        Returns:
            是否需要重新加载
        """
        current_fingerprint = self.compute_file_fingerprint(file_path)
        cached_fingerprint = self._file_fingerprints.get(str(file_path))

        # 文件变更或首次加载
        return current_fingerprint != cached_fingerprint

    def mark_file_loaded(self, file_path: Path):
        """标记文件已加载"""
        fingerprint = self.compute_file_fingerprint(file_path)
        self._file_fingerprints[str(file_path)] = fingerprint

    async def load_file_async(self, file_path: Path) -> Optional[str]:
        """
        异步加载文件内容 (使用线程池)

        Args:
            file_path: 文件路径

        Returns:
            文件内容
        """
        # 先检查缓存
        cache_key = f"file:{str(file_path)}"
        cached = self.get(cache_key)
        if cached:
            return cached

        # 检查是否需要重新加载
        if not self.should_reload_file(file_path):
            logger.debug(f"[{self.bot_name}] File unchanged: {file_path}")
            return None

        # 使用线程池异步加载文件
        loop = asyncio.get_event_loop()
        try:
            content = await loop.run_in_executor(
                self._executor,
                self._load_file_sync,
                file_path
            )

            # 存入缓存
            self.set(cache_key, content)
            self.mark_file_loaded(file_path)

            logger.debug(f"[{self.bot_name}] File loaded async: {file_path} ({len(content)} chars)")
            return content

        except Exception as e:
            logger.error(f"Failed to load file async: {file_path}: {e}")
            return None

    def _load_file_sync(self, file_path: Path) -> str:
        """同步加载文件内容"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def cleanup_expired(self) -> int:
        """
        清理过期条目

        Returns:
            清理的条目数
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.info(f"[{self.bot_name}] Cleaned up {len(expired_keys)} expired entries")

            return len(expired_keys)

    def start_auto_cleanup(self, interval_seconds: int = 60):
        """
        启动自动清理线程

        Args:
            interval_seconds: 清理间隔 (秒)
        """
        def cleanup_loop():
            while True:
                time.sleep(interval_seconds)
                self.cleanup_expired()

        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
        logger.info(f"[{self.bot_name}] Auto cleanup started (interval={interval_seconds}s)")


# 全局缓存实例
_caches: Dict[str, MemoryCache] = {}


def get_memory_cache(bot_name: str, ttl_seconds: int = 300,
                     max_entries: int = 100) -> MemoryCache:
    """获取 Bot 的记忆缓存实例"""
    if bot_name not in _caches:
        _caches[bot_name] = MemoryCache(bot_name, ttl_seconds, max_entries)
    return _caches[bot_name]


def cache_bot_memory(bot_name: str, file_path: Path, content: str = None) -> Optional[str]:
    """
    缓存 Bot 记忆文件

    Args:
        bot_name: Bot 名称
        file_path: 文件路径
        content: 文件内容 (可选，如果提供则直接缓存)

    Returns:
        缓存内容
    """
    cache = get_memory_cache(bot_name)

    if content:
        cache.set(f"memory:{bot_name}:{file_path}", content)
        return content

    # 从缓存获取
    cached = cache.get(f"memory:{bot_name}:{file_path}")
    if cached:
        return cached

    # 从磁盘加载
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        cache.set(f"memory:{bot_name}:{file_path}", content)
        return content

    except Exception as e:
        logger.error(f"Failed to cache bot memory: {file_path}: {e}")
        return None


if __name__ == "__main__":
    # 测试
    print("Testing MemoryCache...")

    cache = MemoryCache(bot_name="测试", ttl_seconds=5, max_entries=3)

    # 测试基本功能
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    print(f"Get key1: {cache.get('key1')}")
    print(f"Get key3: {cache.get('key3')}")

    # 测试 LRU 驱逐
    cache.set("key3", "value3")
    cache.set("key4", "value4")  # 应该驱逐 key1
    print(f"Get key1 after eviction: {cache.get('key1')}")

    # 测试统计
    stats = cache.get_stats()
    print(f"Stats: {stats}")

    # 测试过期
    print("Waiting for expiration...")
    time.sleep(6)
    print(f"Get key1 after expiration: {cache.get('key1')}")

    print("\nTest complete!")
