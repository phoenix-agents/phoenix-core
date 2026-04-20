#!/usr/bin/env python3
"""
测试 Team Delegator v1.3 功能

测试用例:
1. TeamDelegator 初始化
2. TeamConfig 加载
3. delegate_to_team 基本流程
4. TeamDelegationPolicy 策略
5. register_team_as_skill
"""

import sys
sys.path.insert(0, '/Users/wangsai/phoenix-core')

from phoenix_core.team_delegator import (
    TeamDelegator,
    TeamConfig,
    TeamDelegationPolicy,
    TeamTask,
    get_team_delegator,
    register_team_as_skill
)
from datetime import datetime, timedelta
import asyncio


class MockGateway:
    """模拟 Gateway 用于测试"""

    def __init__(self):
        self.bot_responses = {}

    def set_bot_response(self, bot_id: str, response: str):
        """设置 Bot 响应"""
        self.bot_responses[bot_id] = response

    async def send_to_bot(self, bot_id: str, message: str, request_id: str) -> str:
        """模拟发送消息给 Bot"""
        if bot_id in self.bot_responses:
            await asyncio.sleep(0.01)
            return self.bot_responses[bot_id]
        await asyncio.sleep(0.01)
        return f"[模拟] {bot_id} 收到：{message[:30]}..."


def test_team_delegator_init():
    """测试 1: TeamDelegator 初始化"""
    print("\n=== 测试 1: TeamDelegator 初始化 ===")

    delegator = TeamDelegator(gateway=None, config_loader=None)

    assert "内容团队" in delegator.teams
    assert "制作团队" in delegator.teams
    assert "商务团队" in delegator.teams

    content_team = delegator.teams["内容团队"]
    assert content_team.bot_ids == ["运营", "场控", "编导"]
    assert content_team.policy == TeamDelegationPolicy.ALL_COMPLETED

    business_team = delegator.teams["商务团队"]
    assert business_team.bot_ids == ["客服", "渠道"]
    assert business_team.policy == TeamDelegationPolicy.ANY_COMPLETED

    print(f"✓ TeamDelegator 初始化通过，加载 {len(delegator.teams)} 个团队")
    return delegator


def test_get_team_bots():
    """测试 2: 获取团队成员"""
    print("\n=== 测试 2: 获取团队成员 ===")

    delegator = TeamDelegator()

    bots = delegator.get_team_bots("内容团队")
    assert bots == ["运营", "场控", "编导"]

    bots = delegator.get_team_bots("制作团队")
    assert bots == ["剪辑", "美工"]

    bots = delegator.get_team_bots("不存在的团队")
    assert bots == []

    print("✓ 获取团队成员通过")
    return delegator


def test_get_all_teams():
    """测试 3: 获取所有团队信息"""
    print("\n=== 测试 3: 获取所有团队信息 ===")

    delegator = TeamDelegator()
    teams = delegator.get_all_teams()

    assert len(teams) == 3

    for team in teams:
        assert "name" in team
        assert "bots" in team
        assert "description" in team
        assert "skills" in team
        assert "policy" in team

    print(f"✓ 获取所有团队信息通过：{[t['name'] for t in teams]}")


async def test_delegate_to_team_all_completed():
    """测试 4: ALL_COMPLETED 策略"""
    print("\n=== 测试 4: ALL_COMPLETED 策略 ===")

    gateway = MockGateway()
    gateway.set_bot_response("运营", "运营方案：活动策划包含互动环节")
    gateway.set_bot_response("场控", "场控方案：安排场控维护秩序")
    gateway.set_bot_response("编导", "编导方案：设计开场和流程脚本")

    delegator = TeamDelegator(gateway=gateway)

    result = await delegator.delegate_to_team(
        team_name="内容团队",
        brief="策划一个直播活动",
        policy=TeamDelegationPolicy.ALL_COMPLETED
    )

    assert result["success"] is True
    assert result["team_name"] == "内容团队"
    assert len(result["results"]) == 3
    assert len(result["errors"]) == 0
    assert result["policy_used"] == "all"
    assert "运营" in result["bots_responded"]
    assert "场控" in result["bots_responded"]
    assert "编导" in result["bots_responded"]

    print(f"✓ ALL_COMPLETED 策略通过：3 个 Bot 全部完成")


