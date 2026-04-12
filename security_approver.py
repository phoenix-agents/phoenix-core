#!/usr/bin/env python3
"""
Security Approver - 安全审批系统

Phoenix Core Phoenix v2.0 基础安全审批

功能:
1. 危险命令检测 (rm, drop, truncate)
2. 风险分级 (低/中/高/禁止)
3. 中风险→Discord 确认
4. 高风险→用户确认
5. 审批日志记录

Usage:
    from security_approver import SecurityApprover

    approver = SecurityApprover(bot_name="编导")
    allowed, reason = approver.approve_command("rm -rf /tmp/test.txt")
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"           # 直接执行
    MEDIUM = "medium"     # 需要审批
    HIGH = "high"         # 需要用户确认
    BLOCKED = "blocked"   # 禁止执行


class SecurityApprover:
    """
    安全审批器

    对命令进行风险评估和审批
    """

    def __init__(self, bot_name: str):
        self.bot_name = bot_name
        self.workspace_dir = Path(f"workspaces/{bot_name}/")
        self.approval_log_dir = self.workspace_dir / "approvals"

        # 创建审批日志目录
        self.approval_log_dir.mkdir(parents=True, exist_ok=True)

        # 风险模式配置
        self.config = {
            "default_risk": "medium",  # 默认风险等级
            "auto_approve_low": True,  # 自动批准低风险
            "require_approval_medium": True,  # 中风险需要审批
            "require_user_high": True,  # 高风险需要用户确认
        }

        # 危险命令模式
        self._blocked_patterns = [
            # 危险删除命令
            (r'rm\s+(-[rf]+\s+)?/\s', 'BLOCKED', '禁止删除根目录内容'),
            (r'rm\s+-rf\s+/\s*', 'BLOCKED', '禁止强制删除根目录'),
            (r'rm\s+--no-preserve-root', 'BLOCKED', '禁止强制删除根目录'),

            # 数据库危险操作
            (r'drop\s+(database|table|schema)', 'BLOCKED', '禁止删除数据库对象'),
            (r'truncate\s+(table)?', 'BLOCKED', '禁止清空表'),

            # 系统命令
            (r'sudo\s+rm', 'BLOCKED', '禁止使用 sudo 删除'),
            (r'sudo\s+chmod\s+-R', 'BLOCKED', '禁止递归修改权限'),
            (r'sudo\s+chown\s+-R', 'BLOCKED', '禁止递归修改所有者'),

            # 网络攻击相关
            (r'curl.*\|\s*(bash|sh)', 'BLOCKED', '禁止执行远程脚本'),
            (r'wget.*\|\s*(bash|sh)', 'BLOCKED', '禁止执行远程脚本'),
        ]

        # 中风险命令模式
        self._medium_risk_patterns = [
            # 删除操作
            (r'rm\s+', 'MEDIUM', '删除文件需要审批'),
            (r'delete\s+', 'MEDIUM', '删除操作需要审批'),
            (r'rmdir\s+', 'MEDIUM', '删除目录需要审批'),

            # 修改操作
            (r'mv\s+', 'MEDIUM', '移动文件需要审批'),
            (r'chmod\s+', 'MEDIUM', '修改权限需要审批'),
            (r'chown\s+', 'MEDIUM', '修改所有者需要审批'),

            # 下载执行
            (r'curl\s+.*-o', 'MEDIUM', '下载文件需要审批'),
            (r'wget\s+', 'MEDIUM', '下载文件需要审批'),

            # 进程操作
            (r'kill\s+', 'MEDIUM', '终止进程需要审批'),
            (r'pkill\s+', 'MEDIUM', '终止进程需要审批'),
        ]

        # 低风险命令模式
        self._low_risk_patterns = [
            (r'^ls\s*', 'LOW', '列出文件'),
            (r'^pwd', 'LOW', '显示当前目录'),
            (r'^echo\s*', 'LOW', '输出文本'),
            (r'^cat\s+', 'LOW', '查看文件内容'),
            (r'^head\s+', 'LOW', '查看文件头部'),
            (r'^tail\s+', 'LOW', '查看文件尾部'),
            (r'^grep\s+', 'LOW', '搜索文本'),
            (r'^find\s+', 'LOW', '查找文件'),
            (r'^du\s+', 'LOW', '查看磁盘使用'),
            (r'^df\s+', 'LOW', '查看磁盘空间'),
        ]

    def approve_command(self, command: str, context: Dict = None) -> Tuple[bool, str]:
        """
        审批命令

        Args:
            command: 要执行的命令
            context: 执行上下文（可选）

        Returns:
            (是否允许，原因)
        """
        # 1. 检查是否被禁止的命令
        risk_level, reason = self._check_blocked(command)
        if risk_level == RiskLevel.BLOCKED:
            self._log_approval(command, risk_level, allowed=False, reason=reason)
            return False, reason

        # 2. 检查风险等级
        risk_level, reason = self._assess_risk(command)

        # 3. 根据风险等级决定
        if risk_level == RiskLevel.LOW:
            if self.config["auto_approve_low"]:
                self._log_approval(command, risk_level, allowed=True, reason="低风险命令")
                return True, "低风险命令，自动批准"

        elif risk_level == RiskLevel.MEDIUM:
            if self.config["require_approval_medium"]:
                # 需要审批（这里记录审批请求，实际审批需要用户确认）
                approval_request = self._create_approval_request(command, risk_level, context)
                reason = f"中风险命令，需要审批：{reason}"
                self._log_approval(command, risk_level, allowed=False, reason=reason)
                return False, reason
            else:
                self._log_approval(command, risk_level, allowed=True, reason="中风险但配置允许")
                return True, "中风险命令，已批准"

        elif risk_level == RiskLevel.HIGH:
            if self.config["require_user_high"]:
                # 需要用户确认
                approval_request = self._create_approval_request(command, risk_level, context)
                reason = f"高风险命令，需要用户确认：{reason}"
                self._log_approval(command, risk_level, allowed=False, reason=reason)
                return False, reason
            else:
                self._log_approval(command, risk_level, allowed=False, reason="高风险命令")
                return False, "高风险命令，禁止执行"

        # 默认：中风险，需要审批
        self._log_approval(command, RiskLevel.MEDIUM, allowed=False, reason="默认需要审批")
        return False, "未知风险等级，需要审批"

    def _check_blocked(self, command: str) -> Tuple[RiskLevel, str]:
        """检查命令是否被禁止"""
        for pattern, level, reason in self._blocked_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return RiskLevel.BLOCKED, reason

        return RiskLevel.LOW, ""

    def _assess_risk(self, command: str) -> Tuple[RiskLevel, str]:
        """评估命令风险等级"""
        # 检查中风险模式
        for pattern, level, reason in self._medium_risk_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                # 进一步检查是否有危险参数
                if self._has_dangerous_args(command):
                    return RiskLevel.HIGH, reason + " (含危险参数)"
                return RiskLevel.MEDIUM, reason

        # 检查低风险模式
        for pattern, level, reason in self._low_risk_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return RiskLevel.LOW, reason

        # 默认中风险
        return RiskLevel.MEDIUM, "未知命令，默认中风险"

    def _has_dangerous_args(self, command: str) -> bool:
        """检查命令是否有危险参数"""
        dangerous_patterns = [
            r'-rf\s+/',      # 强制删除根目录
            r'-rf\s+\*',    # 强制删除所有
            r'--force.*/',  # 强制操作根目录
            r'-y\s+rm',     # 自动确认删除
            r'>\s*/',       # 重定向到根目录
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                return True

        return False

    def _create_approval_request(self, command: str, risk_level: RiskLevel,
                                  context: Dict = None) -> Dict:
        """创建审批请求"""
        request = {
            "type": "command_approval",
            "bot_name": self.bot_name,
            "command": command,
            "risk_level": risk_level.value,
            "timestamp": datetime.now().isoformat(),
            "context": context or {},
            "status": "pending"
        }

        # 保存到审批日志
        approval_file = self.approval_log_dir / f"approval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(approval_file, "w", encoding="utf-8") as f:
            json.dump(request, f, indent=2, ensure_ascii=False)

        return request

    def _log_approval(self, command: str, risk_level: RiskLevel,
                      allowed: bool, reason: str):
        """记录审批日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "bot_name": self.bot_name,
            "command": command,
            "risk_level": risk_level.value,
            "allowed": allowed,
            "reason": reason
        }

        # 追加到日志文件
        log_file = self.approval_log_dir / f"approval_log_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        # 也记录到控制台
        status = "✅" if allowed else "❌"
        logger.info(f"[{self.bot_name}] {status} {risk_level.value}: {command[:50]}... ({reason})")

    def get_approval_stats(self, date: str = None) -> Dict:
        """获取审批统计"""
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        log_file = self.approval_log_dir / f"approval_log_{date}.jsonl"

        stats = {
            "bot_name": self.bot_name,
            "date": date,
            "total_requests": 0,
            "approved": 0,
            "denied": 0,
            "blocked": 0,
            "low_risk": 0,
            "medium_risk": 0,
            "high_risk": 0
        }

        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        stats["total_requests"] += 1

                        if entry["allowed"]:
                            stats["approved"] += 1
                        else:
                            stats["denied"] += 1
                            if entry["risk_level"] == "blocked":
                                stats["blocked"] += 1

                        stats[f"{entry['risk_level']}_risk"] += 1
                    except:
                        continue

        return stats


