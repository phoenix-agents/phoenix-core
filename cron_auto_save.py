#!/usr/bin/env python3
"""
Cron Job - 定期自动保存 Bot 学习总结

每 5 分钟执行一次，扫描学习总结文件并自动保存知识。
可配置为系统 cron 或使用 Python scheduler 运行。

用法：
    python cron_auto_save.py              # 执行一次
    python cron_auto_save.py --daemon     # 守护进程模式（每 5 分钟）
"""

import os
import sys
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from auto_save_learning import main as save_learning_main

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(Path(__file__).parent / "cron_auto_save.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 300  # 5 minutes


def run_once():
    """执行一次自动保存"""
    logger.info("=" * 50)
    logger.info(f"开始执行自动保存 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    try:
        save_learning_main()
        logger.info("✅ 自动保存完成")
    except Exception as e:
        logger.error(f"❌ 自动保存失败：{e}")
        raise


def run_daemon():
    """守护进程模式，持续运行"""
    logger.info(f"启动守护进程，每 {INTERVAL_SECONDS} 秒执行一次")

    while True:
        try:
            run_once()
        except Exception as e:
            logger.error(f"执行出错：{e}")

        next_run = datetime.now().timestamp() + INTERVAL_SECONDS
        logger.info(f"下次执行时间：{datetime.fromtimestamp(next_run).strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"等待 {INTERVAL_SECONDS} 秒...\n")
        time.sleep(INTERVAL_SECONDS)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Cron Job - 自动保存 Bot 学习总结')
    parser.add_argument('--daemon', action='store_true', help='守护进程模式（持续运行）')
    parser.add_argument('--interval', type=int, default=INTERVAL_SECONDS,
                        help=f'执行间隔（秒），默认{INTERVAL_SECONDS}秒')

    args = parser.parse_args()

    if args.interval:
        INTERVAL_SECONDS = args.interval

    if args.daemon:
        run_daemon()
    else:
        run_once()
