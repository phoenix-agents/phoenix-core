#!/usr/bin/env python3
"""
批量生成测试用 License Key

Usage:
    python3 scripts/generate_test_keys.py --count 10 --type standard
    python3 scripts/generate_test_keys.py --count 5 --type professional
"""

import argparse
import uuid
import json
from datetime import datetime, timedelta
from pathlib import Path


def generate_license_key(license_type: str, serial: int) -> str:
    """生成 License Key"""
    type_codes = {
        "standard": "STD",
        "professional": "PRO",
        "enterprise": "ENT"
    }

    type_code = type_codes.get(license_type, "STD")

    # 生成随机码 (使用 UUID)
    random_uuid = uuid.uuid4().hex[:8].upper()
    parts = [random_uuid[i:i+4] for i in range(0, 8, 4)]

    # 格式：PHOENIX-{TYPE}-{XXXX}-{XXXX}
    return f"PHOENIX-{type_code}-TEST-{parts[0]}-{parts[1]}"


def generate_test_license(license_type: str, serial: int, days: int = 30) -> dict:
    """生成完整的测试 License"""
    license_key = generate_license_key(license_type, serial)
    expiry_date = datetime.now() + timedelta(days=days)

    features = {
        "standard": ["cloud_sync", "monitoring", "support", "10_bots"],
        "professional": ["cloud_sync", "monitoring", "24x7_support",
                        "unlimited_bots", "custom_dev", "training"],
        "enterprise": ["cloud_sync", "monitoring", "24x7_support",
                      "unlimited_bots", "custom_dev", "training",
                      "on_premise", "dedicated_manager"]
    }

    return {
        "license_key": license_key,
        "license_type": license_type,
        "serial": serial,
        "expiry_date": expiry_date.isoformat(),
        "days": days,
        "features": features.get(license_type, []),
        "created_at": datetime.now().isoformat(),
        "status": "available"  # available/activated/expired
    }


def batch_generate(count: int, license_type: str, days: int = 30) -> list:
    """批量生成测试 License"""
    licenses = []

    # 读取已有的 serial
    output_file = Path(__file__).parent / "test_keys.json"
    start_serial = 1
    if output_file.exists():
        with open(output_file, "r") as f:
            existing = json.load(f)
            if existing:
                start_serial = max(k["serial"] for k in existing) + 1

    for i in range(count):
        serial = start_serial + i
        license_data = generate_test_license(license_type, serial, days)
        licenses.append(license_data)

    return licenses


def save_licenses(licenses: list, output_file: str = None):
    """保存 License 到文件"""
    if output_file is None:
        output_file = Path(__file__).parent / "test_keys.json"
    else:
        output_file = Path(output_file)

    # 读取已有数据
    existing = []
    if output_file.exists():
        with open(output_file, "r") as f:
            existing = json.load(f)

    # 合并
    existing.extend(licenses)

    # 保存
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    return output_file


def print_licenses(licenses: list):
    """打印生成的 License"""
    print("\n" + "=" * 60)
    print(f"生成 {len(licenses)} 个测试 License Key")
    print("=" * 60 + "\n")

    for lic in licenses:
        expiry = datetime.fromisoformat(lic["expiry_date"])
        print(f"类型：{lic['license_type'].upper()}")
        print(f"Key:  {lic['license_key']}")
        print(f"有效期：{lic['days']} 天 (至 {expiry.strftime('%Y-%m-%d')})")
        print(f"功能：{', '.join(lic['features'][:3])}...")
        print("-" * 60)

    print(f"\n✅ 已保存到 scripts/test_keys.json")
    print(f"\n激活方式:")
    print(f"   python3 license_manager.py activate <license_key>")


def main():
    parser = argparse.ArgumentParser(description="批量生成测试 License Key")
    parser.add_argument("--count", "-c", type=int, default=10,
                       help="生成数量 (默认 10)")
    parser.add_argument("--type", "-t", type=str, default="standard",
                       choices=["standard", "professional", "enterprise"],
                       help="License 类型 (默认 standard)")
    parser.add_argument("--days", "-d", type=int, default=30,
                       help="有效期天数 (默认 30)")
    parser.add_argument("--output", "-o", type=str, default=None,
                       help="输出文件路径")

    args = parser.parse_args()

    print(f"\n🔑 正在生成测试 License Key...")
    print(f"   类型：{args.type}")
    print(f"   数量：{args.count}")
    print(f"   有效期：{args.days} 天\n")

    # 批量生成
    licenses = batch_generate(args.count, args.type, args.days)

    # 保存
    output_file = save_licenses(licenses, args.output)

    # 打印
    print_licenses(licenses)


if __name__ == "__main__":
    main()
