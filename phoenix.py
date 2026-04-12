#!/usr/bin/env python3
"""
Phoenix Core CLI - 统一命令行工具

Phoenix Core 专属的命令行接口，提供系统管理、Bot 控制、技能管理等功能。

Usage:
    phoenix status          # 查看系统状态
    phoenix doctor          # 健康检查
    phoenix bots list       # Bot 列表
    phoenix skills list     # 技能列表
    phoenix cache stats     # 缓存统计
    phoenix config show     # 显示配置
    phoenix tasks list      # 任务列表
    phoenix web             # 启动 Web UI
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

VERSION = "2.0.0"
PHOENIX_CORE_DIR = Path(__file__).parent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def print_header():
    """打印头部"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║            🦅 Phoenix Core CLI v2.0                       ║
║            AI 驱动的直播运营团队系统                        ║
╚═══════════════════════════════════════════════════════════╝
    """)


def cmd_status(args):
    """查看系统状态"""
    print_header()
    print("📊 系统状态\n")

    # Bot 状态
    try:
        from bot_manager import BotManager
        manager = BotManager()

        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            cwd=str(PHOENIX_CORE_DIR)
        )
        running_bots = []
        for line in result.stdout.split("\n"):
            if "discord_bot.py" in line and "grep" not in line:
                for bot in ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]:
                    if f"--bot {bot}" in line:
                        running_bots.append(bot)

        print(f"🤖 Bot 状态：{len(running_bots)}/8 运行中")
        for bot in running_bots:
            print(f"   ✅ {bot}")
        if not running_bots:
            print("   ⚠️  没有 Bot 运行中")

    except Exception as e:
        print(f"   ❌ 无法获取 Bot 状态：{e}")

    # 缓存状态
    try:
        from phoenix_memory_cache import get_memory_optimizer
        optimizer = get_memory_optimizer()
        stats = optimizer.get_stats()
        print(f"\n💾 缓存状态:")
        print(f"   L1 命中率：{stats['l1_cache']['hit_rate']}")
        print(f"   L2 命中率：{stats['l2_cache']['hit_rate']}")
    except Exception as e:
        print(f"   ⚠️  缓存统计不可用")

    # 任务状态
    try:
        from task_queue import get_task_queue
        queue = get_task_queue()
        stats = queue.get_stats()
        print(f"\n📋 任务状态：{stats.get('total_tasks', 0)} 个任务")
        for status, count in stats.get('by_status', {}).items():
            print(f"   {status}: {count}")
    except Exception as e:
        print(f"   ⚠️  任务统计不可用")

    print()


def cmd_doctor(args):
    """健康检查"""
    doctor_path = PHOENIX_CORE_DIR / "doctor.py"
    if doctor_path.exists():
        cmd = ["python3", str(doctor_path)]
        if args.quick:
            cmd.append("--quick")
        if args.fix:
            cmd.append("--fix")
        subprocess.run(cmd, cwd=str(PHOENIX_CORE_DIR))
    else:
        print("❌ doctor.py 不存在")


def cmd_bots(args):
    """Bot 管理"""
    action = args.action

    if action == "list":
        print("\n🤖 Bot 列表\n")
        bots = {
            "编导": {"model": "deepseek-ai/DeepSeek-V3.2", "provider": "compshare", "role": "内容策划"},
            "剪辑": {"model": "gpt-5.1", "provider": "compshare", "role": "视频编辑"},
            "美工": {"model": "gpt-5.1", "provider": "compshare", "role": "平面设计"},
            "场控": {"model": "claude-haiku-4-5-20251001", "provider": "compshare", "role": "直播控制"},
            "客服": {"model": "qwen3.5-plus", "provider": "coding-plan", "role": "客户支持"},
            "运营": {"model": "claude-sonnet-4-6", "provider": "compshare", "role": "数据分析"},
            "渠道": {"model": "gpt-5.1", "provider": "compshare", "role": "商务合作"},
            "小小谦": {"model": "kimi-k2.5", "provider": "moonshot", "role": "总协调"},
        }

        print(f"{'Bot':<10} {'模型':<30} {'Provider':<15} {'角色':<10}")
        print("-" * 70)
        for name, info in bots.items():
            print(f"{name:<10} {info['model']:<30} {info['provider']:<15} {info['role']:<10}")

    elif action == "start":
        from bot_manager import BotManager
        manager = BotManager()
        if args.name:
            manager.start([args.name])
            print(f"✅ 启动 Bot: {args.name}")
        else:
            manager.start()
            print("✅ 启动所有 Bot")

    elif action == "stop":
        from bot_manager import BotManager
        manager = BotManager()
        manager.stop()
        print("✅ 停止所有 Bot")

    elif action == "restart":
        from bot_manager import BotManager
        manager = BotManager()
        manager.stop()
        import time
        time.sleep(2)
        manager.start()
        print("✅ 重启所有 Bot")

    elif action == "status":
        from bot_manager import BotManager
        manager = BotManager()
        status_dict = manager.get_status()
        print("\n🤖 Bot 状态\n")
        for bot_name, status in status_dict.items():
            if status.get("running"):
                print(f"✅ {bot_name} (PID: {status.get('pid', 'N/A')})")
            else:
                print(f"⏸️  {bot_name}")
        print()


def cmd_skills(args):
    """技能管理"""
    action = args.action

    if action == "list":
        print("\n📚 技能列表\n")
        skills_dir = PHOENIX_CORE_DIR / "skills"
        if skills_dir.exists():
            skill_files = list(skills_dir.glob("*.md"))
            print(f"共 {len(skill_files)} 个技能:\n")
            for f in skill_files[:20]:
                print(f"   - {f.stem}")
            if len(skill_files) > 20:
                print(f"   ... 还有 {len(skill_files) - 20} 个")
        else:
            print("⚠️  技能目录不存在")
        print()

    elif action == "info":
        if args.name:
            skill_file = PHOENIX_CORE_DIR / "skills" / f"{args.name}.md"
            if skill_file.exists():
                print(f"\n📚 技能信息：{args.name}\n")
                with open(skill_file, "r") as f:
                    content = f.read()
                    print(content[:2000])  # 显示前 2000 字符
            else:
                print(f"❌ 技能 '{args.name}' 不存在")
        else:
            print("❌ 请指定技能名称")

    elif action == "remove":
        if args.name:
            skill_file = PHOENIX_CORE_DIR / "skills" / f"{args.name}.md"
            if skill_file.exists():
                skill_file.unlink()
                print(f"✅ 已删除技能：{args.name}")
            else:
                print(f"❌ 技能 '{args.name}' 不存在")
        else:
            print("❌ 请指定技能名称")


def cmd_cache(args):
    """缓存管理"""
    action = args.action

    if action == "stats":
        print("\n💾 缓存统计\n")
        try:
            from phoenix_memory_cache import get_memory_optimizer
            optimizer = get_memory_optimizer()
            stats = optimizer.get_stats()
            print(f"L1 缓存:")
            print(f"  命中数：{stats['l1_cache'].get('hits', 0)}")
            print(f"  未命中数：{stats['l1_cache'].get('misses', 0)}")
            print(f"  命中率：{stats['l1_cache'].get('hit_rate', 'N/A')}")
            print(f"\nL2 缓存:")
            print(f"  命中数：{stats['l2_cache'].get('hits', 0)}")
            print(f"  未命中数：{stats['l2_cache'].get('misses', 0)}")
            print(f"  命中率：{stats['l2_cache'].get('hit_rate', 'N/A')}")
        except Exception as e:
            print(f"⚠️  无法获取缓存统计：{e}")
        print()

    elif action == "clear":
        print("\n🧹 清理缓存...\n")
        cache_dir = PHOENIX_CORE_DIR / "cache"
        if cache_dir.exists():
            count = 0
            for f in cache_dir.rglob("*"):
                if f.is_file():
                    f.unlink()
                    count += 1
            print(f"✅ 已清理 {count} 个缓存文件")
        else:
            print("⚠️  缓存目录不存在")
        print()


def cmd_config(args):
    """配置管理"""
    action = args.action

    if action == "show":
        print("\n⚙️  当前配置\n")

        # 显示 config.json
        config_file = PHOENIX_CORE_DIR / "config.json"
        if config_file.exists():
            print("config.json:")
            with open(config_file, "r") as f:
                print(f.read()[:2000])
        else:
            print("⚠️  config.json 不存在")

        print("\n.env:")
        env_file = PHOENIX_CORE_DIR / ".env"
        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        if "=" in line:
                            key, _ = line.split("=", 1)
                            print(f"  {key}=***")
        else:
            print("⚠️  .env 不存在")
        print()

    elif action == "edit":
        print("⚠️  请手动编辑配置文件:")
        print(f"   - config.json: {PHOENIX_CORE_DIR / 'config.json'}")
        print(f"   - .env: {PHOENIX_CORE_DIR / '.env'}")
        print()


def cmd_version(args):
    """显示版本"""
    print(f"Phoenix Core CLI v{VERSION}")
    print(f"Python {sys.version}")
    print(f"路径：{PHOENIX_CORE_DIR}")

    # 检查最新版本 (如果指定 --check)
    if getattr(args, 'check', False):
        print("\n📡 检查最新版本...")
        try:
            import urllib.request
            import json

            url = "https://api.github.com/repos/phoenix-core/phoenix-core/releases/latest"
            response = urllib.request.urlopen(url, timeout=5)
            data = json.loads(response.read())
            latest_version = data.get("tag_name", "未知")
            release_url = data.get("html_url", "")

            if latest_version != f"v{VERSION}":
                print(f"\n💡 发现新版本：{latest_version}")
                print(f"   当前版本：v{VERSION}")
                print(f"   更新命令：git pull origin main")
                print(f"   发布详情：{release_url}")
            else:
                print(f"\n✅ 已是最新版本 (v{VERSION})")
        except Exception as e:
            logger.debug(f"版本检查失败：{e}")
            print(f"   ⚠️  无法连接版本服务器，请手动检查 GitHub Releases")


def cmd_tasks(args):
    """任务管理"""
    action = args.action

    if action == "list":
        from task_queue import get_task_queue
        queue = get_task_queue()
        stats = queue.get_stats()

        print(f"\n📋 任务统计\n")
        print(f"总任务数：{stats.get('total_tasks', 0)}")
        print(f"\n按状态:")
        for status, count in stats.get('by_status', {}).items():
            print(f"   {status}: {count}")
        print(f"\n按 Bot:")
        for bot, count in stats.get('by_bot', {}).items():
            print(f"   {bot}: {count}")
        print(f"\n按优先级:")
        for priority, count in stats.get('by_priority', {}).items():
            print(f"   {priority}: {count}")

    elif action == "add":
        from task_queue import get_task_queue, TaskPriority
        queue = get_task_queue()

        priority = TaskPriority(args.priority) if args.priority else TaskPriority.NORMAL

        task_id = queue.add_task(
            assigned_to=args.bot,
            title=args.title,
            description=args.description or "",
            priority=priority
        )
        print(f"✅ 任务已创建：{task_id}")


def cmd_web(args):
    """启动 Web UI"""
    web_ui_path = PHOENIX_CORE_DIR / "web_ui.py"
    if web_ui_path.exists():
        cmd = ["python3", str(web_ui_path), "--port", str(args.port), "--host", args.host]
        subprocess.run(cmd)
    else:
        print("❌ web_ui.py 不存在")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Phoenix Core CLI - AI 驱动的直播运营团队系统",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # status
    parser_status = subparsers.add_parser("status", help="查看系统状态")
    parser_status.set_defaults(func=cmd_status)

    # doctor
    parser_doctor = subparsers.add_parser("doctor", help="健康检查")
    parser_doctor.add_argument("--quick", action="store_true", help="快速检查")
    parser_doctor.add_argument("--fix", action="store_true", help="自动修复")
    parser_doctor.set_defaults(func=cmd_doctor)

    # bots
    parser_bots = subparsers.add_parser("bots", help="Bot 管理")
    parser_bots.add_argument("action", choices=["list", "start", "stop", "restart", "status"], help="操作")
    parser_bots.add_argument("--name", help="Bot 名称（可选）")
    parser_bots.set_defaults(func=cmd_bots)

    # skills
    parser_skills = subparsers.add_parser("skills", help="技能管理")
    parser_skills.add_argument("action", choices=["list", "info", "remove"], help="操作")
    parser_skills.add_argument("--name", help="技能名称")
    parser_skills.set_defaults(func=cmd_skills)

    # cache
    parser_cache = subparsers.add_parser("cache", help="缓存管理")
    parser_cache.add_argument("action", choices=["stats", "clear"], help="操作")
    parser_cache.set_defaults(func=cmd_cache)

    # config
    parser_config = subparsers.add_parser("config", help="配置管理")
    parser_config.add_argument("action", choices=["show", "edit"], help="操作")
    parser_config.set_defaults(func=cmd_config)

    # version
    parser_version = subparsers.add_parser("version", help="显示版本")
    parser_version.add_argument("--check", action="store_true", help="检查最新版本")
    parser_version.set_defaults(func=cmd_version)

    # tasks
    parser_tasks = subparsers.add_parser("tasks", help="任务管理")
    parser_tasks.add_argument("action", choices=["list", "add"], help="操作")
    parser_tasks.add_argument("--bot", type=str, help="分配给的 Bot")
    parser_tasks.add_argument("--title", type=str, help="任务标题")
    parser_tasks.add_argument("--description", type=str, help="任务描述")
    parser_tasks.add_argument("--priority", choices=["critical", "high", "normal", "low"], help="优先级")
    parser_tasks.set_defaults(func=cmd_tasks)

    # web
    parser_web = subparsers.add_parser("web", help="启动 Web UI")
    parser_web.add_argument("--port", type=int, default=8080, help="端口号")
    parser_web.add_argument("--host", type=str, default="127.0.0.1", help="主机地址")
    parser_web.set_defaults(func=cmd_web)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if hasattr(args, 'func'):
        args.func(args)


if __name__ == "__main__":
    main()
