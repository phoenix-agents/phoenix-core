#!/usr/bin/env python3
"""
Phoenix Core Launcher - 自动 Bot 识别和启动器

功能:
1. 扫描 workspaces/目录，自动确定协调者 Bot
2. 为每个 Bot 加载配置和 SOUL.md
3. 启动 Gateway 进程（包含大脑和 Dashboard API）

新用户只需：
1. 创建 workspaces/{bot_name}/ 目录
2. 放入 .env 文件（包含 DISCORD_BOT_TOKEN）
3. 运行：python3 phoenix_core_gateway_v2.py
"""

import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


def find_coordinator_bot(workspaces_dir: str = "workspaces") -> Optional[Dict]:
    """
    扫描 workspaces/目录，按以下规则确定协调者：
    1. 优先查找 .env 中显式设置 IS_CONTROLLER=true 的 Bot
    2. 如果没有，则选择按名称排序后的第一个 Bot 作为协调者
    3. 如果 workspaces/目录为空，返回 None

    Args:
        workspaces_dir: 工作区目录路径

    Returns:
        协调者 Bot 信息 dict，包含 folder, bot_name, config 等
        如果没有找到，返回 None
    """
    workspaces_path = Path(workspaces_dir)
    if not workspaces_path.exists():
        logger.warning(f"工作区目录不存在：{workspaces_path}")
        return None

    bot_folders = [f for f in workspaces_path.iterdir() if f.is_dir()]
    if not bot_folders:
        logger.warning(f"工作区目录为空：{workspaces_path}")
        return None

    # 优先查找显式声明的协调者（IS_CONTROLLER=true）
    for folder in bot_folders:
        env_file = folder / ".env"
        if env_file.exists():
            env_content = env_file.read_text(encoding="utf-8")
            if "IS_CONTROLLER=true" in env_content:
                config = _load_bot_config(folder)
                logger.info(f"找到显式声明的协调者 Bot: {config.get('bot_name', folder.name)}")
                return {
                    "folder": folder.name,
                    "bot_name": config.get("bot_name", folder.name),
                    "config": config,
                    "is_controller": True
                }

    # 没有显式声明，选择字母序第一个作为默认协调者
    first_folder = sorted(bot_folders, key=lambda x: x.name)[0]
    config = _load_bot_config(first_folder)

    logger.info(f"自动选择协调者 Bot: {config.get('bot_name', first_folder.name)}")

    return {
        "folder": first_folder.name,
        "bot_name": config.get("bot_name", first_folder.name),
        "config": config,
        "is_controller": True
    }


def _load_bot_config(folder: Path) -> Dict:
    """
    加载 Bot 配置

    优先级：
    1. config.yaml（如果存在）
    2. .env 文件解析
    3. 默认配置
    """
    config = {
        "bot_name": folder.name,
        "bot_model": "qwen3.6-plus",
        "bot_provider": "coding-plan",
        "is_controller": False
    }

    # 尝试加载 config.yaml
    config_file = folder / "config.yaml"
    if config_file.exists():
        try:
            yaml_config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
            if yaml_config:
                config.update(yaml_config)
        except Exception as e:
            logger.warning(f"加载 config.yaml 失败：{e}")

    # 尝试从.env 文件补充配置
    env_file = folder / ".env"
    if env_file.exists():
        env_content = env_file.read_text(encoding="utf-8")
        for line in env_content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # 映射常见配置项
                if key == "BOT_NAME":
                    config["bot_name"] = value
                elif key == "BOT_MODEL":
                    config["bot_model"] = value
                elif key == "BOT_PROVIDER":
                    config["bot_provider"] = value
                elif key == "IS_CONTROLLER":
                    config["is_controller"] = value.lower() == "true"

    return config


def list_all_bots(workspaces_dir: str = "workspaces") -> List[Dict]:
    """
    列出所有可用的 Bot

    Returns:
        Bot 信息列表
    """
    workspaces_path = Path(workspaces_dir)
    if not workspaces_path.exists():
        return []

    bots = []
    for folder in workspaces_path.iterdir():
        if not folder.is_dir():
            continue

        config = _load_bot_config(folder)
        bots.append({
            "folder": folder.name,
            "bot_name": config.get("bot_name", folder.name),
            "config": config
        })

    return bots


def get_bot_env_file(bot_name: str, workspaces_dir: str = "workspaces") -> Optional[Path]:
    """
    获取指定 Bot 的.env 文件路径

    Args:
        bot_name: Bot 名称
        workspaces_dir: 工作区目录

    Returns:
        .env 文件路径，如果不存在返回 None
    """
    workspaces_path = Path(workspaces_dir)
    bot_folder = workspaces_path / bot_name
    env_file = bot_folder / ".env"

    if env_file.exists():
        return env_file

    return None


# 便捷函数
def get_first_bot(workspaces_dir: str = "workspaces") -> Optional[Dict]:
    """获取第一个可用的 Bot（用于快速启动）"""
    bots = list_all_bots(workspaces_dir)
    return bots[0] if bots else None


def is_controller_bot(bot_name: str, workspaces_dir: str = "workspaces") -> bool:
    """判断指定 Bot 是否是协调者"""
    bots = list_all_bots(workspaces_dir)
    for bot in bots:
        if bot["bot_name"] == bot_name:
            return bot["config"].get("is_controller", False)
    return False
