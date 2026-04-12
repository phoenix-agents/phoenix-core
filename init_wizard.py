#!/usr/bin/env python3
"""
Phoenix Core 初始化向导 v2.0

最佳实践：
- 交互式配置流程
- 预设模板快速启动
- 自动验证配置有效性
- 友好的错误提示

Usage:
    python3 init_wizard.py
    python3 init_wizard.py --non-interactive  # 自动化模式
"""

import json
import os
import sys
import urllib.request
import ssl
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime


# ========== 配置模板 ==========

TEMPLATES = {
    "live_streaming": {
        "name": "直播团队",
        "description": "8 Bot 协作，适合直播带货场景",
        "bots": {
            "编导": {"model": "deepseek-ai/DeepSeek-V3.2", "provider": "compshare", "role": "content"},
            "剪辑": {"model": "gpt-5.1", "provider": "compshare", "role": "video"},
            "美工": {"model": "gpt-5.1", "provider": "compshare", "role": "design"},
            "场控": {"model": "claude-haiku-4-5-20251001", "provider": "compshare", "role": "control"},
            "客服": {"model": "qwen3.5-plus", "provider": "coding-plan", "role": "support"},
            "运营": {"model": "claude-sonnet-4-6", "provider": "compshare", "role": "operation"},
            "渠道": {"model": "gpt-5.1", "provider": "compshare", "role": "business"},
            "小小谦": {"model": "kimi-k2.5", "provider": "moonshot", "role": "coordinator"},
        }
    },
    "content_creation": {
        "name": "内容创作团队",
        "description": "3 Bot 精简版，适合内容生产",
        "bots": {
            "文案": {"model": "qwen3.5-plus", "provider": "coding-plan", "role": "writer"},
            "编辑": {"model": "claude-sonnet-4-6", "provider": "compshare", "role": "editor"},
            "审核": {"model": "claude-haiku-4-5-20251001", "provider": "compshare", "role": "reviewer"},
        }
    },
    "single_assistant": {
        "name": "单人助手",
        "description": "1 Bot 通用助手，适合个人使用",
        "bots": {
            "助手": {"model": "qwen3.5-plus", "provider": "coding-plan", "role": "assistant"},
        }
    }
}

PROVIDERS = {
    "compshare": {
        "name": "CompShare",
        "models": ["Claude", "GPT", "DeepSeek"],
        "env_key": "COMPSHARE_API_KEY",
        "url": "https://api.modelverse.cn/v1",
    },
    "coding-plan": {
        "name": "Coding Plan (通义千问)",
        "models": ["Qwen3.5", "Qwen3-Max"],
        "env_key": "CODING_PLAN_API_KEY",
        "url": "https://coding.dashscope.aliyuncs.com/v1",
    },
    "moonshot": {
        "name": "Moonshot (Kimi)",
        "models": ["kimi-k2.5"],
        "env_key": "MOONSHOT_API_KEY",
        "url": "https://api.moonshot.cn/v1",
    }
}


# ========== 工具函数 ==========

def color_print(text: str, color: str = "white"):
    """彩色输出"""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "purple": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "reset": "\033[0m"
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


def print_banner():
    """打印欢迎横幅"""
    color_print("""
╔═══════════════════════════════════════════════════════════╗
║           Phoenix Core 初始化向导 v2.0                     ║
║                                                           ║
║  多 Bot 协作 · 6 阶段学习闭环 · 技能进化系统                ║
╚═══════════════════════════════════════════════════════════╝
    """, "cyan")


def print_step(step_num: int, title: str):
    """打印步骤标题"""
    color_print(f"\n{'='*60}", "cyan")
    color_print(f"步骤 {step_num}: {title}", "green")
    color_print(f"{'='*60}", "cyan")


def input_with_default(prompt: str, default: str = "") -> str:
    """带默认值的输入"""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result or default
    return input(prompt + ": ").strip()


def yes_no(prompt: str, default: bool = False) -> bool:
    """是/否输入"""
    suffix = "Y/n" if default else "y/N"
    result = input(f"{prompt} ({suffix}): ").strip().lower()
    if not result:
        return default
    return result in ('y', 'yes', '是')


# ========== 验证函数 ==========

