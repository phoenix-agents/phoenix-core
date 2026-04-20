#!/usr/bin/env python3
"""
Phoenix Core - 链路追踪模块 (Link Tracing)

功能:
1. 追踪任务执行路径 (类似 Jaeger/Zipkin)
2. Trace ID 跨子任务传播
3. Span 层级结构 (父 Span → 子 Span)
4. 执行时间线记录
5. 可视化执行流程

核心概念:
- Trace: 完整请求链路 (一个 Trace ID 对应一次完整请求)
- Span: 链路中的单个操作 (一个 Trace 包含多个 Span)
- Parent-Child: Span 之间的层级关系

数据结构:
┌─────────────────────────────────────────────────────────┐
│ Trace: user123-20260417-001                              │
│ ├─ Span: intent_recognition (0-50ms)                     │
│ │  └─ Span: llm_inference (10-45ms)                      │
│ ├─ Span: memory_retrieval (50-80ms)                      │
│ ├─ Span: task_decomposition (80-100ms)                   │
│ │  ├─ Span: subtask-0 (100-200ms)                        │
│ │  │  └─ Span: mcp_call (120-180ms)                      │
│ │  └─ Span: subtask-1 (100-220ms)                        │
│ │     └─ Span: bot_call (130-200ms)                      │
│ └─ Span: result_aggregation (220-250ms)                  │
└─────────────────────────────────────────────────────────┘
"""

import json
import logging
import uuid
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager
from enum import Enum
import sqlite3

logger = logging.getLogger(__name__)


class SpanStatus(Enum):
    """Span 状态"""
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class Span:
    """
    链路追踪 Span

    Span 代表链路中的一个操作单元
    """
    trace_id: str           # Trace ID (整个请求的唯一标识)
    span_id: str            # Span ID (当前操作的唯一标识)
    parent_span_id: Optional[str]  # 父 Span ID (可选)
    operation_name: str     # 操作名称 (如 "intent_recognition", "mcp_call")
    start_time: float       # 开始时间 (Unix timestamp)
    end_time: Optional[float] = None  # 结束时间
    status: str = "running"  # running, success, error, timeout
    duration_ms: Optional[float] = None  # 耗时 (毫秒)
    tags: Dict[str, Any] = field(default_factory=dict)  # 标签 (如 bot_id, tool_name)
    logs: List[Dict] = field(default_factory=list)  # 日志 (时间线事件)
    error_message: Optional[str] = None  # 错误信息

    def add_log(self, event: str, timestamp: Optional[float] = None, **kwargs):
        """添加日志事件"""
        log_entry = {
            "timestamp": timestamp or time.time(),
            "event": event,
            **kwargs
        }
        self.logs.append(log_entry)

    def finish(self, status: str = "success", error_message: Optional[str] = None):
        """结束 Span"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status
        self.error_message = error_message

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)

    def to_json(self) -> str:
        """转换为 JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: Dict) -> "Span":
        """从字典创建"""
        return cls(**data)


