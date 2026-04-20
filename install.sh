#!/bin/bash
# Phoenix Core - 交互式安装向导
# 用法：bash install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
WORKSPACES_DIR="$SCRIPT_DIR/workspaces"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo "=================================================="
echo "  Phoenix Core v1.3 - 交互式安装向导"
echo "=================================================="
echo ""
echo "这将帮助你完成系统配置"
echo ""

# ========== 第一步：选择平台 ==========
echo -e "${CYAN}【1/5】选择要部署的平台${NC}"
echo ""
echo "支持的平台:"
echo "  1) Discord      - 游戏/社区机器人"
echo "  2) 微信企业版   - 企业内部使用"
echo "  3) 飞书         - 企业协作平台"
echo "  4) 钉钉         - 阿里巴巴办公平台"
echo "  5) WhatsApp     - 国际通用"
echo "  6) 暂不配置     - 仅安装核心系统"
echo ""
echo -n "请选择 [1-6]: "
read PLATFORM_CHOICE

case $PLATFORM_CHOICE in
    1)
        PLATFORM="discord"
        echo -e "${GREEN}✓ 选择：Discord${NC}"
        ;;
    2)
        PLATFORM="wecom"
        echo -e "${GREEN}✓ 选择：微信企业版${NC}"
        ;;
    3)
        PLATFORM="feishu"
        echo -e "${GREEN}✓ 选择：飞书${NC}"
        ;;
    4)
        PLATFORM="dingtalk"
        echo -e "${GREEN}✓ 选择：钉钉${NC}"
        ;;
    5)
        PLATFORM="whatsapp"
        echo -e "${GREEN}✓ 选择：WhatsApp${NC}"
        ;;
    *)
        PLATFORM="none"
        echo -e "${YELLOW}✓ 选择：暂不配置平台${NC}"
        ;;
esac

echo ""

# ========== 第二步：配置平台 Token ==========
if [ "$PLATFORM" != "none" ]; then
    echo -e "${CYAN}【2/5】配置 $PLATFORM 凭证${NC}"
    echo ""

    case $PLATFORM in
        discord)
            echo "获取 Discord Bot Token:"
            echo "  1. 访问 https://discord.com/developers/applications"
            echo "  2. 创建新应用 → Bot → Reset Token"
            echo ""
            echo -n "Discord Bot Token: "
            read DISCORD_TOKEN
            echo -n "Discord Channel ID (可选): "
            read DISCORD_CHANNEL
            ;;
        wecom)
            echo "获取微信企业版凭证:"
            echo "  1. 访问企业微信管理后台"
            echo "  2. 创建应用获取 CorpID 和 Secret"
            echo ""
            echo -n "企业微信 CorpID: "
            read WECOM_CORP_ID
            echo -n "应用 Secret: "
            read WECOM_SECRET
            ;;
        feishu)
            echo "获取飞书凭证:"
            echo "  1. 访问飞书开放平台"
            echo "  2. 创建应用获取 App ID 和 App Secret"
            echo ""
            echo -n "飞书 App ID: "
            read FEISHU_APP_ID
            echo -n "飞书 App Secret: "
            read FEISHU_APP_SECRET
            ;;
        dingtalk)
            echo "获取钉钉凭证:"
            echo "  1. 访问钉钉开放平台"
            echo "  2. 创建应用获取 AppKey 和 AppSecret"
            echo ""
            echo -n "钉钉 AppKey: "
            read DINGTALK_APP_KEY
            echo -n "钉钉 AppSecret: "
            read DINGTALK_APP_SECRET
            ;;
        whatsapp)
            echo "获取 WhatsApp 凭证:"
            echo "  1. 访问 Meta for Developers"
            echo "  2. 创建应用获取 Token"
            echo ""
            echo -n "WhatsApp Token: "
            read WHATSAPP_TOKEN
            ;;
    esac
    echo ""
fi

# ========== 第三步：配置 LLM ==========
echo -e "${CYAN}【3/5】配置 AI 模型${NC}"
echo ""
echo "支持的模型提供商:"
echo "  1) Anthropic (Claude)  - 推荐"
echo "  2) OpenAI (GPT)        - 通用选择"
echo "  3) 智谱 AI (GLM)        - 国产模型"
echo "  4) 自定义              - 其他兼容 OpenAI 的 API"
echo "  5) 暂不配置"
echo ""
echo -n "请选择 [1-5]: "
read MODEL_CHOICE

