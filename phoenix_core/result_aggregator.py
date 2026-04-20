"""
结果汇总模块 - Result Aggregator

将 Worker Bot 的协议回复转换为用户友好的自然语言格式。

核心理念：
- 用户不关心协议细节，只关心结果
- 不同 Bot 有不同的回复风格
- 保持友好、简洁、有信息量
"""

from dataclasses import dataclass
from typing import Optional, Dict, Callable


@dataclass
class AggregatedResult:
    """汇总结果对象"""

    bot_name: str           # Bot 名称
    original_response: str  # 原始协议回复
    user_message: str       # 用户友好的消息
    is_termination: bool    # 是否终止消息


class ResultAggregator:
    """
    结果汇总器

    负责：
    1. 解析协议回复
    2. 转换为自然语言
    3. 个性化风格处理
    """

    # Bot 个性化回复模板
    BOT_TEMPLATES = {
        "场控": {
            "CONFIRM": [
                "场控已上线待命，状态全开。Qian Zong，请指示下一步。😎",
                "场控 ready！直播间一切正常，请指示。💪",
                "场控报到！刚完成例行检查，随时待命。✨",
            ],
            "REPORT": [
                "场控报告：{content}",
                "直播间监控：{content}",
                "场控实时数据：{content}",
            ],
            "DONE": [
                "场控任务已完成：{content}",
                "执行完毕：{content}",
                "场控报告：任务成功完成，{content}",
            ],
            "FAIL": [
                "场控报告：任务受阻，{content}",
                "场控警报：遇到问题，{content}",
            ],
        },
        "运营": {
            "CONFIRM": [
                "运营已收到，正在分析数据...📊",
                "运营在线，开始处理任务。📈",
            ],
            "REPORT": [
                "运营数据报告：{content}",
                "数据分析中：{content}",
            ],
            "DONE": [
                "运营已完成分析：{content}",
                "数据报告已生成：{content}",
            ],
            "FAIL": [
                "运营报告：数据异常，{content}",
            ],
        },
        "剪辑": {
            "CONFIRM": [
                "剪辑就位，准备开始制作。🎬",
                "剪辑收到，开始处理视频。✂️",
            ],
            "REPORT": [
                "剪辑进度：{content}",
                "视频制作中：{content}",
            ],
            "DONE": [
                "剪辑完成：{content}",
                "视频已交付：{content}",
            ],
            "FAIL": [
                "剪辑报告：制作失败，{content}",
            ],
        },
        "客服": {
            "CONFIRM": [
                "客服已收到，马上处理~💕",
                "客服在线，为粉丝服务！😊",
            ],
            "REPORT": [
                "客服反馈：{content}",
                "粉丝运营报告：{content}",
            ],
            "DONE": [
                "客服已完成：{content}",
                "已回复粉丝：{content}",
            ],
            "FAIL": [
                "客服报告：{content}",
            ],
        },
        "美工": {
            "CONFIRM": [
                "美工已就位，准备设计。🎨",
                "美工收到，开始创作~✨",
            ],
            "DONE": [
                "美工完成：{content}",
                "设计已交付：{content}",
            ],
        },
        "编导": {
            "CONFIRM": [
                "编导已收到，开始构思。📝",
                "编导在线，策划中~💡",
            ],
            "DONE": [
                "编导完成：{content}",
                "脚本已写好：{content}",
            ],
        },
        "渠道": {
            "CONFIRM": [
                "渠道已收到，开始分发。🚀",
                "渠道在线，处理中~📤",
            ],
            "DONE": [
                "渠道完成：{content}",
                "内容已分发：{content}",
            ],
        },
    }

    # 默认模板（未知 Bot）
    DEFAULT_TEMPLATES = {
        "CONFIRM": ["{bot_name}已收到，正在处理..."],
        "REPORT": ["{bot_name}报告：{content}"],
        "DONE": ["{bot_name}已完成：{content}"],
        "FAIL": ["{bot_name}报告：{content}"],
    }

    def __init__(self, custom_templates: Optional[Dict] = None):
        """
        初始化结果汇总器

        Args:
            custom_templates: 自定义模板（可选）
        """
        self._templates = {**self.BOT_TEMPLATES}
        if custom_templates:
            self._templates.update(custom_templates)

    def aggregate(
        self,
        protocol_response: str,
        bot_name: Optional[str] = None
    ) -> Optional[AggregatedResult]:
        """
        汇总协议回复

        Args:
            protocol_response: 协议格式回复
            bot_name: Bot 名称（可选，可从协议中提取）

        Returns:
            AggregatedResult 对象，解析失败返回 None
        """
        # 解析协议（使用本地导入避免循环依赖）
        import importlib
        protocol_parser = importlib.import_module("phoenix_core.protocol_parser")
        ProtocolParser = protocol_parser.ProtocolParser

        parser = ProtocolParser()
        parsed = parser.parse(protocol_response)

        if not parsed:
            return None

        # 提取 Bot 名称
        if not bot_name:
            bot_name = parsed.sender

        # 转换为自然语言
        user_message = self._to_natural_language(
            bot_name=bot_name,
            msg_type=parsed.message_type,
            content=parsed.content
        )

        return AggregatedResult(
            bot_name=bot_name,
            original_response=protocol_response,
            user_message=user_message,
            is_termination=parsed.is_termination
        )

    def _to_natural_language(
        self,
        bot_name: str,
        msg_type: str,
        content: str
    ) -> str:
        """
        转换为自然语言

        Args:
            bot_name: Bot 名称
            msg_type: 消息类型
            content: 原始内容

        Returns:
            用户友好的消息
        """
        import random

        # 获取该 Bot 的模板
        templates = self._templates.get(bot_name, self.DEFAULT_TEMPLATES)

        # 获取对应类型的模板
        msg_templates = templates.get(msg_type, self.DEFAULT_TEMPLATES.get(msg_type, ["{content}"]))

        # 随机选择一个模板
        template = random.choice(msg_templates)

        # 填充内容
        try:
            result = template.format(bot_name=bot_name, content=content)
        except KeyError:
            # 模板格式错误，直接返回内容
            result = content

        return result

    def format_status(
        self,
        bot_name: str,
        status: str,
        details: str
    ) -> str:
        """
        格式化状态查询结果

        Args:
            bot_name: Bot 名称
            status: 状态（pending/confirmed/done/failed）
            details: 详细信息

        Returns:
            用户友好的状态消息
        """
        status_messages = {
            "pending": f"{bot_name}正在处理中，请稍候...",
            "confirmed": f"{bot_name}已确认，正在执行：{details}",
            "done": f"{bot_name}已完成：{details}",
            "failed": f"{bot_name}任务失败：{details}",
            "timeout": f"{bot_name}响应超时，请稍后重试",
        }

        return status_messages.get(status, details)

    def register_template(
        self,
        bot_name: str,
        msg_type: str,
        templates: list
    ):
        """
        注册自定义模板

        Args:
            bot_name: Bot 名称
            msg_type: 消息类型
            templates: 模板列表
        """
        if bot_name not in self._templates:
            self._templates[bot_name] = {}

        self._templates[bot_name][msg_type] = templates


