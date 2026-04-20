#!/usr/bin/env python3
"""
测试 Handoff v1.3 增强功能

测试用例:
1. HandoffPayload 序列化和反序列化
2. create_handoff 生成协议消息
3. parse_handoff 解析协议消息
4. 上下文截断功能
5. SubTask 带 Handoff 上下文
"""

import sys
sys.path.insert(0, '/Users/wangsai/phoenix-core')

from phoenix_core.protocol_v2 import (
    HandoffPayload,
    create_handoff,
    parse_handoff,
    ProtocolMessage,
    PROTOCOL_VERSION
)
from phoenix_core.task_dispatcher import SubTask
from datetime import datetime, timedelta


def test_handoff_payload_serialization():
    """测试 1: HandoffPayload 序列化和反序列化"""
    print("\n=== 测试 1: HandoffPayload 序列化 ===")

    payload = HandoffPayload(
        from_bot="小小谦",
        to_bot="运营",
        original_request="帮我策划一个直播活动，预算 1 万元，时间下周末",
        handoff_reason="运营 Bot 更擅长活动策划",
        essential_entities={
            "budget": "10000",
            "deadline": "下周末",
            "event_type": "直播"
        },
        conversation_context=[
            "用户：帮我策划一个直播活动",
            "小小谦：好的，请问有什么预算和时间要求吗？",
            "用户：预算 1 万元，时间下周末"
        ],
        constraints={"budget": 10000, "timeframe": "next_week"},
        expectations="需要包含互动环节和奖品设计",
        return_channel="小小谦",
        deadline_seconds=300
    )

    # 序列化
    json_str = payload.to_json()
    print(f"序列化 JSON: {json_str[:100]}...")

    # 反序列化
    payload2 = HandoffPayload.from_json(json_str)
    assert payload2.from_bot == "小小谦"
    assert payload2.to_bot == "运营"
    assert payload2.essential_entities["budget"] == "10000"
    print("✓ 序列化和反序列化测试通过")

    return payload


def test_create_handoff_message():
    """测试 2: create_handoff 生成协议消息"""
    print("\n=== 测试 2: create_handoff 生成协议消息 ===")

    payload = HandoffPayload(
        from_bot="小小谦",
        to_bot="运营",
        original_request="帮我策划直播",
        handoff_reason="运营更专业",
        essential_entities={"budget": "10000"},
        conversation_context=["用户：策划直播", "小小谦：收到"],
        return_channel="小小谦"
    )

    message = create_handoff(
        target_bot="123456789012345678",  # Discord ID 格式
        request_id="user_123-20260420-001",
        sub_task_id="main",
        sender="小小谦",
        from_bot=payload.from_bot,
        to_bot=payload.to_bot,
        original_request=payload.original_request,
        handoff_reason=payload.handoff_reason,
        essential_entities=payload.essential_entities,
        conversation_context=payload.conversation_context,
        return_channel=payload.return_channel
    )

    print(f"生成的协议消息：{message[:200]}...")
    assert "[HANDOFF]" in message
    assert "小小谦" in message
    assert "运营" in message
    print("✓ create_handoff 测试通过")

    return message


def test_parse_handoff_message():
    """测试 3: parse_handoff 解析协议消息"""
    print("\n=== 测试 3: parse_handoff 解析协议消息 ===")

    # 先创建一个消息（target_bot 必须是数字格式，模拟 Discord ID）
    msg_str = create_handoff(
        target_bot="123456789012345678",  # Discord ID 格式
        request_id="user_123-20260420-001",
        sub_task_id="main",
        sender="小小谦",
        from_bot="小小谦",
        to_bot="运营",
        original_request="帮我策划直播",
        handoff_reason="运营更专业",
        essential_entities={"budget": "10000", "event_type": "游戏直播"},
        conversation_context=["用户：策划直播", "小小谦：收到"],
        constraints={"max_cost": 15000},
        expectations="需要有趣",
        return_channel="小小谦",
        deadline_seconds=600
    )

    # 解析消息
    proto_msg = ProtocolMessage.parse(msg_str)
    assert proto_msg is not None, f"解析失败：{msg_str}"
    payload = parse_handoff(proto_msg)

    assert payload is not None
    assert payload.from_bot == "小小谦"
    assert payload.to_bot == "运营"
    assert payload.essential_entities["budget"] == "10000"
    assert payload.essential_entities["event_type"] == "游戏直播"
    assert payload.constraints["max_cost"] == 15000
    assert payload.expectations == "需要有趣"
    assert payload.deadline_seconds == 600

    print(f"解析结果：from={payload.from_bot}, to={payload.to_bot}, entities={payload.essential_entities}")
    print("✓ parse_handoff 测试通过")