# 全局实例
_approvers: Dict[str, SecurityApprover] = {}


def get_security_approver(bot_name: str) -> SecurityApprover:
    """获取 Bot 的审批器实例"""
    if bot_name not in _approvers:
        _approvers[bot_name] = SecurityApprover(bot_name)
    return _approvers[bot_name]


def approve_command(bot_name: str, command: str, context: Dict = None) -> Tuple[bool, str]:
    """
    审批命令（便捷函数）

    Args:
        bot_name: Bot 名称
        command: 要执行的命令
        context: 执行上下文

    Returns:
        (是否允许，原因)
    """
    approver = get_security_approver(bot_name)
    return approver.approve_command(command, context)


def approve_skill_execution(bot_name: str, skill: Dict) -> Tuple[bool, str]:
    """
    审批技能执行

    Args:
        bot_name: Bot 名称
        skill: 技能定义

    Returns:
        (是否允许，原因)
    """
    # 提取技能中的命令
    steps = skill.get("steps", [])
    if isinstance(steps, list):
        steps = " ".join(steps)

    # 检查每个步骤
    commands = re.findall(r'```(?:bash|shell)?\s*(.*?)```', steps, re.DOTALL)

    for cmd in commands:
        allowed, reason = approve_command(bot_name, cmd.strip())
        if not allowed:
            return False, f"技能包含危险命令：{reason}"

    return True, "技能命令安全检查通过"


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Security Approver - 安全审批系统")
        print("\nUsage:")
        print("  python3 security_approver.py <bot_name> <command>")
        print("\nExamples:")
        print("  python3 security_approver.py 编导 'ls -la'")
        print("  python3 security_approver.py 编导 'rm -rf /tmp/test'")
        print("  python3 security_approver.py 编导 'rm -rf /'")
        sys.exit(1)

    bot_name = sys.argv[1]
    command = sys.argv[2]

    approver = SecurityApprover(bot_name)
    allowed, reason = approver.approve_command(command)

    print(f"\nBot: {bot_name}")
    print(f"Command: {command}")
    print(f"Allowed: {allowed}")
    print(f"Reason: {reason}")

    # 显示统计
    stats = approver.get_approval_stats()
    print(f"\nToday's Stats: {json.dumps(stats, indent=2)}")
