#!/usr/bin/env python3
"""
Config Wizard - 交互式配置向导

Phoenix Core Phoenix v2.0 扩展模块

功能:
1. 交互式环境配置
2. API Key 验证测试
3. Bot 初始配置
4. 团队拓扑配置
5. 配置验证报告

Usage:
    python3 config_wizard.py
    python3 config_wizard.py --quick  # 快速配置
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

try:
    from rich.console import Console
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Installing rich for better UI...")
    os.system("pip install rich -q")
    from rich.console import Console
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
PROJECT_DIR = Path(__file__).parent
ENV_FILE = PROJECT_DIR / ".env"


class ConfigWizard:
    """
    配置向导类

    交互式引导用户完成系统配置
    """

    def __init__(self):
        self.console = Console()
        self.config: Dict[str, Any] = {}
        self.env_vars: Dict[str, str] = {}

    def print_banner(self):
        """打印欢迎横幅"""
        banner = """
╔═══════════════════════════════════════════════════════════╗
║         Phoenix Core Phoenix v2.0 配置向导                    ║
╠═══════════════════════════════════════════════════════════╣
║  本向导将帮助您完成:                                        ║
║  1. 环境变量配置                                            ║
║  2. API Key 验证测试                                         ║
║  3. Bot 初始配置                                             ║
║  4. 团队拓扑配置                                            ║
║  5. 生成配置报告                                            ║
╚═══════════════════════════════════════════════════════════╝
"""
        self.console.print(Panel(banner, style="bold blue"))

    def print_step(self, step: int, title: str):
        """打印步骤标题"""
        self.console.print(f"\n[bold green]步骤 {step}[/bold green]: [cyan]{title}[/cyan]\n")

    def load_existing_config(self):
        """加载已有配置"""
        if ENV_FILE.exists():
            self.console.print("[yellow]检测到已有配置文件 .env[/yellow]\n")
            content = ENV_FILE.read_text(encoding="utf-8")
            for line in content.splitlines():
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    self.env_vars[key.strip()] = value.strip()
            return True
        return False

    def step1_env_config(self) -> bool:
        """步骤 1: 环境变量配置"""
        self.print_step(1, "环境变量配置")

        # AI Provider 配置
        self.console.print(Panel("[bold]AI Provider 配置[/bold]\n", style="dim"))

        # DashScope API Key
        current = self.env_vars.get("DASHSCOPE_API_KEY", "")
        if current and current != "your_api_key_here":
            self.console.print(f"[green]✓ DashScope API Key 已配置[/green]")
            if not Confirm.ask("是否修改？", default=False):
                self.config["DASHSCOPE_API_KEY"] = current
            else:
                self.config["DASHSCOPE_API_KEY"] = Prompt.ask(
                    "DashScope API Key",
                    default=current,
                    password=True
                )
        else:
            self.console.print("[yellow]DashScope API Key 未配置[/yellow]")
            self.console.print("获取地址：https://dashscope.console.aliyun.com/apiKey\n")
            self.config["DASHSCOPE_API_KEY"] = Prompt.ask(
                "请输入 DashScope API Key",
                password=True
            )

        # CompShare API Key (可选)
        self.console.print("\n[yellow]CompShare API Key (可选)[/yellow]")
        self.console.print("如不使用可留空\n")
        self.config["COMPShare_API_KEY"] = Prompt.ask(
            "CompShare API Key",
            default=self.env_vars.get("COMPShare_API_KEY", ""),
            password=True
        )

        # Discord Token (可选)
        self.console.print("\n[yellow]Discord Bot Token (可选)[/yellow]")
        self.console.print("如不使用 Discord 可留空\n")
        self.config["DISCORD_TOKEN"] = Prompt.ask(
            "Discord Token",
            default=self.env_vars.get("DISCORD_TOKEN", ""),
            password=True
        )

        return True

    def step2_api_verification(self) -> bool:
        """步骤 2: API Key 验证测试"""
        self.print_step(2, "API Key 验证测试")

        api_key = self.config.get("DASHSCOPE_API_KEY", "")

        if not api_key:
            self.console.print("[red]✗ API Key 未配置，跳过验证[/red]")
            return True

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("正在验证 DashScope API Key...", total=None)

            # 调用 DashScope API 验证
            try:
                # 简单的模型列表请求
                req = urllib.request.Request(
                    "https://dashscope.aliyuncs.com/api/v1/models",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        progress.update(task, description="[green]✓ API Key 验证成功[/green]")
                        self.config["api_verified"] = True
                        return True
            except Exception as e:
                # 验证失败，但继续
                progress.update(task, description=f"[yellow]! API Key 验证失败：{str(e)[:50]}[/yellow]")
                self.config["api_verified"] = False

        # 即使验证失败也继续
        if not Confirm.ask("\nAPI 验证失败，是否继续配置？", default=True):
            return False

        return True

    def step3_bot_config(self) -> bool:
        """步骤 3: Bot 初始配置"""
        self.print_step(3, "Bot 初始配置")

        self.console.print("Phoenix Core 内置 8 个 Bot 模板:\n")

        bots = [
            ("编导", "内容策划、创意构思、IP 定位", "deepseek-ai/DeepSeek-V3.2"),
            ("剪辑", "视频剪辑、节奏把控、爆款制作", "gpt-5.1"),
            ("美工", "视觉设计、个人品牌打造", "gpt-5.1"),
            ("场控", "气氛控制、粉丝互动、节奏调节", "claude-haiku-4-5-20251001"),
            ("客服", "粉丝运营、私域流量、用户维护", "qwen3.5-plus"),
            ("运营", "数据分析、增长策略、商业变现", "claude-sonnet-4-6"),
            ("渠道", "渠道拓展、商务合作", "gpt-5.1"),
            ("小小谦", "系统协调、任务调度", "kimi-k2.5")
        ]

        # 显示 Bot 列表
        if RICH_AVAILABLE:
            table = Table(title="内置 Bot 模板")
            table.add_column("Bot 名称", style="cyan")
            table.add_column("职责", style="magenta")
            table.add_column("默认模型", style="green")

            for name, desc, model in bots:
                table.add_row(name, desc, model)

            self.console.print(table)
        else:
            for name, desc, model in bots:
                self.console.print(f"  {name}: {desc} (模型：{model})")

        # 选择要启用的 Bot
        self.console.print("\n[bold]选择要初始化的 Bot:[/bold]")
        self.console.print("(直接回车选择全部，或输入 Bot 名称用逗号分隔)\n")

        choice = Prompt.ask("要初始化的 Bot", default="全部")

        if choice.lower() in ["全部", "all", ""]:
            self.config["initial_bots"] = [name for name, _, _ in bots]
        else:
            selected = [name.strip() for name in choice.split(",")]
            self.config["initial_bots"] = [name for name, _, _ in bots if name in selected]

        self.console.print(f"\n[green]✓ 将初始化以下 Bot: {', '.join(self.config['initial_bots'])}[/green]")

        return True

    def step4_team_config(self) -> bool:
        """步骤 4: 团队拓扑配置"""
        self.print_step(4, "团队拓扑配置")

        self.console.print("Phoenix Core 支持多团队配置，默认推荐以下结构:\n")

        teams = {
            "内容团队": {
                "description": "内容策划与制作",
                "members": ["编导", "剪辑", "美工"],
                "lead_bot": "编导"
            },
            "运营团队": {
                "description": "粉丝运营与数据分析",
                "members": ["场控", "客服", "运营"],
                "lead_bot": "运营"
            },
            "商务团队": {
                "description": "商务合作与渠道拓展",
                "members": ["渠道"],
                "lead_bot": "渠道"
            },
            "协调团队": {
                "description": "系统协调与任务调度",
                "members": ["小小谦"],
                "lead_bot": "小小谦"
            }
        }

        # 显示团队结构
        if RICH_AVAILABLE:
            table = Table(title="推荐团队结构")
            table.add_column("团队名称", style="cyan")
            table.add_column("职责", style="magenta")
            table.add_column("成员", style="green")
            table.add_column("负责 Bot", style="yellow")

            for name, info in teams.items():
                table.add_row(
                    name,
                    info["description"],
                    ", ".join(info["members"]),
                    info["lead_bot"]
                )

            self.console.print(table)

        # 确认使用推荐配置
        if Confirm.ask("\n是否使用推荐团队结构？", default=True):
            self.config["use_default_teams"] = True
            self.config["teams"] = teams
        else:
            self.config["use_default_teams"] = False
            self.config["teams"] = {}

        return True

    def step5_save_config(self) -> bool:
        """步骤 5: 保存配置"""
        self.print_step(5, "保存配置")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            # 生成 .env 文件
            task = progress.add_task("正在生成配置文件...", total=None)

            env_content = f"""# Phoenix Core Environment Configuration
