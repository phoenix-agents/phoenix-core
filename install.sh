#!/usr/bin/env bash
#
# OpenClaw-X 安装脚本
#
# 功能:
# 1. 检查系统依赖
# 2. 创建必要目录
# 3. 安装 Python 依赖
# 4. 配置环境变量
# 5. 初始化 Bot 工作空间
#
# Usage:
#   ./install.sh
#   ./install.sh --production
#   ./install.sh --dev

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
INSTALL_DIR="${INSTALL_DIR:-$HOME/openclaw-x}"
WORKSPACES_DIR="$INSTALL_DIR/workspaces"
TEAMS_DIR="$INSTALL_DIR/teams"
EVOLUTION_DIR="$INSTALL_DIR/evolution_triggers"
PYTHON="${PYTHON:-python3}"
PIP="${PIP:-pip3}"

# 解析参数
PRODUCTION=false
DEV=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --production)
            PRODUCTION=true
            shift
            ;;
        --dev)
            DEV=true
            shift
            ;;
        --help)
            echo "OpenClaw-X 安装脚本"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --production    生产环境安装 (跳过测试依赖)"
            echo "  --dev           开发环境安装 (包含测试和调试工具)"
            echo "  --help          显示帮助"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查系统依赖
check_dependencies() {
    echo_info "Checking system dependencies..."

    # 检查 Python
    if ! command -v $PYTHON &> /dev/null; then
        echo_error "Python 3 is required but not installed"
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo_success "Python $PYTHON_VERSION detected"

    # 检查 Python 版本 (需要 3.8+)
    if [[ $(echo "$PYTHON_VERSION < 3.8" | bc) == "1" ]]; then
        echo_error "Python 3.8 or higher is required"
        exit 1
    fi

    # 检查 pip
    if ! command -v $PIP &> /dev/null; then
        echo_warning "pip not found, attempting to install..."
        $PYTHON -m ensurepip --upgrade || true
    fi

    # 检查 git
    if ! command -v git &> /dev/null; then
        echo_warning "git not found, some features may be limited"
    fi

    # 检查 SQLite
    if ! $PYTHON -c "import sqlite3" &> /dev/null; then
        echo_error "SQLite3 module is required but not available"
        exit 1
    fi

    echo_success "System dependencies check passed"
}

# 创建目录结构
create_directories() {
    echo_info "Creating directory structure..."

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$WORKSPACES_DIR"
    mkdir -p "$TEAMS_DIR"
    mkdir -p "$EVOLUTION_DIR"

    # 创建内置 Bot 工作空间
    BUILTIN_BOTS=("编导" "剪辑" "美工" "场控" "客服" "运营" "渠道" "小小谦")
    for bot in "${BUILTIN_BOTS[@]}"; do
        bot_dir="$WORKSPACES_DIR/$bot"
        if [[ ! -d "$bot_dir" ]]; then
            mkdir -p "$bot_dir/memory/知识库"
            mkdir -p "$bot_dir/memory/项目"
            mkdir -p "$bot_dir/memory/学习笔记"
            mkdir -p "$bot_dir/memory/日志"
            mkdir -p "$bot_dir/DYNAMIC/skills"
            mkdir -p "$bot_dir/DYNAMIC/learnings"
            mkdir -p "$bot_dir/DYNAMIC/relationships"
        fi
    done

    echo_success "Directory structure created"
}

