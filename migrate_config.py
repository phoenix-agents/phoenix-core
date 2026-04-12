#!/usr/bin/env python3
"""
Phoenix Core Configuration Migrator

Migrates existing Phoenix Core Gateway config to Phoenix Core multi-bot setup.

Key insight: Phoenix Core used a SINGLE Discord Bot Token via Phoenix Core Gateway,
not 8 separate tokens. All 8 agents share the same Discord bot.

Usage:
    python3 migrate_config.py  # Migrate existing config
"""

import json
import logging
import shutil
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

HERMES_HOME = Path.home() / ".phoenix"
PHOENIX_CORE_DIR = Path(__file__).parent
WORKSPACES_DIR = PHOENIX_CORE_DIR / "workspaces"


def check_phoenix_config() -> bool:
    """Check if Phoenix Core config exists."""
    phoenix_env = HERMES_HOME / ".env"
    phoenix_config = HERMES_HOME / "config.yaml"

    if not phoenix_env.exists():
        logger.warning(f"Phoenix Core .env not found: {phoenix_env}")
        return False

    if not phoenix_config.exists():
        logger.warning(f"Phoenix Core config.yaml not found: {phoenix_config}")
        return False

    # Check for Discord token
    with open(phoenix_env, "r") as f:
        content = f.read()

    if "DISCORD_BOT_TOKEN" in content or "DISCORD_TOKEN" in content:
        if "YOUR_TOKEN_HERE" not in content and "YOUR_DISCORD" not in content:
            logger.info("Found valid Discord token in Phoenix Core config")
            return True

    logger.warning("Discord token not configured in Phoenix Core")
    return False


def migrate_to_phoenix_core():
    """Migrate Phoenix Core config to Phoenix Core."""
    logger.info("Starting Phoenix Core configuration migration...")

    # 1. Check existing Phoenix Core config
    if not check_phoenix_config():
        logger.info("No existing Discord config found.")
        logger.info("Please configure Phoenix Core Gateway first:")
        logger.info("  1. Get Discord Bot Token from https://discord.com/developers/applications")
        logger.info("  2. Edit ~/.phoenix/.env and set DISCORD_BOT_TOKEN")
        logger.info("  3. Run this script again")
        return

    # 2. Copy Phoenix Core .env to Phoenix Core
    phoenix_env = HERMES_HOME / ".env"
    phoenix_core_env = PHOENIX_CORE_DIR / ".env"

    shutil.copy(phoenix_env, phoenix_core_env)
    logger.info(f"Copied Phoenix Core config to Phoenix Core: {phoenix_core_env}")

    # 3. Create shared config for all bots
    # In Phoenix Core, all bots share the same Discord connection
    # but have independent workspaces and memory

    shared_config = {
        "discord": {
            "enabled": True,
            "require_mention": False,
            "allow_all_users": True
        },
        "gateway": {
            "mode": "local",
            "platforms": ["discord"]
        },
        "bots": {
            "编导": {"workspace": "workspaces/编导", "model": "deepseek-ai/DeepSeek-V3.2"},
            "剪辑": {"workspace": "workspaces/剪辑", "model": "gpt-5.1"},
            "美工": {"workspace": "workspaces/美工", "model": "gpt-5.1"},
            "场控": {"workspace": "workspaces/场控", "model": "claude-haiku-4-5-20251001"},
            "客服": {"workspace": "workspaces/客服", "model": "qwen3.5-plus"},
            "运营": {"workspace": "workspaces/运营", "model": "claude-sonnet-4-6"},
            "渠道": {"workspace": "workspaces/渠道", "model": "gpt-5.1"},
            "小小谦": {"workspace": "workspaces/小小谦", "model": "kimi-k2.5"},
        }
    }

    config_file = PHOENIX_CORE_DIR / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(shared_config, f, indent=2, ensure_ascii=False)

    logger.info(f"Created Phoenix Core config: {config_file}")

    # 4. Verify workspaces
    for bot_name in shared_config["bots"].keys():
        workspace = WORKSPACES_DIR / bot_name
        if workspace.exists():
            logger.info(f"✓ Workspace exists: {workspace}")
        else:
            logger.warning(f"✗ Workspace missing: {workspace}")

    logger.info("=" * 60)
    logger.info("Migration complete!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Start Bot Manager: python3 bot_manager.py start")
    logger.info("2. Start Dashboard: python3 bot_dashboard.py --port 4321")
    logger.info("3. Access Dashboard: http://localhost:4321")
    logger.info("")


if __name__ == "__main__":
    migrate_to_phoenix_core()
