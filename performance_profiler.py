#!/usr/bin/env python3
"""
Performance Profiler - 性能分析和优化工具

Phoenix Core Phoenix v2.0 扩展模块

功能:
1. 模块加载时间分析
2. 内存使用监控
3. SQLite 性能检测
4. API 响应时间追踪
5. 性能报告生成

Usage:
    from performance_profiler import PerformanceProfiler

    profiler = PerformanceProfiler()
    profiler.start_monitoring()

    with profiler.profile("operation_name"):
        # 执行操作
        pass

    report = profiler.generate_report()
"""

import json
import logging
import os
import resource
import sqlite3
import time
import tracemalloc
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from contextlib import contextmanager
from collections import defaultdict
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
PROFILER_DIR = Path(__file__).parent / "performance_logs")
PROFILER_DIR.mkdir(parents=True, exist_ok=True)


class ProfileResult:
    """单次性能分析结果"""

    def __init__(self, name: str, start_time: float, end_time: float,
                 memory_start: int = None, memory_end: int = None):
        self.name = name
        self.start_time = start_time
        self.end_time = end_time
        self.duration_ms = (end_time - start_time) * 1000
        self.memory_start = memory_start or 0
        self.memory_end = memory_end or 0
        self.memory_delta = memory_end - memory_start if memory_end else 0
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "duration_ms": round(self.duration_ms, 2),
            "memory_start_kb": self.memory_start,
            "memory_end_kb": self.memory_end,
            "memory_delta_kb": self.memory_delta,
            "timestamp": self.timestamp
        }


