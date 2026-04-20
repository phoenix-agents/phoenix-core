#!/usr/bin/env python3
"""
Phoenix Core - 核心工具库

包含:
- atomic_writer: 原子写入工具
- config_schema: Pydantic 配置验证
- heartbeat / heartbeat_v2 / heartbeat_cache: 心跳监控 (v2 独立文件，cache 内存缓存)
- api_validator: Flask/FastAPI 路由 Pydantic 校验装饰器
- api_schemas: Pydantic 请求模型基类 (8 Bot 优化)
- memory_db: SQLite 记忆存储加固 (WAL + 事务 + 备份)
- memory_encryption: 记忆备份加密 (GPG 对称加密)
"""

from .atomic_writer import atomic_write_file, atomic_json_dump, atomic_env_write, AtomicWriter
from .heartbeat import HeartbeatSender, HeartbeatMonitor, check_health, send_heartbeat_once
from .heartbeat_v2 import (
    write_heartbeat,
    read_all_heartbeats,
    get_bot_health,
    get_all_bots_health,
    get_healthy_bots,
    get_unhealthy_bots,
    cleanup_stale_heartbeats,
    delete_bot_heartbeat,
    HeartbeatManager,
)
from .heartbeat_cache import (
    HeartbeatCache,
    update_heartbeat,
    get_bot_health as cache_get_bot_health,
    get_all_bots_health as cache_get_all_bots_health,
)

# API Validator (可选，需要 Flask)
try:
    from .api_validator import validate_request as flask_validate_request, validate_request_async
    API_VALIDATOR_AVAILABLE = True
except ImportError:
    API_VALIDATOR_AVAILABLE = False
    flask_validate_request = None
    validate_request_async = None

# FastAPI Validator (原生支持)
try:
    from .fastapi_validator import validate_request
    FASTAPI_VALIDATOR_AVAILABLE = True
except ImportError:
    FASTAPI_VALIDATOR_AVAILABLE = False
    validate_request = None

# 便捷模型 (8 Bot 优化 - 抽取基类)
try:
    from .api_schemas import (
        BotIdRequest,
        BotActionRequest,
        StartBotRequest,
        StopBotRequest,
        RestartBotRequest,
        SendMessageRequest,
        GetBotInfoRequest,
        CreateTaskRequest,
        UpdateTaskRequest,
        DeleteTaskRequest,
        GetConfigRequest,
        UpdateConfigRequest,
        GetBotHealthRequest,
        HeartbeatResponse,
        SuccessResponse,
        ErrorResponse,
    )
except ImportError:
    pass

# 记忆数据库 (SQLite 加固)
try:
    from .memory_db import (
        MemoryDatabase,
        get_memory_db,
        safe_memory_write,
        save_conversation,
        get_recent_memory,
        backup_memory_db,
        restore_latest_backup,
        cleanup_old_backups,
        start_backup_scheduler,
    )
except ImportError:
    pass

# 记忆加密 (可选，需要 GPG)
try:
    from .memory_encryption import (
        encrypt_backup,
        decrypt_backup,
        backup_and_encrypt,
        decrypt_and_restore,
        check_gpg_available,
    )
except ImportError:
    pass

# Link Tracing (P1 - 链路追踪)
try:
    from .link_tracing import (
        LinkTracer,
        Span,
        SpanStatus,
        get_tracer,
        trace_operation,
        start_trace,
        get_trace_timeline,
    )
except ImportError:
    pass

# Audit Logger (P1 - 审计日志)
try:
    from .audit_logger import (
        AuditLogger,
        AuditEntry,
        get_audit_logger,
        log_message,
        log_operation,
        log_error,
        log_alert,
    )
except ImportError:
    pass

# Progress Reporter (P1 - 进度汇报)
try:
    from .progress_reporter import (
        ProgressReporter,
        TaskProgress,
        SubTaskProgress,
        ProgressStatus,
        get_progress_reporter,
        create_progress,
        update_progress,
        get_progress_summary,
    )
except ImportError:
    pass

# Audit API (Web 面板 - 可选，需要 FastAPI)
try:
    from .audit_api import app as audit_web_app
    AUDIT_WEB_AVAILABLE = True
except ImportError:
    AUDIT_WEB_AVAILABLE = False

# 可选导入（需要 pydantic）
try:
    from .config_schema import (
        BotModelConfig,
        ProviderConfig,
        ChannelConfig,
        AdvancedConfig,
        SystemConfig,
        validate_bot_config,
        validate_system_config,
    )
    CONFIG_SCHEMA_AVAILABLE = True
except ImportError:
    CONFIG_SCHEMA_AVAILABLE = False

__version__ = "2.0.0"  # v6.0 架构 - 新增主大脑 (CoreBrain)

# 主大脑 (v6.0 新增)
try:
    from .core_brain import (
        CoreBrain,
        BrainConfig,
        BrainResponse,
        get_brain,
        process_input,
    )
    CORE_BRAIN_AVAILABLE = True
except ImportError:
    CORE_BRAIN_AVAILABLE = False

