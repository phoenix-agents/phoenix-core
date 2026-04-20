#!/usr/bin/env python3
"""
Channel Config Loader - 渠道配置加载器

从 YAML 文件加载渠道配置

Usage:
    from channels.config_loader import load_channel_configs

    configs = load_channel_configs("workspaces/运营/channels.yaml")
    for config in configs:
        print(f"Channel: {config.id}, Enabled: {config.enabled}")
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import yaml
except ImportError:
    yaml = None
    logging.warning("PyYAML not installed, using JSON config only")
    import json

from .base import ChannelConfig

logger = logging.getLogger(__name__)


def load_channel_configs(config_path: str) -> List[ChannelConfig]:
    """
    从配置文件加载渠道配置

    支持格式:
    - YAML (.yaml, .yml)
    - JSON (.json)

    Args:
        config_path: 配置文件路径

    Returns:
        ChannelConfig 列表
    """
    path = Path(config_path)

    if not path.exists():
        logger.warning(f"Config file not found: {config_path}")
        return []

    if path.suffix in [".yaml", ".yml"]:
        if yaml is None:
            logger.error("PyYAML not installed, cannot load YAML config")
            return []
        return _load_yaml_config(path)
    elif path.suffix == ".json":
        return _load_json_config(path)
    else:
        logger.error(f"Unsupported config format: {path.suffix}")
        return []


def _load_yaml_config(path: Path) -> List[ChannelConfig]:
    """加载 YAML 配置"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return _parse_config_data(data, str(path))


def _load_json_config(path: Path) -> List[ChannelConfig]:
    """加载 JSON 配置"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return _parse_config_data(data, str(path))


def _parse_config_data(data: Dict[str, Any], source: str) -> List[ChannelConfig]:
    """解析配置数据"""
    configs = []

    channels_data = data.get("channels", {})

    for channel_id, channel_config in channels_data.items():
        if not isinstance(channel_config, dict):
            logger.warning(f"Invalid config for channel {channel_id}")
            continue

        enabled = channel_config.get("enabled", False)
        if not enabled:
            logger.info(f"Channel {channel_id} is disabled, skipping")
            continue

        # 提取凭证
        credentials = channel_config.get("credentials", {})

        # 提取设置
        settings = channel_config.get("settings", {})

        # 提取安全设置
        dm_policy = channel_config.get("dm_policy", "pairing")
        allow_from = channel_config.get("allow_from", [])
        deny_from = channel_config.get("deny_from", [])

        # 获取显示名称
        name = channel_config.get("name", channel_id.title())

        config = ChannelConfig(
            id=channel_id,
            name=name,
            enabled=enabled,
            credentials=credentials,
            settings=settings,
            dm_policy=dm_policy,
            allow_from=allow_from,
            deny_from=deny_from,
        )

        configs.append(config)
        logger.info(f"Loaded config for channel: {channel_id}")

    return configs


def create_default_config(
    channel_id: str,
    bot_name: str,
    config_dir: Optional[Path] = None,
) -> ChannelConfig:
    """
    创建默认渠道配置

    Args:
        channel_id: 渠道 ID
        bot_name: Bot 名称
        config_dir: 配置目录

    Returns:
        ChannelConfig
    """
    if config_dir is None:
        config_dir = Path(f"workspaces/{bot_name}")

    # Worker Bots need allow_bots=True to receive ASK messages from controller
    worker_bots = {"场控", "运营", "渠道", "美工", "编导", "剪辑", "客服"}
    allow_bots_default = bot_name in worker_bots

    # 根据渠道 ID 设置默认值
    defaults = {
        "discord": {
            "name": "Discord",
            "credentials": {
                "bot_token": "${DISCORD_BOT_TOKEN}",
                "client_id": "${DISCORD_CLIENT_ID}",
            },
            "settings": {
                "allow_bots": allow_bots_default,
            },
            "dm_policy": "pairing",
        },
        "wechat": {
            "name": "企业微信",
            "credentials": {
                "corp_id": "${WECHAT_CORP_ID}",
                "secret": "${WECHAT_SECRET}",
                "token": "${WECHAT_TOKEN}",
                "aes_key": "${WECHAT_AES_KEY}",
                "agent_id": "${WECHAT_AGENT_ID}",
            },
            "settings": {},
            "dm_policy": "closed",
        },
        "telegram": {
            "name": "Telegram",
            "credentials": {
                "bot_token": "${TELEGRAM_BOT_TOKEN}",
            },
            "settings": {},
            "dm_policy": "open",
        },
    }

    default = defaults.get(channel_id, {
        "name": channel_id.title(),
        "credentials": {},
        "settings": {},
        "dm_policy": "pairing",
    })

    return ChannelConfig(
        id=channel_id,
        name=default["name"],
        enabled=True,
        credentials=default["credentials"],
        settings=default["settings"],
        dm_policy=default["dm_policy"],
    )


def save_config(config: ChannelConfig, save_path: Path) -> bool:
    """
    保存配置到文件

    Args:
        config: 渠道配置
        save_path: 保存路径

    Returns:
        是否保存成功
    """
    data = {
        "channels": {
            config.id: config.to_dict(),
        }
    }

    save_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if save_path.suffix in [".yaml", ".yml"]:
            if yaml is None:
                logger.error("PyYAML not installed")
                return False
            with open(save_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)
        else:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Config saved to {save_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False


def get_env_var_name(channel_id: str, key: str) -> str:
    """生成环境变量名"""
    prefix_map = {
        "discord": "DISCORD",
        "wechat": "WECHAT",
        "telegram": "TELEGRAM",
        "slack": "SLACK",
        "dingtalk": "DINGTALK",
        "feishu": "FEISHU",
    }
    prefix = prefix_map.get(channel_id, channel_id.upper())
    return f"{prefix}_{key.upper()}"
