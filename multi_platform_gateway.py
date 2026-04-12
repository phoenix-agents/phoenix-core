#!/usr/bin/env python3
"""
Multi-Platform Gateway - 多平台网关支持

Phoenix Core Phoenix v2.0 扩展模块

支持平台:
1. Discord (已有 phoenix_gateway.py)
2. Telegram Bot API
3. Slack Bot API
4. Webhook (通用 HTTP 接口)

Usage:
    from multi_platform_gateway import TelegramGateway, SlackGateway

    # Telegram
    tg = TelegramGateway(bot_token="xxx")
    tg.start_polling()

    # Slack
    sg = SlackGateway(bot_token="xxx", signing_secret="xxx")
    sg.start()
"""

import json
import logging
import os
import threading
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from abc import ABC, abstractmethod
import hashlib
import hmac
import base64

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
GATEWAY_DIR = Path(__file__).parent / "gateways")
GATEWAY_DIR.mkdir(parents=True, exist_ok=True)


class Message:
    """统一消息格式"""

    def __init__(self, platform: str, chat_id: str, user_id: str,
                 content: str, message_id: str = None,
                 timestamp: str = None, raw_data: Dict = None):
        self.platform = platform
        self.chat_id = chat_id
        self.user_id = user_id
        self.content = content
        self.message_id = message_id or datetime.now().isoformat()
        self.timestamp = timestamp or datetime.now().isoformat()
        self.raw_data = raw_data or {}

    def to_dict(self) -> Dict:
        return {
            "platform": self.platform,
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "content": self.content,
            "message_id": self.message_id,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Message":
        return cls(
            platform=data.get("platform", "unknown"),
            chat_id=data.get("chat_id", ""),
            user_id=data.get("user_id", ""),
            content=data.get("content", ""),
            message_id=data.get("message_id"),
            timestamp=data.get("timestamp")
        )


class BaseGateway(ABC):
    """网关基类"""

    def __init__(self, platform_name: str, config: Dict = None):
        self.platform_name = platform_name
        self.config = config or {}
        self.running = False
        self.message_handlers: List[Callable] = []
        self._threads: List[threading.Thread] = []

    @abstractmethod
    def start(self):
        """启动网关"""
        pass

    @abstractmethod
    def stop(self):
        """停止网关"""
        pass

    @abstractmethod
    def send_message(self, chat_id: str, content: str) -> bool:
        """发送消息"""
        pass

    @abstractmethod
    def send_typing(self, chat_id: str) -> bool:
        """发送正在输入状态"""
        pass

    def register_handler(self, handler: Callable):
        """注册消息处理器"""
        self.message_handlers.append(handler)
        logger.info(f"Registered message handler for {self.platform_name}")

    def _dispatch_message(self, message: Message):
        """分发消息到所有处理器"""
        for handler in self.message_handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"Message handler error: {e}")

    def _log_gateway_event(self, event_type: str, details: str):
        """记录网关节件到日志"""
        log_file = GATEWAY_DIR / f"{self.platform_name}_gateway.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n## [{datetime.now().strftime('%H:%M:%S')}] {event_type}\n\n")
            f.write(f"{details}\n\n---\n")


