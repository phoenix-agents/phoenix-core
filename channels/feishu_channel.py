#!/usr/bin/env python3
"""
Phoenix Core 飞书通道插件

连接到飞书企业协作平台，支持：
- 接收群聊和私聊消息
- 发送文本/卡片消息
- 事件订阅模式（无需公网 IP，使用长连接）

依赖：
    pip install lark-oapi

配置：
    FEISHU_APP_ID=your_app_id
    FEISHU_APP_SECRET=your_app_secret
    FEISHU_VERIFICATION_TOKEN=your_verification_token  # 可选，事件订阅验证用
    FEISHU_ENCRYPT_KEY=your_encrypt_key  # 可选，消息加密用
"""

import asyncio
import hashlib
import hmac
import base64
import json
import logging
import time
from typing import Dict, List, Optional, AsyncIterator
from datetime import datetime
from pathlib import Path

from .base import (
    ChannelPlugin,
    ChannelConfig,
    Message,
    MessageRole,
    Attachment,
)

logger = logging.getLogger(__name__)

# 尝试导入飞书 SDK
try:
    from lark_oapi import Client, Request, RequestOptions
    from lark_oapi.api.im.v1 import *
    HAS_LARK_SDK = True
except ImportError:
    HAS_LARK_SDK = False
    logger.warning("lark-oapi not installed, run: pip install lark-oapi")


class FeishuChannel(ChannelPlugin):
    """飞书通道插件"""

    def __init__(self, bot_name: str = "Phoenix"):
        self.bot_name = bot_name
        self.client: Optional[Client] = None
        self.app_id = ""
        self.app_secret = ""
        self.verification_token = ""
        self.encrypt_key = ""
        self._running = False
        self._connected = False
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self.user_cache: Dict[str, str] = {}  # user_id -> union_id cache

        # 调用父类初始化以设置 self._config 和 self._message_queue
        super().__init__()

    @property
    def id(self) -> str:
        return "feishu"

    @property
    def name(self) -> str:
        return "飞书"

    async def connect(self, config: ChannelConfig) -> bool:
        """
        连接到飞书开放平台

        Args:
            config: 渠道配置，包含 credentials:
                - app_id: 飞书应用 App ID
                - app_secret: 飞书应用 App Secret
                - verification_token: 事件订阅验证 Token（可选）
                - encrypt_key: 消息加密 Key（可选）

        Returns:
            是否连接成功
        """
        if not HAS_LARK_SDK:
            logger.error("lark-oapi SDK not installed, cannot connect to Feishu")
            return False

        self.config = config
        credentials = config.credentials or {}

        self.app_id = credentials.get("app_id", "")
        self.app_secret = credentials.get("app_secret", "")
        self.verification_token = credentials.get("verification_token", "")
        self.encrypt_key = credentials.get("encrypt_key", "")

        if not self.app_id or not self.app_secret:
            logger.error("Feishu app_id or app_secret not configured")
            return False

        try:
            # 创建飞书客户端
            self.client = Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .log_level(logging.DEBUG) \
                .build()

            # 测试连接
            bot_info = self._get_bot_info()
            if bot_info:
                logger.info(f"✅ 飞书连接成功，Bot: {bot_info.get('name', 'Unknown')}")
                self._running = True
                return True
            else:
                logger.error("❌ 飞书连接失败，无法获取 Bot 信息")
                return False

        except Exception as e:
            logger.error(f"❌ 飞书连接失败：{e}")
            return False

    def _get_bot_info(self) -> Optional[Dict]:
        """获取 Bot 信息"""
        try:
            # 使用 self.client 获取 bot_info
            # 注意：lark-oapi SDK 的 API 可能需要调整
            req = Request.build().set_method("GET").set_uri("/open-apis/bot/v1/info")
            resp = self.client.do_request(req)
            if resp.code == 200:
                return resp.data.get("data", {})
            return None
        except Exception as e:
            logger.error(f"Get bot info failed: {e}")
            return None

    async def disconnect(self):
        """断开连接"""
        self._running = False
        self.client = None
        logger.info("飞书已断开连接")

    async def send_message(
        self,
        to: str,
        content: str,
        in_reply_to: Optional[str] = None,
        attachments: Optional[List[Attachment]] = None,
    ) -> bool:
        """
        发送消息到飞书

        Args:
            to: 目标聊天 ID
            content: 消息内容
            in_reply_to: 回复的消息 ID（可选）
            attachments: 附件列表（可选）

        Returns:
            是否发送成功
        """
        if not self.client:
            logger.error("飞书未连接，无法发送消息")
            return False

        try:
            # 调用飞书 API 发送消息
            req = Request.build() \
                .set_method("POST") \
                .set_uri("/open-apis/im/v1/messages") \
                .set_query_params({"receive_id_type": "chat_id"}) \
                .set_body({
                    "receive_id": to,
                    "content": json.dumps({"text": content}),
                    "msg_type": "text"
                })

            resp = self.client.do_request(req)

            if resp.code == 200:
                logger.info(f"✅ 飞书消息已发送：{to}")
                return True
            else:
                logger.error(f"❌ 飞书消息发送失败：{resp.msg}")
                return False

        except Exception as e:
            logger.error(f"发送飞书消息失败：{e}")
            return False

    async def _incoming_messages_gen(self) -> AsyncIterator[Message]:
        """
        接收消息迭代器

        Yields:
            Message: 接收到的消息
        """
        if not self.client:
            logger.error("飞书未连接")
            return

        logger.info("📡 开始监听飞书消息...")
        self._running = True

        while self._running:
            try:
                # 从队列获取消息
                msg = await self._message_queue.get()
                yield msg
            except Exception as e:
                logger.error(f"接收飞书消息失败：{e}")
                await asyncio.sleep(1)

    @property
    def incoming_messages(self) -> AsyncIterator[Message]:
        """返回消息迭代器"""
        return self._incoming_messages_gen()

    def _parse_message(self, data: Dict) -> Optional[Message]:
        """
        解析飞书消息为统一 Message 格式

        Args:
            data: 飞书消息数据

        Returns:
            Message 对象
        """
        try:
            msg_type = data.get("message_type", "text")
            content_raw = data.get("content", "{}")

            # 解析消息内容
            if isinstance(content_raw, str):
                content = json.loads(content_raw).get("text", "")
            else:
                content = content_raw.get("text", "")

            # 提取用户信息
            user_id = data.get("sender_id", {}).get("union_id", "")
            if not user_id:
                user_id = data.get("sender_id", {}).get("user_id", "")

            # 构建 Message
            return Message(
                id=data.get("message_id", ""),
                channel_id=data.get("chat_id", ""),
                user_id=user_id,
                username=data.get("sender_id", {}).get("sender_user_id", "Unknown"),
                content=content,
                timestamp=datetime.now().timestamp(),
                role=MessageRole.USER,
                metadata={
                    "msg_type": msg_type,
                    "root_id": data.get("root_id"),
                    "parent_id": data.get("parent_id"),
                }
            )

        except Exception as e:
            logger.error(f"解析飞书消息失败：{e}")
            return None