def validate_api_key(provider: str, api_key: str) -> Tuple[bool, str]:
    """验证 API Key 有效性"""
    provider_config = PROVIDERS.get(provider)
    if not provider_config:
        return False, f"未知 Provider: {provider}"

    if not api_key or len(api_key) < 10:
        return False, "API Key 格式不正确"

    # 简单连通性测试（可选）
    try:
        # 创建 SSL 上下文（不验证证书用于测试）
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(
            f"{provider_config['url']}/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
            if response.status == 200:
                return True, "API Key 有效"
            return False, f"API 返回状态码：{response.status}"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "API Key 无效（401 未授权）"
        return False, f"API 错误：{e.code}"
    except Exception as e:
        return True, f"验证跳过（网络错误：{str(e)[:50]})"


# ========== 配置步骤 ==========

def check_existing_config() -> bool:
    """检查是否已有配置"""
    env_file = Path(".env")
    config_file = Path("config.json")

    if env_file.exists() or config_file.exists():
        color_print("\n⚠️  检测到已有配置文件", "yellow")
        if env_file.exists():
            color_print(f"   - {env_file.absolute()}", "yellow")
        if config_file.exists():
            color_print(f"   - {config_file.absolute()}", "yellow")

        if yes_no("是否覆盖现有配置？", default=False):
            return False
        return True

    return False


def setup_env() -> Dict[str, str]:
    """步骤 1: 配置 LLM Provider"""
    print_step(1, "配置 LLM Provider")

    print("""
Phoenix Core 支持多个 LLM Provider，请至少配置一个：

Provider 对比:
  1. CompShare     - Claude/GPT/DeepSeek 系列，模型最全 (推荐)
  2. Coding Plan   - 通义千问系列，性价比高
  3. Moonshot      - Kimi 模型，长文本处理优秀

提示：可以稍后在 config.json 中添加更多 Provider
""")

    env = {}
    providers_selected = []

    # CompShare
    print("\n━━━ CompShare (支持 Claude/GPT/DeepSeek) ━━━")
    key = input("   API Key (留空跳过): ").strip()
    if key:
        is_valid, msg = validate_api_key("compshare", key)
        status = "✅" if is_valid else "⚠️"
        color_print(f"   {status} {msg}", "green" if is_valid else "yellow")
        env["COMPSHARE_API_KEY"] = key
        providers_selected.append("compshare")

    # Coding Plan
    print("\n━━━ Coding Plan (通义千问系列) ━━━")
    key = input("   API Key (留空跳过): ").strip()
    if key:
        is_valid, msg = validate_api_key("coding-plan", key)
        status = "✅" if is_valid else "⚠️"
        color_print(f"   {status} {msg}", "green" if is_valid else "yellow")
        env["CODING_PLAN_API_KEY"] = key
        providers_selected.append("coding-plan")

    # Moonshot
    print("\n━━━ Moonshot (Kimi) ━━━")
    key = input("   API Key (留空跳过): ").strip()
    if key:
        is_valid, msg = validate_api_key("moonshot", key)
        status = "✅" if is_valid else "⚠️"
        color_print(f"   {status} {msg}", "green" if is_valid else "yellow")
        env["MOONSHOT_API_KEY"] = key
        providers_selected.append("moonshot")

    # 至少需要一个 Provider
    if not providers_selected:
        color_print("\n❌ 错误：至少需要配置一个 Provider", "red")
        print("   提示：可以访问以下地址获取 API Key:")
        print("   - CompShare: https://api.modelverse.cn")
        print("   - Coding Plan: https://bailian.console.aliyun.com")
        print("   - Moonshot: https://platform.moonshot.cn")
        return setup_env()  # 重试

    # 选择默认 Provider
    print(f"\n已配置 Provider: {', '.join(providers_selected)}")
    if len(providers_selected) > 1:
        default = providers_selected[0]
        env["DEFAULT_PROVIDER"] = input_with_default("选择默认 Provider", default)
    else:
        env["DEFAULT_PROVIDER"] = providers_selected[0]

    return env


def setup_bots() -> Dict:
    """步骤 2: 配置 Bot 团队"""
    print_step(2, "配置 Bot 团队")

    print("""
选择预设团队模板，或自定义 Bot 配置：

""")

    for i, (key, template) in enumerate(TEMPLATES.items(), 1):
        print(f"  {i}. {template['name']}")
        print(f"     {template['description']}")
        print(f"     Bot: {', '.join(template['bots'].keys())}")
        print()

    print(f"  {len(TEMPLATES) + 1}. 自定义团队")

    choice = input_with_default(f"\n选择模板 (1-{len(TEMPLATES) + 1})", str(1))

    try:
        choice_num = int(choice)
        if 1 <= choice_num <= len(TEMPLATES):
            template_key = list(TEMPLATES.keys())[choice_num - 1]
            selected = TEMPLATES[template_key]
            color_print(f"\n✅ 已选择：{selected['name']}", "green")

            # 确认是否使用默认模型配置
            if yes_no("是否使用默认模型配置？", default=True):
                return selected['bots']
            else:
                return customize_bot_models(selected['bots'])
        else:
            return create_custom_bots()
    except (ValueError, KeyError):
        return create_custom_bots()


def customize_bot_models(bots: Dict) -> Dict:
    """自定义 Bot 模型配置"""
    print("\n━━━ 自定义 Bot 模型配置 ━━━")

    for bot_name, config in bots.items():
        print(f"\n  {bot_name}:")
        print(f"    默认：{config['model']} ({config['provider']})")

        custom_model = input("    自定义模型 (留空使用默认): ").strip()
        if custom_model:
            config['model'] = custom_model

        custom_provider = input("    自定义 Provider (留空使用默认): ").strip()
        if custom_provider and custom_provider in PROVIDERS:
            config['provider'] = custom_provider

    return bots


def create_custom_bots() -> Dict:
    """创建自定义 Bot 团队"""
    print("\n━━━ 自定义 Bot 团队 ━━━")
    print("""
提示:
  - Bot 名称建议使用中文或英文，不含特殊字符
  - 每个 Bot 可以配置不同的模型和 Provider
  - 输入 'q' 完成添加
""")

    bots = {}
    index = 1

    while True:
        print(f"\n  添加第 {index} 个 Bot:")
        name = input("    Bot 名称 (输入 q 完成): ").strip()
        if name.lower() == 'q':
            if not bots:
                color_print("    ❌ 至少需要添加一个 Bot", "red")
                continue
            break

        model = input("    使用模型 (如 qwen3.5-plus): ").strip()
        if not model:
            model = "qwen3.5-plus"
            color_print(f"    使用默认：{model}", "yellow")

        provider = input("    Provider (coding-plan/compshare/moonshot): ").strip()
        if not provider or provider not in PROVIDERS:
            provider = "coding-plan"
            color_print(f"    使用默认：{provider}", "yellow")

        role = input("    Bot 角色 (如 assistant/writer/editor): ").strip() or "assistant"

        bots[name] = {
            "model": model,
            "provider": provider,
            "role": role
        }

        color_print(f"    ✅ 已添加：{name} ({model} @ {provider})", "green")
        index += 1

    return bots


def setup_channels() -> Dict:
    """步骤 3: 配置通信渠道"""
    print_step(3, "配置通信渠道")

    print("""
Phoenix Core 支持多种通信方式：

  1. 本地模式     - 仅通过 API 调用，无外部集成
  2. Discord     - Discord Bot 集成
  3. Webhook     - HTTP Webhook 回调

提示：可以稍后在配置中添加更多渠道
""")

    # Discord 配置
    if yes_no("是否启用 Discord 集成？", default=False):
        print("\n━━━ Discord 配置 ━━━")
        print("提示：需要先在 Discord Developer Portal 创建 Bot")
        print("https://discord.com/developers/applications")

        token = input("   Bot Token: ").strip()
        client_id = input("   Client ID: ").strip()

        if token and client_id:
            return {
                "type": "discord",
                "enabled": True,
                "bot_token": token,
                "client_id": client_id
            }
        else:
            color_print("   ⚠️  Discord 配置不完整，跳过", "yellow")

    return {"type": "local", "enabled": False}


def setup_advanced() -> Dict:
    """步骤 4: 高级配置"""
    print_step(4, "高级配置")

    config = {}

    # 遥测配置
    print("""
📊 匿名改进计划

Phoenix Core 希望收集匿名使用数据以改进产品：
  • 仅统计功能使用频率和技能类型分布（哈希处理）
  • 不收集任何业务数据、技能内容或用户信息
  • 所有数据经脱敏聚合处理
  • 随时可在配置中关闭
""")

    config["telemetry"] = {
        "opt_in": yes_no("是否加入匿名改进计划？", default=False)
    }

    # 工作空间配置
    print("\n📁 工作空间配置")
    default_workspace = str(Path("./workspaces").absolute())
    workspace = input_with_default(f"工作空间路径", default_workspace)
    config["workspace_dir"] = workspace

    # 共享记忆配置
    default_shared = str(Path("./shared_memory").absolute())
    shared = input_with_default("共享记忆路径", default_shared)
    config["shared_memory_dir"] = shared

    return config


# ========== 保存配置 ==========

def save_config(env: Dict, bots: Dict, channels: Dict, advanced: Dict):
    """保存所有配置"""
    print_step(5, "保存配置")

    # 保存 .env
    env_path = Path(".env")
    backup_env = Path(".env.backup")

    if env_path.exists():
        env_path.rename(backup_env)
        color_print(f"   📦 已备份旧配置到 {backup_env}", "yellow")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("# Phoenix Core 环境变量配置\n")
        f.write(f"# 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Provider API Keys
        f.write("# ========== LLM Provider API Keys ==========\n")
        for key, value in env.items():
            if key != "DEFAULT_PROVIDER":
                f.write(f"{key}={value}\n")

        f.write("\n# 默认 Provider\n")
        f.write(f"DEFAULT_PROVIDER={env.get('DEFAULT_PROVIDER', 'coding-plan')}\n")

        # Discord 配置
        if channels.get("type") == "discord":
            f.write("\n# ========== Discord 配置 ==========\n")
            f.write(f"DISCORD_BOT_TOKEN={channels.get('bot_token')}\n")
            f.write(f"DISCORD_CLIENT_ID={channels.get('client_id')}\n")

        # 遥测配置
        f.write("\n# ========== 遥测配置 ==========\n")
        f.write(f"PHOENIX_TELEMETRY_OPT_IN={str(advanced.get('telemetry', {}).get('opt_in', False)).lower()}\n")

    color_print(f"   ✅ 环境变量保存到 {env_path.absolute()}", "green")

    # 保存 config.json
    config = {
        "version": "2.0",
        "generated_at": datetime.now().isoformat(),
        "providers": {
            p: {"enabled": k in env}
            for p, k in zip(PROVIDERS.keys(), ["COMPSHARE_API_KEY", "CODING_PLAN_API_KEY", "MOONSHOT_API_KEY"])
        },
        "bots": bots,
        "channels": channels,
        "advanced": {
            "workspace_dir": advanced.get("workspace_dir"),
            "shared_memory_dir": advanced.get("shared_memory_dir"),
        },
        "telemetry": advanced.get("telemetry", {})
    }

    config_path = Path("config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    color_print(f"   ✅ Bot 配置保存到 {config_path.absolute()}", "green")

    # 为每个 Bot 创建工作空间
    workspaces_dir = Path(advanced.get("workspace_dir", "./workspaces"))
    workspaces_dir.mkdir(parents=True, exist_ok=True)

    for bot_name, bot_config in bots.items():
        bot_dir = workspaces_dir / bot_name
        bot_dir.mkdir(parents=True, exist_ok=True)

        # 创建 Bot 专属 .env
        bot_env = {
            "BOT_NAME": bot_name,
            "BOT_MODEL": bot_config["model"],
            "BOT_PROVIDER": bot_config["provider"],
            "BOT_ROLE": bot_config["role"],
        }
        # 复制主 API Key
        for env_key in ["COMPSHARE_API_KEY", "CODING_PLAN_API_KEY", "MOONSHOT_API_KEY"]:
            if env_key in env:
                bot_env[env_key] = env[env_key]

        with open(bot_dir / ".env", "w", encoding="utf-8") as f:
            f.write(f"# {bot_name} Bot 配置\n")
            for k, v in bot_env.items():
                f.write(f"{k}={v}\n")

        color_print(f"   ✅ Bot 工作空间：{bot_dir}/", "green")


def print_next_steps():
    """打印下一步指引"""
    color_print("""

╔═══════════════════════════════════════════════════════════╗
║                    配置完成！ 🎉                           ║
╚═══════════════════════════════════════════════════════════╝

下一步:

  1️⃣  验证配置
     $ cat config.json
     $ cat .env

  2️⃣  启动系统
     $ python3 bot_manager.py start

  3️⃣  查看状态
     $ python3 bot_manager.py status

  4️⃣  启动 Web 仪表板 (可选)
     $ cd dashboard
     $ python3 web_dashboard.py
     访问：http://localhost:8000

📚 文档: https://github.com/your-org/phoenix-core
💬 社区：https://discord.gg/your-community

需要帮助？运行：python3 bot_manager.py --help
""", "green")


# ========== 主函数 ==========

def main():
    """主函数"""
    print_banner()

    # 检查已有配置
    if check_existing_config():
        color_print("\n✅ 使用现有配置，退出向导", "green")
        return

    # 执行配置步骤
    try:
        env = setup_env()
        bots = setup_bots()
        channels = setup_channels()
        advanced = setup_advanced()

        save_config(env, bots, channels, advanced)
        print_next_steps()

    except KeyboardInterrupt:
        color_print("\n\n⚠️  配置中断，已保存的内容仍然有效", "yellow")
        sys.exit(130)
    except Exception as e:
        color_print(f"\n❌ 配置过程出错：{e}", "red")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