class PerformanceProfiler:
    """
    性能分析器

    追踪代码执行时间和内存使用
    """

    def __init__(self, bot_name: str = None):
        self.bot_name = bot_name or "system"
        self.results: List[ProfileResult] = []
        self._results_by_name: Dict[str, List[ProfileResult]] = defaultdict(list)
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._sqlite_stats: Dict = {}

        # 启动 tracemalloc
        if not tracemalloc.is_tracing():
            tracemalloc.start()

        logger.info(f"Performance Profiler initialized for {self.bot_name}")

    @contextmanager
    def profile(self, name: str, track_memory: bool = True):
        """
        性能分析上下文管理器

        Usage:
            with profiler.profile("database_query"):
                result = db.execute(query)
        """
        start_time = time.time()
        memory_start = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if track_memory else None

        try:
            yield
        finally:
            end_time = time.time()
            memory_end = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if track_memory else None

            result = ProfileResult(name, start_time, end_time, memory_start, memory_end)
            self.results.append(result)
            self._results_by_name[name].append(result)

            logger.debug(f"Profiled '{name}': {result.duration_ms:.2f}ms, memory: {result.memory_delta}KB")

    def start_monitoring(self, interval: int = 60):
        """启动后台监控"""
        if self._monitoring:
            logger.warning("Monitoring already running")
            return

        self._monitoring = True

        def monitor_loop():
            logger.info("Starting performance monitoring loop...")
            while self._monitoring:
                try:
                    self._collect_sqlite_stats()
                    self._check_memory_usage()
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"Monitor error: {e}")

        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info(f"Performance monitoring started (interval: {interval}s)")

    def stop_monitoring(self):
        """停止后台监控"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
        logger.info("Performance monitoring stopped")

    def _collect_sqlite_stats(self):
        """收集 SQLite 性能统计"""
        db_path = Path(f"workspaces/{self.bot_name}/session_store.db")
        if not db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # WAL 检查
            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]

            # 页面大小
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]

            # 页面计数
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]

            # 空闲页面
            cursor.execute("PRAGMA freelist_count")
            freelist_count = cursor.fetchone()[0]

            self._sqlite_stats = {
                "journal_mode": journal_mode,
                "page_size": page_size,
                "page_count": page_count,
                "freelist_count": freelist_count,
                "db_size_kb": (page_count * page_size) // 1024,
                "collected_at": datetime.now().isoformat()
            }

            conn.close()
        except Exception as e:
            logger.error(f"Failed to collect SQLite stats: {e}")

    def _check_memory_usage(self):
        """检查内存使用"""
        memory_info = tracemalloc.get_traced_memory()
        current, peak = memory_info

        if current > 100 * 1024 * 1024:  # 100MB 警告
            logger.warning(f"High memory usage: {current // 1024 // 1024}MB")

        if peak > 500 * 1024 * 1024:  # 500MB 峰值警告
            logger.warning(f"Peak memory usage: {peak // 1024 // 1024}MB")

    def get_stats(self, name: str = None) -> Dict:
        """获取性能统计"""
        if name:
            # 获取特定操作的统计
            results = self._results_by_name.get(name, [])
            if not results:
                return {"name": name, "count": 0}

            durations = [r.duration_ms for r in results]
            return {
                "name": name,
                "count": len(results),
                "total_ms": round(sum(durations), 2),
                "avg_ms": round(sum(durations) / len(durations), 2),
                "min_ms": round(min(durations), 2),
                "max_ms": round(max(durations), 2),
                "last_run": results[-1].timestamp
            }
        else:
            # 获取所有统计
            all_stats = {}
            for op_name in self._results_by_name.keys():
                all_stats[op_name] = self.get_stats(op_name)
            return all_stats

    def get_slowest_operations(self, top_n: int = 10) -> List[Dict]:
        """获取最慢的操作"""
        sorted_results = sorted(self.results, key=lambda r: r.duration_ms, reverse=True)
        return [r.to_dict() for r in sorted_results[:top_n]]

    def get_memory_snapshot(self) -> Dict:
        """获取内存快照"""
        current, peak = tracemalloc.get_traced_memory()
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')[:10]

        return {
            "current_kb": current // 1024,
            "peak_kb": peak // 1024,
            "top_allocations": [
                {
                    "file": str(stat.traceback),
                    "size_kb": stat.size // 1024,
                    "count": stat.count
                }
                for stat in top_stats
            ],
            "timestamp": datetime.now().isoformat()
        }

    def generate_report(self) -> Dict:
        """生成性能报告"""
        return {
            "bot_name": self.bot_name,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_operations": len(self.results),
                "unique_operations": len(self._results_by_name),
                "total_time_ms": round(sum(r.duration_ms for r in self.results), 2)
            },
            "stats_by_operation": self.get_stats(),
            "slowest_operations": self.get_slowest_operations(10),
            "memory_snapshot": self.get_memory_snapshot(),
            "sqlite_stats": self._sqlite_stats
        }

    def save_report(self, filename: str = None):
        """保存性能报告"""
        if not filename:
            filename = f"performance_report_{self.bot_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report_path = PROFILER_DIR / filename
        report = self.generate_report()

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Performance report saved: {report_path}")
        return report_path

    def compare_operations(self, *names) -> Dict:
        """比较多个操作的性能"""
        comparison = {}
        for name in names:
            comparison[name] = self.get_stats(name)
        return comparison

    def clear_history(self):
        """清除分析历史"""
        self.results.clear()
        self._results_by_name.clear()
        logger.info("Performance history cleared")


class BotPerformanceMonitor:
    """
    Bot 性能监控器

    持续监控 Bot 性能指标
    """

    def __init__(self, bot_name: str):
        self.bot_name = bot_name
        self.profiler = PerformanceProfiler(bot_name)
        self.metrics_file = PROFILER_DIR / f"{bot_name}_metrics.jsonl"
        self._metrics_buffer: List[Dict] = []
        self._buffer_size = 100

    def record_metric(self, metric_name: str, value: float, metadata: Dict = None):
        """记录性能指标"""
        metric = {
            "timestamp": datetime.now().isoformat(),
            "bot_name": self.bot_name,
            "metric_name": metric_name,
            "value": value,
            "metadata": metadata or {}
        }

        self._metrics_buffer.append(metric)

        # 批量写入
        if len(self._metrics_buffer) >= self._buffer_size:
            self._flush_metrics()

    def _flush_metrics(self):
        """刷新指标到文件"""
        if not self._metrics_buffer:
            return

        with open(self.metrics_file, "a", encoding="utf-8") as f:
            for metric in self._metrics_buffer:
                f.write(json.dumps(metric, ensure_ascii=False) + "\n")

        self._metrics_buffer.clear()
        logger.debug(f"Flushed {len(self._metrics_buffer)} metrics to disk")

    def get_metrics(self, metric_name: str = None,
                    time_range: timedelta = None) -> List[Dict]:
        """获取历史指标"""
        if not self.metrics_file.exists():
            return []

        metrics = []
        cutoff = datetime.now() - time_range if time_range else None

        with open(self.metrics_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    metric = json.loads(line)
                    if metric_name and metric.get("metric_name") != metric_name:
                        continue
                    if cutoff:
                        metric_time = datetime.fromisoformat(metric["timestamp"])
                        if metric_time < cutoff:
                            continue
                    metrics.append(metric)
                except:
                    continue

        return metrics

    def get_metric_stats(self, metric_name: str,
                         time_range: timedelta = None) -> Dict:
        """获取指标统计"""
        metrics = self.get_metrics(metric_name, time_range)
        if not metrics:
            return {"count": 0}

        values = [m["value"] for m in metrics]
        return {
            "metric_name": metric_name,
            "count": len(metrics),
            "avg": round(sum(values) / len(values), 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "last_value": metrics[-1]["value"],
            "time_range": str(time_range) if time_range else "all"
        }

    def start(self, interval: int = 60):
        """启动监控"""
        self.profiler.start_monitoring(interval)
        logger.info(f"Bot Performance Monitor started for {self.bot_name}")

    def stop(self):
        """停止监控"""
        self._flush_metrics()
        self.profiler.stop_monitoring()
        logger.info(f"Bot Performance Monitor stopped for {self.bot_name}")


# 装饰器
def profile_operation(name: str = None):
    """性能分析装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 尝试获取 profiler 实例
            profiler = None
            for arg in args:
                if isinstance(arg, PerformanceProfiler):
                    profiler = arg
                    break

            operation_name = name or func.__name__

            if profiler:
                with profiler.profile(operation_name):
                    return func(*args, **kwargs)
            else:
                # 无 profiler 时直接执行
                return func(*args, **kwargs)
        return wrapper
    return decorator