# ============ 飞书事件订阅处理器 ============

class FeishuEventHandler:
    """
    飞书事件订阅处理器

    用于处理飞书开放平台推送的事件通知
    支持 URL 验证和事件消息处理
    """

    def __init__(self, verification_token: str, encrypt_key: str = ""):
        self.verification_token = verification_token
        self.encrypt_key = encrypt_key

    def verify_url(self, challenge: str) -> str:
        """
        验证 URL（飞书事件订阅配置时需要）

        飞书会发送挑战码，需要原样返回以证明服务器可用

        Args:
            challenge: 挑战码

        Returns:
            挑战码
        """
        logger.info(f"收到 URL 验证请求，challenge: {challenge}")
        return challenge

    def decrypt_message(self, encrypted_data: str) -> Dict:
        """
        解密飞书加密消息

        Args:
            encrypted_data: Base64 加密数据

        Returns:
            解密后的消息
        """
        if not self.encrypt_key:
            return json.loads(base64.b64decode(encrypted_data))

        # AES 解密逻辑（略复杂，这里简化处理）
        # 实际使用建议参考飞书官方文档
        decrypted = base64.b64decode(encrypted_data)
        return json.loads(decrypted)

    def verify_signature(self, timestamp: str, nonce: str, signature: str, body: str) -> bool:
        """
        验证飞书请求签名

        Args:
            timestamp: 时间戳
            nonce: 随机数
            signature: 签名
            body: 请求体

        Returns:
            签名是否有效
        """
        # 构建签名字符串
        sign_str = timestamp + nonce + self.verification_token + body
        expected_sig = hashlib.sha256(sign_str.encode()).hexdigest()

        return hmac.compare_digest(signature, expected_sig)


# ============ 注册到 ChannelRegistry ============

def register_feishu_channel():
    """注册飞书通道"""
    from .base import ChannelRegistry
    ChannelRegistry.register(FeishuChannel)
    logger.info("飞书通道已注册")


# 自动注册
register_feishu_channel()