async def test_delegate_to_team_any_completed():
    """测试 5: ANY_COMPLETED 策略"""
    print("\n=== 测试 5: ANY_COMPLETED 策略 ===")

    gateway = MockGateway()
    gateway.set_bot_response("客服", "客服回复：收到客户问题")
    # 渠道不回复（模拟）

    delegator = TeamDelegator(gateway=gateway)

    result = await delegator.delegate_to_team(
        team_name="商务团队",
        brief="处理客户投诉",
        policy=TeamDelegationPolicy.ANY_COMPLETED
    )

    assert result["success"] is True
    assert result["team_name"] == "商务团队"
    assert len(result["results"]) >= 1
    assert result["policy_used"] == "any"

    print(f"✓ ANY_COMPLETED 策略通过：至少 1 个 Bot 完成")


async def test_delegate_with_context():
    """测试 6: 带上下文的团队委托"""
    print("\n=== 测试 6: 带上下文的团队委托 ===")

    gateway = MockGateway()
    delegator = TeamDelegator(gateway=gateway)

    result = await delegator.delegate_to_team(
        team_name="内容团队",
        brief="策划周年庆活动",
        context={
            "预算": "5 万元",
            "时间": "下个月 15 号",
            "主题": "科技未来风"
        }
    )

    assert result["success"] is True
    assert result["team_name"] == "内容团队"

    print("✓ 带上下文的团队委托通过")


def test_register_team_as_skill():
    """测试 7: 注册团队为技能"""
    print("\n=== 测试 7: 注册团队为技能 ===")

    gateway = MockGateway()
    delegator = TeamDelegator(gateway=gateway)

    # 注册团队技能
    success = register_team_as_skill(
        team_name="内容团队",
        coordinator_bot="小小谦",
        description="可以调用内容团队执行活动策划和直播运营",
        gateway=gateway
    )

    assert success is True

    # 验证技能已注册
    from phoenix_core.skill_registry import get_skill_registry
    registry = get_skill_registry()
    skills = registry.get_skills("小小谦")

    skill_names = [s["name"] for s in skills]
    assert "调用内容团队" in skill_names

    print(f"✓ 注册团队为技能通过：小小谦现在有 {len(skills)} 个技能")


def test_team_config_custom():
    """测试 8: 自定义团队配置"""
    print("\n=== 测试 8: 自定义团队配置 ===")

    custom_team = TeamConfig(
        team_name="AI 研发团队",
        bot_ids=["AI 研究员", "算法工程师", "数据科学家"],
        description="负责 AI 技术研发",
        skills=["模型训练", "算法优化", "数据分析"],
        policy=TeamDelegationPolicy.QUORUM,
        quorum_ratio=0.67,
        timeout_seconds=600
    )

    assert custom_team.team_name == "AI 研发团队"
    assert len(custom_team.bot_ids) == 3
    assert custom_team.policy == TeamDelegationPolicy.QUORUM
    assert custom_team.quorum_ratio == 0.67

    print("✓ 自定义团队配置通过")


async def main():
    print("=" * 60)
    print("Phoenix Core Team Delegator v1.3 功能测试")
    print("=" * 60)

    try:
        # 同步测试
        test_team_delegator_init()
        test_get_team_bots()
        test_get_all_teams()
        test_register_team_as_skill()
        test_team_config_custom()

        # 异步测试
        await test_delegate_to_team_all_completed()
        await test_delegate_to_team_any_completed()
        await test_delegate_with_context()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)

        # 打印团队列表
        delegator = TeamDelegator()
        print("\n可用团队:")
        for team in delegator.get_all_teams():
            print(f"  - {team['name']}: {team['bots']} ({team['policy']})")

    except AssertionError as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ 意外错误：{e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
