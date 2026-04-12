#!/usr/bin/env python3
"""
Phoenix Core Doctor - 健康检查与诊断工具

Phoenix Core 专属的健康检查系统

检查项目:
1. Bot 进程状态
2. Discord 连接健康
3. 数据库锁定检测
4. 工作区文件完整性
5. 技能系统状态
6. 记忆系统健康
7. 配置文件验证

Usage:
    python3 doctor.py              # 完整检查
    python3 doctor.py --quick      # 快速检查
    python3 doctor.py --fix        # 自动修复
    python3 doctor.py --category bots  # 只检查 Bot
"""

import json
import logging
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Phoenix Core 目录
PHOENIX_CORE_DIR = Path(__file__).parent
WORKSPACES_DIR = PHOENIX_CORE_DIR / "workspaces"
PID_FILE = Path("/tmp/phoenix_bots.pid.json")
MAIN_DB = PHOENIX_CORE_DIR / "main.db"

# Bot 列表
BOTS = ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]


@dataclass
class CheckResult:
    """检查结果"""
    category: str
    name: str
    status: str  # "ok", "warning", "error"
    message: str
    fix_hint: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DoctorContext:
    """Doctor 上下文"""
    results: List[CheckResult] = field(default_factory=list)
    should_fix: bool = False
    quick_mode: bool = False
    category_filter: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.now)

    def add_result(self, result: CheckResult):
        if self.category_filter and result.category != self.category_filter:
            return
        self.results.append(result)

    def get_summary(self) -> Dict[str, int]:
        summary = {"ok": 0, "warning": 0, "error": 0}
        for r in self.results:
            if r.category == self.category_filter or self.category_filter is None:
                summary[r.status] += 1
        return summary


