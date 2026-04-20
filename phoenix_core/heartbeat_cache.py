#!/usr/bin/env python3
"""
Phoenix Core Heartbeat Cache - 心跳内存缓存

适用场景：Bot 数量 50+ 时减少 I/O 压力
- 内存维护心跳状态
- 文件仅作持久化备份
- Dashboard 从缓存读取

Usage:
    from phoenix_core.heartbeat_cache import HeartbeatCache

    # 单例模式
    cache = HeartbeatCache.instance()

    # Bot 端：更新心跳（同时写文件和内存）
    cache.update_heartbeat("客服", status="running")

    # Dashboard 端：从缓存读取（不读文件）
    status = cache.get_bot_health("客服")
    all_status = cache.get_all_bots_health()
"""

import json
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# 心跳目录
HEARTBEAT_DIR = Path(__file__).parent.parent.parent / "data" / "heartbeats"

# 缓存过期时间 (秒)
CACHE_TTL = 30.0


class HeartbeatCache:
    """心跳内存缓存 (单例模式)"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 内存缓存：{bot_id: heartbeat_data}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._lock = threading.RLock()

        # 后台清理线程
        self._stop_event = threading.Event()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

        # 启动时从文件加载一次
        self._load_from_files()

        logger.info(f"[HeartbeatCache] 已启动，TTL={CACHE_TTL}s")

    @classmethod
    def instance(cls) -> "HeartbeatCache":
        """获取单例实例"""
        return cls()

    def _load_from_files(self):
        """从文件加载心跳数据 (启动时执行)"""
        if not HEARTBEAT_DIR.exists():
            return

        loaded = 0
        for file_path in HEARTBEAT_DIR.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                bot_id = data.get("bot_id", file_path.stem)

                with self._lock:
                    self._cache[bot_id] = data
                    self._cache_timestamps[bot_id] = time.time()
                    loaded += 1
            except Exception as e:
                logger.warning(f"[HeartbeatCache] 加载文件失败 {file_path.name}: {e}")

        logger.info(f"[HeartbeatCache] 从文件加载 {loaded} 个 Bot 心跳")

    def update_heartbeat(self, bot_id: str, status: str = "running", extra_info: Optional[Dict] = None):
        """
        更新心跳 (同时写文件和内存)

        Args:
            bot_id: Bot 名称
            status: 状态
            extra_info: 额外信息
        """
        data = {
            "bot_id": bot_id,
            "last_beat": time.time(),
            "last_beat_iso": datetime.now().isoformat(),
            "status": status,
            "timeout": CACHE_TTL,
            "extra": extra_info or {},
        }

        # 写文件 (原子写入)
        file_path = HEARTBEAT_DIR / f"{bot_id}.json"
        try:
            HEARTBEAT_DIR.mkdir(parents=True, exist_ok=True)
            tmp_path = file_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, file_path)
        except Exception as e:
            logger.error(f"[HeartbeatCache] 写文件失败 {bot_id}: {e}")

        # 更新内存缓存
        with self._lock:
            self._cache[bot_id] = data
            self._cache_timestamps[bot_id] = time.time()

    def get_bot_health(self, bot_id: str) -> Dict[str, Any]:
        """
        获取 Bot 健康状态 (从内存读取，不读文件)

        Returns:
            {
                "healthy": bool,
                "bot_id": str,
                "last_beat": float,
                "status": str,
                "seconds_ago": float,
                "from_cache": bool
            }
        """
        with self._lock:
            data = self._cache.get(bot_id)
            cache_ts = self._cache_timestamps.get(bot_id, 0)

        if data is None:
            return {
                "healthy": False,
                "bot_id": bot_id,
                "error": "heartbeat_not_found",
                "message": f"心跳数据不存在：{bot_id}",
                "from_cache": True,
            }

        last_beat = data.get("last_beat", 0)
        now = time.time()
        seconds_ago = now - last_beat
        cache_age = now - cache_ts

        # 缓存过期检查
        if cache_age > CACHE_TTL:
            return {
                "healthy": False,
                "bot_id": bot_id,
                "error": "cache_expired",
                "seconds_ago": seconds_ago,
                "from_cache": True,
            }

        healthy = seconds_ago < CACHE_TTL

        return {
            "healthy": healthy,
            "bot_id": bot_id,
            "last_beat": last_beat,
            "last_beat_iso": data.get("last_beat_iso"),
            "status": data.get("status", "unknown"),
            "seconds_ago": round(seconds_ago, 1),
            "timeout": CACHE_TTL,
            "extra": data.get("extra", {}),
            "from_cache": True,
            "cache_age": round(cache_age, 1),
        }

    def get_all_bots_health(self) -> Dict[str, Dict[str, Any]]:
        """获取所有 Bot 健康状态 (从内存读取)"""
        with self._lock:
            bot_ids = list(self._cache.keys())

        result = {}
        for bot_id in bot_ids:
            result[bot_id] = self.get_bot_health(bot_id)

        return result

    def get_healthy_bots(self) -> list:
        """获取健康 Bot 列表"""
        all_health = self.get_all_bots_health()
        return [
            bot_id for bot_id, health in all_health.items()
            if health.get("healthy", False)
        ]

    def get_unhealthy_bots(self) -> list:
        """获取不健康 Bot 列表"""
        all_health = self.get_all_bots_health()
        return [
            bot_id for bot_id, health in all_health.items()
            if not health.get("healthy", False)
        ]

    def _cleanup_loop(self):
        """后台清理过期缓存"""
        while not self._stop_event.is_set():
            time.sleep(60)  # 每分钟清理一次
            self._cleanup_expired()

    def _cleanup_expired(self):
        """清理过期缓存"""
        now = time.time()
        cleaned = 0

        with self._lock:
            expired = [
                bot_id for bot_id, ts in self._cache_timestamps.items()
                if now - ts > CACHE_TTL * 2  # 2 倍 TTL 后清理
            ]
            for bot_id in expired:
                del self._cache[bot_id]
                del self._cache_timestamps[bot_id]
                cleaned += 1

        if cleaned > 0:
            logger.info(f"[HeartbeatCache] 清理 {cleaned} 个过期缓存")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            return {
                "cached_bots": len(self._cache),
                "cache_keys": list(self._cache.keys()),
                "ttl": CACHE_TTL,
            }

    def shutdown(self):
        """关闭缓存 (停止后台线程)"""
        self._stop_event.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)


# 便捷函数
def update_heartbeat(bot_id: str, status: str = "running", extra_info: Optional[Dict] = None):
    """便捷函数：更新心跳"""
    cache = HeartbeatCache.instance()
    cache.update_heartbeat(bot_id, status, extra_info)


def get_bot_health(bot_id: str) -> Dict[str, Any]:
    """便捷函数：获取 Bot 健康"""
    cache = HeartbeatCache.instance()
    return cache.get_bot_health(bot_id)


def get_all_bots_health() -> Dict[str, Dict[str, Any]]:
    """便捷函数：获取所有 Bot 健康"""
    cache = HeartbeatCache.instance()
    return cache.get_all_bots_health()


# 导入 os，用于原子写入
import os
