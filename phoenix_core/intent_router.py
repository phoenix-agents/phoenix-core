"""
Phoenix Core 意图路由模块

封装 phoenix_bot_init.intent_router，提供统一的意图路由接口。

支持：
1. 关键词匹配（快速路径）
2. 自定义路由规则
3. YAML 配置文件加载
"""

try:
    from phoenix_bot_init.intent_router import IntentRouter as BaseIntentRouter
except ImportError:
    # Fallback for direct module import
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "phoenix_bot_init"))
    from intent_router import IntentRouter as BaseIntentRouter

from typing import Dict, Optional


class IntentRouter:
    """
    意图路由器（Phoenix Core 封装版）

    用法：
        router = IntentRouter()
        target_bot = router.route("直播间现在多少人？")  # 返回 "场控"
    """

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化意图路由器

        Args:
            config_file: 自定义配置文件路径（可选）
                         默认：config/intent_routing.yaml
        """
        if config_file is None:
            config_file = "config/intent_routing.yaml"

        self._router = BaseIntentRouter(config_file)

    def route(self, message: str) -> str:
        """
        根据消息内容路由到合适的 Bot

        Args:
            message: 消息内容

        Returns:
            目标 Bot 名称
        """
        return self._router.route(message)

    def analyze(self, message: str) -> dict:
        """
        分析消息，返回详细的路由信息

        Args:
            message: 消息内容

        Returns:
            包含路由决策详情的字典
        """
        return self._router.analyze_message(message)

    def register_route(
        self,
        keywords: list,
        bot_name: str,
        priority: bool = True
    ):
        """
        注册自定义路由

        Args:
            keywords: 关键词列表
            bot_name: 目标 Bot 名称
            priority: 是否优先匹配
        """
        self._router.register_custom_route(keywords, bot_name, priority)

    def get_routes(self) -> list:
        """
        获取所有路由配置

        Returns:
            路由配置列表
        """
        return self._router.get_all_routes()

    @property
    def default_bot(self) -> str:
        """获取默认 Bot 名称"""
        return self._router._default_bot


# 全局单例
_global_router: Optional[IntentRouter] = None


def get_router() -> IntentRouter:
    """获取全局路由器实例"""
    global _global_router
    if _global_router is None:
        _global_router = IntentRouter()
    return _global_router


def route_message(message: str) -> str:
    """快捷函数：路由消息到合适的 Bot"""
    router = get_router()
    return router.route(message)


# 命令行测试
if __name__ == "__main__":
    import sys
    from pathlib import Path

    # 添加项目根目录到路径
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    router = IntentRouter()

    print("=" * 60)
    print("意图路由测试")
    print("=" * 60)

    # 测试消息
    test_messages = [
        "问问场控在不在",
        "让运营分析昨天的直播数据",
        "场控任务完成了吗",
        "你好",
        "直播间现在多少人？",
        "让剪辑做个视频",
        "客服处理一下这个粉丝的反馈",
        "做个海报宣传一下",
        "写个脚本策划活动",
    ]

    if len(sys.argv) > 1:
        test_messages = [sys.argv[1]]

    print("\n路由结果:")
    print("-" * 60)

    for msg in test_messages:
        result = router.analyze(msg)
        print(f"\n消息：{msg}")
        print(f"  目标 Bot: {result['target_bot']}")
        print(f"  匹配关键词：{result['matched_keywords']}")
        print(f"  路由类型：{result['route_type']}")
        print(f"  置信度：{result['confidence']:.2f}")

    # 显示所有路由
    print("\n" + "=" * 60)
    print("完整路由表:")
    print("-" * 60)

    for route in router.get_routes():
        print(f"  [{route['type']}] {route['keywords']} → {route['bot']}")