class PhoenixDoctor:
    """
    Phoenix Core 健康检查器

    检查项注册模式、上下文传递、检查与修复分离
    """

    def __init__(self, ctx: DoctorContext):
        self.ctx = ctx
        self.checks: List[Callable] = []
        self._register_checks()

    def _register_checks(self):
        """注册所有检查项"""
        # 核心检查
        self.checks.append(self.check_bot_processes)
        self.checks.append(self.check_database)
        self.checks.append(self.check_workspace_files)
        self.checks.append(self.check_env_configs)

        if not self.ctx.quick_mode:
            self.checks.append(self.check_memory_system)
            self.checks.append(self.check_skill_system)
            self.checks.append(self.check_discord_connections)

    def run(self) -> List[CheckResult]:
        """执行所有检查"""
        for check in self.checks:
            try:
                check()
            except Exception as e:
                logger.error(f"Check {check.__name__} failed: {e}")
                self.ctx.add_result(CheckResult(
                    category="system",
                    name=check.__name__,
                    status="error",
                    message=f"检查失败：{e}",
                    fix_hint="请查看日志获取详细信息"
                ))
        return self.ctx.results

    def check_bot_processes(self):
        """检查 Bot 进程状态"""
        logger.info("Checking bot processes...")

        # 读取 PID 文件
        pid_data = {}
        if PID_FILE.exists():
            try:
                with open(PID_FILE, "r") as f:
                    pid_data = json.load(f)
            except Exception as e:
                self.ctx.add_result(CheckResult(
                    category="bots",
                    name="pid_file",
                    status="error",
                    message=f"PID 文件读取失败：{e}",
                    fix_hint="运行 bot_manager.py restart"
                ))
                return

        # 检查每个 Bot
        for bot_name in BOTS:
            pid = pid_data.get(bot_name)

            if not pid:
                self.ctx.add_result(CheckResult(
                    category="bots",
                    name=f"{bot_name}_pid",
                    status="error",
                    message=f"Bot {bot_name} 没有 PID 记录",
                    fix_hint="运行 bot_manager.py start",
                    details={"expected_pid": None}
                ))
                continue

            # 检查进程是否存在
            try:
                result = subprocess.run(
                    ["ps", "-p", str(pid)],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    self.ctx.add_result(CheckResult(
                        category="bots",
                        name=f"{bot_name}_pid",
                        status="ok",
                        message=f"Bot {bot_name} 运行中 (PID: {pid})",
                        details={"pid": pid}
                    ))
                else:
                    self.ctx.add_result(CheckResult(
                        category="bots",
                        name=f"{bot_name}_pid",
                        status="error",
                        message=f"Bot {bot_name} 进程不存在 (PID: {pid})",
                        fix_hint="运行 bot_manager.py restart",
                        details={"stale_pid": pid}
                    ))
            except subprocess.TimeoutExpired:
                self.ctx.add_result(CheckResult(
                    category="bots",
                    name=f"{bot_name}_pid",
                    status="warning",
                    message=f"Bot {bot_name} 进程检查超时",
                    details={"pid": pid}
                ))

    def check_database(self):
        """检查数据库健康"""
        logger.info("Checking database...")

        if not MAIN_DB.exists():
            self.ctx.add_result(CheckResult(
                category="database",
                name="main_db",
                status="warning",
                message="主数据库文件不存在",
                fix_hint="首次运行时会自动创建"
            ))
            return

        # 检查数据库锁定
        try:
            conn = sqlite3.connect(f"file:{MAIN_DB}?mode=ro", uri=True)
            conn.execute("SELECT 1")
            conn.close()

            self.ctx.add_result(CheckResult(
                category="database",
                name="main_db",
                status="ok",
                message="数据库可访问"
            ))
        except sqlite3.OperationalError as e:
            error_msg = str(e)
            if "locked" in error_msg:
                self.ctx.add_result(CheckResult(
                    category="database",
                    name="main_db",
                    status="error",
                    message="数据库被锁定",
                    fix_hint="关闭占用进程或清理 WAL 文件",
                    details={"error": error_msg}
                ))
            else:
                self.ctx.add_result(CheckResult(
                    category="database",
                    name="main_db",
                    status="error",
                    message=f"数据库错误：{e}",
                    fix_hint="检查数据库文件完整性"
                ))

        # 检查 WAL 文件
        wal_files = list(PHOENIX_CORE_DIR.glob("*.db-wal"))
        shm_files = list(PHOENIX_CORE_DIR.glob("*.db-shm"))

        if wal_files or shm_files:
            self.ctx.add_result(CheckResult(
                category="database",
                name="wal_files",
                status="warning",
                message=f"发现 {len(wal_files)} 个 WAL 文件，{len(shm_files)} 个 SHM 文件",
                fix_hint="正常运行中可忽略，如数据库锁定可运行：python3 doctor.py --fix"
            ))

    def check_workspace_files(self):
        """检查工作区文件完整性"""
        logger.info("Checking workspace files...")

        for bot_name in BOTS:
            workspace = WORKSPACES_DIR / bot_name

            if not workspace.exists():
                self.ctx.add_result(CheckResult(
                    category="workspace",
                    name=f"{bot_name}_workspace",
                    status="error",
                    message=f"Bot {bot_name} 工作区不存在",
                    fix_hint=f"创建目录：mkdir -p {workspace}"
                ))
                continue

            # 检查关键文件
            required_files = [".env", "MEMORY.md", "USER.md"]
            missing = []

            for rf in required_files:
                if not (workspace / rf).exists():
                    missing.append(rf)

            if missing:
                self.ctx.add_result(CheckResult(
                    category="workspace",
                    name=f"{bot_name}_files",
                    status="warning",
                    message=f"Bot {bot_name} 缺少文件：{', '.join(missing)}",
                    fix_hint="这些文件会在首次运行时自动创建"
                ))
            else:
                self.ctx.add_result(CheckResult(
                    category="workspace",
                    name=f"{bot_name}_files",
                    status="ok",
                    message=f"Bot {bot_name} 工作区完整"
                ))

    def check_env_configs(self):
        """检查配置文件"""
        logger.info("Checking environment configs...")

        # 检查主 .env 文件
        main_env = PHOENIX_CORE_DIR / ".env"
        if not main_env.exists():
            self.ctx.add_result(CheckResult(
                category="config",
                name="main_env",
                status="error",
                message="主配置文件 .env 不存在",
                fix_hint="运行配置向导或手动创建"
            ))
        else:
            content = main_env.read_text()
            if "BOTS_CONFIG" not in content:
                self.ctx.add_result(CheckResult(
                    category="config",
                    name="main_env",
                    status="warning",
                    message=".env 文件缺少 BOTS_CONFIG",
                    fix_hint="添加 Bot Token 配置"
                ))
            else:
                self.ctx.add_result(CheckResult(
                    category="config",
                    name="main_env",
                    status="ok",
                    message="主配置文件存在"
                ))

        # 检查 bot_ids.json
        bot_ids_file = PHOENIX_CORE_DIR / "bot_ids.json"
        if not bot_ids_file.exists():
            self.ctx.add_result(CheckResult(
                category="config",
                name="bot_ids",
                status="warning",
                message="bot_ids.json 不存在",
                fix_hint="Bot @mention 功能可能受影响"
            ))
        else:
            try:
                with open(bot_ids_file, "r") as f:
                    data = json.load(f)
                if len(data) == len(BOTS):
                    self.ctx.add_result(CheckResult(
                        category="config",
                        name="bot_ids",
                        status="ok",
                        message=f"Bot ID 映射完整 ({len(data)} 个 Bot)"
                    ))
                else:
                    self.ctx.add_result(CheckResult(
                        category="config",
                        name="bot_ids",
                        status="warning",
                        message=f"Bot ID 映射不完整 (期望{len(BOTS)}, 实际{len(data)})",
                        fix_hint="更新 bot_ids.json"
                    ))
            except json.JSONDecodeError:
                self.ctx.add_result(CheckResult(
                    category="config",
                    name="bot_ids",
                    status="error",
                    message="bot_ids.json 格式错误",
                    fix_hint="修复 JSON 格式"
                ))

    def check_memory_system(self):
        """检查记忆系统"""
        logger.info("Checking memory system...")

        for bot_name in BOTS:
            memory_dir = WORKSPACES_DIR / bot_name / "memory"
            if not memory_dir.exists():
                continue

            # 检查日志文件
            log_files = list((memory_dir / "日志").glob("*.md")) if (memory_dir / "日志").exists() else []

            if log_files:
                self.ctx.add_result(CheckResult(
                    category="memory",
                    name=f"{bot_name}_memory",
                    status="ok",
                    message=f"Bot {bot_name} 有 {len(log_files)} 条记忆日志"
                ))
            else:
                self.ctx.add_result(CheckResult(
                    category="memory",
                    name=f"{bot_name}_memory",
                    status="warning",
                    message=f"Bot {bot_name} 暂无记忆日志",
                    fix_hint="与 Bot 互动后会自动创建"
                ))

    def check_skill_system(self):
        """检查技能系统"""
        logger.info("Checking skill system...")

        for bot_name in BOTS:
            skills_dir = WORKSPACES_DIR / bot_name / "DYNAMIC" / "skills"
            if not skills_dir.exists():
                continue

            skill_files = list(skills_dir.glob("*.md"))

            if skill_files:
                self.ctx.add_result(CheckResult(
                    category="skills",
                    name=f"{bot_name}_skills",
                    status="ok",
                    message=f"Bot {bot_name} 有 {len(skill_files)} 个技能"
                ))
            else:
                self.ctx.add_result(CheckResult(
                    category="skills",
                    name=f"{bot_name}_skills",
                    status="warning",
                    message=f"Bot {bot_name} 暂无技能",
                    fix_hint="完成复杂任务后会自动生成技能"
                ))

    def check_discord_connections(self):
        """检查 Discord 连接状态 (通过日志)"""
        logger.info("Checking Discord connections...")

        for bot_name in BOTS:
            log_file = Path(f"/tmp/bot_{bot_name}.log")
            if not log_file.exists():
                self.ctx.add_result(CheckResult(
                    category="discord",
                    name=f"{bot_name}_connection",
                    status="warning",
                    message=f"Bot {bot_name} 日志文件不存在",
                    fix_hint="Bot 可能未启动"
                ))
                continue

            content = log_file.read_text()
            if "Shard ID None has connected" in content:
                self.ctx.add_result(CheckResult(
                    category="discord",
                    name=f"{bot_name}_connection",
                    status="ok",
                    message=f"Bot {bot_name} 已连接 Discord"
                ))
            elif "error" in content.lower() or "exception" in content.lower():
                self.ctx.add_result(CheckResult(
                    category="discord",
                    name=f"{bot_name}_connection",
                    status="error",
                    message=f"Bot {bot_name} 连接错误",
                    fix_hint="查看日志：cat /tmp/bot_{bot_name}.log"
                ))
            else:
                self.ctx.add_result(CheckResult(
                    category="discord",
                    name=f"{bot_name}_connection",
                    status="warning",
                    message=f"Bot {bot_name} 连接状态未知",
                    fix_hint="等待 Bot 启动或重启 Bot"
                ))

    def fix_issues(self):
        """尝试自动修复问题"""
        logger.info("Attempting to fix issues...")

        for result in self.ctx.results:
            if result.status != "error":
                continue

            if result.name == "wal_files" or "WAL" in result.message:
                # 清理 WAL 文件
                for pattern in ["*.db-wal", "*.db-shm"]:
                    for f in PHOENIX_CORE_DIR.glob(pattern):
                        try:
                            f.unlink()
                            logger.info(f"Deleted: {f}")
                        except Exception as e:
                            logger.error(f"Failed to delete {f}: {e}")
                result.status = "ok"
                result.message = "已清理 WAL 文件"

            elif "stale_pid" in result.details:
                # 更新 PID 文件
                self._update_pid_file()
                result.message = "PID 文件已更新 (需重启 Bot)"

            elif result.category == "database" and "locked" in result.message:
                # 尝试清理 WAL
                for pattern in ["*.db-wal", "*.db-shm"]:
                    for f in PHOENIX_CORE_DIR.glob(pattern):
                        try:
                            f.unlink()
                        except:
                            pass
                result.message = "已尝试清理数据库锁"


def _update_pid_file():
    """更新 PID 文件"""
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    pids = {}

    for line in result.stdout.split("\n"):
        if "discord_bot.py" in line and "grep" not in line:
            for bot in BOTS:
                if f"--bot {bot}" in line:
                    parts = line.split()
                    if len(parts) > 1:
                        pids[bot] = int(parts[1])

    with open(PID_FILE, "w") as f:
        json.dump(pids, f, indent=2, ensure_ascii=False)

    logger.info(f"Updated PID file with {len(pids)} bots")


def print_header():
    """打印头部"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║            🦅 Phoenix Core Doctor                         ║
║            健康检查与诊断工具                              ║
╚═══════════════════════════════════════════════════════════╝
    """)