__all__ = [
    # Core Brain (v6.0 新增 - 主大脑)
    "CoreBrain",
    "BrainConfig",
    "BrainResponse",
    "get_brain",
    "process_input",
    "CORE_BRAIN_AVAILABLE",
    # Atomic writer
    "atomic_write_file",
    "atomic_json_dump",
    "atomic_env_write",
    "AtomicWriter",
    # Heartbeat (v1 - 单文件模式)
    "HeartbeatSender",
    "HeartbeatMonitor",
    "check_health",
    "send_heartbeat_once",
    # Heartbeat (v2 - 独立文件模式，推荐)
    "write_heartbeat",
    "read_all_heartbeats",
    "get_bot_health",
    "get_all_bots_health",
    "get_healthy_bots",
    "get_unhealthy_bots",
    "cleanup_stale_heartbeats",
    "delete_bot_heartbeat",
    "HeartbeatManager",
    # Heartbeat (v3 - 内存缓存，50+ Bot 场景)
    "HeartbeatCache",
    "update_heartbeat",
    "cache_get_bot_health",
    "cache_get_all_bots_health",
    # Link Tracing (P1 - 链路追踪)
    "LinkTracer",
    "Span",
    "SpanStatus",
    "get_tracer",
    "trace_operation",
    "start_trace",
    "get_trace_timeline",
    # Audit Logger (P1 - 审计日志)
    "AuditLogger",
    "AuditEntry",
    "get_audit_logger",
    "log_message",
    "log_operation",
    "log_error",
    "log_alert",
    # Progress Reporter (P1 - 进度汇报)
    "ProgressReporter",
    "TaskProgress",
    "SubTaskProgress",
    "ProgressStatus",
    "get_progress_reporter",
    "create_progress",
    "update_progress",
    "get_progress_summary",
    # API Validator (可选)
    "API_VALIDATOR_AVAILABLE",
    "FASTAPI_VALIDATOR_AVAILABLE",
    # Audit Web Panel (可选)
    "AUDIT_WEB_AVAILABLE",
    # Intent Recognition (v5.0 新增)
    "IntentRecognizer",
    "Intent",
    "recognize_intent",
    # Protocol Generator (v5.0 新增)
    "ProtocolGenerator",
    "generate_protocol",
    # Protocol Parser (v5.0 新增)
    "ProtocolParser",
    "ProtocolMessage",
    "parse_protocol",
    "is_termination",
    # Task Tracker (v5.0 新增)
    "TaskTracker",
    "Task",
    "TaskStatus",
    "get_tracker",
    # Result Aggregator (v5.0 新增)
    "ResultAggregator",
    "SimpleAggregator",
    "aggregate_response",
    # Intent Router (v5.0 新增)
    "IntentRouter",
    "get_router",
    "route_message",
    # Orchestrator (v5.0 新增)
    "Orchestrator",
    "OrchestratorConfig",
    "get_orchestrator",
]

if API_VALIDATOR_AVAILABLE:
    __all__.extend([
        "flask_validate_request",
        "validate_request_async",
    ])

if FASTAPI_VALIDATOR_AVAILABLE:
    __all__.extend([
        "validate_request",
    ])

# Memory DB (SQLite 加固)
__all__.extend([
    "MemoryDatabase",
    "get_memory_db",
    "safe_memory_write",
    "save_conversation",
    "get_recent_memory",
    "backup_memory_db",
    "restore_latest_backup",
    "cleanup_old_backups",
    "start_backup_scheduler",
])

# Memory Encryption (可选)
__all__.extend([
    "encrypt_backup",
    "decrypt_backup",
    "backup_and_encrypt",
    "decrypt_and_restore",
    "check_gpg_available",
])

# Config schema (optional)
__all__.append("CONFIG_SCHEMA_AVAILABLE")

if CONFIG_SCHEMA_AVAILABLE:
    __all__.extend([
        "BotModelConfig",
        "ProviderConfig",
        "ChannelConfig",
        "AdvancedConfig",
        "SystemConfig",
        "validate_bot_config",
        "validate_system_config",
    ])

# Intent Recognition (v5.0)
try:
    from .intent_recognition import (
        IntentRecognizer,
        Intent,
        recognize_intent,
    )
except ImportError:
    pass

# Protocol Generator (v5.0)
try:
    from .protocol_generator import (
        ProtocolGenerator,
        generate_protocol,
    )
except ImportError:
    pass

# Protocol Parser (v5.0)
try:
    from .protocol_parser import (
        ProtocolParser,
        ProtocolMessage,
        parse_protocol,
        is_termination,
    )
except ImportError:
    pass

# Task Tracker (v5.0)
try:
    from .task_tracker import (
        TaskTracker,
        Task,
        TaskStatus,
        get_tracker,
    )
except ImportError:
    pass

# Result Aggregator (v5.0)
try:
    from .result_aggregator import (
        ResultAggregator,
        SimpleAggregator,
        aggregate_response,
    )
except ImportError:
    pass

# Intent Router (v5.0)
try:
    from .intent_router import (
        IntentRouter,
        get_router,
        route_message,
    )
except ImportError:
    pass

# Orchestrator (v5.0)
try:
    from .orchestrator import (
        Orchestrator,
        OrchestratorConfig,
        get_orchestrator,
    )
except ImportError:
    pass