def test_context_truncation():
    """测试 4: 上下文截断功能"""
    print("\n=== 测试 4: 上下文截断功能 ===")

    # 创建超长上下文
    long_context = [f"对话第{i}轮：这是一段比较长的对话内容" * 10 for i in range(20)]

    payload = HandoffPayload(
        from_bot="测试 Bot",
        to_bot="接收 Bot",
        original_request="测试",
        handoff_reason="测试",
        conversation_context=long_context
    )

    print(f"截断前：{len(payload.conversation_context)} 条，总字符={sum(len(c) for c in payload.conversation_context)}")

    # 截断
    payload.truncate_context(max_messages=5, max_chars=500)

    print(f"截断后：{len(payload.conversation_context)} 条，总字符={sum(len(c) for c in payload.conversation_context)}")

    assert len(payload.conversation_context) <= 5
    assert sum(len(c) for c in payload.conversation_context) <= 500
    print("✓ 上下文截断测试通过")


def test_subtask_with_handoff():
    """测试 5: SubTask 带 Handoff 上下文"""
    print("\n=== 测试 5: SubTask 带 Handoff 上下文 ===")

    # 创建 HandoffPayload
    handoff = HandoffPayload(
        from_bot="小小谦",
        to_bot="运营",
        original_request="策划直播活动",
        handoff_reason="运营专业",
        essential_entities={"budget": "10000"},
        return_channel="小小谦"
    )

    # 创建简单子任务
    task1 = SubTask.simple(
        bot_id="运营",
        prompt="请策划一个直播活动",
        deadline=datetime.now() + timedelta(minutes=10)
    )
    assert task1.handoff_context is None
    print(f"简单子任务：bot={task1.bot_id}, handoff=None")

    # 创建带 Handoff 的子任务
    task2 = SubTask.with_handoff(
        bot_id="运营",
        prompt="请执行交接的任务",
        context=handoff,
        deadline=datetime.now() + timedelta(minutes=10),
        priority=3
    )
    assert task2.handoff_context is not None
    assert task2.handoff_context.from_bot == "小小谦"
    assert task2.priority == 3
    print(f"Handoff 子任务：bot={task2.bot_id}, from={task2.handoff_context.from_bot}, priority={task2.priority}")

    print("✓ SubTask 带 Handoff 上下文测试通过")


def test_backward_compatibility():
    """测试 6: 向后兼容性（旧格式消息）"""
    print("\n=== 测试 6: 向后兼容性测试 ===")

    # 模拟旧格式消息（没有 JSON payload）- target_bot 使用数字格式
    old_format_msg = "<@123456789> [HANDOFF|1.2|req_001|main|小小谦] [HANDOFF] 请处理这个任务 | 原因：你很专业"

    proto_msg = ProtocolMessage.parse(old_format_msg)
    assert proto_msg is not None, f"旧格式消息解析失败：{old_format_msg}"
    payload = parse_handoff(proto_msg)

    # 应该降级处理，返回基本 payload
    assert payload is not None
    assert "请处理这个任务" in payload.original_request

    print(f"旧格式消息解析结果：{payload.original_request[:50]}...")
    print("✓ 向后兼容性测试通过")


def main():
    print("=" * 60)
    print("Phoenix Core Handoff v1.3 功能测试")
    print("=" * 60)

    try:
        # 运行所有测试
        test_handoff_payload_serialization()
        test_create_handoff_message()
        test_parse_handoff_message()
        test_context_truncation()
        test_subtask_with_handoff()
        test_backward_compatibility()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)

        # 打印协议版本
        print(f"\n当前协议版本：{PROTOCOL_VERSION}")

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
    exit(main())
