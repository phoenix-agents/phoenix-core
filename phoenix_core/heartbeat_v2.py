#!/usr/bin/env python3
"""
Phoenix Core Heartbeat v2 - 独立心跳文件模式

每个 Bot 写自己的心跳文件，避免并发冲突

目录结构:
    data/heartbeats/
    ├── 客服.json
    ├── 运营.json
    └── 编导.json

Usage:
    # Bot 端 - 写入心跳
    from phoenix_core.heartbeat_v2 import write_heartbeat
    write_heartbeat("客服", status="running")

    # Dashboard 端 - 读取所有心跳
    from phoenix_core.heartbeat_v2 import read_all_heartbeats, get_bot_health
    heartbeats = read_all_heartbeats()
    is_healthy = get_bot_health("客服")
"""

import json
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# 心跳目录（相对于项目根目录）
PROJECT_ROOT = Path(__file__).parent.parent
HEARTBEAT_DIR = PROJECT_ROOT / "data" / "heartbeats"

# 超时阈值 (秒)
DEFAULT_TIMEOUT = 15.0


def ensure_heartbeat_dir():
    """确保心跳目录存在"""
    HEARTBEAT_DIR.mkdir(parents=True, exist_ok=True)


def write_heartbeat(
    bot_id: str,
    status: str = "running",
    extra_info: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> bool:
    """
    Bot 进程调用：写入自己的心跳文件

    Args:
        bot_id: Bot 名称 (如 "客服", "运营")
        status: 状态字符串 ("running", "idle", "busy", "error")
        extra_info: 额外信息 (如内存占用、当前任务)
        timeout: 超时阈值 (秒)

    Returns:
        是否成功
    """
    ensure_heartbeat_dir()
    file_path = HEARTBEAT_DIR / f"{bot_id}.json"

    data = {
        "bot_id": bot_id,
        "last_beat": time.time(),
        "last_beat_iso": datetime.now().isoformat(),
        "status": status,
        "timeout": timeout,
        "extra": extra_info or {},
    }

    try:
        # 原子写入：先写 .tmp 再 replace
        tmp_path = file_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, file_path)
        return True

    except Exception as e:
        logger.error(f"[Heartbeat] {bot_id} 写入失败：{e}")
        return False


def read_all_heartbeats() -> Dict[str, Dict[str, Any]]:
    """
    Dashboard 调用：读取所有 Bot 的心跳数据

    Returns:
        {"客服": {...}, "运营": {...}, ...}
    """
    ensure_heartbeat_dir()
    result = {}

    for file_path in HEARTBEAT_DIR.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                bot_id = data.get("bot_id", file_path.stem)
                result[bot_id] = data
        except json.JSONDecodeError as e:
            logger.warning(f"[Heartbeat] 文件损坏 {file_path.name}: {e}")
            continue
        except IOError as e:
            logger.warning(f"[Heartbeat] 读取失败 {file_path.name}: {e}")
            continue

    return result