class TelegramGateway(BaseGateway):
    """
    Telegram Bot 网关

    配置:
    - bot_token: Telegram Bot Token
    - webhook_url: Webhook URL (可选，用于 webhook 模式)
    - use_webhook: 是否使用 webhook 模式 (默认 False)
    """

    def __init__(self, bot_token: str = None, webhook_url: str = None,
                 use_webhook: bool = False, config: Dict = None):
        super().__init__("Telegram", config)
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.webhook_url = webhook_url
        self.use_webhook = use_webhook
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"

        if not self.bot_token:
            logger.error("Telegram Bot Token is required")
            raise ValueError("TELEGRAM_BOT_TOKEN not set")

        self._last_update_id = 0

    def _api_request(self, method: str, params: Dict = None) -> Optional[Dict]:
        """调用 Telegram API"""
        url = f"{self.api_base}/{method}"
        data = None

        if params:
            data = urllib.parse.urlencode(params).encode('utf-8')

        req = urllib.request.Request(url, data=data)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result if result.get("ok") else None
        except Exception as e:
            logger.error(f"Telegram API error: {e}")
            return None

    def start(self):
        """启动网关"""
        if self.running:
            logger.warning("Gateway already running")
            return

        self.running = True

        if self.use_webhook and self.webhook_url:
            # Webhook 模式
            self._setup_webhook()
            self._log_gateway_event("START", f"Webhook mode: {self.webhook_url}")
        else:
            # 轮询模式
            self._start_polling()
            self._log_gateway_event("START", "Polling mode")

        logger.info(f"Telegram Gateway started on {self.platform_name}")

    def _setup_webhook(self):
        """设置 Webhook"""
        result = self._api_request("setWebhook", {"url": self.webhook_url})
        if result:
            logger.info("Webhook set successfully")
        else:
            logger.error("Failed to set webhook")

    def _start_polling(self):
        """启动轮询"""
        def poll_loop():
            logger.info("Starting polling loop...")
            while self.running:
                try:
                    updates = self._get_updates(offset=self._last_update_id + 1, timeout=30)
                    if updates:
                        for update in updates:
                            self._last_update_id = update.get("update_id", 0)
                            self._process_update(update)
                except Exception as e:
                    logger.error(f"Polling error: {e}")
                    import time
                    time.sleep(5)

        thread = threading.Thread(target=poll_loop, daemon=True)
        thread.start()
        self._threads.append(thread)

    def _get_updates(self, offset: int = None, timeout: int = 30) -> List[Dict]:
        """获取更新"""
        params = {"timeout": timeout}
        if offset:
            params["offset"] = offset

        result = self._api_request("getUpdates", params)
        return result.get("result", []) if result else []

    def _process_update(self, update: Dict):
        """处理更新"""
        # 处理消息
        if "message" in update:
            msg = update["message"]
            chat = msg.get("chat", {})
            user = msg.get("from", {})

            message = Message(
                platform="Telegram",
                chat_id=str(chat.get("id", "")),
                user_id=str(user.get("id", "")),
                content=msg.get("text", ""),
                message_id=str(msg.get("message_id", "")),
                timestamp=datetime.fromtimestamp(msg.get("date", 0)).isoformat(),
                raw_data=msg
            )
            self._dispatch_message(message)
            self._log_gateway_event("MESSAGE", f"From {user.get('username', user.get('id'))}: {msg.get('text', '')[:50]}")

        # 处理回调查询
        elif "callback_query" in update:
            callback = update["callback_query"]
            self._handle_callback(callback)

    def _handle_callback(self, callback: Dict):
        """处理回调查询"""
        message = callback.get("message", {})
        data = callback.get("data", "")

        # 解析回调数据
        try:
            callback_data = json.loads(data)
        except:
            callback_data = {"action": data}

        logger.info(f"Callback received: {callback_data}")

    def stop(self):
        """停止网关"""
        self.running = False

        if self.use_webhook:
            self._api_request("deleteWebhook")

        # 等待线程结束
        for thread in self._threads:
            thread.join(timeout=5)

        self._threads.clear()
        self._log_gateway_event("STOP", "Gateway stopped")
        logger.info("Telegram Gateway stopped")

    def send_message(self, chat_id: str, content: str,
                     parse_mode: str = "Markdown") -> bool:
        """发送消息"""
        params = {
            "chat_id": chat_id,
            "text": content,
            "parse_mode": parse_mode
        }
        result = self._api_request("sendMessage", params)
        return result is not None

    def send_typing(self, chat_id: str) -> bool:
        """发送正在输入状态"""
        result = self._api_request("sendChatAction", {
            "chat_id": chat_id,
            "action": "typing"
        })
        return result is not None

    def edit_message(self, chat_id: str, message_id: str,
                     new_content: str) -> bool:
        """编辑消息"""
        params = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": new_content,
            "parse_mode": "Markdown"
        }
        result = self._api_request("editMessageText", params)
        return result is not None

    def delete_message(self, chat_id: str, message_id: str) -> bool:
        """删除消息"""
        result = self._api_request("deleteMessage", {
            "chat_id": chat_id,
            "message_id": message_id
        })
        return result is not None

    def get_bot_info(self) -> Optional[Dict]:
        """获取 Bot 信息"""
        result = self._api_request("getMe")
        return result.get("result") if result else None


