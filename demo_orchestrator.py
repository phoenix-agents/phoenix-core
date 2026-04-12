#!/usr/bin/env python3
"""
Phoenix Core Multi-Agent Orchestrator Demo

演示多 Agent 协作流程
"""

import sys
import time
sys.path.insert(0, str(Path(__file__).parent))

from multi_agent_orchestrator import (
    AgentOrchestrator, AgentRole, TaskPriority,
    assign_task, get_status
)
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


def demo_live_scenario():
    """演示真实直播场景"""
    print("\n" + "=" * 70)
    print("🎯 Phoenix Core 多 Agent 协作演示 - 直播场景")
    print("=" * 70)

    orch = AgentOrchestrator()
    orch.start()

    # 场景 1: 直播前准备
    print("\n📋 场景 1: 直播前准备")
    print("-" * 70)

    tasks = []
    tasks.append(orch.assign_task(
        AgentRole.DIRECTOR,
        "策划今晚直播内容和互动环节",
        TaskPriority.URGENT,
        {"deadline": "20:00"}
    ))
    print(f"✅ 任务分配给编导：策划今晚直播内容")

    tasks.append(orch.assign_task(
        AgentRole.DESIGNER,
        "设计今晚直播封面图",
        TaskPriority.HIGH
    ))
    print(f"✅ 任务分配给美工：设计直播封面")

    tasks.append(orch.assign_task(
        AgentRole.OPERATOR,
        "分析上周直播数据报告",
        TaskPriority.NORMAL
    ))
    print(f"✅ 任务分配给运营：分析上周数据")

    tasks.append(orch.assign_task(
        AgentRole.CONTROLLER,
        "准备观众互动游戏方案",
        TaskPriority.NORMAL
    ))
    print(f"✅ 任务分配给场控：准备互动游戏")

    # 等待任务执行
    print("\n⏳ 等待任务执行...")
    time.sleep(3)

    # 场景 2: 直播中协作
    print("\n🎬 场景 2: 直播中协作")
    print("-" * 70)

    tasks.append(orch.assign_task(
        AgentRole.CONTROLLER,
        "欢迎 VIP 观众进入直播间",
        TaskPriority.HIGH
    ))
    print(f"✅ 任务分配给场控：欢迎 VIP 观众")

    tasks.append(orch.assign_task(
        AgentRole.SUPPORT,
        "解答粉丝关于直播时间的问题",
        TaskPriority.NORMAL
    ))
    print(f"✅ 任务分配给客服：解答粉丝问题")

    tasks.append(orch.assign_task(
        AgentRole.OPERATOR,
        "监控当前在线人数和互动率",
        TaskPriority.HIGH
    ))
    print(f"✅ 任务分配给运营：监控实时数据")

    # 等待任务执行
    print("\n⏳ 等待任务执行...")
    time.sleep(3)

    # 场景 3: 直播后复盘
    print("\n📊 场景 3: 直播后复盘")
    print("-" * 70)

    tasks.append(orch.assign_task(
        AgentRole.EDITOR,
        "剪辑昨晚直播高光片段",
        TaskPriority.HIGH
    ))
    print(f"✅ 任务分配给剪辑：制作高光片段")

    tasks.append(orch.assign_task(
        AgentRole.OPERATOR,
        "生成昨晚直播复盘报告",
        TaskPriority.NORMAL
    ))
    print(f"✅ 任务分配给运营：生成复盘报告")

    tasks.append(orch.assign_task(
        AgentRole.DIRECTOR,
        "根据复盘提出改进方案",
        TaskPriority.NORMAL
    ))
    print(f"✅ 任务分配给编导：提出改进方案")

    # 等待所有任务完成
    print("\n⏳ 等待所有任务完成...")
    time.sleep(5)

    # 最终状态
    print("\n" + "=" * 70)
    print("📈 最终 Agent 状态")
    print("=" * 70)

    status = orch.get_all_agents_status()
    for role, agent in status['agents'].items():
        emoji = {"编导": "📝", "剪辑": "🎬", "美工": "🎨", "场控": "🎮",
                 "客服": "💬", "运营": "📊", "渠道": "🤝", "小小谦": "🤖"}.get(role, "👤")
        print(f"{emoji} {role}: {agent['task_count']} 个任务完成")

    print(f"\n总完成任务数：{status['completed_count']}")

    orch.stop()

    print("\n" + "=" * 70)
    print("✅ 演示完成!")
    print("=" * 70)
    print("\n💡 访问 UI Dashboard: http://localhost:4320")
    print()


if __name__ == "__main__":
    demo_live_scenario()
