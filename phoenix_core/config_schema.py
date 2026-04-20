#!/usr/bin/env python3
"""
Phoenix Core Config Schema - Pydantic 配置模型

用于验证配置文件的 schema，启动时验证确保数据有效性

Usage:
    from phoenix_core.config_schema import BotConfig, validate_config

    # 验证 Bot 配置
    config = BotConfig.model_validate(raw_data)

    # 验证整个系统配置
    system_config = SystemConfig.model_validate(config_dict)
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class BotModelConfig(BaseModel):
    """单个 Bot 的模型配置"""
    model: str = Field(..., description="模型名称，如 qwen3.5-plus")
    provider: str = Field(..., description="Provider 名称，如 coding-plan")
    role: str = Field(default="assistant", description="Bot 角色")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v):
        valid_providers = ["coding-plan", "compshare", "moonshot", "openai", "anthropic"]
        if v not in valid_providers and not v.startswith("custom-"):
            raise ValueError(f"Provider 必须是 {valid_providers} 之一或以 custom- 开头")
        return v


class ProviderConfig(BaseModel):
    """Provider 配置"""
    enabled: bool = Field(default=True, description="是否启用")
    api_key_env: Optional[str] = Field(default=None, description="API Key 环境变量名")
    base_url: Optional[str] = Field(default=None, description="API 基础 URL")


class ChannelCredentials(BaseModel):
    """渠道凭证"""
    bot_token: Optional[str] = Field(default=None, description="Bot Token")
    client_id: Optional[str] = Field(default=None, description="Client ID")
    corp_id: Optional[str] = Field(default=None, description="企业 ID")
    secret: Optional[str] = Field(default=None, description="密钥")
    # 支持任意额外的凭证字段
    class Config:
        extra = "allow"


class ChannelConfig(BaseModel):
    """渠道配置"""
    enabled: bool = Field(default=False, description="是否启用")
    name: Optional[str] = Field(default=None, description="渠道显示名称")
    credentials: Dict[str, Any] = Field(default_factory=dict, description="凭证")
    settings: Dict[str, Any] = Field(default_factory=dict, description="设置")
    dm_policy: str = Field(default="pairing", description="私聊策略：open/pairing/closed")
    allow_from: List[str] = Field(default_factory=list, description="允许的用户白名单")
    deny_from: List[str] = Field(default_factory=list, description="拒绝的用户黑名单")

    @field_validator("dm_policy")
    @classmethod
    def validate_dm_policy(cls, v):
        if v not in ["open", "pairing", "closed"]:
            raise ValueError("dm_policy 必须是 open/pairing/closed 之一")
        return v


class AdvancedConfig(BaseModel):
    """高级配置"""
    workspace_dir: Optional[str] = Field(default="./workspaces", description="工作空间目录")
    shared_memory_dir: Optional[str] = Field(default="./shared_memory", description="共享记忆目录")
    log_level: str = Field(default="INFO", description="日志级别")
    heartbeat_interval: int = Field(default=30, description="心跳间隔 (秒)")


class SystemConfig(BaseModel):
    """系统完整配置"""
    version: str = Field(..., description="配置版本")
    generated_at: str = Field(..., description="生成时间 ISO 格式")
    providers: Dict[str, ProviderConfig] = Field(default_factory=dict, description="Provider 配置")
    bots: Dict[str, BotModelConfig] = Field(default_factory=dict, description="Bot 配置")
    channels: Dict[str, ChannelConfig] = Field(default_factory=dict, description="渠道配置")
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig, description="高级配置")

    @field_validator("version")
    @classmethod
    def validate_version(cls, v):
        if not v:
            raise ValueError("version 不能为空")
        return v


# 便捷验证函数
def validate_bot_config(bot_name: str, bot_data: dict) -> tuple[bool, str]:
    """
    验证单个 Bot 配置

    Returns:
        (是否有效，错误信息)
    """
    try:
        BotModelConfig.model_validate(bot_data)
        return True, ""
    except Exception as e:
        return False, f"Bot '{bot_name}' 配置无效：{e}"


def validate_system_config(config_data: dict) -> tuple[bool, str]:
    """
    验证系统完整配置

    Returns:
        (是否有效，错误信息)
    """
    try:
        SystemConfig.model_validate(config_data)
        return True, ""
    except Exception as e:
        return False, f"系统配置无效：{e}"
