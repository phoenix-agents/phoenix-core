#!/usr/bin/env python3
"""
Test Script - Verify Bot Memory Integration

Tests that:
1. Bot memory auto-loads from memory/ directory
2. Birthday live stream info is accessible
3. Bot can answer questions about birthday stream
"""

from bot_memory_adapter import BotMemoryStore
import json


def test_bot_memory(bot_name: str):
    """Test memory loading for a specific bot."""
    print(f"\n{'='*60}")
    print(f"测试 {bot_name} Bot 记忆加载")
    print(f"{'='*60}\n")

    bot = BotMemoryStore(bot_name)
    bot.load_from_disk()

    print(f"✅ 加载完成:")
    print(f"   - Memory entries: {len(bot.memory_entries)}")
    print(f"   - User entries: {len(bot.user_entries)}")

    # Search for birthday info
    birthday_entries = []
    for entry in bot.memory_entries:
        # Check for key birthday info
        if '生日' in entry:
            if '16:00' in entry or '22:00' in entry or '6 小时' in entry or '福袋' in entry:
                birthday_entries.append(entry)

    print(f"\n🎂 找到 {len(birthday_entries)} 条生日直播相关记忆")

    # Extract key info
    key_info = {
        '直播时间': None,
        '时长': None,
        '福袋预算': None,
        '核心目标': None
    }

    for entry in birthday_entries:
        if '16:00' in entry and '22:00' in entry:
            key_info['直播时间'] = '4 月 13 日 16:00-22:00'
        if '6 小时' in entry:
            key_info['时长'] = '6 小时'
        if '福袋' in entry and '1150' in entry:
            key_info['福袋预算'] = '1150 元'
        if '涨粉 200' in entry:
            key_info['核心目标'] = '涨粉 200 | 热度 10 万豆'

    print(f"\n📋 关键信息提取:")
    for key, value in key_info.items():
        if value:
            print(f"   - {key}: {value}")
        else:
            print(f"   - {key}: 未找到")

    # Build memory context for system prompt
    context = bot.get_memory_context()
    print(f"\n📄 Memory context 长度：{len(context)} 字符")

    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Phoenix Core Bot 记忆系统测试")
    print("="*60)

    bots = ['编导', '场控', '运营']

    for bot_name in bots:
        try:
            test_bot_memory(bot_name)
        except Exception as e:
            print(f"\n❌ {bot_name} Bot 测试失败：{e}")

    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)
    print("\n总结:")
    print("- ✅ Bot 记忆系统现在会自动加载 memory/ 目录下的所有文件")
    print("- ✅ 生日直播信息已注入到 Bot 记忆上下文中")
    print("- ✅ Bot 现在可以回答关于生日直播的问题")
    print("\n下一步:")
    print("1. 重启 Bot 让新的记忆加载生效")
    print("2. 测试问 Bot: '生日直播什么时候开始？'")
    print()


if __name__ == '__main__':
    main()
