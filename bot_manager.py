#!/usr/bin/env python3
"""
Phoenix Core Bot Manager

Multi-bot process manager for starting, stopping, and monitoring all 8 bots.

Usage:
    python3 bot_manager.py start      # Start all bots
    python3 bot_manager.py stop       # Stop all bots
    python3 bot_manager.py restart    # Restart all bots
    python3 bot_manager.py status     # Show bot status
    python3 bot_manager.py start 编导  # Start specific bot
    python3 bot_manager.py health     # Start health checker
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Bot configuration
BOTS = {
    "编导": {"model": "deepseek-ai/DeepSeek-V3.2", "provider": "compshare"},
    "剪辑": {"model": "gpt-5.1", "provider": "compshare"},
    "美工": {"model": "gpt-5.1", "provider": "compshare"},
    "场控": {"model": "claude-haiku-4-5-20251001", "provider": "compshare"},
    "客服": {"model": "qwen3.5-plus", "provider": "coding-plan"},
    "运营": {"model": "claude-sonnet-4-6", "provider": "compshare"},
    "渠道": {"model": "gpt-5.1", "provider": "compshare"},
    "小小谦": {"model": "kimi-k2.5", "provider": "moonshot"},
}

PID_FILE = Path("/tmp/phoenix_bots.pid.json")
PHOENIX_AGENT_DIR = Path.home() / ".phoenix" / "phoenix-agent"
PHOENIX_CORE_DIR = Path(__file__).parent
WORKSPACES_DIR = PHOENIX_CORE_DIR / "workspaces"


class BotManager:
    """Manages all bot processes."""

    def __init__(self):
        self.bots = BOTS
        self.pid_file = PID_FILE

    def _load_pids(self) -> Dict[str, int]:
        """Load bot PIDs from file."""
        if self.pid_file.exists():
            with open(self.pid_file, "r") as f:
                return json.load(f)
        return {}

    def _save_pids(self, pids: Dict[str, int]):
        """Save bot PIDs to file."""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.pid_file, "w") as f:
            json.dump(pids, f, indent=2)

    def _load_bot_env(self, bot_name: str) -> Dict[str, str]:
        """Load environment variables from bot's .env file."""
        env = os.environ.copy()
        env_file = WORKSPACES_DIR / bot_name / ".env"

        if not env_file.exists():
            logger.error(f"Bot {bot_name} .env not found: {env_file}")
            return env

        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, value = line.split("=", 1)
                        env[key.strip()] = value.strip()

        # Set PHOENIX_HOME for this bot
        env["PHOENIX_HOME"] = str(Path.home() / ".phoenix")

        return env

    def _get_bot_process(self, bot_name: str) -> Optional[subprocess.Popen]:
        """Start a bot process."""
        workspace = WORKSPACES_DIR / bot_name
        workspace.mkdir(parents=True, exist_ok=True)

        # Load environment from bot's .env file
        env = self._load_bot_env(bot_name)

        # Set additional environment
        env["PHOENIX_BOT"] = bot_name
        env["PHOENIX_WORKSPACE"] = str(workspace)

        # Start phoenix gateway for this bot
        cmd = [
            sys.executable,
            str(Path.home() / ".phoenix" / "gateway" / "run.py")
        ]

        logger.info(f"Starting bot: {bot_name} ({env.get('BOT_MODEL', 'N/A')})")

        # Create log file for this bot
        log_file = workspace / "bot.log"

        try:
            process = subprocess.Popen(
                cmd,
                env=env,
                cwd=str(Path.home() / ".phoenix"),
                stdout=open(log_file, "w"),
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            return process
        except Exception as e:
            logger.error(f"Failed to start {bot_name}: {e}")
            return None

    def start(self, bot_names: List[str] = None):
        """Start specified bots or all bots."""
        if bot_names is None:
            bot_names = list(self.bots.keys())

        pids = self._load_pids()
        started = []

        for bot_name in bot_names:
            if bot_name not in self.bots:
                logger.warning(f"Unknown bot: {bot_name}")
                continue

            # Check if already running
            if bot_name in pids:
                pid = pids[bot_name]
                if self._is_process_running(pid):
                    logger.info(f"{bot_name} already running (PID: {pid})")
                    continue
                else:
                    logger.warning(f"{bot_name} PID {pid} is stale, removing")
                    del pids[bot_name]

            # Start the bot
            process = self._get_bot_process(bot_name)
            if process:
                pids[bot_name] = process.pid
                started.append(bot_name)
                logger.info(f"Started {bot_name} (PID: {process.pid})")

        self._save_pids(pids)
        logger.info(f"Started {len(started)} bots: {started}")

    def stop(self, bot_names: List[str] = None):
        """Stop specified bots or all bots."""
        if bot_names is None:
            bot_names = list(self.bots.keys())

        pids = self._load_pids()
        stopped = []

        for bot_name in bot_names:
            if bot_name in pids:
                pid = pids[bot_name]
                if self._is_process_running(pid):
                    try:
                        os.killpg(os.getpgid(pid), signal.SIGTERM)
                        stopped.append(bot_name)
                        logger.info(f"Stopped {bot_name} (PID: {pid})")
                    except Exception as e:
                        logger.error(f"Failed to stop {bot_name}: {e}")
                else:
                    logger.warning(f"{bot_name} PID {pid} not running")
                del pids[bot_name]

        self._save_pids(pids)

        if stopped:
            logger.info(f"Stopped {len(stopped)} bots: {stopped}")
        else:
            logger.info("No bots were running")

    def restart(self, bot_names: List[str] = None):
        """Restart specified bots or all bots."""
        self.stop(bot_names)
        time.sleep(2)  # Wait for processes to fully stop
        self.start(bot_names)

    def status(self) -> Dict[str, str]:
        """Get status of all bots."""
        pids = self._load_pids()
        status = {}

        for bot_name in self.bots.keys():
            if bot_name in pids:
                pid = pids[bot_name]
                if self._is_process_running(pid):
                    status[bot_name] = f"running (PID: {pid})"
                else:
                    status[bot_name] = "stale (process not found)"
                    del pids[bot_name]
            else:
                status[bot_name] = "stopped"

        if pids != self._load_pids():
            self._save_pids(pids)

        return status

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is running."""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def main():
    manager = BotManager()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    bot_names = sys.argv[2:] if len(sys.argv) > 2 else None

    if command == "start":
        manager.start(bot_names)
    elif command == "stop":
        manager.stop(bot_names)
    elif command == "restart":
        manager.restart(bot_names)
    elif command == "status":
        status = manager.status()
        print("\nPhoenix Core Bot Status")
        print("=" * 50)
        for bot, status_text in status.items():
            emoji = "🟢" if "running" in status_text else "🔴"
            print(f"{emoji} {bot}: {status_text}")
        print("=" * 50)
    elif command == "pid":
        pids = manager._load_pids()
        print(json.dumps(pids, indent=2))
    elif command == "logs":
        if bot_names:
            for bot_name in bot_names:
                log_file = WORKSPACES_DIR / bot_name / "bot.log"
                if log_file.exists():
                    print(f"\n=== {bot_name} logs ===")
                    with open(log_file, "r") as f:
                        print(f.read()[-2000:])  # Last 2000 chars
        else:
            print("Usage: bot_manager.py logs <bot_name>")
    elif command == "health":
        # Start health checker
        logger.info("Starting health checker...")
        subprocess.run([sys.executable, str(PHOENIX_CORE_DIR / "bot_health_checker.py"), "start"])
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
