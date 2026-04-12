#!/usr/bin/env python3
"""
Test script for Multi-Agent Orchestrator
"""

import sys
sys.path.insert(0, str(Path(__file__).parent))

from multi_agent_orchestrator import (
    AgentOrchestrator, AgentRole, TaskPriority,
    get_orchestrator, assign_task, get_status
)
import time


def test_orchestrator_init():
    print("=" * 60)
    print("Testing Orchestrator Initialization")
    print("=" * 60)

    orch = AgentOrchestrator()

    print(f"\nInitialized {len(orch.agents)} agents:")
    for role, agent in orch.agents.items():
        print(f"  - {agent.name} ({role.value}): {agent.model}")

    print("\n" + "=" * 60)
    print("Initialization test complete!")
    print("=" * 60)


def test_task_assignment():
    print("\n" + "=" * 60)
    print("Testing Task Assignment")
    print("=" * 60)

    orch = get_orchestrator()
    orch.start()

    # Assign tasks to different agents
    print("\n[Assigning tasks...]")

    task1 = orch.assign_task(
        AgentRole.DIRECTOR,
        "策划本周直播内容主题",
        TaskPriority.HIGH,
        {"deadline": "2026-04-12"}
    )
    print(f"Task 1 assigned: {task1}")

    task2 = orch.assign_task(
        AgentRole.EDITOR,
        "剪辑昨晚直播高光片段",
        TaskPriority.NORMAL,
        {"source": "recording_20260409.mp4"}
    )
    print(f"Task 2 assigned: {task2}")

    task3 = orch.assign_task(
        AgentRole.OPERATOR,
        "分析上周直播数据",
        TaskPriority.NORMAL
    )
    print(f"Task 3 assigned: {task3}")

    # Wait for tasks to complete
    print("\n[Waiting for tasks to complete...]")
    time.sleep(3)

    # Check status
    print("\n[Agent Status:]")
    status = orch.get_all_agents_status()
    for role, agent_data in status['agents'].items():
        print(f"  {role}: {agent_data['status']} (tasks: {agent_data['task_count']})")

    orch.stop()
    print("\n" + "=" * 60)
    print("Task assignment test complete!")
    print("=" * 60)


def test_convenience_functions():
    print("\n" + "=" * 60)
    print("Testing Convenience Functions")
    print("=" * 60)

    # Use convenience functions
    print("\n[Using convenience functions...]")

    task_id = assign_task("场控", "欢迎新进入直播间的观众", 2)
    print(f"Assigned task: {task_id}")

    status = get_status()
    print(f"\nQueue size: {status['queue_size']}")
    print(f"Completed: {status['completed_count']}")

    print("\n" + "=" * 60)
    print("Convenience functions test complete!")
    print("=" * 60)


def test_dependency_handling():
    print("\n" + "=" * 60)
    print("Testing Task Dependencies")
    print("=" * 60)

    orch = AgentOrchestrator()

    # Create parent task
    parent_id = orch.assign_task(
        AgentRole.DIRECTOR,
        "确定直播主题",
        TaskPriority.HIGH
    )
    print(f"Parent task: {parent_id}")

    # Create child task with dependency
    child_id = orch.assign_task(
        AgentRole.EDITOR,
        "根据主题制作预告片",
        TaskPriority.NORMAL,
        dependencies=[parent_id]
    )
    print(f"Child task (depends on {parent_id}): {child_id}")

    # Check queue
    queue = orch.get_task_queue()
    print(f"\nTask queue: {len(queue)} tasks")
    for t in queue:
        print(f"  - {t['task_id']}: {t['status']} (deps: {t['dependencies']})")

    print("\n" + "=" * 60)
    print("Dependency handling test complete!")
    print("=" * 60)


def test_priority_ordering():
    print("\n" + "=" * 60)
    print("Testing Priority Ordering")
    print("=" * 60)

    orch = AgentOrchestrator()

    # Add tasks in random priority order
    orch.assign_task(AgentRole.SUPPORT, "低优先级任务", TaskPriority.LOW)
    orch.assign_task(AgentRole.OPERATOR, "紧急任务！", TaskPriority.URGENT)
    orch.assign_task(AgentRole.DESIGNER, "普通任务", TaskPriority.NORMAL)
    orch.assign_task(AgentRole.CHANNEL, "高优先级任务", TaskPriority.HIGH)

    # Check queue order
    queue = orch.get_task_queue()
    print("\nTask queue (should be ordered by priority):")
    for i, t in enumerate(queue):
        print(f"  {i+1}. [{t['priority']}] {t['description']}")

    print("\n" + "=" * 60)
    print("Priority ordering test complete!")
    print("=" * 60)


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    test_orchestrator_init()
    test_task_assignment()
    test_convenience_functions()
    test_dependency_handling()
    test_priority_ordering()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
