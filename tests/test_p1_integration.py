#!/usr/bin/env python3
"""
Phoenix Core - P1 功能集成测试

测试链路追踪、进度汇报、审计日志的集成工作
"""

import asyncio
import logging
from phoenix_core import CoreBrain, BrainConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


async def test_integration():
    """测试 P1 功能集成"""
    print("=" * 60)
    print("Phoenix Core - P1 功能集成测试")
    print("=" * 60)

    brain = CoreBrain(BrainConfig(debug=True))

    # 测试 1: 简单闲聊
    print("\n[测试 1] 简单闲聊")
    response = await brain.process("你好", user_id="test_user")
    print(f"  回复：{response.message}")
    print(f"  请求 ID: {response.request_id}")

    # 测试 2: 查询任务 (带链路追踪)
    print("\n[测试 2] 查询任务")
    response = await brain.process("帮我查订单 #12345", user_id="test_user")
    print(f"  回复：{response.message}")
    print(f"  请求 ID: {response.request_id}")

    # 查看链路追踪
    trace_id = response.request_id
    timeline = brain.tracer.get_trace_timeline(trace_id)
    print(f"  链路追踪 ({len(timeline)} 个 Span):")
    for span in timeline:
        print(f"    - {span['operation']}: {span['duration_ms']:.1f}ms")

    # 测试 3: 查看审计日志
    print(f"\n[测试 3] 审计日志查询")
    entries = brain.audit_logger.query_by_request(response.request_id)
    print(f"  审计日志 ({len(entries)} 条):")
    for entry in entries:
        print(f"    [{entry.entry_type}] {entry.content[:50]}")

    # 测试 4: 进度汇报 (模拟多子任务)
    print(f"\n[测试 4] 进度汇报")
    progress = brain.progress_reporter.create_progress(
        task_id="test-progress-001",
        user_id="test_user",
        description="测试多子任务",
        subtasks=["sub-0", "sub-1", "sub-2"]
    )
    print(f"  初始进度：{progress.total_percent}%")

    brain.progress_reporter.update_progress(
        task_id="test-progress-001",
        sub_task_id="sub-0",
        status="completed",
        progress_percent=100.0,
        description="子任务 1 完成"
    )
    print(f"  完成 sub-0 后：{progress.total_percent:.1f}%")

    brain.progress_reporter.update_progress(
        task_id="test-progress-001",
        sub_task_id="sub-1",
        status="running",
        progress_percent=50.0,
        description="子任务 2 进行中"
    )
    print(f"  更新 sub-1 后：{progress.total_percent:.1f}%")

    # 打印进度文本
    print(f"\n  进度文本:")
    print("  " + "\n  ".join(brain.progress_reporter.format_progress_text("test-progress-001").split("\n")))

    # 关闭
    await brain.shutdown()

    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_integration())
