#!/usr/bin/env python3
"""
Skill Approval Tool - 技能审批工具

用于审批和管理待处理的技能
"""

import json
from pathlib import Path
from typing import List, Dict
import sys

WORKSPACES_DIR = Path(__file__).parent / "workspaces"


def find_pending_approvals() -> List[Path]:
    """查找所有待审批的技能"""
    approvals = []
    for bot_dir in WORKSPACES_DIR.iterdir():
        if not bot_dir.is_dir():
            continue

        # Check DYNAMIC/approvals
        dynamic_dir = bot_dir / "DYNAMIC"
        if dynamic_dir.exists():
            for f in dynamic_dir.glob("approval_*.json"):
                approvals.append(f)

        # Check approvals dir
        approvals_dir = bot_dir / "approvals"
        if approvals_dir.exists():
            for f in approvals_dir.glob("approval_*.json"):
                approvals.append(f)

    return sorted(approvals, reverse=True)


def load_approval(approval_file: Path) -> Dict:
    """加载审批文件"""
    with open(approval_file, "r", encoding="utf-8") as f:
        return json.load(f)


def approve_skill(approval_file: Path) -> bool:
    """批准技能并保存到 skills 目录"""
    approval = load_approval(approval_file)

    bot_name = approval.get("bot_name", "unknown")
    skill_name = approval.get("skill_name", "unnamed")
    skill_preview = approval.get("skill_preview", "")

    # Save to skills directory
    bot_dir = WORKSPACES_DIR / bot_name
    skills_dir = bot_dir / "DYNAMIC" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Generate skill filename
    safe_name = skill_name.replace("/", "_").replace("\\", "_")[:50]
    skill_file = skills_dir / f"{safe_name}.md"

    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(skill_preview)

    # Update approval status
    approval["status"] = "approved"
    approval["skill_file"] = str(skill_file)

    with open(approval_file, "w", encoding="utf-8") as f:
        json.dump(approval, f, indent=2, ensure_ascii=False)

    print(f"✅ Approved: {bot_name} - {skill_name}")
    print(f"   Saved to: {skill_file}")
    return True


def reject_skill(approval_file: Path) -> bool:
    """拒绝技能"""
    approval = load_approval(approval_file)
    approval["status"] = "rejected"

    with open(approval_file, "w", encoding="utf-8") as f:
        json.dump(approval, f, indent=2, ensure_ascii=False)

    bot_name = approval.get("bot_name", "unknown")
    skill_name = approval.get("skill_name", "unnamed")
    print(f"❌ Rejected: {bot_name} - {skill_name}")
    return True


def list_approvals(approvals: List[Path]):
    """列出所有待审批"""
    print(f"\n{'='*60}")
    print(f"待审批技能列表 (共 {len(approvals)} 个)")
    print(f"{'='*60}\n")

    for i, f in enumerate(approvals, 1):
        approval = load_approval(f)
        status = approval.get("status", "pending")
        bot = approval.get("bot_name", "?")
        name = approval.get("skill_name", "?")
        ts = approval.get("timestamp", "?")[:19]

        status_icon = "⏳" if status == "pending" else ("✅" if status == "approved" else "❌")
        print(f"{i}. {status_icon} [{bot}] {name}")
        print(f"   时间：{ts}")
        print(f"   文件：{f.name}")
        print()


def main():
    print("="*60)
    print("Skill Approval Tool - 技能审批工具")
    print("="*60)

    approvals = find_pending_approvals()
    pending = [a for a in approvals if load_approval(a).get("status") == "pending"]

    if not pending:
        print("\n没有待审批的技能！")
        return

    list_approvals(pending)

    print("="*60)
    print("操作指南:")
    print("  approve <编号>  - 批准指定技能")
    print("  reject <编号>   - 拒绝指定技能")
    print("  approve all     - 批准所有待审批")
    print("  exit            - 退出")
    print("="*60)

    if len(sys.argv) > 1:
        # Command line mode
        cmd = sys.argv[1]
        if cmd == "all":
            print(f"\n批准 {len(pending)} 个技能...")
            for a in pending:
                approve_skill(a)
            return
        elif cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(pending):
                approve_skill(pending[idx])
            return

    # Interactive mode
    while True:
        try:
            cmd = input("\n请输入命令：").strip()
        except EOFError:
            break

        if cmd == "exit":
            break

        parts = cmd.split()
        if len(parts) < 2:
            print("命令格式：approve <编号> 或 reject <编号>")
            continue

        action, arg = parts[0], parts[1]

        if arg == "all":
            for a in pending:
                if action == "approve":
                    approve_skill(a)
                elif action == "reject":
                    reject_skill(a)
        elif arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(pending):
                if action == "approve":
                    approve_skill(pending[idx])
                elif action == "reject":
                    reject_skill(pending[idx])
            else:
                print(f"编号超出范围 (1-{len(pending)})")


if __name__ == "__main__":
    main()