class SlackGateway(BaseGateway):
    """
    Slack Bot 网关

    配置:
    - bot_token: Slack Bot Token (xoxb-...)
    - signing_secret: Slack Signing Secret
    - app_token: Socket Mode App Token (可选)
    """

    def __init__(self, bot_token: str = None, signing_secret: str = None,
                 app_token: str = None, config: Dict = None):
        super().__init__("Slack", config)
        self.bot_token = bot_token or os.environ.get("SLACK_BOT_TOKEN", "")
        self.signing_secret = signing_secret or os.environ.get("SLACK_SIGNING_SECRET", "")
        self.app_token = app_token or os.environ.get("SLACK_APP_TOKEN", "")

        if not self.bot_token:
            logger.error("Slack Bot Token is required")
            raise ValueError("SLACK_BOT_TOKEN not set")

        self.api_base = "https://slack.com/api"
        self._rtm_socket = None

    def _api_request(self, method: str, params: Dict = None) -> Optional[Dict]:
        """调用 Slack API"""
        url = f"{self.api_base}/{method}"
        data = None
        headers = {"Authorization": f"Bearer {self.bot_token}"}

        if params:
            data = urllib.parse.urlencode(params).encode('utf-8')

        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result if result.get("ok") else None
        except Exception as e:
            logger.error(f"Slack API error: {e}")
            return None

    def verify_signature(self, payload: str, signature: str,
                         timestamp: str) -> bool:
        """验证 Slack 请求签名"""
        if not self.signing_secret:
            return False

        sig_basestring = f"v0:{timestamp}:{payload}"
        my_signature = "v0=" + hmac.new(
            self.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(my_signature, signature)

    def start(self):
        """启动网关"""
        if self.running:
            logger.warning("Gateway already running")
            return

        self.running = True

        # 使用 Socket Mode 或 Events API
        if self.app_token:
            self._start_socket_mode()
        else:
            self._log_gateway_event("START", "Events API mode")
            logger.info("Slack Gateway started (Events API mode)")

    def _start_socket_mode(self):
        """启动 Socket Mode"""
        def socket_loop():
            logger.info("Starting Socket Mode loop...")
            # 简化实现，实际应该使用 slack_bolt 库
            while self.running:
                import time
                time.sleep(1)

        thread = threading.Thread(target=socket_loop, daemon=True)
        thread.start()
        self._threads.append(thread)
        self._log_gateway_event("START", "Socket Mode")

    def stop(self):
        """停止网关"""
        self.running = False

        for thread in self._threads:
            thread.join(timeout=5)

        self._threads.clear()
        self._log_gateway_event("STOP", "Gateway stopped")
        logger.info("Slack Gateway stopped")

    def send_message(self, channel_id: str, content: str) -> bool:
        """发送消息"""
        params = {
            "channel": channel_id,
            "text": content
        }
        result = self._api_request("chat.postMessage", params)
        return result is not None

    def send_typing(self, channel_id: str) -> bool:
        """发送正在输入状态 (Slack 不支持原生 typing，用空消息模拟)"""
        params = {
            "channel": channel_id,
            "text": "_typing..._"
        }
        result = self._api_request("chat.postMessage", params)
        return result is not None

    def send_block_message(self, channel_id: str, blocks: List[Dict]) -> bool:
        """发送 Blocks 消息"""
        params = {
            "channel": channel_id,
            "blocks": json.dumps(blocks)
        }
        result = self._api_request("chat.postMessage", params)
        return result is not None

    def get_bot_info(self) -> Optional[Dict]:
        """获取 Bot 信息"""
        result = self._api_request("auth.test")
        return result.get("user") if result else None

    def get_channel_members(self, channel_id: str) -> List[str]:
        """获取频道成员"""
        members = []
        cursor = None

        while True:
            params = {"channel": channel_id, "limit": 200}
            if cursor:
                params["cursor"] = cursor

            result = self._api_request("conversations.members", params)
            if result:
                members.extend(result.get("members", []))
                cursor = result.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
            else:
                break

        return members


class WebhookGateway(BaseGateway):
    """
    通用 Webhook 网关

    支持接收和发送 HTTP Webhook 消息
    适用于自定义集成或内部系统

    配置:
    - port: HTTP 服务器端口 (默认 8080)
    - secret: Webhook 验证密钥
    - endpoint: 外部 Webhook URL (用于发送)
    """

    def __init__(self, port: int = 8080, secret: str = None,
                 endpoint: str = None, config: Dict = None):
        super().__init__("Webhook", config)
        self.port = port
        self.secret = secret or os.environ.get("WEBHOOK_SECRET", "default_secret")
        self.endpoint = endpoint
        self._server = None

    def start(self):
        """启动 HTTP 服务器"""
        if self.running:
            logger.warning("Gateway already running")
            return

        self.running = True
        self._start_server()
        self._log_gateway_event("START", f"Listening on port {self.port}")
        logger.info(f"Webhook Gateway started on port {self.port}")

    def _start_server(self):
        """启动 HTTP 服务器"""
        from http.server import HTTPServer, BaseHTTPRequestHandler

        gateway = self

        class WebhookHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')

                # 验证签名
                signature = self.headers.get('X-Webhook-Signature', '')
                if not gateway._verify_signature(body, signature):
                    self.send_response(401)
                    self.end_headers()
                    return

                # 解析消息
                try:
                    data = json.loads(body)
                    message = Message(
                        platform="Webhook",
                        chat_id=data.get("chat_id", "default"),
                        user_id=data.get("user_id", "webhook"),
                        content=data.get("content", ""),
                        message_id=data.get("message_id"),
                        raw_data=data
                    )
                    gateway._dispatch_message(message)
                    gateway._log_gateway_event("WEBHOOK", f"Received: {message.content[:50]}")

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status": "ok"}')
                except Exception as e:
                    logger.error(f"Webhook error: {e}")
                    self.send_response(400)
                    self.end_headers()

            def log_message(self, format, *args):
                logger.debug(f"Webhook: {args[0]}")

        self._server = HTTPServer(('0.0.0.0', self.port), WebhookHandler)
        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()
        self._threads.append(thread)

    def _verify_signature(self, payload: str, signature: str) -> bool:
        """验证 Webhook 签名"""
        expected = hmac.new(
            self.secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def stop(self):
        """停止服务器"""
        self.running = False

        if self._server:
            self._server.shutdown()

        for thread in self._threads:
            thread.join(timeout=5)

        self._threads.clear()
        self._log_gateway_event("STOP", "Gateway stopped")
        logger.info("Webhook Gateway stopped")

    def send_message(self, chat_id: str, content: str) -> bool:
        """发送消息到外部端点"""
        if not self.endpoint:
            logger.warning("No endpoint configured")
            return False

        payload = {
            "chat_id": chat_id,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }

        body = json.dumps(payload).encode('utf-8')
        signature = hmac.new(
            self.secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        req = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'X-Webhook-Signature': signature
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False

    def send_typing(self, chat_id: str) -> bool:
        """Webhook 不支持 typing 状态"""
        return True


# 工厂函数
def create_gateway(platform: str, **kwargs) -> BaseGateway:
    """创建网关实例"""
    platforms = {
        "telegram": TelegramGateway,
        "slack": SlackGateway,
        "webhook": WebhookGateway
    }

    platform_lower = platform.lower()
    if platform_lower not in platforms:
        raise ValueError(f"Unknown platform: {platform}. Supported: {list(platforms.keys())}")

    return platforms[platform_lower](**kwargs)


if __name__ == "__main__":
    import sys

    print("Multi-Platform Gateway - 多平台网关支持")
    print("\nSupported platforms:")
    print("  - Telegram: Telegram Bot API")
    print("  - Slack: Slack Bot API")
    print("  - Webhook: Generic HTTP Webhook")
    print("\nUsage:")
    print("  from multi_platform_gateway import TelegramGateway, SlackGateway, WebhookGateway")
    print()

    # 简单测试
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        platform = sys.argv[2] if len(sys.argv) > 2 else "webhook"

        print(f"\nTesting {platform} gateway...")

        if platform == "webhook":
            gateway = WebhookGateway(port=8080)
            gateway.register_handler(lambda msg: print(f"Received: {msg.content}"))
            gateway.start()
            print(f"Webhook server running on http://localhost:8080")
            print("Press Ctrl+C to stop")

            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                gateway.stop()
                print("\nGateway stopped")

        elif platform == "telegram":
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            if not token:
                print("Set TELEGRAM_BOT_TOKEN environment variable")
                sys.exit(1)

            gateway = TelegramGateway(bot_token=token)
            gateway.register_handler(lambda msg: print(f"Telegram message: {msg.content}"))
            gateway.start()
            print("Telegram Gateway running")

            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                gateway.stop()

        elif platform == "slack":
            token = os.environ.get("SLACK_BOT_TOKEN")
            if not token:
                print("Set SLACK_BOT_TOKEN environment variable")
                sys.exit(1)

            gateway = SlackGateway(bot_token=token)
            gateway.register_handler(lambda msg: print(f"Slack message: {msg.content}"))
            gateway.start()
            print("Slack Gateway running")

            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                gateway.stop()
