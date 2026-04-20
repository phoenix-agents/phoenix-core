#!/usr/bin/env python3
"""
Feishu (Lark) Message Channel Adapter

飞书平台适配器，实现 MessageChannel 接口

依赖：
    pip install lark-oapi

配置：
    FEISHU_APP_ID=xxx
    FEISHU_APP_SECRET=xxx
    FEISHU_BOT_NAME=xxx
"""

import asyncio
import hashlib
import base64
import json
from typing import Callable, Optional
from dataclasses import dataclass

from phoenix_core.message_channel import MessageChannel, PlatformMessage


@dataclass
class FeishuConfig:
    """飞书配置"""
    app_id: str
    app_secret: str
    bot_name: str = "助手"
    verification_token: Optional[str] = None


class FeishuMessageChannel(MessageChannel):
    """
    飞书平台适配器
    """

    def __init__(self, config: FeishuConfig):
        self.config = config
        self._message_callback: Optional[Callable[[PlatformMessage], None]] = None
        self._client = None
        self._bot_id: Optional[str] = None

    @property
    def platform_name(self) -> str:
        return "feishu"

    async def connect(self) -> bool:
        """连接飞书"""
        try:
            # 懒加载 lark-oapi
            import lark.oapi as lark
            from lark.api import (
                Lark,
                LarkConfig,
                api,
                LarkLogger,
            )

            # 创建飞书客户端
            self._client = Lark(
                app_id=self.config.app_id,
                app_secret=self.config.app_secret,
                log_level="info",
            )

            # 获取 Bot ID
            bot_info = await self._client.bots.v3.info()
            self._bot_id = bot_info.data.id
            print(f"飞书已连接：Bot={bot_info.data.name} (ID: {self._bot_id})")

            # 注册事件处理器（接收消息）
            # 飞书使用 HTTP Event Subscription 推送消息
            # 这里使用轮询方式作为简化实现
            asyncio.create_task(self._poll_messages())

            return True

        except ImportError:
            print("lark-oapi 未安装，运行：pip install lark-oapi")
            return False
        except Exception as e:
            print(f"飞书连接失败：{e}")
            return False

    async def _poll_messages(self):
        """轮询获取消息（简化实现，生产环境应使用 Event Subscription）"""
        import time
        last_cursor = "0"

        while True:
            try:
                await asyncio.sleep(2)  # 每 2 秒轮询一次

                # 获取 Bot 收到的消息
                # 注意：这里需要根据飞书 API 实际接口调整
                # 以下仅为示例代码

            except Exception as e:
                print(f"飞书轮询失败：{e}")

    async def send_message(self, target: str, content: str, **kwargs) -> bool:
        """发送消息到飞书"""
        if not self._client:
            return False

        try:
            # 飞书发送消息 API
            # target 可以是 open_chat_id 或 user_id

            request = api.im.v1.message.create().request(
                receive_id=target,
                msg_type="text",
                content=json.dumps({"text": content}),
            )

            response = await self._client.do_async(request)

            if response.code == 0:
                return True
            else:
                print(f"飞书发送失败：{response.msg}")
                return False

        except Exception as e:
            print(f"飞书发送错误：{e}")
            return False

    async def on_message(self, callback: Callable[[PlatformMessage], None]) -> None:
        """注册消息回调"""
        self._message_callback = callback

    async def disconnect(self) -> None:
        """Disconnected"""
        self._client = None

    def _parse_feishu_message(self, data: dict) -> PlatformMessage:
        """解析飞书消息为 PlatformMessage"""
        sender = data.get("sender", {})
        message = data.get("message", {})

        content = message.get("content", "")
        # 飞书文本消息内容是 JSON 字符串
        if content.startswith("{"):
            try:
                content = json.loads(content).get("text", "")
            except:
                pass

        return PlatformMessage(
            platform="feishu",
            content=content,
            author_id=sender.get("sender_id", {}).get("union_id", ""),
            author_name=sender.get("sender_name", "Unknown"),
            channel_id=message.get("chat_id", ""),
            timestamp=float(message.get("create_time", 0)) / 1000,
            is_mention=self._bot_id in content if self._bot_id else False,
            raw=data
        )


# ==================== 便捷创建函数 ====================

def create_feishu_channel(
    app_id: str = None,
    app_secret: str = None,
    bot_name: str = None,
    **kwargs
) -> Optional[FeishuMessageChannel]:
    """
    创建飞书 Channel

    优先级：
    1. 参数传入
    2. 环境变量
    """
    import os

    app_id = app_id or os.environ.get("FEISHU_APP_ID")
    app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")
    bot_name = bot_name or os.environ.get("FEISHU_BOT_NAME", "助手")

    if not app_id or not app_secret:
        print("错误：缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET")
        return None

    config = FeishuConfig(
        app_id=app_id,
        app_secret=app_secret,
        bot_name=bot_name,
    )

    return FeishuMessageChannel(config)