class LinkTracer:
    """
    链路追踪器

    职责:
    1. 创建和管理 Trace
    2. 创建 Span (支持父子关系)
    3. 记录操作耗时
    4. 存储和查询链路数据
    """

    def __init__(
        self,
        storage_path: str = "logs/tracing",
        db_path: Optional[str] = None
    ):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path or str(self.storage_path / "tracing.db")

        # 内存缓存 (活跃的 Trace)
        self._active_traces: Dict[str, List[Span]] = {}

        # Span 堆栈 (用于自动父子关系)
        self._span_stack: Dict[str, List[str]] = {}  # trace_id -> [span_id, ...]

        # 数据库连接
        self._db_conn: Optional[sqlite3.Connection] = None

        # 初始化
        self._init_db()
        logger.info(f"链路追踪初始化完成：{self.storage_path}")

    def _init_db(self):
        """初始化 SQLite 数据库"""
        conn = self._get_db_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL UNIQUE,
                user_id TEXT,
                request_id TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS spans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                span_id TEXT NOT NULL,
                parent_span_id TEXT,
                operation_name TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL,
                status TEXT NOT NULL,
                duration_ms REAL,
                tags TEXT,
                logs TEXT,
                error_message TEXT,
                FOREIGN KEY (trace_id) REFERENCES traces(trace_id)
            )
        """)

        # 创建索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trace_id ON spans(trace_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_operation ON spans(operation_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON spans(status)")

        conn.commit()
        logger.debug("链路追踪数据库初始化完成")

    def _get_db_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._db_conn is None:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            self._db_conn = conn
        return self._db_conn

    # ============ 核心方法 ============

    def start_trace(
        self,
        user_id: str,
        request_id: Optional[str] = None
    ) -> str:
        """
        开始新的 Trace

        Args:
            user_id: 用户 ID
            request_id: 请求 ID (可选，不提供则自动生成)

        Returns:
            str: Trace ID
        """
        trace_id = request_id or f"{user_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

        # 记录 Trace
        conn = self._get_db_connection()
        conn.execute(
            "INSERT OR IGNORE INTO traces (trace_id, user_id, request_id) VALUES (?, ?, ?)",
            (trace_id, user_id, request_id)
        )
        conn.commit()

        # 初始化活跃 Trace
        self._active_traces[trace_id] = []
        self._span_stack[trace_id] = []

        logger.info(f"开始追踪：trace_id={trace_id}")
        return trace_id

    def start_span(
        self,
        trace_id: str,
        operation_name: str,
        parent_span_id: Optional[str] = None,
        **tags
    ) -> Span:
        """
        开始新的 Span

        Args:
            trace_id: Trace ID
            operation_name: 操作名称
            parent_span_id: 父 Span ID (不提供则自动使用堆栈中的父 Span)
            **tags: 标签键值对

        Returns:
            Span: 新创建的 Span
        """
        span_id = uuid.uuid4().hex[:8]

        # 自动推断父 Span (如果没有显式指定)
        if parent_span_id is None and self._span_stack.get(trace_id):
            parent_span_id = self._span_stack[trace_id][-1]

        # 创建 Span
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            start_time=time.time(),
            tags=tags or {}
        )

        # 记录到堆栈
        if trace_id not in self._span_stack:
            self._span_stack[trace_id] = []
        self._span_stack[trace_id].append(span_id)

        # 添加到活跃 Trace
        if trace_id not in self._active_traces:
            self._active_traces[trace_id] = []
        self._active_traces[trace_id].append(span)

        # 写入数据库 (开始记录)
        self._write_span_to_db(span)

        logger.debug(f"开始 Span: {operation_name} ({span_id})")
        return span

    def end_span(
        self,
        span: Span,
        status: str = "success",
        error_message: Optional[str] = None
    ):
        """
        结束 Span

        Args:
            span: Span 对象
            status: 状态 (success, error, timeout)
            error_message: 错误信息
        """
        span.finish(status=status, error_message=error_message)

        # 从堆栈弹出
        trace_id = span.trace_id
        if self._span_stack.get(trace_id) and span.span_id in self._span_stack[trace_id]:
            self._span_stack[trace_id].remove(span.span_id)

        # 更新数据库
        self._update_span_in_db(span)

        logger.debug(f"结束 Span: {span.operation_name} ({span.span_id}) - {span.duration_ms:.2f}ms")

    @contextmanager
    def trace_operation(
        self,
        trace_id: str,
        operation_name: str,
        parent_span_id: Optional[str] = None,
        **tags
    ):
        """
        上下文管理器：自动记录操作

        Usage:
            with tracer.trace_operation(trace_id, "mcp_call", tool="filesystem") as span:
                # 执行操作
                span.add_log("started")
                result = do_something()
                span.add_log("completed", result=result)
        """
        span = self.start_span(trace_id, operation_name, parent_span_id, **tags)
        try:
            yield span
            self.end_span(span, status="success")
        except Exception as e:
            self.end_span(span, status="error", error_message=str(e))
            raise

    # ============ 内部方法 ============

    def _write_span_to_db(self, span: Span):
        """写入 Span 到数据库"""
        conn = self._get_db_connection()
        conn.execute(
            """INSERT INTO spans
               (trace_id, span_id, parent_span_id, operation_name, start_time, status, tags, logs)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                span.trace_id,
                span.span_id,
                span.parent_span_id,
                span.operation_name,
                span.start_time,
                span.status,
                json.dumps(span.tags, ensure_ascii=False) if span.tags else None,
                json.dumps(span.logs, ensure_ascii=False) if span.logs else None
            )
        )
        conn.commit()

    def _update_span_in_db(self, span: Span):
        """更新 Span 到数据库"""
        conn = self._get_db_connection()
        conn.execute(
            """UPDATE spans
               SET end_time = ?, status = ?, duration_ms = ?,
                   tags = ?, logs = ?, error_message = ?
               WHERE span_id = ?""",
            (
                span.end_time,
                span.status,
                span.duration_ms,
                json.dumps(span.tags, ensure_ascii=False) if span.tags else None,
                json.dumps(span.logs, ensure_ascii=False) if span.logs else None,
                span.error_message,
                span.span_id
            )
        )
        conn.commit()

    # ============ 查询方法 ============

    def get_trace(self, trace_id: str) -> List[Span]:
        """获取完整 Trace"""
        conn = self._get_db_connection()
        cursor = conn.execute(
            "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time",
            (trace_id,)
        )
        return [self._row_to_span(row) for row in cursor.fetchall()]

    def get_trace_timeline(self, trace_id: str) -> List[Dict]:
        """
        获取 Trace 时间线 (可视化友好)

        Returns:
            [
                {"span_id": "...", "operation": "...", "start_offset_ms": 0, "duration_ms": 50},
                {"span_id": "...", "operation": "...", "start_offset_ms": 50, "duration_ms": 30},
                ...
            ]
        """
        spans = self.get_trace(trace_id)
        if not spans:
            return []

        # 找到最早开始时间
        min_start = min(s.start_time for s in spans)

        timeline = []
        for span in spans:
            timeline.append({
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id,
                "operation": span.operation_name,
                "start_offset_ms": round((span.start_time - min_start) * 1000, 2),
                "duration_ms": round(span.duration_ms, 2) if span.duration_ms else None,
                "status": span.status,
                "error_message": span.error_message
            })

        return timeline

    def get_trace_tree(self, trace_id: str) -> Dict:
        """
        获取 Trace 树形结构

        Returns:
            {
                "span_id": "root",
                "operation": "intent_recognition",
                "duration_ms": 50,
                "children": [
                    {"span_id": "...", "operation": "...", "children": [...]}
                ]
            }
        """
        spans = self.get_trace(trace_id)
        if not spans:
            return {}

        # 构建 Span 映射
        span_map = {s.span_id: s for s in spans}

        # 找到根 Span (没有 parent 的)
        root_spans = [s for s in spans if s.parent_span_id is None]

        def build_tree(span: Span) -> Dict:
            children = [s for s in spans if s.parent_span_id == span.span_id]
            return {
                "span_id": span.span_id,
                "operation": span.operation_name,
                "duration_ms": round(span.duration_ms, 2) if span.duration_ms else None,
                "status": span.status,
                "children": [build_tree(c) for c in children]
            }

        # 如果有多个根，创建虚拟根
        if len(root_spans) == 1:
            return build_tree(root_spans[0])
        else:
            return {
                "span_id": "root",
                "operation": "trace",
                "children": [build_tree(r) for r in root_spans]
            }

    def get_slow_traces(self, threshold_ms: float = 1000, limit: int = 10) -> List[Dict]:
        """获取慢调用 Trace"""
        conn = self._get_db_connection()
        cursor = conn.execute(
            """SELECT trace_id, SUM(duration_ms) as total_duration
               FROM spans
               WHERE end_time IS NOT NULL
               GROUP BY trace_id
               HAVING total_duration > ?
               ORDER BY total_duration DESC
               LIMIT ?""",
            (threshold_ms, limit)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_operation_stats(self, operation_name: str, limit: int = 100) -> Dict:
        """获取操作统计信息"""
        conn = self._get_db_connection()
        cursor = conn.execute(
            """SELECT
                   COUNT(*) as count,
                   AVG(duration_ms) as avg_duration,
                   MIN(duration_ms) as min_duration,
                   MAX(duration_ms) as max_duration,
                   SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count
               FROM spans
               WHERE operation_name = ?
               LIMIT ?""",
            (operation_name, limit)
        )
        row = cursor.fetchone()
        return dict(row) if row else {}

    def _row_to_span(self, row: sqlite3.Row) -> Span:
        """将数据库行转为 Span"""
        return Span(
            trace_id=row["trace_id"],
            span_id=row["span_id"],
            parent_span_id=row["parent_span_id"],
            operation_name=row["operation_name"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            status=row["status"],
            duration_ms=row["duration_ms"],
            tags=json.loads(row["tags"]) if row["tags"] else {},
            logs=json.loads(row["logs"]) if row["logs"] else [],
            error_message=row["error_message"]
        )

    # ============ 导出和可视化 ============

    def export_trace_to_json(self, trace_id: str, output_path: str):
        """导出 Trace 为 JSON"""
        spans = self.get_trace(trace_id)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump([s.to_dict() for s in spans], f, indent=2, ensure_ascii=False)
        logger.info(f"导出 Trace {trace_id} 到 {output_path}")

    def print_trace_timeline(self, trace_id: str):
        """打印 Trace 时间线 (ASCII 可视化)"""
        timeline = self.get_trace_timeline(trace_id)
        if not timeline:
            print("未找到 Trace")
            return

        print(f"\n{'='*60}")
        print(f"Trace: {trace_id}")
        print(f"{'='*60}\n")

        # 找到最大时长用于缩放
        max_end = max(t["start_offset_ms"] + (t["duration_ms"] or 0) for t in timeline)
        scale = 50 / max_end if max_end > 0 else 1

        for item in timeline:
            indent = "  " * (len(item["span_id"]) % 4)  # 简单缩进
            start_pos = int(item["start_offset_ms"] * scale)
            duration = int((item["duration_ms"] or 0) * scale) if item["duration_ms"] else 1

            # 状态符号
            status_symbol = {
                "success": "✓",
                "error": "✗",
                "running": "⟳",
                "timeout": "⏱"
            }.get(item["status"], "?")

            # 绘制时间线
            bar = "─" * duration
            if item["status"] == "error":
                bar = f"🔴{bar}"
            elif item["status"] == "success":
                bar = f"🟢{bar}"

            error_info = f" (错误：{item['error_message']})" if item["error_message"] else ""

            print(f"{indent}{status_symbol} {item['operation']}: [{bar}] {item['duration_ms']:.1f}ms{error_info}")

        print(f"\n{'='*60}\n")

    # ============ 清理 ============

    def cleanup_old_traces(self, retention_days: int = 7):
        """清理旧 Trace"""
        from datetime import timedelta
        cutoff = time.time() - (retention_days * 24 * 60 * 60)

        conn = self._get_db_connection()
        cursor = conn.execute(
            "DELETE FROM spans WHERE start_time < ?",
            (cutoff,)
        )
        deleted = cursor.rowcount
        conn.commit()

        logger.info(f"清理 {deleted} 条过期 Span")

    def close(self):
        """关闭追踪器"""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None
        logger.info("链路追踪已关闭")


# ============ 全局实例 ============

_global_tracer: Optional[LinkTracer] = None


def get_tracer() -> LinkTracer:
    """获取全局追踪器实例"""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = LinkTracer()
    return _global_tracer


@contextmanager
def trace_operation(trace_id: str, operation_name: str, **tags):
    """便捷函数：追踪操作"""
    tracer = get_tracer()
    with tracer.trace_operation(trace_id, operation_name, **tags) as span:
        yield span


def start_trace(user_id: str, request_id: Optional[str] = None) -> str:
    """便捷函数：开始 Trace"""
    return get_tracer().start_trace(user_id, request_id)


def get_trace_timeline(trace_id: str) -> List[Dict]:
    """便捷函数：获取时间线"""
    return get_tracer().get_trace_timeline(trace_id)


# ============ 命令行工具 ============

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    tracer = LinkTracer()

    if len(sys.argv) < 2:
        print("Phoenix Core - 链路追踪工具")
        print()
        print("Usage:")
        print("  python3 link_tracing.py timeline <trace_id>    # 查看时间线")
        print("  python3 link_tracing.py tree <trace_id>        # 查看树形结构")
        print("  python3 link_tracing.py slow [threshold_ms]    # 查看慢调用")
        print("  python3 link_tracing.py export <trace_id>      # 导出 Trace")
        print()
        print("便捷函数:")
        print("  from phoenix_core import trace_operation, start_trace")
        sys.exit(0)

    command = sys.argv[1]

    if command == "timeline" and len(sys.argv) > 2:
        trace_id = sys.argv[2]
        tracer.print_trace_timeline(trace_id)

    elif command == "tree" and len(sys.argv) > 2:
        trace_id = sys.argv[2]
        tree = tracer.get_trace_tree(trace_id)
        print(json.dumps(tree, indent=2, ensure_ascii=False))

    elif command == "slow":
        threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 1000
        slow_traces = tracer.get_slow_traces(threshold)
        print(f"慢调用 Trace (>{threshold}ms):")
        for t in slow_traces:
            print(f"  {t['trace_id']}: {t['total_duration']:.2f}ms")

    elif command == "export" and len(sys.argv) > 2:
        trace_id = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else f"trace_{trace_id}.json"
        tracer.export_trace_to_json(trace_id, output_path)
        print(f"Trace 已导出到 {output_path}")

    else:
        print(f"未知命令：{command}")

    tracer.close()
