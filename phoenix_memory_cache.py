#!/usr/bin/env python3
"""
Phoenix Core Memory Cache - 记忆缓存优化

功能:
1. LRU 缓存策略
2. 批量写入优化
3. 异步刷新
4. 命中率统计

Usage:
    from phoenix_memory_cache import MemoryCache
    cache = MemoryCache(max_size=100, ttl=300)
    cache.set("key", "value")
    value = cache.get("key")
"""

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_access: Optional[datetime] = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def touch(self):
        self.access_count += 1
        self.last_access = datetime.now()


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    writes: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total * 100

    def to_dict(self) -> Dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "writes": self.writes,
            "hit_rate": f"{self.hit_rate:.2f}%",
            "total_requests": self.hits + self.misses
        }


class MemoryCache:
    """
    记忆缓存系统 - LRU 策略 + TTL 过期

    优化策略:
    1. LRU (Least Recently Used) 淘汰
    2. TTL (Time To Live) 自动过期
    3. 批量写入缓冲
    4. 后台异步刷新
    """

    def __init__(
        self,
        max_size: int = 100,
        ttl_seconds: int = 300,
        batch_size: int = 10,
        flush_interval: int = 60,
        persist_path: Optional[Path] = None
    ):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.persist_path = persist_path

        # LRU 缓存 (OrderedDict)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # 批量写入缓冲
        self._write_buffer: List[Tuple[str, Any]] = []
        self._last_flush = datetime.now()

        # 统计
        self._stats = CacheStats()

        # 后台刷新线程
        self._running = True
        self._flush_thread = threading.Thread(target=self._background_flush, daemon=True)
        self._flush_thread.start()

        # 加载持久化数据
        if self.persist_path and self.persist_path.exists():
            self._load_persisted()

        logger.info(
            f"MemoryCache initialized: max_size={max_size}, ttl={ttl_seconds}s, "
            f"batch_size={batch_size}, persist={persist_path}"
        )

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired():
                self._evict(key)
                self._stats.misses += 1
                return None

            # 更新访问 (LRU: 移到末尾)
            self._cache.move_to_end(key)
            entry.touch()
            self._stats.hits += 1

            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存值"""
        with self._lock:
            # 检查是否已存在
            if key in self._cache:
                entry = self._cache[key]
                entry.value = value
                entry.expires_at = datetime.now() + timedelta(
                    seconds=ttl or self.ttl_seconds
                )
                self._cache.move_to_end(key)
            else:
                # 新条目
                entry = CacheEntry(
                    key=key,
                    value=value,
                    expires_at=datetime.now() + timedelta(
                        seconds=ttl or self.ttl_seconds
                    )
                )
                self._cache[key] = entry

                # 检查是否需要淘汰
                if len(self._cache) > self.max_size:
                    self._evict_lru()

            self._stats.writes += 1

            # 批量写入缓冲
            self._write_buffer.append((key, value))
            if len(self._write_buffer) >= self.batch_size:
                self._flush_buffer()

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        with self._lock:
            if key in self._cache:
                self._evict(key)
                return True
            return False

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._write_buffer.clear()
            logger.info("Cache cleared")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            stats = self._stats.to_dict()
            stats["size"] = len(self._cache)
            stats["max_size"] = self.max_size
            stats["buffer_size"] = len(self._write_buffer)
            return stats

    def _evict(self, key: str):
        """淘汰单个条目"""
        del self._cache[key]
        self._stats.evictions += 1

    def _evict_lru(self):
        """淘汰最久未使用的条目"""
        if self._cache:
            # OrderedDict 第一个是最久未使用的
            oldest_key = next(iter(self._cache))
            self._evict(oldest_key)
            logger.debug(f"Evicted LRU entry: {oldest_key}")

    def _flush_buffer(self):
        """刷新写入缓冲"""
        if not self._write_buffer:
            return

        # 持久化
        if self.persist_path:
            try:
                data = {key: value for key, value in self._write_buffer}
                self._persist(data)
            except Exception as e:
                logger.error(f"Failed to persist cache: {e}")

        self._write_buffer.clear()
        self._last_flush = datetime.now()

    def _background_flush(self):
        """后台刷新线程"""
        while self._running:
            time.sleep(self.flush_interval)
            with self._lock:
                self._flush_buffer()

                # 清理过期条目
                expired_keys = [
                    k for k, v in self._cache.items()
                    if v.is_expired()
                ]
                for key in expired_keys:
                    self._evict(key)

                if expired_keys:
                    logger.debug(f"Cleaned {len(expired_keys)} expired entries")

    def _persist(self, data: Dict):
        """持久化数据"""
        if not self.persist_path:
            return

        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)

            # 追加写入
            if self.persist_path.exists():
                with open(self.persist_path, "r") as f:
                    existing = json.load(f)
            else:
                existing = {}

            existing.update(data)

            with open(self.persist_path, "w") as f:
                json.dump(existing, f, indent=2)

        except Exception as e:
            logger.error(f"Persist error: {e}")

    def _load_persisted(self):
        """加载持久化数据"""
        if not self.persist_path or not self.persist_path.exists():
            return

        try:
            with open(self.persist_path, "r") as f:
                data = json.load(f)

            for key, value in data.items():
                self.set(key, value)

            logger.info(f"Loaded {len(data)} persisted cache entries")
        except Exception as e:
            logger.error(f"Load persisted error: {e}")

    def close(self):
        """关闭缓存"""
        self._running = False
        with self._lock:
            self._flush_buffer()
        logger.info("Cache closed")


class PhoenixMemoryOptimizer:
    """
    Phoenix Core 记忆优化器

    整合多个优化策略:
    1. 多层缓存 (L1/L2)
    2. 预加载热点数据
    3. 智能过期策略
    """

    def __init__(self, workspaces_dir: Path):
        self.workspaces_dir = workspaces_dir

        # L1 缓存：进程内缓存 (快速)
        self.l1_cache = MemoryCache(
            max_size=50,
            ttl_seconds=60,
            persist_path=None
        )

        # L2 缓存：磁盘缓存 (持久)
        self.l2_path = workspaces_dir.parent / ".phoenix_cache"
        self.l2_path.mkdir(parents=True, exist_ok=True)

        self.l2_cache = MemoryCache(
            max_size=200,
            ttl_seconds=600,
            persist_path=self.l2_path / "memory_cache.json"
        )

        logger.info("PhoenixMemoryOptimizer initialized")

    def get_memory(self, bot_name: str, memory_type: str) -> Optional[str]:
        """
        获取 Bot 记忆 (带缓存)

        Args:
            bot_name: Bot 名称
            memory_type: 记忆类型 (long_term, short_term, session)

        Returns:
            记忆内容
        """
        cache_key = f"{bot_name}:{memory_type}"

        # L1 缓存
        value = self.l1_cache.get(cache_key)
        if value:
            return value

        # L2 缓存
        value = self.l2_cache.get(cache_key)
        if value:
            # 回填 L1
            self.l1_cache.set(cache_key, value)
            return value

        # 从文件读取
        memory_file = self.workspaces_dir / bot_name / "MEMORY.md"
        if memory_file.exists():
            content = memory_file.read_text(encoding="utf-8")

            # 写入缓存
            self.l1_cache.set(cache_key, content)
            self.l2_cache.set(cache_key, content)

            return content

        return None

    def set_memory(self, bot_name: str, memory_type: str, content: str):
        """设置记忆 (带缓存更新)"""
        cache_key = f"{bot_name}:{memory_type}"

        # 更新缓存
        self.l1_cache.set(cache_key, content)
        self.l2_cache.set(cache_key, content)

        # 写入文件
        memory_file = self.workspaces_dir / bot_name / "MEMORY.md"
        memory_file.parent.mkdir(parents=True, exist_ok=True)
        memory_file.write_text(content, encoding="utf-8")

    def get_stats(self) -> Dict:
        """获取优化器统计"""
        return {
            "l1_cache": self.l1_cache.get_stats(),
            "l2_cache": self.l2_cache.get_stats(),
            "workspaces": len(list(self.workspaces_dir.glob("*")))
        }

    def preload_hot_memories(self, bot_names: List[str]):
        """预加载热点记忆"""
        for bot_name in bot_names:
            # 预加载常用记忆类型
            for memory_type in ["long_term", "short_term", "session"]:
                cache_key = f"{bot_name}:{memory_type}"

                # 如果不在缓存中，主动加载
                if self.l1_cache.get(cache_key) is None:
                    content = self.get_memory(bot_name, memory_type)
                    if content:
                        logger.debug(f"Preloaded {cache_key}")

    def close(self):
        """关闭优化器"""
        self.l1_cache.close()
        self.l2_cache.close()


# 全局实例
_memory_optimizer: Optional[PhoenixMemoryOptimizer] = None


def get_memory_optimizer(workspaces_dir: Path = None) -> PhoenixMemoryOptimizer:
    """获取记忆优化器实例"""
    global _memory_optimizer

    if _memory_optimizer is None:
        if workspaces_dir is None:
            workspaces_dir = Path(__file__).parent / "workspaces"
        _memory_optimizer = PhoenixMemoryOptimizer(workspaces_dir)

    return _memory_optimizer
