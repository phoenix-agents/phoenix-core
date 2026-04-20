"""
意图识别模块 - Intent Recognition

将用户自然语言转换为结构化意图对象。

支持两种模式：
1. 关键词匹配（快速路径）- 用于常见场景
2. LLM 意图识别（复杂场景）- 用于模糊语义
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Intent:
    """结构化意图对象"""

    intent_type: str      # inquiry | task | status | chat | forward
    target_bot: str       # 场控 | 运营 | 剪辑 | ...
    content: str          # 原始内容
    entities: dict = field(default_factory=dict)  # 提取的实体
    confidence: float = 1.0  # 置信度 0-1

    # 元数据
    raw_message: str = ""  # 原始消息
    request_id: str = ""   # 请求 ID（可选，由后续生成）


class IntentRecognizer:
    """
    意图识别器

    优先级：
    1. 关键词匹配（快速路径）
    2. LLM 意图识别（复杂场景）
    3. 默认路由（小小谦）
    """

    # 意图类型定义
    INTENT_INQUIRY = "inquiry"   # 询问
    INTENT_TASK = "task"         # 任务
    INTENT_STATUS = "status"     # 状态查询
    INTENT_CHAT = "chat"         # 闲聊
    INTENT_FORWARD = "forward"   # 转发

    # 关键词映射表（按优先级排序）
    KEYWORD_MAP = [
        # 场控 - 直播间管理
        (["直播间", "在线", "人数", "场控", "灯光", "设备", "检查"], "场控", INTENT_INQUIRY),
        (["调整", "检查", "准备", "开播", "下播"], "场控", INTENT_TASK),

        # 运营 - 数据分析
        (["数据", "分析", "运营", "粉丝", "增长", "报告", "统计"], "运营", INTENT_INQUIRY),
        (["做活动", "策划", "涨粉", "引流"], "运营", INTENT_TASK),

        # 美工 - 设计
        (["设计", "海报", "封面", "图片", "美工", "视觉"], "美工", INTENT_INQUIRY),
        (["做个海报", "设计封面", "P 图"], "美工", INTENT_TASK),

        # 编导 - 内容策划
        (["脚本", "策划", "编导", "文案", "内容", "话题"], "编导", INTENT_INQUIRY),
        (["写脚本", "策划活动", "想话题"], "编导", INTENT_TASK),

        # 剪辑 - 视频制作
        (["剪辑", "视频", "切片", "剪辑师", "高光"], "剪辑", INTENT_INQUIRY),
        (["剪视频", "做切片", "剪辑"], "剪辑", INTENT_TASK),

        # 客服 - 粉丝运营
        (["客服", "粉丝", "私域", "用户", "问题", "反馈"], "客服", INTENT_INQUIRY),
        (["联系粉丝", "回复用户", "处理投诉"], "客服", INTENT_TASK),

        # 渠道 - 分发
        (["渠道", "分发", "平台", "合作", "商务"], "渠道", INTENT_INQUIRY),
        (["发视频", "分发内容", "联系合作"], "渠道", INTENT_TASK),
    ]

    # 状态查询关键词
    STATUS_KEYWORDS = ["完成了吗", "进度", "状态", "怎么样", "好了吗", "完成没"]

    # 闲聊关键词
    CHAT_KEYWORDS = ["你好", "好", "在吗", "在不在", "hi", "hello", "hey"]

    # Bot 名称映射（处理别名）
    BOT_ALIAS_MAP = {
        "视频剪辑": "剪辑",
        "剪辑师": "剪辑",
        "设计": "美工",
        "视觉": "美工",
        "内容": "编导",
        "策划": "编导",
        "商务": "渠道",
        "分发": "渠道",
    }

    def __init__(self, default_bot: str = "小小谦"):
        """
        初始化意图识别器

        Args:
            default_bot: 默认路由目标（当无法识别时）
        """
        self.default_bot = default_bot
        self.custom_routes = []  # 自定义路由规则

    def recognize(self, message: str) -> Intent:
        """
        识别用户消息的意图

        Args:
            message: 用户消息（自然语言）

        Returns:
            Intent 对象
        """
        # 1. 尝试关键词匹配（快速路径）
        intent = self._keyword_match(message)
        if intent and intent.confidence >= 0.8:
            intent.raw_message = message
            return intent

        # 2. 尝试自定义路由
        intent = self._custom_route_match(message)
        if intent:
            intent.raw_message = message
            return intent

        # 3. 尝试 LLM 意图识别（复杂场景）
        intent = self._llm_recognize(message)
        if intent and intent.confidence >= 0.6:
            intent.raw_message = message
            return intent

        # 4. 默认路由到小小谦
        return Intent(
            intent_type=self.INTENT_CHAT,
            target_bot=self.default_bot,
            content=message,
            confidence=0.5,
            raw_message=message
        )

    def _keyword_match(self, message: str) -> Optional[Intent]:
        """关键词匹配（快速路径）"""
        message_lower = message.lower()

        # 检查是否是状态查询
        is_status_query = any(kw in message_lower for kw in self.STATUS_KEYWORDS)

        # 检查是否是闲聊
        is_chat = any(kw in message_lower for kw in self.CHAT_KEYWORDS)

        # 遍历关键词映射表
        for keywords, bot_name, intent_type in self.KEYWORD_MAP:
            if any(kw in message_lower for kw in keywords):
                # 处理状态查询
                if is_status_query:
                    return Intent(
                        intent_type=self.INTENT_STATUS,
                        target_bot=bot_name,
                        content=message,
                        confidence=0.9
                    )

                # 确定意图类型
                if is_chat and intent_type == self.INTENT_INQUIRY:
                    # "场控在不在" -> 询问
                    return Intent(
                        intent_type=self.INTENT_INQUIRY,
                        target_bot=bot_name,
                        content=message,
                        confidence=0.9
                    )

                return Intent(
                    intent_type=intent_type,
                    target_bot=self._normalize_bot_name(bot_name),
                    content=message,
                    confidence=0.9
                )

        # 没有找到匹配的关键词
        return None

    def _custom_route_match(self, message: str) -> Optional[Intent]:
        """自定义路由匹配"""
        for route_func in self.custom_routes:
            intent = route_func(message)
            if intent:
                return intent
        return None

    def _llm_recognize(self, message: str) -> Optional[Intent]:
        """
        LLM 意图识别（复杂场景）

        TODO: 接入 LLM 进行语义分析
        当前返回 None，使用默认路由
        """
        # 未来实现示例：
        # response = llm.chat(f"""
        # 分析以下消息的意图：
        # - 消息：{message}
        #
        # 返回 JSON：
        # {{
        #   "intent_type": "inquiry|task|status|chat|forward",
        #   "target_bot": "场控 | 运营 | ...",
        #   "entities": {{}},
        #   "confidence": 0.0-1.0
        # }}
        # """)
        #
        # return Intent(...)

        return None

    def _normalize_bot_name(self, bot_name: str) -> str:
        """标准化 Bot 名称（处理别名）"""
        return self.BOT_ALIAS_MAP.get(bot_name, bot_name)

    def register_custom_route(self, route_func):
        """
        注册自定义路由规则

        Args:
            route_func: 函数，接收 message str，返回 Intent 或 None
        """
        self.custom_routes.append(route_func)

    def analyze_message(self, message: str) -> dict:
        """
        分析消息并返回详细结果（用于调试）

        Args:
            message: 用户消息

        Returns:
            包含分析结果的字典
        """
        intent = self.recognize(message)

        return {
            "intent_type": intent.intent_type,
            "target_bot": intent.target_bot,
            "content": intent.content,
            "confidence": intent.confidence,
            "raw_message": intent.raw_message,
            "entities": intent.entities,
        }


# 快捷函数
def recognize_intent(message: str, default_bot: str = "小小谦") -> Intent:
    """快捷函数：识别消息意图"""
    recognizer = IntentRecognizer(default_bot=default_bot)
    return recognizer.recognize(message)


# 命令行测试
if __name__ == "__main__":
    import sys

    test_messages = [
        "问问场控在不在",
        "让运营分析昨天的直播数据",
        "场控任务完成了吗",
        "你好",
        "直播间现在多少人？",
        "让剪辑做个视频",
        "客服处理一下这个粉丝的反馈",
    ]

    if len(sys.argv) > 1:
        test_messages = [sys.argv[1]]

    recognizer = IntentRecognizer()

    print("=" * 60)
    print("意图识别测试")
    print("=" * 60)

    for msg in test_messages:
        intent = recognizer.recognize(msg)
        print(f"\n消息：{msg}")
        print(f"  意图类型：{intent.intent_type}")
        print(f"  目标 Bot: {intent.target_bot}")
        print(f"  置信度：{intent.confidence}")
        print(f"  内容：{intent.content}")
