#!/usr/bin/env python3
"""
Phoenix Core 代码完整性校验

验证关键文件是否被篡改。

Usage:
    python3 integrity_check.py
"""

import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime

# 关键文件列表 (需要校验完整性的文件)
CRITICAL_FILES = [
    "license_manager.py",
    "phoenix.py",
    "bot_manager.py",
    "enterprise_features.py",
]

# 哈希存储文件
HASH_STORE_FILE = Path(__file__).parent / ".integrity_hashes.json"


def calculate_file_hash(filepath: Path) -> str:
    """计算文件 SHA256 哈希"""
    sha256_hash = hashlib.sha256()

    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


def generate_baseline():
    """生成基准哈希值 (发布时执行)"""
    print("📋 生成完整性基准哈希...\n")

    hashes = {
        "generated_at": datetime.now().isoformat(),
        "version": "2.0.0",
        "files": {}
    }

    for filename in CRITICAL_FILES:
        filepath = Path(__file__).parent / filename
        if filepath.exists():
            file_hash = calculate_file_hash(filepath)
            hashes["files"][filename] = file_hash
            print(f"  ✅ {filename}: {file_hash[:16]}...")
        else:
            print(f"  ⚠️  {filename}: 文件不存在")

    # 保存哈希
    with open(HASH_STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2)

    print(f"\n✅ 基准哈希已保存到：{HASH_STORE_FILE}")
    return hashes


def verify_integrity():
    """验证代码完整性"""
    print("🔒 验证代码完整性...\n")

    # 加载基准哈希
    if not HASH_STORE_FILE.exists():
        print("⚠️  基准哈希文件不存在，先生成基准...")
        generate_baseline()
        return True

    with open(HASH_STORE_FILE, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    all_ok = True

    for filename, expected_hash in baseline.get("files", {}).items():
        filepath = Path(__file__).parent / filename

        if not filepath.exists():
            print(f"  ❌ {filename}: 文件缺失!")
            all_ok = False
            continue

        current_hash = calculate_file_hash(filepath)

        if current_hash == expected_hash:
            print(f"  ✅ {filename}: 校验通过")
        else:
            print(f"  ❌ {filename}: 校验失败 (可能被篡改)")
            print(f"     期望：{expected_hash[:16]}...")
            print(f"     实际：{current_hash[:16]}...")
            all_ok = False

    print()

    if all_ok:
        print("✅ 所有文件完整性校验通过")
        return True
    else:
        print("⚠️  部分文件校验失败，代码可能被篡改!")
        return False


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--generate":
        # 生成基准
        generate_baseline()
    else:
        # 验证完整性
        success = verify_integrity()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