# 安装 Python 依赖
install_python_deps() {
    echo_info "Installing Python dependencies..."

    # 检查 requirements.txt
    if [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
        $PIP install -r "$INSTALL_DIR/requirements.txt" --quiet
        echo_success "Python dependencies installed"
    else
        # 默认依赖
        $PIP install requests rich click python-dotenv aiohttp --quiet --upgrade
        echo_success "Default Python dependencies installed"
    fi

    # 开发环境额外依赖
    if [[ "$DEV" == true ]]; then
        echo_info "Installing development dependencies..."
        $PIP install pytest pytest-cov black flake8 mypy --quiet --upgrade
        echo_success "Development dependencies installed"
    fi
}

# 配置环境变量
setup_environment() {
    echo_info "Setting up environment..."

    # 创建 .env 文件
    ENV_FILE="$INSTALL_DIR/.env"
    if [[ ! -f "$ENV_FILE" ]]; then
        cat > "$ENV_FILE" << 'EOF'
# OpenClaw-X Environment Configuration

# AI Provider Configuration
DASHSCOPE_API_KEY=your_api_key_here
COMPShare_API_KEY=your_api_key_here

# Discord Configuration (optional)
DISCORD_TOKEN=your_discord_token_here

# Model Configuration
DEFAULT_MODEL=claude-sonnet-4-6
FALLBACK_MODEL=qwen3-coder-next

# System Configuration
LOG_LEVEL=INFO
HEARTBEAT_INTERVAL=30
EOF
        echo_success "Environment file created: $ENV_FILE"
        echo_warning "Please update API keys in $ENV_FILE"
    else
        echo_info "Environment file already exists: $ENV_FILE"
    fi

    # 创建配置说明
    cat > "$INSTALL_DIR/CONFIG_GUIDE.md" << 'EOF'
# OpenClaw-X 配置指南

## 环境变量配置

编辑 `.env` 文件，设置以下必需的配置：

### AI Provider 配置

```bash
# DashScope (通义千问) API Key
DASHSCOPE_API_KEY=sk-xxx

# CompShare API Key (如有使用)
COMPShare_API_KEY=xxx
```

### 模型配置

```bash
# 默认模型
DEFAULT_MODEL=claude-sonnet-4-6

# 降级备用模型
FALLBACK_MODEL=qwen3-coder-next
```

### Discord 集成 (可选)

```bash
DISCORD_TOKEN=your_discord_bot_token
```

## Bot 配置

每个 Bot 在 `workspaces/<BotName>/` 目录下有自己的配置文件：

- `.env` - Bot 专属配置
- `SOUL.md` - Bot 人设定义
- `IDENTITY.md` - Bot 身份说明
- `AGENTS.md` - Bot 工作手册

## 团队配置

编辑 `team_topology.json` 配置团队结构：

```json
{
  "teams": {
    "内容团队": {
      "members": ["编导", "剪辑", "美工"],
      "lead_bot": "编导"
    }
  }
}
```
EOF

    echo_success "Configuration guide created"
}

# 初始化 Bot 注册表
init_bot_registry() {
    echo_info "Initializing Bot registry..."

    # 运行 Bot 注册表初始化
    if [[ -f "$INSTALL_DIR/bot_registry.py" ]]; then
        $PYTHON "$INSTALL_DIR/bot_registry.py" stats || true
        echo_success "Bot registry initialized"
    fi
}

# 初始化团队拓扑
init_team_topology() {
    echo_info "Initializing team topology..."

    # 创建默认团队配置
    if [[ ! -f "$INSTALL_DIR/team_topology.json" ]]; then
        cat > "$INSTALL_DIR/team_topology.json" << 'EOF'
{
  "last_updated": "2026-04-10T00:00:00",
  "teams": {
    "内容团队": {
      "name": "内容团队",
      "description": "内容策划与制作",
      "lead_bot": "编导",
      "members": ["编导", "剪辑", "美工"],
      "skills": ["内容策划", "视频制作", "视觉设计"],
      "status": "active"
    },
    "运营团队": {
      "name": "运营团队",
      "description": "粉丝运营与数据分析",
      "lead_bot": "运营",
      "members": ["场控", "客服", "运营"],
      "skills": ["数据分析", "用户运营", "活动策划"],
      "status": "active"
    },
    "商务团队": {
      "name": "商务团队",
      "description": "商务合作与渠道拓展",
      "lead_bot": "渠道",
      "members": ["渠道"],
      "skills": ["商务谈判", "渠道管理"],
      "status": "active"
    },
    "协调团队": {
      "name": "协调团队",
      "description": "系统协调与任务调度",
      "lead_bot": "小小谦",
      "members": ["小小谦"],
      "skills": ["任务调度", "系统协调", "跨团队协作"],
      "status": "active"
    }
  },
  "bot_team_map": {
    "编导": "内容团队",
    "剪辑": "内容团队",
    "美工": "内容团队",
    "场控": "运营团队",
    "客服": "运营团队",
    "运营": "运营团队",
    "渠道": "商务团队",
    "小小谦": "协调团队"
  }
}
EOF
        echo_success "Default team topology created"
    fi
}

# 验证安装
verify_installation() {
    echo_info "Verifying installation..."

    # 检查核心模块
    CORE_MODULES=(
        "bot_registry.py"
        "team_topology.py"
        "dynamic_growth_engine.py"
        "memory_manager_v2.py"
        "autonomous_evolution_trigger.py"
        "security_approver.py"
        "tech_radar.py"
        "ai_evaluator.py"
        "cli.py"
    )

    missing=0
    for module in "${CORE_MODULES[@]}"; do
        if [[ ! -f "$INSTALL_DIR/$module" ]]; then
            echo_error "Missing core module: $module"
            ((missing++))
        fi
    done

    if [[ $missing -gt 0 ]]; then
        echo_error "$missing core modules missing"
        return 1
    fi

    echo_success "All core modules present"

    # 测试 Python 模块导入
    echo_info "Testing module imports..."
    $PYTHON -c "
import sys
sys.path.insert(0, '$INSTALL_DIR')
try:
    from bot_registry import BotRegistry
    from team_topology import TeamTopology
    print('All modules imported successfully')
except Exception as e:
    print(f'Import error: {e}')
    exit(1)
" || return 1

    echo_success "Module imports verified"
}

# 显示安装后信息
show_post_install() {
    echo ""
    echo_success "OpenClaw-X installation completed!"
    echo ""
    echo "=============================================="
    echo "Next Steps:"
    echo "=============================================="
    echo ""
    echo "1. Configure API keys:"
    echo "   nano $INSTALL_DIR/.env"
    echo ""
    echo "2. Verify installation:"
    echo "   python3 $INSTALL_DIR/cli.py --version"
    echo ""
    echo "3. Check Bot status:"
    echo "   python3 $INSTALL_DIR/cli.py health"
    echo ""
    echo "4. List available Bots:"
    echo "   python3 $INSTALL_DIR/bot_registry.py list"
    echo ""
    echo "5. List teams:"
    echo "   python3 $INSTALL_DIR/team_topology.py list"
    echo ""
    echo "=============================================="
    echo "Documentation:"
    echo "  - $INSTALL_DIR/CONFIG_GUIDE.md"
    echo "  - $INSTALL_DIR/PHOENIX_V2_FINAL_REPORT.md"
    echo "=============================================="
    echo ""
}

# 主安装流程
main() {
    echo ""
    echo "=============================================="
    echo "  OpenClaw-X Phoenix v2.0 Installer"
    echo "=============================================="
    echo ""

    check_dependencies
    create_directories
    install_python_deps
    setup_environment
    init_bot_registry
    init_team_topology
    verify_installation
    show_post_install
}

# 运行安装
main