def print_results(results: List[CheckResult]):
    """打印检查结果"""
    categories = {}
    for r in results:
        if r.category not in categories:
            categories[r.category] = []
        categories[r.category].append(r)

    for category, items in categories.items():
        icon = {"ok": "✅", "warning": "⚠️", "error": "❌"}.get(
            max([i.status for i in items], key=lambda x: {"ok": 0, "warning": 1, "error": 2}[x]),
            "•"
        )
        print(f"\n{icon} {category.upper()}")
        print("─" * 50)

        for item in items:
            status_icon = {"ok": "✅", "warning": "⚠️", "error": "❌"}.get(item.status, "•")
            print(f"  {status_icon} {item.name}: {item.message}")
            if item.fix_hint:
                print(f"     💡 修复：{item.fix_hint}")


def print_summary(ctx: DoctorContext):
    """打印摘要"""
    summary = ctx.get_summary()
    elapsed = (datetime.now() - ctx.start_time).total_seconds()

    print("\n" + "=" * 50)
    print(f"检查完成 (耗时：{elapsed:.2f}秒)")
    print(f"  ✅ 正常：{summary['ok']}")
    print(f"  ⚠️  警告：{summary['warning']}")
    print(f"  ❌ 错误：{summary['error']}")

    if summary['error'] > 0:
        print("\n💡 运行 python3 doctor.py --fix 尝试自动修复")
    elif summary['warning'] > 0:
        print("\n💡 部分项目需要关注，但不影响运行")
    else:
        print("\n🎉 所有检查通过！系统运行正常")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Phoenix Core 健康检查工具")
    parser.add_argument("--quick", action="store_true", help="快速检查 (跳过详细检查)")
    parser.add_argument("--fix", action="store_true", help="自动修复问题")
    parser.add_argument("--category", type=str, choices=[
        "bots", "database", "workspace", "config", "memory", "skills", "discord"
    ], help="只检查指定类别")

    args = parser.parse_args()

    # 创建上下文
    ctx = DoctorContext(
        should_fix=args.fix,
        quick_mode=args.quick,
        category_filter=args.category
    )

    print_header()

    # 创建 Doctor 并运行
    doctor = PhoenixDoctor(ctx)
    results = doctor.run()

    # 尝试修复
    if args.fix:
        print("\n🔧 正在尝试自动修复...")
        doctor.fix_issues()

    # 打印结果
    print_results(results)
    print_summary(ctx)


if __name__ == "__main__":
    main()
