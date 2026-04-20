#!/usr/bin/env python3
"""
Phoenix Core API Schemas - Pydantic 请求模型基类

8 个 Bot 场景下，抽取公共字段，避免重复定义

Usage:
    from phoenix_core.api_schemas import BotIdRequest, BotActionRequest

    class StopBotRequest(BotIdRequest):
        pass

    class SendMessageRequest(BotIdRequest):
        message: str
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


# ========== 基础请求模型 ==========

class BotIdRequest(BaseModel):
    """Bot ID 基础请求"""
    bot_id: str = Field(..., description="Bot 名称 (如：客服，运营，编导)")


class BotActionRequest(BotIdRequest):
    """Bot 动作请求"""
    action: str = Field(..., description="动作类型", examples=["start", "stop", "restart"])


# ========== Bot 管理相关 ==========

class StartBotRequest(BotActionRequest):
    """启动 Bot 请求"""
    action: str = "start"
    config_override: Optional[Dict[str, Any]] = Field(default=None, description="配置覆盖")


class StopBotRequest(BotActionRequest):
    """停止 Bot 请求"""
    action: str = "stop"
    force: bool = Field(default=False, description="是否强制停止")


class RestartBotRequest(BotActionRequest):
    """重启 Bot 请求"""
    action: str = "restart"
    graceful: bool = Field(default=True, description="是否优雅重启")


class SendMessageRequest(BotIdRequest):
    """发送消息请求"""
    channel_id: str = Field(..., description="频道/聊天室 ID")
    message: str = Field(..., description="消息内容")
    message_type: str = Field(default="text", description="消息类型：text/image/file")


class GetBotInfoRequest(BotIdRequest):
    """获取 Bot 信息请求"""
    include_logs: bool = Field(default=False, description="是否包含日志")
    include_memory: bool = Field(default=False, description="是否包含记忆")
    log_limit: int = Field(default=50, description="日志条数限制")


# ========== 任务相关 ==========

class CreateTaskRequest(BaseModel):
    """创建任务请求"""
    title: str = Field(..., description="任务标题")
    description: str = Field(..., description="任务描述")
    assigned_to: Optional[str] = Field(default=None, description="分配给哪个 Bot")
    priority: str = Field(default="normal", description="优先级：low/normal/high/urgent")
    tags: List[str] = Field(default_factory=list, description="标签列表")


class UpdateTaskRequest(BaseModel):
    """更新任务请求"""
    task_id: str = Field(..., description="任务 ID")
    title: Optional[str] = Field(default=None, description="新标题")
    description: Optional[str] = Field(default=None, description="新描述")
    status: Optional[str] = Field(default=None, description="新状态")
    assigned_to: Optional[str] = Field(default=None, description="新的负责人")


class DeleteTaskRequest(BaseModel):
    """删除任务请求"""
    task_id: str = Field(..., description="任务 ID")


# ========== 配置管理相关 ==========

class GetConfigRequest(BaseModel):
    """获取配置请求"""
    bot_id: Optional[str] = Field(default=None, description="Bot 名称，为 None 则获取全局配置")
    section: Optional[str] = Field(default=None, description="配置段落")


class UpdateConfigRequest(BaseModel):
    """更新配置请求"""
    bot_id: Optional[str] = Field(default=None, description="Bot 名称，为 None 则更新全局配置")
    section: str = Field(..., description="配置段落")
    key: str = Field(..., description="配置键")
    value: Any = Field(..., description="配置值")


# ========== 心跳/健康相关 ==========

class GetBotHealthRequest(BotIdRequest):
    """获取 Bot 健康状态"""
    include_memory: bool = Field(default=False, description="是否包含内存信息")


class HeartbeatResponse(BaseModel):
    """心跳响应"""
    bot_id: str
    healthy: bool
    last_beat: float
    status: str
    seconds_ago: float
    extra: Optional[Dict[str, Any]] = None


# ========== 通用响应模型 ==========

class SuccessResponse(BaseModel):
    """成功响应"""
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: str
    message: str
    details: Optional[Any] = None