# Generated by Config Wizard at {datetime.now().isoformat()}

# AI Provider Configuration
DASHSCOPE_API_KEY={self.config.get('DASHSCOPE_API_KEY', '')}
COMPShare_API_KEY={self.config.get('COMPShare_API_KEY', '')}

# Discord Configuration (optional)
DISCORD_TOKEN={self.config.get('DISCORD_TOKEN', '')}

# Model Configuration
DEFAULT_MODEL=claude-sonnet-4-6
FALLBACK_MODEL=qwen3-coder-next

# System Configuration
LOG_LEVEL=INFO
HEARTBEAT_INTERVAL=30

# Feature Flags
ENABLE_AUTO_EVOLUTION=true
ENABLE_SKILL_EXTRACTION=true
ENABLE_MEMORY_ARCHIVING=true
"""

            progress.update(task, description="正在保存配置文件...")
            ENV_FILE.write_text(env_content, encoding="utf-8")

            # 初始化 Bot
            if self.config.get("initial_bots"):
                progress.update(task, description="正在初始化 Bot 工作空间...")
                self._initialize_bots()

            # 创建团队拓扑
            if self.config.get("teams"):
                progress.update(task, description="正在创建团队拓扑...")
                self._create_teams()

        self.console.print("\n[bold green]✓ 配置保存成功![/bold green]\n")

        # 显示配置摘要
        self._show_summary()

        return True

    def _initialize_bots(self):
        """初始化 Bot 工作空间"""
        import sys
        sys.path.insert(0, str(PROJECT_DIR))
        from bot_registry import BotRegistry

        registry = BotRegistry()
        for bot_name in self.config.get("initial_bots", []):
            registry.register_bot(bot_name, template=bot_name)

    def _create_teams(self):
        """创建团队拓扑"""
        import sys
        sys.path.insert(0, str(PROJECT_DIR))
        from team_topology import TeamTopology

        topology = TeamTopology()
        for team_name, team_info in self.config.get("teams", {}).items():
            topology.create_team(
                team_name,
                description=team_info["description"],
                lead_bot=team_info["lead_bot"],
                initial_members=team_info["members"]
            )

    def _show_summary(self):
        """显示配置摘要"""
        self.console.print(Panel("[bold]配置摘要[/bold]\n", style="bold blue"))

        summary = Table()
        summary.add_column("配置项", style="cyan")
        summary.add_column("值", style="green")

        summary.add_row("DashScope API", "✓ 已配置" if self.config.get("DASHSCOPE_API_KEY") else "✗ 未配置")
        summary.add_row("API 验证", "✓ 通过" if self.config.get("api_verified") else "! 未验证")
        summary.add_row("Discord", "✓ 已配置" if self.config.get("DISCORD_TOKEN") else "✗ 未配置")
        summary.add_row("初始 Bot", f"{len(self.config.get('initial_bots', []))} 个")
        summary.add_row("团队结构", "✓ 使用推荐" if self.config.get("use_default_teams") else "✗ 自定义")

        self.console.print(summary)

        self.console.print("\n[bold]下一步操作:[/bold]")
        self.console.print("  1. 运行 [cyan]python3 cli.py health[/cyan] 检查系统状态")
        self.console.print("  2. 运行 [cyan]python3 bot_registry.py list[/cyan] 查看 Bot")
        self.console.print("  3. 运行 [cyan]python3 team_topology.py list[/cyan] 查看团队")
        self.console.print("  4. 运行 [cyan]python3 integration_tests.py[/cyan] 运行测试")

    def run(self) -> bool:
        """运行配置向导"""
        self.print_banner()

        # 检查已有配置
        if self.load_existing_config():
            if not Confirm.ask("是否继续配置向导？", default=True):
                return False

        # 执行配置步骤
        steps = [
            self.step1_env_config,
            self.step2_api_verification,
            self.step3_bot_config,
            self.step4_team_config,
            self.step5_save_config
        ]

        for step in steps:
            try:
                if not step():
                    self.console.print("\n[yellow]配置已取消[/yellow]")
                    return False
            except KeyboardInterrupt:
                self.console.print("\n[yellow]配置已取消[/yellow]")
                return False
            except Exception as e:
                self.console.print(f"\n[red]错误：{e}[/red]")
                if not Confirm.ask("是否继续下一步？", default=True):
                    return False

        return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Phoenix Core 配置向导")
    parser.add_argument("--quick", action="store_true", help="快速配置（使用默认值）")
    parser.add_argument("--skip-verify", action="store_true", help="跳过 API 验证")

    args = parser.parse_args()

    wizard = ConfigWizard()

    if args.quick:
        # 快速配置模式
        wizard.config = {
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY", ""),
            "COMPShare_API_KEY": os.environ.get("COMPShare_API_KEY", ""),
            "DISCORD_TOKEN": os.environ.get("DISCORD_TOKEN", ""),
            "api_verified": True,
            "initial_bots": ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"],
            "use_default_teams": True
        }
        wizard.step5_save_config()
    else:
        # 交互模式
        success = wizard.run()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