case $MODEL_CHOICE in
    1)
        PROVIDER="anthropic"
        echo -n "Anthropic API Key: "
        read API_KEY
        echo -n "默认模型 [claude-sonnet-4-6]: "
        read MODEL
        MODEL=${MODEL:-claude-sonnet-4-6}
        ;;
    2)
        PROVIDER="openai"
        echo -n "OpenAI API Key: "
        read API_KEY
        echo -n "默认模型 [gpt-4o]: "
        read MODEL
        MODEL=${MODEL:-gpt-4o}
        ;;
    3)
        PROVIDER="zhipu"
        echo -n "智谱 API Key: "
        read API_KEY
        echo -n "默认模型 [glm-4]: "
        read MODEL
        MODEL=${MODEL:-glm-4}
        ;;
    4)
        PROVIDER="custom"
        echo -n "自定义 API Base URL: "
        read API_BASE
        echo -n "API Key: "
        read API_KEY
        echo -n "默认模型："
        read MODEL
        ;;
    *)
        PROVIDER=""
        API_KEY=""
        MODEL=""
        echo -e "${YELLOW}✓ 暂不配置 AI 模型${NC}"
        ;;
esac

echo ""

# ========== 第四步：配置 Bot 信息 ==========
echo -e "${CYAN}【4/5】配置 Bot 信息${NC}"
echo ""
echo "Bot 名称是你在系统中识别这个 Bot 的名字"
echo -n "Bot 名称 [客服]: "
read BOT_NAME
BOT_NAME=${BOT_NAME:-客服}

echo ""
echo "Bot 角色定位（用于多 Bot 协作）:"
echo "  1) 协调者 - 分配任务给其他 Bot (如：客服主管)"
echo "  2) 执行者 - 执行具体任务 (如：文案、翻译)"
echo "  3) 专家   - 提供专业建议 (如：技术支持)"
echo "  0) 独立   - 单 Bot 工作，不与其他 Bot 协作"
echo ""
echo -n "请选择 [0-3]: "
read BOT_TYPE_CHOICE

case $BOT_TYPE_CHOICE in
    1) BOT_TYPE="coordinator" ;;
    2) BOT_TYPE="worker" ;;
    3) BOT_TYPE="specialist" ;;
    *) BOT_TYPE="standalone" ;;  # 默认独立模式
esac

echo ""

# ========== 第五步：远程调试 ==========
echo -e "${CYAN}【5/5】远程调试 (可选)${NC}"
echo ""
echo "远程调试允许技术支持团队远程协助调试"
echo "需要技术支持先运行调试服务器 (debug_master.py)"
echo ""
echo "功能:"
echo "  - 技术支持远程查看你的 Bot 日志"
echo "  - 技术支持远程更新你的 Bot 配置"
echo "  - 技术支持远程运行诊断命令"
echo ""
echo -n "是否启用远程调试？[y/N]: "
read REMOTE_DEBUG_CHOICE

if [ "$REMOTE_DEBUG_CHOICE" = "y" ] || [ "$REMOTE_DEBUG_CHOICE" = "Y" ]; then
    echo -n "调试服务器地址 (例如 192.168.1.100:9000): "
    read DEBUG_URL
    echo -n "设备 ID (留空自动生成，例如 客服 -001): "
    read DEBUG_DEVICE_ID
    echo -n "认证 Token (可选，技术支持提供): "
    read DEBUG_TOKEN
fi

echo ""

# ========== 生成配置文件 ==========
echo -e "${CYAN}正在生成配置文件...${NC}"

# 创建 .env 文件
cat > "$ENV_FILE" << EOF
# Phoenix Core 环境配置
# 生成时间：$(date)

# ===== 平台配置 =====
PLATFORM=$PLATFORM
EOF

if [ "$PLATFORM" = "discord" ]; then
    echo "DISCORD_BOT_TOKEN=$DISCORD_TOKEN" >> "$ENV_FILE"
    if [ -n "$DISCORD_CHANNEL" ]; then
        echo "DISCORD_CHANNEL_ID=$DISCORD_CHANNEL" >> "$ENV_FILE"
    fi
elif [ "$PLATFORM" = "wecom" ]; then
    echo "WECOM_CORP_ID=$WECOM_CORP_ID" >> "$ENV_FILE"
    echo "WECOM_SECRET=$WECOM_SECRET" >> "$ENV_FILE"
