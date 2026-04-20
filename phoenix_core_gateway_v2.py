#!/usr/bin/env python3
"""
Phoenix Core Gateway v2 - 框架核心

职责：
1. 管理所有ChannelConnection器 (ChannelPlugin)
2. Message路由到正确的 Agent
3. 会话管理
4. Skill执行
5. 记忆管理
6. 共享上下文管理

Usage:
    python3 phoenix_core_gateway_v2.py --workspace ./phx-workspace
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

# Add Phoenix Core to path
sys.path.insert(0, str(Path(__file__).parent))

from channels.base import ChannelPlugin, Message, ChannelConfig
from channels.manager import ChannelManager

# Phoenix Core Heartbeat
from phoenix_core import write_heartbeat

# Phoenix Core 记忆数据库
try:
    from phoenix_core import save_conversation
    MEMORY_DB_AVAILABLE = True
except ImportError:
    MEMORY_DB_AVAILABLE = False
    save_conversation = None

# Phoenix Core v5.0 编排器模块 (仅小小谦使用)
try:
    from phoenix_core import Orchestrator, OrchestratorConfig
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    Orchestrator = None
    OrchestratorConfig = None

# Phoenix Core P1 功能模块 (AuditLog、链路Trace、Progress汇报)
try:
    from phoenix_core import (
        get_audit_logger,
        log_message,
        log_operation,
        log_error,
        get_tracer,
        start_trace,
        get_progress_reporter,
        create_progress,
        update_progress,
    )
    P1_FEATURES_AVAILABLE = True
except ImportError:
    P1_FEATURES_AVAILABLE = False

# Phoenix Core 配置加载器
try:
    from config_loader import get_config
    CONFIG_LOADER_AVAILABLE = True
except ImportError:
    CONFIG_LOADER_AVAILABLE = False
    get_config = None

# Phoenix Core RemoteDebug集成 (Phase 3)
try:
    from phoenix_core.remote_integration import get_debugger, send_log, start_remote_debug
    REMOTE_DEBUG_AVAILABLE = True
except ImportError:
    REMOTE_DEBUG_AVAILABLE = False
    get_debugger = None
    send_log = lambda level, msg: None
    start_remote_debug = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class PhoenixCoreGateway:
    """
    Phoenix Core Gateway - 统一控制平面

    所有业务逻辑都在这一层，Channel层只负责平台 API 对接

    支持两种模式：
    1. ChannelManager 模式：管理多个 ChannelPlugin（多频道/多 bot）
    2. MessageChannel 模式：注入单个 MessageChannel（平台无关）
    """

    def __init__(self, workspace: str = None, channel: "MessageChannel" = None, bot_name: str = None):
        """
        初始化 Phoenix Core Gateway

        Args:
            workspace: Workspace路径
            channel: 平台适配器（可选）
            bot_name: Bot 名称（可选，优先于从 workspace 推导）
        """
        # 如果未指定 bot_name，从 workspace 推导
        self.workspace = Path(workspace) if workspace else Path.cwd() / "phx-workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Bot name: 优先使用传入参数，其次从 workspace 推导
        if bot_name:
            self.bot_name = bot_name
        else:
            self.bot_name = self.workspace.name if self.workspace else "unknown"

        # 从 config_loader 加载 Bot 配置（如果可用）
        self.bot_config = None
        if CONFIG_LOADER_AVAILABLE and get_config:
            config_loader = get_config()
            self.bot_config = config_loader.get_bot_by_name(self.bot_name)
            if self.bot_config:
                logger.info(f"Loaded Bot config：{self.bot_name}")
                # 如果 Bot 配置中有 workspace，更新 workspace 路径
                if workspace is None and self.bot_config.get("workspace"):
                    self.workspace = Path(self.bot_config["workspace"])
                    self.workspace.mkdir(parents=True, exist_ok=True)
                    logger.info(f"使用配置中的 workspace: {self.workspace}")
        else:
            logger.warning("Config loader not available，Using default config")

        # Load .env file from workspace directory
        from dotenv import load_dotenv
        env_file = self.workspace / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            logger.info(f"Loaded .env from {env_file}")
        else:
            logger.warning(f".env file not found: {env_file}")

        # ====== 平台适配器注入（可选） ======
        # 如果传入了 MessageChannel 实例，使用平台无关模式
        self._platform_channel = channel
        if self._platform_channel:
            logger.info(f"使用平台适配器：{self._platform_channel.platform_name}")
            # 注册Message回调
            asyncio.create_task(self._register_platform_message_callback())
        # ====================================

        # Shared memory directory (all bots share this)
        self.shared_memory_dir = self.workspace / "shared_memory"
        self.shared_memory_dir.mkdir(parents=True, exist_ok=True)

        # Load configuration
        self.config = self._load_config()

        # ========== Coordinator自动识别（新增） ==========
        # 加载所有 Bot 配置，识别Coordinator
        self._all_bots = []
        self._coordinator_name = None
        self._is_coordinator = False

        if CONFIG_LOADER_AVAILABLE and get_config:
            config_loader = get_config()
            self._all_bots = config_loader.get_enabled_bots()

            # 策略 1: 查找 role="controller" 的 Bot
            for bot in self._all_bots:
                if bot.get("role") == "controller":
                    self._coordinator_name = bot.get("name")
                    break

            # 策略 2: 如果没有 controller，选择第一个 Bot
            if not self._coordinator_name and self._all_bots:
                self._coordinator_name = self._all_bots[0].get("name")

            # 判断当前 Bot 是否是Coordinator
            if self._coordinator_name and self.bot_name == self._coordinator_name:
                self._is_coordinator = True
                logger.info(f"自动识别：当前 Bot '{self.bot_name}' 是Coordinator")
                logger.info(f"系统共有 {len(self._all_bots)} 个 Bot：{[b['name'] for b in self._all_bots]}")
            else:
                logger.info(f"自动识别：Coordinator是 '{self._coordinator_name}'，当前 Bot '{self.bot_name}' 是 Worker")
        else:
            logger.warning("Config loader not available，Coordinator识别已跳过")
        # =========================================

        # Initialize channel manager (仅在未注入 MessageChannel 时使用)
        if not self._platform_channel:
            self.channel_manager = ChannelManager(
                workspace=str(self.workspace),
                message_callback=self._handle_message_from_channel,
                bot_name=self.bot_name
            )
        else:
            self.channel_manager = None

        # Sessions and agents
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.agents = self.config.get("agents", {}).get("list", [])

        # Dedup cache - Layer 1: Message deduplication
        self._seen_messages: dict[str, float] = {}
        self._SEEN_TTL = 300  # 5 minutes
        self._SEEN_MAX = 2000

        # Layer 1: REQUEST_ID based deduplication for bot messages
        self._request_dedup_cache: dict[str, float] = {}
        self._REQUEST_DEDUP_TTL = 60  # 60 seconds
        self._REQUEST_DEDUP_MAX = 500

        # Layer 2: Pending requests for request-response correlation
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._REQUEST_TIMEOUT = 10.0  # 10 seconds default timeout

        # Layer 4: User request deduplication
        self._user_request_cache: dict[str, float] = {}
        self._USER_REQUEST_TTL = 10  # 10 seconds
        self._USER_REQUEST_MAX = 100

        # Discussion turn control
        self._discussion_turns: dict[str, int] = {}
        self._bot_replied_this_round: dict[str, set] = {}
        self._waiting_confirmation: set[str] = set()

        # Orchestrator (v5.0) - only for controller bot (小小谦)
        self._orchestrator: Optional[Orchestrator] = None
        # 使用Coordinator自动识别结果（新增）
        self._is_controller = self._is_coordinator
        if self._is_controller and ORCHESTRATOR_AVAILABLE:
            self._init_orchestrator()

        # ========== 自动化集成核心：大脑创建和注入 ==========
        # 只有Coordinator Bot 才需要内置大脑（大脑与协调员一体）
        self.brain = None
        if self._is_controller:
            from phoenix_core.core_brain import get_brain
            self.brain = get_brain()
            # 将 Gateway 自身注入大脑，这样大脑可以直接调用 Gateway 发送 Discord Message
            self.brain._gateway = self
            logger.info(f"Coordinator Bot 已初始化大脑，Gateway 已注入")
        # ===================================================

        # Discord mention mapping (Chinese name -> Discord ID)
        self._discord_mentions = {
            "@小小谦": "1483335704590155786",
            "@StageControl": "1479053473038467212",
            "@Operations": "1479047738371870730",
            "@Channel": "1483334000109162586",
            "@Designer": "1479055713220431995",
            "@Director": "1479060596648312942",
            "@Editor": "1479054512114368512",
            "@Support": "1479061563737641095",
        }

        # P1 Features (AuditLog、链路Trace、Progress汇报)
        if P1_FEATURES_AVAILABLE:
            self.audit_logger = get_audit_logger()
            self.tracer = get_tracer()
            self.progress_reporter = get_progress_reporter()
            logger.info("P1 功能模块已加载 (AuditLog、链路Trace、Progress汇报)")
        else:
            self.audit_logger = None
            self.tracer = None
            self.progress_reporter = None
            logger.warning("P1 功能模块不可用")

        # 并发管理器 (用于等待 Bot 回复)
        from phoenix_core.gateway_concurrency import GatewayConcurrencyManager
        self.concurrency_manager = GatewayConcurrencyManager(max_retries=0, default_timeout=60.0)
        logger.info("并发管理器已加载")

        # ========== Skill执行器（新增） ==========
        # 加载 SkillExecutor 用于执行可执行Skill
        try:
            from phoenix_core.skill_executor import get_executor
            self.skill_executor = get_executor()
            logger.info(f"Skill执行器已加载 ({len(self.skill_executor.get_all_skills())} 个Skill)")
        except ImportError as e:
            self.skill_executor = None
            logger.warning(f"Skill执行器不可用：{e}")
        # =======================================

        # ========== TeamDelegation器（新增 Phase 2） ==========
        # 加载 TeamDelegator 用于TeamTaskDelegation
        try:
            from phoenix_core.team_delegator import get_team_delegator, register_team_as_skill
            self.team_delegator = get_team_delegator(gateway=self, config_loader=None)
            logger.info(f"TeamDelegation器已加载 ({len(self.team_delegator.teams)} 个Team)")

            # 自动将Team注册为Coordinator Bot 的Skill
            if self.bot_name in ["小小谦", "Coordinator"]:
                for team_name in self.team_delegator.teams.keys():
                    register_team_as_skill(
                        team_name=team_name,
                        coordinator_bot=self.bot_name,
                        gateway=self
                    )
                logger.info(f"已将Team注册为 {self.bot_name} 的Skill")
        except ImportError as e:
            self.team_delegator = None
            logger.warning(f"TeamDelegation器不可用：{e}")
        # ===============================================

        # Heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._heartbeat_interval = 5  # 每秒上报

    # ========== Phase 2: Team Delegation 快捷方法 ==========
    async def delegate_to_team(
        self,
        team_name: str,
        brief: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        便捷方法：DelegationTeamTask

        Usage in CoreBrain:
            result = await gateway.delegate_to_team("内容Team", "策划直播活动")
        """
        if not self.team_delegator:
            return {
                "success": False,
                "error": "TeamDelegator not available"
            }

        return await self.team_delegator.delegate_to_team(
            team_name=team_name,
            brief=brief,
            context=context or {}
        )

    def get_team_list(self) -> List[Dict]:
        """获取Team列表（用于 API 展示）"""
        if not self.team_delegator:
            return []
        return self.team_delegator.get_all_teams()
    # =======================================================

    # ========== Phase 3: Remote Debug RemoteDebug ==========
    async def start_remote_debug(self) -> bool:
        """StartingRemoteDebug客户端"""
        if not REMOTE_DEBUG_AVAILABLE:
            logger.warning("RemoteDebug模块不可用")
            return False

        server_url = os.environ.get("DEBUG_MASTER_URL")
        device_id = os.environ.get("DEBUG_DEVICE_ID")

        if not server_url:
            logger.info("📡 RemoteDebug未启用 (缺少 DEBUG_MASTER_URL)")
            return False

        logger.info(f"📡 StartingRemoteDebug客户端...")
        logger.info(f"   Server：{server_url}")
        logger.info(f"   Device ID: {device_id or '自动生成'}")

        task = await start_remote_debug()
        if task:
            logger.info("✅ RemoteDebug客户端已Starting")
            send_log("INFO", f"Gateway Starting - Bot: {self.bot_name}")
            return True
        return False

    def send_debug_log(self, level: str, message: str):
        """发送DebugLog到Server"""
        if REMOTE_DEBUG_AVAILABLE:
            send_log(level, message)
    # =======================================================


    def _is_duplicate_request(self, request_id: str, bot_id: str) -> bool:
        """Layer 1: Check if this REQUEST_ID has been processed."""
        import hashlib
        key = f"{request_id}:{bot_id}"
        now = time.time()

        # Clean expired entries
        cutoff = now - self._REQUEST_DEDUP_TTL
        self._request_dedup_cache = {
            k: v for k, v in self._request_dedup_cache.items()
            if v > cutoff
        }

        if key in self._request_dedup_cache:
            logger.info(f"Duplicate request detected: {request_id}")
            return True

        self._request_dedup_cache[key] = now
        return False

    def _is_duplicate_user_request(self, user_id: str, content: str) -> bool:
        """Layer 4: Check if user sent duplicate request."""
        import hashlib
        key = f"{user_id}:{hashlib.md5(content.encode()).hexdigest()}"
        now = time.time()

        # Clean expired entries
        cutoff = now - self._USER_REQUEST_TTL
        self._user_request_cache = {
            k: v for k, v in self._user_request_cache.items()
            if v > cutoff
        }

        if key in self._user_request_cache:
            logger.info(f"Duplicate user request detected: {user_id} - {content[:30]}")
            return True

        self._user_request_cache[key] = now
        return False

    async def _send_protocol_request(
        self,
        target_bot_id: str,
        target_bot_discord_id: str,
        content: str,
        timeout: float = None
    ) -> str:
        """
        Layer 2: Send protocol request and wait for response with timeout.

        Args:
            target_bot_id: Bot name (e.g., "StageControl")
            target_bot_discord_id: Discord ID (e.g., "1479053473038467212")
            content: Request content
            timeout: Timeout in seconds

        Returns:
            Response content or timeout message
        """
        import uuid
        request_id = f"{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:3].upper()}"
        timeout = timeout or self._REQUEST_TIMEOUT

        # Build protocol message: [REQUEST|RequestID|Sender|TTL]
        protocol_msg = f"<@{target_bot_discord_id}> [REQUEST|{request_id}|{self.bot_name}|{int(timeout)}] {content}"

        # Create future to wait for response
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending_requests[request_id] = future

        # Send to Discord
        channel = self.channel_manager.get_channel("discord")
        if not channel or not channel.connected:
            logger.error("Discord channel not available")
            return "Error：Discord 频道不可用"

        # Get Discord channel ID from environment
        discord_channel_id = os.environ.get("DISCORD_CHANNEL_ID")
        if not discord_channel_id:
            logger.error("DISCORD_CHANNEL_ID not set")
            return "Error：频道配置缺失"

        try:
            await channel.send_message(to=discord_channel_id, content=protocol_msg)
            logger.info(f"Sent protocol request {request_id} to {target_bot_id}: {content[:50]}")
        except Exception as e:
            logger.error(f"Failed to send protocol request: {e}")
            return f"Error：发送Failed - {e}"

        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            logger.info(f"Received response for {request_id}: {response[:50] if response else 'empty'}")
            return response or "（无内容）"
        except asyncio.TimeoutError:
            logger.warning(f"Request {request_id} timed out after {timeout}s")
            return f"{target_bot_id} 响应超时，请稍后重试"
        finally:
            self._pending_requests.pop(request_id, None)

    async def _handle_incoming_protocol_response(self, content: str, sender_bot: str) -> bool:
        """
        Layer 2: Handle incoming protocol response from Worker Bot.

        Protocol v1.1 format: <@BOT_ID> [TYPE|VERSION|REQUEST_ID|SUB_TASK_ID|SENDER|FLAGS] CONTENT
        Returns True if this was a protocol response that was handled, False otherwise.
        """
        import re

        # Parse protocol format: <@BOT_ID> [TYPE|VERSION|REQUEST_ID|SUB_TASK_ID|SENDER|FLAGS] CONTENT
        # Also support CONFIRM/DONE/FAIL as implicit responses
        match = re.match(
            r'<@(\d+)> \[(REQUEST|RESPONSE|CONFIRM|DONE|FAIL|REPORT)\|([^\|]+)\|([^\|]+)\|([^\|]+)\|([^\|]+)(?:\|([^\]]*))?\](.*)',
            content.strip(),
            re.DOTALL
        )

        if not match:
            logger.debug(f"Protocol regex did not match. Content: {content[:100]}")
            return False

        target_bot_id, msg_type, version, request_id, sub_task_id, sender, flags_str, reply_content = match.groups()
        flags = set(flags_str.split(",")) if flags_str else set()
        is_final = "FINAL" in flags

        logger.info(f"Parsed protocol: type={msg_type}, request_id={request_id}, sub_task_id={sub_task_id}, sender={sender}, final={is_final}")

        # Check Gateway's pending requests first
        if request_id in self._pending_requests:
            logger.info(f"Matched protocol response {request_id} from {sender} (Gateway pending)")
            reply = reply_content.strip() if reply_content else ""
            self._pending_requests[request_id].set_result(reply)
            return True

        # Check concurrency manager (for brain task dispatcher)
        if hasattr(self, 'concurrency_manager'):
            cm = self.concurrency_manager
            # Check if this request_id is in any user's pending
            # Structure: cm.pending[user_id][request_id][sub_task_id] = future
            for user_id, requests in cm.pending.items():
                # requests = {request_id: {sub_task_id: future}}
                for req_id, sub_tasks in requests.items():
                    # Check if the incoming request_id matches or starts with req_id (for R2 requests)
                    # AND if the sub_task_id matches
                    if request_id == req_id or request_id.startswith(req_id + "-"):
                        if sub_task_id in sub_tasks:
                            future = sub_tasks[sub_task_id]
                            if not future.done():
                                logger.info(f"Matched protocol response {request_id}/{sub_task_id} from {sender} (ConcurrencyManager pending: user={user_id})")
                                reply = reply_content.strip() if reply_content else ""
                                # Resolve the subtask
                                cm.resolve_subtask(
                                    user_id=user_id,
                                    request_id=req_id,
                                    sub_task_id=sub_task_id,
                                    result=reply,
                                    bot_id=sender,
                                    is_final=is_final
                                )
                                return True

        # Check Orchestrator's pending tasks (for controller bot)
        if self._orchestrator and hasattr(self._orchestrator, '_pending_tasks'):
            future = self._orchestrator._pending_tasks.get(request_id)
            if future and not future.done():
                logger.info(f"Matched protocol response {request_id} from {sender} (Orchestrator pending)")
                # Extract clean content for Orchestrator
                reply = reply_content.strip() if reply_content else ""
                future.set_result(reply)
                return True

        logger.debug(f"Protocol message {request_id}/{sub_task_id} not in pending requests (may have expired)")
        return False

    def _load_config(self) -> dict:
        """
        Load gateway configuration.

        优先级：
        1. 从 config_loader 加载 Bot 配置（中央配置）
        2. 从 workspace/gateway.yaml 加载
        3. Using default config
        """
        # 优先级 1: 从 config_loader 加载 Bot 配置
        if self.bot_config:
            logger.info(f"从 config_loader 加载 Bot 配置：{self.bot_name}")
            model = self.bot_config.get("model", "qwen3.6-plus")
            provider = self.bot_config.get("provider", "coding-plan")
            role = self.bot_config.get("role", "worker")
            teams = self.bot_config.get("teams", [])

            return {
                "gateway": {"name": "Phoenix Gateway", "version": "2.0"},
                "bot": {
                    "name": self.bot_name,
                    "role": role,
                    "model": model,
                    "provider": provider,
                    "teams": teams,
                },
                "channels": {"enabled": []},
                "agents": {"list": [{"id": "main", "model": model, "provider": provider}]},
            }

        # 优先级 2: 从 workspace/gateway.yaml 加载
        config_file = self.workspace / "gateway.yaml"
        if not config_file.exists():
            config_file = self.workspace / "gateway.json"

        if not config_file.exists():
            logger.warning("No config found, using defaults")
            return {
                "gateway": {"name": "Phoenix Gateway", "version": "1.0.0"},
                "channels": {"enabled": []},
                "agents": {"list": [{"id": "main", "model": "qwen3.6-plus"}]},
            }

        try:
            import yaml
            if config_file.suffix in [".yaml", ".yml"]:
                with open(config_file, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            else:
                with open(config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def _check_is_controller_bot(self) -> bool:
        """Check if this bot is the controller bot (小小谦)."""
        controller_names = {"小小谦", "XiaoXiaoQian", "xiaoxiaoqian"}
        return self.bot_name in controller_names

    def _init_orchestrator(self):
        """Initialize Orchestrator for controller bot."""
        if not ORCHESTRATOR_AVAILABLE:
            logger.warning("Orchestrator module not available, skipping initialization")
            return

        try:
            config = OrchestratorConfig(
                controller_name=self.bot_name,
                controller_id="1483335704590155786",  # 小小谦 Discord ID
                simple_inquiry_timeout=30,
                execution_task_timeout=300,
                debug=True
            )
            self._orchestrator = Orchestrator(config)

            # Set send callback
            async def send_protocol(bot_id: str, protocol: str):
                """Send protocol message to Worker Bot via Discord.

                Args:
                    bot_id: Bot name (e.g., "StageControl", "Operations")
                    protocol: Protocol format message (may or may not have <@BOT_ID> prefix)
                """
                try:
                    # Get target bot's Discord ID
                    target_discord_id = self._discord_mentions.get(f"@{bot_id}", "")
                    if not target_discord_id:
                        logger.error(f"Discord ID not found for bot: {bot_id}")
                        return

                    # Parse protocol to check if it already has target_bot
                    from phoenix_core import ProtocolParser
                    parser = ProtocolParser()
                    parsed = parser.parse(protocol)

                    if parsed:
                        # Re-create protocol with correct Discord ID as target
                        from phoenix_core.protocol_v2 import ProtocolMessage, PROTOCOL_VERSION
                        new_msg = ProtocolMessage(
                            target_bot=target_discord_id,  # Use Discord ID, not bot name
                            msg_type=parsed.msg_type,
                            version=parsed.version,
                            request_id=parsed.request_id,
                            sub_task_id=parsed.sub_task_id,
                            sender=parsed.sender,
                            flags=parsed.flags,
                            content=parsed.content
                        )
                        protocol = new_msg.to_string()
                        logger.info(f"Sending protocol to {bot_id} ({target_discord_id}): {protocol[:50]}...")
                    else:
                        logger.error(f"Failed to parse protocol: {protocol[:50]}...")
                        return

                    # Get Discord channel
                    channel = self.channel_manager.get_channel("discord")
                    if not channel or not channel.connected:
                        logger.error("Discord channel not available")
                        return

                    # Get Discord channel ID from environment
                    discord_channel_id = os.environ.get("DISCORD_CHANNEL_ID")
                    if not discord_channel_id:
                        logger.error("DISCORD_CHANNEL_ID not set")
                        return

                    # Send to Discord channel (no auto-delete)
                    await channel.send_message(to=discord_channel_id, content=protocol, auto_delete=False)
                    logger.info(f"Protocol message sent to <@{target_discord_id}> in channel {discord_channel_id}")

                except Exception as e:
                    logger.error(f"Failed to send protocol: {e}", exc_info=True)

            self._orchestrator.set_send_callback(send_protocol)
            logger.info(f"Orchestrator initialized for {self.bot_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Orchestrator: {e}")

    async def initialize(self):
        """Initialize the gateway."""
        logger.info(f"Initializing Phoenix Core Gateway")
        logger.info(f"Workspace: {self.workspace}")

        # Initialize channel manager
        await self.channel_manager.initialize()

        # Start heartbeat loop
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Run startup routines
        await self._on_startup()

        logger.info("Gateway initialized")

    async def start(self):
        """Start the gateway."""
        logger.info("Starting Phoenix Core Gateway...")

        # Start channel listeners
        await self.channel_manager.start_listening()

        logger.info("Gateway started")

    async def stop(self):
        """Stop the gateway (包括 P1 功能模块)."""
        logger.info("Stopping Phoenix Core Gateway...")

        # Stop heartbeat loop
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Stop channel listeners
        await self.channel_manager.stop_listening()

        # Send final heartbeat (offline)
        write_heartbeat(self.bot_name, status="stopped")

        # Close P1 modules
        if self.tracer:
            self.tracer.close()
        if self.progress_reporter:
            self.progress_reporter.close()
        if self.audit_logger:
            self.audit_logger.close()

        logger.info("Gateway stopped")

    async def _heartbeat_loop(self):
        """Heartbeat loop - send heartbeat every 5 seconds."""
        logger.info(f"Starting heartbeat loop (interval={self._heartbeat_interval}s)")

        while True:
            try:
                await asyncio.sleep(self._heartbeat_interval)

                # Get memory usage
                import psutil
                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / 1024 / 1024

                write_heartbeat(
                    bot_id=self.bot_name,
                    status="running",
                    extra_info={"memory_mb": round(memory_mb, 1)}
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    def _replace_mentions(self, text: str) -> str:
        """Replace @Chinese mentions with Discord IDs."""
        result = text
        for chinese, discord_id in self._discord_mentions.items():
            # Convert to Discord mention format <@ID>
            result = result.replace(chinese, f"<@{discord_id}>")
        return result

    async def _on_startup(self):
        """Gateway startup routine - load shared context and identity files."""
        logger.info("Running startup routine...")

        # Load identity files (cache for LLM calls)
        self._bot_soul = self._load_identity_file("SOUL.md")
        self._bot_identity = self._load_identity_file("IDENTITY.md")
        self._bot_agents = self._load_identity_file("AGENTS.md")
        self._bot_tools = self._load_identity_file("TOOLS.md")
        if self._bot_soul:
            logger.info(f"Loaded SOUL.md ({len(self._bot_soul)} chars)")
        if self._bot_identity:
            logger.info(f"Loaded IDENTITY.md ({len(self._bot_identity)} chars)")

        # ========== 自动导入Skill到 SkillRegistry（新增） ==========
        # Starting时将 SOUL.md 内容注册为Skill，这样讨论机制可以动态匹配
        if self._bot_soul and self.brain:
            try:
                from phoenix_core.skill_registry import import_from_soul_md
                soul_path = self.workspace / "SOUL.md"
                import_from_soul_md(self.brain.skill_registry, self.bot_name, soul_path)
                logger.info(f"已导入 SOUL.md Skill：{self.bot_name}")
            except Exception as e:
                logger.warning(f"导入 SOUL.md SkillFailed：{e}")
        # =======================================================

        # Read daily tasks
        task_file = self.shared_memory_dir / "今日Task.md"
        if task_file.exists():
            content = task_file.read_text(encoding="utf-8")
            logger.info(f"Loaded daily tasks ({len(content)} chars)")

        # Read streamer profile
        profile_file = self.shared_memory_dir / "主播资料.md"
        if profile_file.exists():
            content = profile_file.read_text(encoding="utf-8")
            logger.info(f"Loaded streamer profile ({len(content)} chars)")

        # Read team memory
        memory_file = self.shared_memory_dir / "MEMORY.md"
        if memory_file.exists():
            content = memory_file.read_text(encoding="utf-8")
            logger.info(f"Loaded team memory ({len(content)} chars)")

        # Read today's log
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.shared_memory_dir / "logs" / f"{today}.md"
        if log_file.exists():
            content = log_file.read_text(encoding="utf-8")
            logger.info(f"Loaded today's log ({len(content)} chars)")

        logger.info("Startup routine completed")

        # ========== Phase 3: StartingRemoteDebug ==========
        if REMOTE_DEBUG_AVAILABLE:
            asyncio.create_task(self.start_remote_debug())
        # =========================================

        # Layer 5: 静默Starting - 不再发送上线广播到 Discord 频道
        # 上线状态仅通过Heartbeat文件报告给 Dashboard
        logger.info(f"{self.bot_name} started silently (no Discord broadcast)")

    def _get_main_channel_id(self, channel_id: str) -> str:
        """Get main channel ID for a channel type."""
        # Get from environment variable (set by .env file)
        import os
        discord_channel_id = os.environ.get("DISCORD_CHANNEL_ID")
        if discord_channel_id:
            return discord_channel_id
        return "0"  # Placeholder

    def _is_collaboration_request(self, user_message: str) -> bool:
        """
        判断User请求是否需要多 Bot 协作

        判断依据：
        1. 包含多个 Bot 的@mention
        2. 包含协作相关关键词（讨论、方案、策划、组织、安排等）
        3. 是复杂Task（涉及多个领域）

        Args:
            user_message: UserMessage内容

        Returns:
            是否需要多 Bot 协作
        """
        # 1. 检查是否@了多个 Bot
        import re
        mentions = re.findall(r'<@\d+>', user_message)
        if len(mentions) >= 2:
            logger.info(f"检测到多 Bot @mention: {len(mentions)} 个")
            return True

        # 2. 检查协作关键词
        collaboration_keywords = [
            "讨论", "方案", "策划", "组织", "安排", "协调",
            "一起", "协作", "配合", "Team", "大家", "所有",
            "整体", "全面", "计划", "规划", "筹备"
        ]
        for keyword in collaboration_keywords:
            if keyword in user_message:
                logger.info(f"检测到协作关键词：'{keyword}'")
                return True

        # 3. 检查是否@了Coordinator + 复杂Task
        if self._is_coordinator:
            # 如果Message是发给Coordinator的，且包含复杂Task特征
            complex_keywords = ["直播", "活动", "项目", "Task", "工作"]
            for kw in complex_keywords:
                if kw in user_message:
                    logger.info(f"Coordinator收到复杂Task：'{kw}'")
                    return True

        return False

    async def _try_execute_skill(self, user_message: str) -> Optional[str]:
        """
        尝试执行Skill

        流程：
        1. 使用 LLM 判断User输入是否匹配已注册Skill
        2. 如果匹配，调用 SkillExecutor 执行
        3. 返回执行结果

        Args:
            user_message: UserMessage

        Returns:
            Skill执行结果（如果匹配），否则 None
        """
        if not self.skill_executor:
            return None

        # Step 1: 检查是否匹配Skill触发词
        matched_skill = self.skill_executor.find_skill_by_trigger(user_message)

        if not matched_skill:
            return None

        logger.info(f"匹配到Skill：{matched_skill}")

        # Step 2: 执行Skill
        try:
            result = await self.skill_executor.execute(matched_skill, {
                "user_input": user_message,
                "bot_name": self.bot_name
            })

            if result.get("success"):
                logger.info(f"Skill执行成功：{matched_skill}")
                return result.get("suggested_action", str(result))
            else:
                logger.warning(f"Skill执行Failed：{matched_skill} - {result.get('error')}")
                return None

        except Exception as e:
            logger.error(f"Skill执行异常：{e}")
            return None

    async def _handle_message_from_channel(self, message: Message, channel: ChannelPlugin) -> Optional[str]:
        """
        Handle message from a channel.

        This is the callback that ChannelManager uses to route messages to Gateway.
        """
        # Dedup check - Layer 0: Message ID based deduplication
        msg_id = f"{message.id}"
        now = time.time()
        if msg_id in self._seen_messages:
            logger.debug(f"Duplicate message ID ignored: {msg_id}")
            return None
        self._seen_messages[msg_id] = now
        if len(self._seen_messages) > self._SEEN_MAX:
            cutoff = now - self._SEEN_TTL
            self._seen_messages = {k: v for k, v in self._seen_messages.items() if v > cutoff}

        # Log ALL messages to shared context (auto-save chat history)
        await self._log_message_to_shared(message, channel)

        # Layer 2: Check if this is a protocol response to a pending request
        # This handles CONFIRM/DONE/FAIL/REPORT messages from Worker Bots
        if self._is_controller:
            handled = await self._handle_incoming_protocol_response(
                message.content,
                sender_bot=message.username
            )
            if handled:
                logger.info(f"Protocol response handled, no further processing needed")
                return None

            # Even if not handled (e.g., request_id expired), check if this looks like a protocol message
            # If so, don't process it as a regular user message (prevent loops)
            import re
            if re.search(r'\[(REQUEST|RESPONSE|CONFIRM|DONE|FAIL|REPORT)\|', message.content):
                logger.info(f"Protocol-format message detected, skipping regular processing")
                return None

        # v5.0: 小小谦处理 Worker Bot 的协议回复 (fallback for Orchestrator)
        if self._is_controller and self._orchestrator:
            if self._is_protocol_message(message.content):
                response = await self._handle_protocol_from_bot(message.content)
                if response:
                    return response

        # Process message through Gateway
        try:
            response = await self._process_message(message, channel)

            # Log response to shared context
            if response:
                await self._log_to_shared_context(message, response, channel)

            return response
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return None

    async def _process_message(self, message: Message, channel: ChannelPlugin) -> Optional[str]:
        """
        Process a message through the Gateway (集成 P1 功能：AuditLog、链路Trace、Progress汇报).

        This is the core business logic that was previously in discord_bot.py
        """
        logger.info(f"Received message from {message.username}: {message.content[:50]}...")

        # P1: 开始链路Trace
        trace_id = None
        if self.tracer:
            trace_id = self.tracer.start_trace(
                user_id=message.username,
                request_id=f"{message.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )

        # P1: 记录AuditLog
        if self.audit_logger:
            self.audit_logger.log_message(
                content=message.content,
                user_id=message.username,
                request_id=trace_id,
                metadata={"channel": channel.id, "bot_name": self.bot_name}
            )

        try:
            user_message = message.content

            # Remove @mention prefix if present
            if channel.id == "discord":
                # Discord mentions are handled at channel level
                pass

            # P1: 创建ProgressTrace (如果是Task请求)
            progress = None
            if self.progress_reporter and self._is_task_request(message.content):
                progress = self.progress_reporter.create_progress(
                    task_id=trace_id or message.id,
                    user_id=message.username,
                    description=message.content[:100],
                    subtasks=["sub-0", "sub-1"]  # 默认 2 个子Task
                )

            # Layer 3: Worker Bot 响应协议格式Message 或 直接@它的Message
            if not self._is_controller:
                import re
                # 注意：RESPONSE Message不需要 Worker Bot 处理，只给控制器 Bot 匹配 pending future
                protocol_match = re.search(r'\[(ASK|DO|REQUEST)\|', user_message)
                # 检查是否有@mention（使用 bot_name 匹配）
                has_mention = self.bot_name in user_message or f"<@{self._discord_mentions.get('@' + self.bot_name, '')}>" in user_message

                # 检查是否是 RESPONSE Message - Worker Bot 应该忽略
                is_response = re.search(r'\[RESPONSE\|', user_message)
                if is_response:
                    logger.info(f"Ignoring RESPONSE message (Worker Bot skip): {user_message[:50]}")
                    return None

                # 检查协议Message是否是发给自己的（检查<@BOT_ID>）
                is_targeted = True
                if protocol_match:
                    # 提取Message中的@目标 ID
                    mention_match = re.match(r'<@(\d+)>', user_message.strip())
                    if mention_match:
                        target_bot_id = mention_match.group(1)
                        my_bot_id = self._discord_mentions.get(f"@{self.bot_name}", "")
                        # 如果@的目标不是自己，忽略Message
                        if target_bot_id and my_bot_id and target_bot_id != my_bot_id:
                            is_targeted = False
                            logger.info(f"Ignoring ASK message for another bot (target={target_bot_id}, myself={my_bot_id}): {user_message[:50]}")

                if not protocol_match and not has_mention:
                    logger.info(f"Ignoring non-protocol message (Worker Bot): {user_message[:50]}")
                    return None

                if not is_targeted:
                    return None

                logger.info(f"Processing message (protocol={protocol_match}, mention={has_mention}, targeted={is_targeted}): {user_message[:50]}")

            # Layer 4: 小小谦跳过 Worker Bot 的自然语言回复（防止Message循环）
            # 当StageControl等 Worker Bot 回复@mention 时，回复是自然语言格式，不应该再次触发 ASK
            if self._is_controller:
                import re
                worker_bot_names = {"StageControl", "Operations", "Channel", "Designer", "Director", "Editor", "Support"}
                # 检查Message是否来自 Worker Bot（通过User名判断，检查是否包含 Bot 名称）
                is_worker_bot = any(name in (message.username or '') for name in worker_bot_names)
                # 检查是否包含协议格式（如果有协议格式，说明是 Bot 之间的通信，需要处理）
                has_protocol = re.search(r'\[(ASK|DO|REQUEST|RESPONSE)\|', user_message)

                if is_worker_bot and not has_protocol:
                    logger.info(f"Ignoring Worker Bot natural language response (controller skip): {user_message[:50]}")
                    return None

            if not user_message:
                return None

            # ========== Skill执行检查（新增） ==========
            # 在 LLM 处理之前，先尝试匹配并执行已注册的Skill
            if self.skill_executor and not self._is_controller:
                # Worker Bot 优先检查Skill匹配
                skill_result = await self._try_execute_skill(user_message)
                if skill_result:
                    # Skill匹配成功，直接返回结果
                    logger.info(f"Skill执行Completed，跳过 LLM 处理")

                    # 包装协议响应
                    import re
                    protocol_match = re.search(r'\[(ASK|DO|REQUEST)\|([^\|]+)\|([^\|]+)\|([^\|]+)\|([^\|]+)(?:\|([^\]]*))?\]', user_message)
                    if protocol_match:
                        msg_type, version, request_id, sub_task_id, sender, flags = protocol_match.groups()
                        sender_discord_id = self._discord_mentions.get(f"@{self.bot_name}", "")
                        response = f"<@{sender_discord_id}> [RESPONSE|{version}|{request_id}|{sub_task_id}|{self.bot_name}|FINAL] {skill_result}"
                    else:
                        response = skill_result

                    # Stopping typing
                    typing_task.cancel()

                    # 发送响应
                    await channel.send_message(
                        to=message.channel_id,
                        content=response,
                        in_reply_to=message.id,
                        auto_delete=False
                    )
                    return response
            # =========================================

            # 立即发送第一次 typing
            await channel.send_typing(message.channel_id)

            # 在 LLM 处理期间持续发送 typing
            typing_task = asyncio.create_task(
                self._continuous_typing(channel, message.channel_id)
            )

            # P1: 更新Progress (开始处理)
            if progress and self.progress_reporter:
                self.progress_reporter.update_progress(
                    task_id=trace_id or message.id,
                    sub_task_id="sub-0",
                    status="running",
                    progress_percent=10.0,
                    description="正在处理..."
                )

            # v5.0: 小小谦使用 Orchestrator 处理UserMessage
            if self._is_controller and self._orchestrator:
                # 小小谦：使用编排器处理（意图识别→协议生成→路由分发→结果汇总）
                response = await self._process_with_orchestrator(user_message, message, channel)
            else:
                # Worker Bot：直接使用 LLM 处理
                # 提取协议Info用于包装响应
                import re
                # Protocol v1.1 format: [ASK|VERSION|REQUEST_ID|SUB_TASK_ID|SENDER|FLAGS]
                protocol_match = re.search(r'\[(ASK|DO|REQUEST)\|([^\|]+)\|([^\|]+)\|([^\|]+)\|([^\|]+)(?:\|([^\]]*))?\]', user_message)
                if protocol_match:
                    msg_type, version, request_id, sub_task_id, sender, flags = protocol_match.groups()
                    # 清理协议头，只保留自然语言部分给 LLM
                    clean_content = re.sub(r'<@\d+>\s*\[.*?\]\s*', '', user_message).strip()
                    logger.info(f"Clean content for LLM: {clean_content[:50]}...")
                    # 获取 LLM 生成的自然语言回复
                    llm_raw = await self._call_llm(clean_content, message, channel)
                    # 清理 LLM 输出中可能包含的协议标记（防止双层协议头）
                    llm_response = re.sub(r'\[(CONFIRM|RESPONSE|ASK|REQUEST)\|[^\]]*\]\s*', '', llm_raw)
                    llm_response = re.sub(r'<@\d+>\s*', '', llm_response).strip()
                    logger.info(f"Cleaned LLM response: {llm_response[:50]}...")
                    # 强制包装协议头：[RESPONSE|VERSION|REQUEST_ID|SUB_TASK_ID|SENDER|FINAL]
                    # 回复给当前 Bot 自己（因为Message是发给自己的）
                    sender_discord_id = self._discord_mentions.get(f"@{self.bot_name}", "")
                    # 降级逻辑：如果映射不存在，使用空 ID
                    if not sender_discord_id:
                        logger.warning(f"Cannot find Discord ID for self '{self.bot_name}', using empty ID")
                        sender_discord_id = ""
                    response = f"<@{sender_discord_id}> [RESPONSE|{version}|{request_id}|{sub_task_id}|{self.bot_name}|FINAL] {llm_response}"
                    logger.info(f"Wrapped response with protocol header: {response[:80]}...")
                else:
                    response = await self._call_llm(user_message, message, channel)

            # Stopping typing
            typing_task.cancel()

            if response:
                # Worker Bot 需要发送协议格式到 Discord，这样小小谦才能收到并匹配
                # 不需要清理协议头，由小小谦在收到后删除
                await channel.send_message(
                    to=message.channel_id,
                    content=response,
                    in_reply_to=message.id,
                    auto_delete=False
                )

            # P1: 更新Progress (Completed)
            if progress and self.progress_reporter:
                self.progress_reporter.update_progress(
                    task_id=trace_id or message.id,
                    status="completed",
                    description="处理Completed"
                )

            # P1: 记录CompletedAuditLog
            if self.audit_logger:
                self.audit_logger.log_operation(
                    operation="message_processed",
                    user_id=message.username,
                    request_id=trace_id,
                    details=f"response_length={len(response) if response else 0}"
                )

            # P1: 结束链路Trace
            if self.tracer and trace_id:
                with self.tracer.trace_operation(trace_id, "response_sent") as span:
                    span.add_log("response_sent", length=len(response) if response else 0)

            return response

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

            # P1: 记录ErrorAuditLog
            if self.audit_logger:
                self.audit_logger.log_error(
                    error=str(e),
                    user_id=message.username,
                    request_id=trace_id,
                    traceback=str(e)
                )

            # P1: 更新Progress (Failed)
            if self.progress_reporter and trace_id:
                self.progress_reporter.update_progress(
                    task_id=trace_id,
                    status="failed",
                    description=f"处理Failed：{e}"
                )

            # P1: 结束链路Trace (Error)
            if self.tracer and trace_id:
                with self.tracer.trace_operation(trace_id, "error") as span:
                    span.add_log("error", message=str(e))

            return None

    def _is_task_request(self, content: str) -> bool:
        """判断是否是Task请求 (需要ProgressTrace)"""
        task_keywords = ["订单", "退款", "查询", "处理", "Task", "帮我", "check", "order", "refund"]
        return any(kw in content for kw in task_keywords)

    async def _continuous_typing(self, channel: ChannelPlugin, channel_id: str):
        """持续发送 typing 状态，每 3 秒一次（Discord typing 持续约 10 秒）"""
        try:
            while True:
                await channel.send_typing(channel_id)
                await asyncio.sleep(3)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Typing error: {e}")

    async def _call_llm(self, user_message: str, original_message: Message, channel: ChannelPlugin) -> str:
        """
        Call LLM API to process message.

        This integrates with the existing Phoenix Core LLM calling logic.
        """
        import time
        llm_start_time = time.time()
        bot_name = self.bot_name
        logger.info(f"[{bot_name}] LLM call started - model={os.environ.get('BOT_MODEL', 'unknown')}, input_length={len(user_message)}")

        try:
            # Load only essential identity files for fast response
            bot_soul = self._load_identity_file("SOUL.md")
            bot_identity = self._load_identity_file("IDENTITY.md")

            # Load shared context (limited size)
            shared_context = self._load_shared_context()

            # Build minimal system prompt
            model = os.environ.get("BOT_MODEL", "qwen3.6-plus")
            provider = os.environ.get("BOT_PROVIDER", "coding-plan")

            # Check if incoming message uses protocol format (for Worker Bots)
            # Note: Protocol header is added by Gateway, so LLM only generates natural language
            protocol_instruction = ""
            import re
            protocol_match = re.search(r'\[(ASK|DO|REQUEST)\|([^|]+)\|([^\]]+)\]', user_message)
            if protocol_match:
                # 收到协议格式Message，LLM 只需生成自然语言回复
                msg_type, request_id, sender = protocol_match.groups()
                logger.info(f"[{bot_name}] Protocol message: type={msg_type}, request_id={request_id}, sender={sender}")

            system_prompt = f"""{bot_soul}

{bot_identity}

{shared_context}

---
## 当前配置
- 模型：{model} ({provider})
- 人格设定：以上是你的身份和人格设定，请根据设定进行自然对话。

请根据以上人格设定、身份Info和共享上下文进行自然对话。要求回复简洁、快速。{protocol_instruction}
"""

            # Call LLM API (run in thread to avoid blocking event loop)
            from phoenix_core_gateway import call_llm as original_call_llm

            messages = [{"role": "user", "content": user_message}]

            logger.info(f"[{bot_name}] Calling LLM API...")
            # Run synchronous call_llm in a thread pool
            response = await asyncio.to_thread(
                original_call_llm,
                model=model,
                provider=provider,
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=1024,
            )

            llm_elapsed = time.time() - llm_start_time
            logger.info(f"[{bot_name}] LLM call completed in {llm_elapsed:.2f}s - response_length={len(response)}")

            # 集成记忆数据库：保存对话到 SQLite
            if MEMORY_DB_AVAILABLE and save_conversation:
                try:
                    save_conversation(
                        bot_id=self.bot_name,
                        user_msg=user_message,
                        bot_reply=response,
                        channel_id=original_message.channel_id,
                        username=original_message.username,
                    )
                    logger.info(f"[{bot_name}] Memory saved successfully")
                except Exception as e:
                    logger.error(f"[{bot_name}] 保存对话Failed：{e}", exc_info=True)

            return response

        except Exception as e:
            llm_elapsed = time.time() - llm_start_time
            logger.error(f"[{bot_name}] LLM call failed after {llm_elapsed:.2f}s: {e}", exc_info=True)
            return ""

    async def _process_with_orchestrator(
        self,
        user_message: str,
        original_message: Message,
        channel: ChannelPlugin
    ) -> str:
        """
        Process user message using Orchestrator (v5.0).

        This is the controller bot (小小谦) specific logic that:
        1. Recognizes user intent
        2. Generates protocol message
        3. Routes to Worker Bot
        4. Waits for Bot response
        5. Aggregates result to user-friendly message

        Args:
            user_message: User message (natural language)
            original_message: Original Message object
            channel: Channel plugin

        Returns:
            User-friendly response
        """
        if not self._orchestrator:
            logger.warning("Orchestrator not available, falling back to LLM")
            return await self._call_llm(user_message, original_message, channel)

        try:
            # Extract user/channel info
            user_id = str(original_message.user_id)
            channel_id = str(original_message.channel_id)

            # Check if this is a collaboration request (needs multiple Bots)
            if self._is_collaboration_request(user_message):
                logger.info(f"Detected collaboration request: {user_message[:50]}...")
                # Forward to CoreBrain for multi-Bot coordination
                return await self._forward_to_brain(user_message, user_id, channel_id)

            # Process through Orchestrator
            response = await self._orchestrator.handle_user_message(
                user_message=user_message,
                user_id=user_id,
                channel_id=channel_id
            )

            return response

        except Exception as e:
            logger.error(f"Orchestrator processing error: {e}", exc_info=True)
            # Fallback to LLM
            return await self._call_llm(user_message, original_message, channel)

    def _is_collaboration_request(self, content: str) -> bool:
        """
        Check if this is a collaboration request (needs multiple Bots to discuss/coordinate)

        Keywords that trigger collaboration:
        - "讨论" (discuss)
        - "组织" (organize)
        - "协调" (coordinate)
        - "大家一起" (all together)
        - "策划" (plan together)
        - "方案" + multiple bots mentioned
        """
        # Direct collaboration keywords
        collaboration_keywords = ["讨论", "组织", "协调", "大家一起", "一起", "都", "各自", "协作", "配合", "分工"]
        for kw in collaboration_keywords:
            if kw in content:
                return True

        # Strong planning keywords (trigger alone)
        strong_planning_keywords = ["直播方案", "直播策划", "活动方案", "活动策划", "多 Bot", "Team协作"]
        for kw in strong_planning_keywords:
            if kw in content:
                return True

        # Planning keywords + group context
        planning_keywords = ["方案", "策划", "计划", "安排", "分工"]
        if any(kw in content for kw in planning_keywords):
            if "大家" in content or "各" in content or "所有" in content or "多个" in content:
                return True
            # Live streaming related usually needs multiple Bots
            if "直播" in content or "活动" in content or "场次" in content:
                return True

        return False

    async def _forward_to_brain(
        self,
        user_message: str,
        user_id: str,
        channel_id: str
    ) -> str:
        """
        Forward collaboration request to CoreBrain for multi-Bot coordination

        Args:
            user_message: User message
            user_id: User ID
            channel_id: Channel ID

        Returns:
            Response from CoreBrain
        """
        try:
            # 使用内置的大脑实例（在__init__中已创建并注入）
            if not self.brain:
                logger.error("大脑未初始化，只有Coordinator Bot 才有大脑")
                return f"Error：大脑未初始化"

            # 大脑已经注入 Gateway，无需重复设置
            # self.brain._gateway = self  (已在__init__中Completed)

            # Call CoreBrain's collaboration method
            response = await self.brain.process_collaboration_request(
                user_query=user_message,
                user_id=user_id
            )

            if response.success:
                return response.message
            else:
                return f"Task分发Failed：{response.message}"

        except Exception as e:
            logger.error(f"Brain forwarding error: {e}", exc_info=True)
            return f"大脑处理出错：{e}"

    async def _send_protocol_to_bot(self, protocol: str):
        """
        Send protocol message to Worker Bot via Discord.

        Args:
            protocol: Protocol format message (already has <@BOT_ID> prefix)
        """
        try:
            # Parse protocol to extract target bot ID
            from phoenix_core import ProtocolParser
            parser = ProtocolParser()
            parsed = parser.parse(protocol)

            if not parsed:
                logger.error(f"Failed to parse protocol: {protocol[:50]}...")
                return

            # Get Discord channel
            channel = self.channel_manager.get_channel("discord")
            if not channel or not channel.connected:
                logger.error("Discord channel not available")
                return

            # Get target bot's Discord ID and add mention prefix if not already present
            target_bot_discord_id = parsed.target_bot_id
            logger.info(f"Sending protocol to bot {target_bot_discord_id}: {protocol[:50]}...")

            # Get Discord channel ID from environment
            discord_channel_id = os.environ.get("DISCORD_CHANNEL_ID")
            if not discord_channel_id:
                logger.error("DISCORD_CHANNEL_ID not set")
                return

            # Add Discord mention prefix if not already in the protocol
            full_message = protocol
            if not protocol.startswith(f"<@{target_bot_discord_id}>"):
                full_message = f"<@{target_bot_discord_id}> {protocol}"

            # Send to Discord channel (no auto-delete)
            await channel.send_message(to=discord_channel_id, content=full_message, auto_delete=False)
            logger.info(f"Protocol message sent to <@{target_bot_discord_id}> in channel {discord_channel_id}")

        except Exception as e:
            logger.error(f"Failed to send protocol: {e}", exc_info=True)

    async def send_to_bot(
        self,
        bot_id: str,
        message: str,
        protocol_msg: str = None,
        request_id: str = None
    ) -> str:
        """
        Send message to a specific Bot and wait for response via Discord.

        Args:
            bot_id: Target Bot name (e.g., "Operations", "Director")
            message: Message content
            protocol_msg: Optional protocol format message
            request_id: Request ID for tracking

        Returns:
            Bot's response
        """
        import datetime
        # 构建协议Message (Protocol v1.1): [ASK|VERSION|REQUEST_ID|SUB_TASK_ID|SENDER|FLAGS]
        if not protocol_msg:
            request_id = request_id or f"TASK-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            sub_task_id = "main"
            protocol_msg = f"[ASK|1.1|{request_id}|{sub_task_id}|brain|] {message}"

        # 获取目标 Bot 的 Discord ID（从映射中）
        bot_discord_id = self._discord_mentions.get(f"@{bot_id}", "")
        if not bot_discord_id:
            logger.warning(f"Bot {bot_id} Discord ID not found in mentions, using empty ID")
            bot_discord_id = ""

        # 包装成完整的 Discord Message
        full_message = f"<@{bot_discord_id}> {protocol_msg}"

        # 发送到 Discord 频道
        channel = self.channel_manager.get_channel("discord")
        if not channel or not channel.connected:
            logger.error("Discord channel not available")
            return f"Error：Discord 频道不可用"

        discord_channel_id = os.environ.get("DISCORD_CHANNEL_ID")
        if not discord_channel_id:
            logger.error("DISCORD_CHANNEL_ID not set")
            return f"Error：频道配置缺失"

        # 注册 Future 等待回复
        cm = self.concurrency_manager if hasattr(self, 'concurrency_manager') else None

        if cm:
            # 使用并发管理器注册子Task
            sub_task_id = "main"
            future = cm.register_subtask(
                user_id="core_brain",
                request_id=request_id,
                sub_task_id=sub_task_id
            )
            logger.info(f"Registered pending task: request_id={request_id}, sub_task_id={sub_task_id} -> {bot_id}")

        # 发送Message到 Discord
        send_success = await channel.send_message(to=discord_channel_id, content=full_message, auto_delete=False)
        if send_success:
            logger.info(f"[DISCORD] Sent to {bot_id}: {full_message[:80]}...")
        else:
            logger.error(f"[DISCORD] Failed to send message to {bot_id}: {full_message[:80]}")
            return f"Error：Message发送Failed"

        # 等待回复
        if cm and future:
            try:
                # 120 秒超时 - 考虑 LLM API 延迟和网络波动
                response = await asyncio.wait_for(future, timeout=120.0)
                logger.info(f"Received from {bot_id}: {response[:50] if response else 'empty'}")
                return response
            except asyncio.TimeoutError:
                logger.warning(f"{bot_id} timeout after 120s - possible LLM API delay or message delivery failure")
                return f"{bot_id} 响应超时"
            finally:
                # 清理 Future
                cm.pending.get("core_brain", {}).pop(request_id, None)

        # 没有并发管理器，返回Error
        logger.error("Concurrency manager not available")
        return f"Error：并发管理器不可用"

    def _is_protocol_message(self, content: str) -> bool:
        """
        Check if message content is in protocol format.

        Protocol format: <@BOT_ID> [MESSAGE_TYPE|REQUEST_ID|SENDER] CONTENT

        Args:
            content: Message content

        Returns:
            True if protocol format, False otherwise
        """
        if not content or not isinstance(content, str):
            return False

        # Quick check: protocol messages start with <@
        if not content.startswith("<@"):
            return False

        # Check for protocol pattern
        from phoenix_core import ProtocolParser
        parser = ProtocolParser()
        return parser.parse(content) is not None

    # ==================== 平台无关Message处理 ====================

    async def _register_platform_message_callback(self):
        """注册平台Message回调（平台无关模式）"""
        if not self._platform_channel:
            return

        async def handle_platform_message(msg: "PlatformMessage"):
            """处理平台Message"""
            # 1. Message去重
            msg_hash = f"{msg.platform}:{msg.channel_id}:{msg.author_id}:{msg.content}:{msg.timestamp}"
            if self._is_duplicate_message(msg_hash):
                logger.debug(f"Duplicate message ignored: {msg_hash[:50]}")
                return

            # 2. 检查是否@了 Bot（控制器 Bot 需要@才响应）
            if self._is_controller and not msg.is_mention:
                # 检查是否是协议Message（Bot 之间的协作）
                from phoenix_core import ProtocolParser
                parser = ProtocolParser()
                parsed = parser.parse(msg.content)
                if not parsed:
                    logger.debug(f"Ignoring message (no mention): {msg.content[:50]}")
                    return

            # 3. 调用大脑处理
            if self.brain:
                response = await self.brain.process(
                    msg.content,
                    user_id=f"{msg.platform}:{msg.author_id}"
                )
                # 4. 发送响应
                if response and response.message:
                    await self._platform_channel.send_message(
                        target=msg.channel_id,
                        content=response.message
                    )

        await self._platform_channel.on_message(handle_platform_message)
        logger.info(f"平台Message回调已注册：{self._platform_channel.platform_name}")

    def _is_duplicate_message(self, msg_hash: str) -> bool:
        """检查是否是重复Message"""
        import time
        now = time.time()

        # Clean old entries
        self._seen_messages = {
            k: v for k, v in self._seen_messages.items()
            if now - v < self._SEEN_TTL
        }

        if msg_hash in self._seen_messages:
            return True

        # Add new entry
        if len(self._seen_messages) >= self._SEEN_MAX:
            # Remove oldest
            oldest = min(self._seen_messages, key=self._seen_messages.get)
            del self._seen_messages[oldest]

        self._seen_messages[msg_hash] = now
        return False

    async def send_to_platform(self, target: str, content: str) -> bool:
        """
        平台无关的发送接口（大脑调用）

        Args:
            target: 目标频道/User ID
            content: Message内容

        Returns:
            bool: 是否发送成功
        """
        if self._platform_channel:
            return await self._platform_channel.send_message(target, content)

        # Fallback to Discord channel manager (legacy mode)
        if self.channel_manager:
            discord_channel = self.channel_manager.get_channel("discord")
            if discord_channel:
                return await discord_channel.send_message(to=target, content=content)

        logger.error("No platform channel available")
        return False

    async def _handle_protocol_from_bot(self, protocol_str: str) -> Optional[str]:
        """
        Handle protocol message from Worker Bot.

        Args:
            protocol_str: Protocol format message

        Returns:
            User-friendly response or None
        """
        if not self._orchestrator:
            return None

        try:
            # Pass to Orchestrator for processing
            await self._orchestrator.handle_protocol_message(protocol_str)

            # Protocol messages (CONFIRM/DONE/FAIL) are termination messages
            # No immediate response needed - the Orchestrator will handle
            # the user-facing response in handle_user_message()
            return None

        except Exception as e:
            logger.error(f"Failed to handle protocol from bot: {e}", exc_info=True)
            return None

    def _load_identity_file(self, filename: str) -> str:
        """Load identity file from workspace/DYNAMIC/."""
        # Try DYNAMIC subdirectory first (new structure)
        filepath = self.workspace / "DYNAMIC" / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        # Fallback to workspace root (legacy structure)
        filepath = self.workspace / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return ""

    def _load_shared_context(self) -> str:
        """Load shared context from shared_memory directory."""
        shared_parts = []

        # Load shared MEMORY.md
        shared_memory = self.shared_memory_dir / "MEMORY.md"
        if shared_memory.exists():
            content = shared_memory.read_text()
            if len(content) > 3000:
                content = content[:3000] + "\n\n[...共享记忆已截断...]"
            shared_parts.append(f"## Team共享记忆\n{content}")

        # Load 主播资料 (streamer profile) - PRIORITY #1
        streamer_profile = self.shared_memory_dir / "主播资料.md"
        if streamer_profile.exists():
            content = streamer_profile.read_text()
            if len(content) > 5000:
                content = content[:5000] + "\n\n[...主播资料已截断...]"
            shared_parts.insert(0, f"## 主播资料（重要）\n{content}")

        # Load today's shared log
        today = datetime.now().strftime("%Y-%m-%d")
        today_log = self.shared_memory_dir / "logs" / f"{today}.md"
        if today_log.exists():
            content = today_log.read_text()
            if len(content) > 3000:
                content = content[:3000] + "\n\n[...今日Log已截断...]"
            shared_parts.append(f"## 今日共享Log ({today})\n{content}")

        return "\n\n".join(shared_parts) if shared_parts else ""

    async def _log_message_to_shared(self, message: Message, channel: ChannelPlugin):
        """Log ALL messages to shared context for auto-save."""
        # Skip empty messages
        if not message.content:
            return

        # Skip bot messages (to avoid duplicate logging)
        if message.role.value == "assistant":
            return

        # Log to shared log file
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.shared_memory_dir / "logs" / f"{today}.md"

        # Ensure directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Prepare log entry
        time_str = datetime.fromtimestamp(message.timestamp).strftime("%H:%M")
        user_name = message.username
        content_preview = message.content[:200] + "..." if len(message.content) > 200 else message.content

        log_entry = f"\n### [{time_str}] {user_name}\n{content_preview}\n"

        # Append to log file
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
            logger.debug(f"Logged message to {log_file}")
        except Exception as e:
            logger.debug(f"Could not log message: {e}")

        # Also log to database
        try:
            from memory_share import share_memory
            share_memory(
                bot_name="gateway",
                content=content_preview,
                visibility="public",
                tags=f"channel:{message.channel_id},user:{user_name}",
                channel_id=message.channel_id
            )
            logger.debug("Logged message to shared memory database")
        except Exception as e:
            logger.debug(f"Could not log to database: {e}")

    async def _log_to_shared_context(self, message: Message, response: str, channel: ChannelPlugin):
        """Log important interactions to shared context."""
        # Skip ack-only responses
        if len(response) < 20 or response in ["收到", "在的", "好的", "明白"]:
            return

        # Skip if message is from another bot (bot-to-bot coordination)
        if message.role.value == "assistant":
            return

        # Log to shared log file
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.shared_memory_dir / "logs" / f"{today}.md"

        # Ensure directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Prepare log entry
        time_str = datetime.now().strftime("%H:%M")
        user_name = message.username
        response_preview = response[:100] + "..." if len(response) > 100 else response

        log_entry = f"\n### [{time_str}] {user_name} → Gateway\n- **内容**: {response_preview}\n"

        # Append to log file
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.debug(f"Could not write to shared log: {e}")

        # Also log to database for cross-Bot querying
        try:
            from memory_share import share_memory
            share_memory(
                bot_name="gateway",
                content=response_preview,
                visibility="public",
                tags=f"channel:{message.channel_id}",
                channel_id=message.channel_id
            )
            logger.debug("Logged to shared memory database")
        except Exception as e:
            logger.debug(f"Could not log to shared memory database: {e}")


async def main():
    import os

    parser = argparse.ArgumentParser(description="Phoenix Core Gateway v2")
    parser.add_argument("--workspace", "-w", type=str, help="Workspace directory")
    parser.add_argument("--platform", type=str, default=None, help="Platform (discord, feishu, etc.)")
    parser.add_argument("--no-dashboard", action="store_true", help="Disable Dashboard API")
    args = parser.parse_args()

    workspace = Path(args.workspace) if args.workspace else Path.cwd() / "phx-workspace"

    # ====== 平台适配器模式：从环境变量加载配置 ======
    platform = args.platform or os.environ.get("PLATFORM", "discord").lower()
    platform_channel = None

    if platform:
        from phoenix_core.message_channel import get_channel

        if platform == "discord":
            token = os.environ.get("DISCORD_BOT_TOKEN")
            channel_id = os.environ.get("DISCORD_CHANNEL_ID")
            if token:
                platform_channel = get_channel("discord", token=token, channel_id=channel_id)
                logger.info(f"使用 Discord 平台适配器")
        elif platform == "feishu":
            from phoenix_core.feishu_channel import create_feishu_channel
            platform_channel = create_feishu_channel()
            if platform_channel:
                logger.info(f"使用Feishu平台适配器")

        if not platform_channel:
            logger.warning(f"平台 {platform} 配置不完整，使用默认 ChannelManager 模式")

    # =====================================================

    gateway = PhoenixCoreGateway(workspace=str(workspace), channel=platform_channel)

    # Setup signal handlers
    import signal
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal")
        stop_event.set()

    # Windows 不支持信号处理
    # for sig in (signal.SIGINT, signal.SIGTERM):
    #     loop.add_signal_handler(sig, signal_handler)  # Windows not supported

    # Initialize and start
    await gateway.initialize()
    await gateway.start()

    # Register as global gateway if this is the controller bot (小小谦)
    if gateway._is_controller:
        set_global_gateway(gateway)
        logger.info("协调员 Bot 已注册为全局 Gateway")

        # Start embedded Dashboard API (Coordinator Bot 才需要)
        if not args.no_dashboard:
            await start_embedded_dashboard(gateway)

    logger.info("Gateway is running. Press Ctrl+C to stop.")

    # Wait for shutdown signal
    await stop_event.wait()

    await gateway.stop()
    logger.info("Gateway stopped")


# ============ 全局 Gateway 单例 ============

_global_gateway: Optional["PhoenixCoreGateway"] = None


def set_global_gateway(gateway: "PhoenixCoreGateway"):
    """设置全局 Gateway 实例（由协调员 Bot 调用）"""
    global _global_gateway
    _global_gateway = gateway
    logger.info(f"全局 Gateway 已注册：{gateway.bot_name}")


def get_gateway_instance() -> Optional["PhoenixCoreGateway"]:
    """获取全局 Gateway 实例"""
    return _global_gateway


# ============ 内嵌 Dashboard API ============

async def start_embedded_dashboard(gateway: "PhoenixCoreGateway"):
    """
    Starting内嵌的 Dashboard API Server

    Coordinator Bot 专用：将大脑和 Gateway 注入到 Dashboard API 中
    """
    import uvicorn
    from phoenix_core.api_server import create_app

    # 创建 FastAPI 应用，传入大脑和 Gateway 实例
    app = create_app(
        brain=gateway.brain,
        gateway=gateway,
        project_dir=str(Path(__file__).parent.parent)
    )

    # 配置 uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="info")
    server = uvicorn.Server(config)

    # 在后台Task中Starting
    asyncio.create_task(server.serve())

    # 等待ServerStarting
    await asyncio.sleep(2)

    logger.info("=" * 60)
    logger.info("Dashboard API 已Starting:")
    logger.info("  URL: http://localhost:8001")
    logger.info("  端点:")
    logger.info("    GET  /           - 欢迎页")
    logger.info("    GET  /health     - 健康检查")
    logger.info("    POST /api/chat   - 与大脑对话")
    logger.info("    GET  /api/bots   - Bot 列表")
    logger.info("    GET  /api/tasks  - Task列表")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