# 全局实例
_monitors: Dict[str, BotPerformanceMonitor] = {}


def get_performance_monitor(bot_name: str) -> BotPerformanceMonitor:
    """获取 Bot 性能监控器"""
    if bot_name not in _monitors:
        _monitors[bot_name] = BotPerformanceMonitor(bot_name)
    return _monitors[bot_name]


def start_bot_monitoring(bot_name: str, interval: int = 60) -> BotPerformanceMonitor:
    """启动 Bot 性能监控"""
    monitor = get_performance_monitor(bot_name)
    monitor.start(interval)
    return monitor


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Performance Profiler - 性能分析和优化工具")
        print("\nUsage:")
        print("  python3 performance_profiler.py <bot_name> test")
        print("  python3 performance_profiler.py report")
        sys.exit(1)

    command = sys.argv[1]

    if command == "report":
        # 生成所有 Bot 的性能报告
        print("\nGenerating performance reports...")
        for metrics_file in PROFILER_DIR.glob("*_metrics.jsonl"):
            bot_name = metrics_file.name.replace("_metrics.jsonl", "")
            monitor = BotPerformanceMonitor(bot_name)
            stats = monitor.get_metric_stats("api_latency")
            if stats.get("count", 0) > 0:
                print(f"\n{bot_name}:")
                print(f"  Avg Latency: {stats.get('avg', 0)}ms")
                print(f"  Max Latency: {stats.get('max', 0)}ms")
                print(f"  Min Latency: {stats.get('min', 0)}ms")

    elif len(sys.argv) > 1 and sys.argv[2] == "test":
        bot_name = sys.argv[1]
        print(f"\nTesting Performance Profiler for {bot_name}\n")

        monitor = BotPerformanceMonitor(bot_name)

        # 模拟性能测试
        print("Running performance test...")

        # 测试 1: 快速操作
        with monitor.profiler.profile("fast_operation"):
            time.sleep(0.01)

        # 测试 2: 中等操作
        with monitor.profiler.profile("medium_operation"):
            time.sleep(0.1)

        # 测试 3: 慢速操作
        with monitor.profiler.profile("slow_operation"):
            time.sleep(0.5)

        # 重复测试
        for i in range(5):
            with monitor.profiler.profile("repeated_operation"):
                time.sleep(0.02 * (i + 1))

        # 记录自定义指标
        monitor.record_metric("api_latency", 45.2, {"endpoint": "/chat"})
        monitor.record_metric("api_latency", 32.1, {"endpoint": "/chat"})
        monitor.record_metric("api_latency", 78.5, {"endpoint": "/chat"})
        monitor.record_metric("memory_usage", 52.3, {"unit": "MB"})

        # 获取统计
        print("\nPerformance Stats:")
        stats = monitor.profiler.get_stats()
        for op_name, op_stats in stats.items():
            print(f"  {op_name}: {op_stats.get('avg_ms', 0)}ms avg ({op_stats.get('count', 0)} calls)")

        # 最慢操作
        print("\nSlowest Operations:")
        for op in monitor.profiler.get_slowest_operations(3):
            print(f"  {op['name']}: {op['duration_ms']}ms")

        # 内存快照
        print("\nMemory Snapshot:")
        mem = monitor.profiler.get_memory_snapshot()
        print(f"  Current: {mem['current_kb']}KB")
        print(f"  Peak: {mem['peak_kb']}KB")

        # 指标统计
        print("\nMetric Stats:")
        latency_stats = monitor.get_metric_stats("api_latency")
        print(f"  API Latency: {latency_stats.get('avg', 0)}ms avg")

        # 保存报告
        report_path = monitor.profiler.save_report()
        print(f"\nReport saved: {report_path}")

        # 清理
        monitor.stop()
