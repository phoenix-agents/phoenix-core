#!/usr/bin/env python3
"""
Discord 历史自动同步工具

1. 导出最新 Discord 消息
2. 增量导入到共享上下文

Usage:
    python3 sync_discord_history.py
"""

import logging
import subprocess
import sys
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent
EXPORT_SCRIPT = PROJECT_DIR / "export_discord_history.py"
IMPORT_SCRIPT = PROJECT_DIR / "import_discord_history_full.py"


def run_export():
    """Run Discord history export."""
    logger.info("Starting Discord history export...")
    result = subprocess.run(
        [sys.executable, str(EXPORT_SCRIPT), "--incremental"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        logger.info("Export completed successfully")
    else:
        logger.error(f"Export failed: {result.stderr}")
    return result.returncode == 0


def run_import():
    """Import history to shared context."""
    logger.info("Starting history import to shared context...")
    result = subprocess.run(
        [sys.executable, str(IMPORT_SCRIPT)],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        logger.info("Import completed successfully")
    else:
        logger.error(f"Import failed: {result.stderr}")
    return result.returncode == 0


def create_sync_log(export_ok: bool, import_ok: bool):
    """Create sync log entry."""
    log_file = PROJECT_DIR / "shared_memory" / "logs" / "discord_sync.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().isoformat()
    status = "✅" if (export_ok and import_ok) else "❌"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} | Export: {'✅' if export_ok else '❌'} | Import: {'✅' if import_ok else '❌'}\n")


def main():
    logger.info("=" * 50)
    logger.info("Discord History Auto-Sync")
    logger.info("=" * 50)

    export_ok = run_export()
    import_ok = run_import() if export_ok else False

    create_sync_log(export_ok, import_ok)

    logger.info("=" * 50)
    logger.info(f"Sync finished: {'SUCCESS' if (export_ok and import_ok) else 'FAILED'}")
    logger.info("=" * 50)

    return 0 if (export_ok and import_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