elif [ "$PLATFORM" = "feishu" ]; then
    echo "FEISHU_APP_ID=$FEISHU_APP_ID" >> "$ENV_FILE"
    echo "FEISHU_APP_SECRET=$FEISHU_APP_SECRET" >> "$ENV_FILE"
elif [ "$PLATFORM" = "dingtalk" ]; then
    echo "DINGTALK_APP_KEY=$DINGTALK_APP_KEY" >> "$ENV_FILE"
    echo "DINGTALK_APP_SECRET=$DINGTALK_APP_SECRET" >> "$ENV_FILE"
elif [ "$PLATFORM" = "whatsapp" ]; then
    echo "WHATSAPP_TOKEN=$WHATSAPP_TOKEN" >> "$ENV_FILE"
fi

cat >> "$ENV_FILE" << EOF

# ===== AI 模型配置 =====
DEFAULT_PROVIDER=$PROVIDER
DEFAULT_MODEL=$MODEL
EOF

if [ -n "$API_BASE" ]; then
    echo "API_BASE_URL=$API_BASE" >> "$ENV_FILE"
fi

if [ -n "$API_KEY" ]; then
    echo "ANTHROPIC_API_KEY=$API_KEY" >> "$ENV_FILE"
    echo "OPENAI_API_KEY=$API_KEY" >> "$ENV_FILE"
fi

cat >> "$ENV_FILE" << EOF

# ===== Bot 配置 =====
# Bot 角色定位：coordinator(协调者) / worker(执行者) / specialist(专家) / standalone(独立)
BOT_NAME=$BOT_NAME
BOT_TYPE=$BOT_TYPE
EOF

# 远程调试配置
if [ "$REMOTE_DEBUG_CHOICE" = "y" ] || [ "$REMOTE_DEBUG_CHOICE" = "Y" ]; then
    cat >> "$ENV_FILE" << EOF

# ===== 远程调试 =====
DEBUG_MASTER_URL=$DEBUG_URL
EOF
    if [ -n "$DEBUG_DEVICE_ID" ]; then
        echo "DEBUG_DEVICE_ID=$DEBUG_DEVICE_ID" >> "$ENV_FILE"
    fi
    if [ -n "$DEBUG_TOKEN" ]; then
        echo "DEBUG_AUTH_TOKEN=$DEBUG_TOKEN" >> "$ENV_FILE"
    fi
fi

echo -e "${GREEN}✓ 配置文件已生成：$ENV_FILE${NC}"
echo ""

# ========== 创建工作区 ==========
echo -e "${CYAN}创建工作区...${NC}"
mkdir -p "$WORKSPACES_DIR/$BOT_NAME"

cat > "$WORKSPACES_DIR/$BOT_NAME/BOT_CONFIG.yaml" << EOF
# Bot 配置文件
bot_name: $BOT_NAME
bot_type: $BOT_TYPE
language: zh-CN
workspace: workspaces/$BOT_NAME
platform: $PLATFORM
EOF

echo -e "${GREEN}✓ 工作区已创建：workspaces/$BOT_NAME${NC}"
echo ""

# ========== 安装依赖 ==========
echo -e "${CYAN}检查依赖...${NC}"

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建虚拟环境...${NC}"
    python3 -m venv venv
fi

source venv/bin/activate

echo "安装/更新依赖..."
pip install -q -r requirements.txt

echo -e "${GREEN}✓ 依赖已安装${NC}"
echo ""

# ========== 完成 ==========
echo ""
echo "=================================================="
echo -e "${GREEN}  ✅ 安装完成!${NC}"
echo "=================================================="
echo ""
echo "配置摘要:"
echo "  平台：$PLATFORM"
echo "  AI 模型：$PROVIDER / $MODEL"
echo "  Bot 名称：$BOT_NAME"
echo "  Bot 类型：$BOT_TYPE"
if [ "$REMOTE_DEBUG_CHOICE" = "y" ] || [ "$REMOTE_DEBUG_CHOICE" = "Y" ]; then
    echo "  远程调试：已启用"
fi
echo ""
echo "下一步操作:"
echo ""
echo "  1. 启动 Dashboard + Bot:"
echo "     ${BLUE}bash start.sh $BOT_NAME${NC}"
echo ""
echo "  2. 访问 Dashboard:"
echo "     ${BLUE}http://localhost:8000${NC}"
echo ""
echo "  3. 在对应平台中 @你的 Bot 进行测试"
echo ""
echo "=================================================="
echo ""
INSTALLSCRIPT
chmod +x /Users/wangsai/phoenix-core/install.sh