def get_bot_health(
    bot_id: str,
    timeout_seconds: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    判断单个 Bot 健康状态

    Returns:
        {
            "healthy": bool,
            "bot_id": str,
            "last_beat": float,
            "last_beat_iso": str,
            "status": str,
            "seconds_ago": float,
            "extra": dict
        }
    """
    file_path = HEARTBEAT_DIR / f"{bot_id}.json"

    if not file_path.exists():
        return {
            "healthy": False,
            "bot_id": bot_id,
            "error": "heartbeat_file_not_found",
            "message": f"心跳文件不存在：{bot_id}",
        }

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        last_beat = data.get("last_beat", 0)
        now = time.time()
        seconds_ago = now - last_beat

        # 使用文件中记录的 timeout 或传入的 timeout
        timeout = data.get("timeout", timeout_seconds)
        healthy = seconds_ago < timeout

        return {
            "healthy": healthy,
            "bot_id": bot_id,
            "last_beat": last_beat,
            "last_beat_iso": data.get("last_beat_iso"),
            "status": data.get("status", "unknown"),
            "seconds_ago": round(seconds_ago, 1),
            "timeout": timeout,
            "extra": data.get("extra", {}),
        }

    except json.JSONDecodeError as e:
        return {
            "healthy": False,
            "bot_id": bot_id,
            "error": "heartbeat_file_corrupted",
            "message": f"心跳文件损坏：{e}",
        }
    except IOError as e:
        return {
            "healthy": False,
            "bot_id": bot_id,
            "error": "heartbeat_file_io_error",
            "message": f"读取心跳文件失败：{e}",
        }


def get_all_bots_health(timeout_seconds: float = DEFAULT_TIMEOUT) -> Dict[str, Dict[str, Any]]:
    """
    获取所有 Bot 健康状态

    Returns:
        {"客服": {...}, "运营": {...}, ...}
    """
    all_heartbeats = read_all_heartbeats()
    result = {}

    for bot_id in all_heartbeats.keys():
        result[bot_id] = get_bot_health(bot_id, timeout_seconds)

    return result


def get_healthy_bots(timeout_seconds: float = DEFAULT_TIMEOUT) -> list:
    """获取健康 Bot 列表"""
    all_health = get_all_bots_health(timeout_seconds)
    return [
        bot_id for bot_id, health in all_health.items()
        if health.get("healthy", False)
    ]


def get_unhealthy_bots(timeout_seconds: float = DEFAULT_TIMEOUT) -> list:
    """获取不健康 Bot 列表"""
    all_health = get_all_bots_health(timeout_seconds)
    return [
        bot_id for bot_id, health in all_health.items()
        if not health.get("healthy", False)
    ]


def cleanup_stale_heartbeats(max_age_days: int = 7) -> int:
    """
    清理过期心跳文件

    Args:
        max_age_days: 最大保留天数

    Returns:
        清理的文件数
    """
    ensure_heartbeat_dir()
    now = time.time()
    cleaned = 0

    for file_path in HEARTBEAT_DIR.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            last_beat = data.get("last_beat", 0)
            age_seconds = now - last_beat
            age_days = age_seconds / 86400

            if age_days > max_age_days:
                file_path.unlink()
                cleaned += 1
                logger.info(f"[Heartbeat] 清理过期文件 {file_path.name} ({age_days:.1f}天)")

        except Exception as e:
            logger.warning(f"[Heartbeat] 清理失败 {file_path.name}: {e}")
            continue

    return cleaned


def delete_bot_heartbeat(bot_id: str) -> bool:
    """
    删除指定 Bot 的心跳文件 (Bot 下线时使用)

    Args:
        bot_id: Bot 名称

    Returns:
        是否成功删除
    """
    file_path = HEARTBEAT_DIR / f"{bot_id}.json"
    try:
        if file_path.exists():
            file_path.unlink()
        return True
    except Exception as e:
        logger.error(f"[Heartbeat] 删除失败 {bot_id}: {e}")
        return False


# ========== 便捷类：Bot 端心跳管理器 ==========

class HeartbeatManager:
    """
    Bot 进程心跳管理器

    Usage:
        from phoenix_core.heartbeat_v2 import HeartbeatManager

        # 启动 Bot 时
        hb = HeartbeatManager("客服")
        hb.start()  # 后台线程每 2 秒发送心跳

        # Bot 主循环中 (可选，如果需要传递更多信息)
        hb.update(status="busy", extra_info={"task": "处理消息中"})

        # Bot 停止时
        hb.stop()
    """

    def __init__(
        self,
        bot_id: str,
        interval: float = 2.0,
        timeout: float = DEFAULT_TIMEOUT,
        status: str = "running",
    ):
        """
        Args:
            bot_id: Bot 名称
            interval: 心跳间隔 (秒)
            timeout: 超时阈值 (秒)
            status: 初始状态
        """
        self.bot_id = bot_id
        self.interval = interval
        self.timeout = timeout
        self.status = status
        self.extra_info = {}

        self._running = False
        self._thread = None
        self._stop_event = None

    def start(self):
        """启动心跳线程"""
        import threading

        if self._thread and self._thread.is_alive():
            return

        self._running = True
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()

    def _heartbeat_loop(self):
        """心跳循环"""
        while self._running and not self._stop_event.is_set():
            write_heartbeat(
                self.bot_id,
                status=self.status,
                extra_info=self.extra_info,
                timeout=self.timeout,
            )
            self._stop_event.wait(timeout=self.interval)

    def update(self, status: Optional[str] = None, extra_info: Optional[Dict] = None):
        """更新状态 (不等待下次心跳，立即写入)"""
        if status:
            self.status = status
        if extra_info:
            self.extra_info = extra_info

        write_heartbeat(self.bot_id, status=self.status, extra_info=self.extra_info, timeout=self.timeout)

    def stop(self):
        """停止心跳线程"""
        self._running = True
        if self._stop_event:
            self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

        # 最后写入一次离线状态
        write_heartbeat(self.bot_id, status="stopped", extra_info={}, timeout=self.timeout)

    def cleanup(self):
        """清理心跳文件"""
        delete_bot_heartbeat(self.bot_id)