class SimpleAggregator(ResultAggregator):
    """
    简化版汇总器（用于快速测试）

    不做风格转换，直接返回内容
    """

    def _to_natural_language(
        self,
        bot_name: str,
        msg_type: str,
        content: str
    ) -> str:
        return content


# 快捷函数
def aggregate_response(protocol_response: str) -> Optional[str]:
    """快捷函数：汇总协议回复"""
    aggregator = ResultAggregator()
    result = aggregator.aggregate(protocol_response)
    return result.user_message if result else None


# 命令行测试
if __name__ == "__main__":
    import sys
    from pathlib import Path

    # 添加项目根目录到路径
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    aggregator = ResultAggregator()

    print("=" * 60)
    print("结果汇总测试")
    print("=" * 60)

    # 测试协议回复转换
    test_cases = [
        (
            "<@1483335704590155786> [CONFIRM|20260416-001|场控] 在的！刚完成灯光检查，随时待命~",
            "场控"
        ),
        (
            "<@1483335704590155786> [DONE|20260416-002|运营] 数据报告已生成：累计观看 5000 人",
            "运营"
        ),
        (
            "<@1483335704590155786> [DONE|20260416-003|剪辑] 视频已交付，共 3 个切片",
            "剪辑"
        ),
        (
            "<@1483335704590155786> [REPORT|20260416-004|场控] 当前直播间 520 人，弹幕密度 300 条/分钟",
            "场控"
        ),
    ]

    print("\n1. 协议回复转换:")
    for protocol, bot_name in test_cases:
        result = aggregator.aggregate(protocol, bot_name)
        if result:
            print(f"\n   原始：{result.original_response[:50]}...")
            print(f"   用户消息：{result.user_message}")
            print(f"   终止消息：{result.is_termination}")

    # 测试状态格式化
    print("\n2. 状态格式化:")
    status_cases = [
        ("场控", "pending", ""),
        ("运营", "confirmed", "数据分析中..."),
        ("剪辑", "done", "3 个视频已上传"),
        ("客服", "timeout", ""),
    ]

    for bot, status, details in status_cases:
        msg = aggregator.format_status(bot, status, details)
        print(f"   {bot} - {status}: {msg}")

    # 测试简化版
    print("\n3. 简化版汇总器:")
    simple = SimpleAggregator()
    result = simple.aggregate(
        "<@1483335704590155786> [DONE|20260416-005|剪辑] 视频已交付"
    )
    print(f"   原始：{result.original_response}")
    print(f"   用户消息：{result.user_message}（直接返回内容）")
