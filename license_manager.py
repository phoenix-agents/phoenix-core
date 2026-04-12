#!/usr/bin/env python3
"""
Phoenix Core License Manager - 许可证管理器

管理企业版 License 的激活、验证和过期检查。

Usage:
    python3 license_manager.py activate <license_key>
    python3 license_manager.py status
    python3 license_manager.py deactivate
"""

import json
import hashlib
import uuid
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# 配置
PHOENIX_CORE_DIR = Path(__file__).parent
LICENSE_FILE = PHOENIX_CORE_DIR / ".license.json"
LICENSE_SERVER_URL = "https://api.phoenix-core.dev/license/verify"  # 待实现


class LicenseInfo:
    """许可证信息"""

    def __init__(self, data: Dict[str, Any]):
        self.license_key = data.get("license_key", "")
        self.license_type = data.get("license_type", "community")  # community/standard/professional/enterprise
        self.email = data.get("email", "")
        self.company = data.get("company", "")
        self.expiry_date = data.get("expiry_date")  # None = 永久
        self.max_bots = data.get("max_bots", 1)
        self.features = data.get("features", [])
        self.valid = data.get("valid", False)

    @property
    def is_expired(self) -> bool:
        """检查是否过期"""
        if not self.expiry_date:
            return False  # None = 永久
        try:
            expiry = datetime.fromisoformat(self.expiry_date)
            return datetime.now() > expiry
        except Exception:
            return True

    @property
    def days_remaining(self) -> int:
        """剩余天数"""
        if not self.expiry_date:
            return 999999  # 永久
        try:
            expiry = datetime.fromisoformat(self.expiry_date)
            delta = expiry - datetime.now()
            return max(0, delta.days)
        except Exception:
            return 0

    def __repr__(self):
        return f"License({self.license_type}, valid={self.valid}, expires={self.expiry_date})"


class LicenseManager:
    """许可证管理器"""

    def __init__(self):
        self.license: Optional[LicenseInfo] = None
        self._load_license()

    def _load_license(self):
        """从本地加载许可证"""
        if LICENSE_FILE.exists():
            try:
                with open(LICENSE_FILE, "r") as f:
                    data = json.load(f)
                self.license = LicenseInfo(data)
                # 检查过期
                if self.license.is_expired:
                    self.license.valid = False
                    self._save_license()
            except Exception as e:
                print(f"⚠️  加载许可证失败：{e}")
                self.license = LicenseInfo({"license_type": "community"})
        else:
            self.license = LicenseInfo({"license_type": "community"})

    def _save_license(self, data: Optional[Dict] = None):
        """保存许可证到本地"""
        if data:
            license_data = data
        elif self.license:
            license_data = {
                "license_key": self.license.license_key,
                "license_type": self.license.license_type,
                "email": self.license.email,
                "company": self.license.company,
                "expiry_date": self.license.expiry_date,
                "max_bots": self.license.max_bots,
                "features": self.license.features,
                "valid": self.license.valid
            }
        else:
            return

        LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LICENSE_FILE, "w") as f:
            json.dump(license_data, f, indent=2)

    def _generate_machine_id(self) -> str:
        """生成机器唯一标识"""
        # 使用 UUID + 主机名哈希
        hostname = os.uname().nodename if os.name != 'nt' else os.getlogin()
        unique_id = f"{uuid.getnode()}_{hostname}"
        return hashlib.sha256(unique_id.encode()).hexdigest()[:16]

    def _verify_license_offline(self, license_key: str) -> Optional[Dict]:
        """离线验证 License (简化版)"""
        # 实际应该调用云端 API
        # 这里仅作示例
        if license_key.startswith("PHOENIX-"):
            # 模拟验证通过
            return {
                "valid": True,
                "license_type": "standard",
                "email": "user@example.com",
                "company": "Test Company",
                "expiry_date": (datetime.now() + timedelta(days=30)).isoformat(),
                "max_bots": 10,
                "features": ["cloud_sync", "monitoring", "support"]
            }
        return None

    def _verify_license_online(self, license_key: str) -> Optional[Dict]:
        """云端验证 License (推荐用于生产环境)"""
        try:
            import urllib.request
            import json

            # 云端验证 API (待实现)
            url = "https://api.phoenix-core.dev/license/verify"
            data = json.dumps({
                "license_key": license_key,
                "machine_id": self._generate_machine_id(),
                "version": "2.0.0"
            }).encode('utf-8')

            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            response = urllib.request.urlopen(req, timeout=10)
            result = json.loads(response.read())

            if result.get("valid"):
                return result
            return None

        except Exception as e:
            logger.debug(f"云端验证失败：{e}")
            # 降级为离线验证 (可配置)
            return self._verify_license_offline(license_key)

    def activate(self, license_key: str) -> bool:
        """激活许可证"""
        print(f"🔑 正在激活许可证：{license_key[:20]}...")

        # 离线验证 (演示用)
        # 实际应该调用云端 API: self._verify_license_online(license_key)
        result = self._verify_license_offline(license_key)

        if result and result.get("valid"):
            self.license = LicenseInfo({
                "license_key": license_key,
                "license_type": result["license_type"],
                "email": result.get("email", ""),
                "company": result.get("company", ""),
                "expiry_date": result.get("expiry_date"),
                "max_bots": result.get("max_bots", 1),
                "features": result.get("features", []),
                "valid": True
            })
            self._save_license()
            print(f"✅ 激活成功!")
            print(f"   类型：{self.license.license_type}")
            print(f"   过期：{self.license.expiry_date or '永久'}")
            print(f"   剩余：{self.license.days_remaining} 天")
            return True
        else:
            print(f"❌ 激活失败：无效的许可证")
            return False

    def deactivate(self):
        """禁用许可证 (恢复社区版)"""
        print("🔓 正在禁用许可证...")
        self.license = LicenseInfo({"license_type": "community"})
        if LICENSE_FILE.exists():
            LICENSE_FILE.unlink()
        print("✅ 已恢复为社区版")

    def status(self):
        """显示许可证状态"""
        print("\n📋 Phoenix Core 许可证状态\n")

        if self.license and self.license.valid:
            print(f"许可证类型：{self.license.license_type.upper()}")
            print(f"许可证密钥：{self.license.license_key[:20]}...")
            if self.license.company:
                print(f"公司名称：{self.license.company}")
            if self.license.email:
                print(f"绑定邮箱：{self.license.email}")
            print(f"最大 Bot 数：{self.license.max_bots}")
            print(f"有效期至：{self.license.expiry_date or '永久'}")
            print(f"剩余天数：{self.license.days_remaining}")
            print(f"功能特性:")
            for feature in self.license.features:
                print(f"  ✅ {feature}")
        else:
            print("许可证类型：COMMUNITY (社区版)")
            print("状态：未激活")
            print("\n💡 升级到企业版：访问 phoenix-core.dev/pricing")

        print()

    def check_feature_enabled(self, feature: str) -> bool:
        """检查功能是否启用"""
        if not self.license or not self.license.valid:
            return False
        return feature in self.license.features

    def get_max_bots(self) -> int:
        """获取最大 Bot 数"""
        if not self.license or not self.license.valid:
            return 1  # 社区版单 Bot
        return self.license.max_bots


# 全局实例
_license_manager = None

def get_license_manager() -> LicenseManager:
    """获取许可证管理器实例"""
    global _license_manager
    if _license_manager is None:
        _license_manager = LicenseManager()
    return _license_manager


if __name__ == "__main__":
    import sys

    manager = get_license_manager()

    if len(sys.argv) < 2:
        print("Usage: python3 license_manager.py <command> [args]")
        print("\nCommands:")
        print("  activate <license_key>  - 激活许可证")
        print("  status                  - 查看许可证状态")
        print("  deactivate              - 禁用许可证 (恢复社区版)")
        sys.exit(1)

    command = sys.argv[1]

    if command == "activate":
        if len(sys.argv) < 3:
            print("❌ 请提供许可证密钥")
            print("用法：python3 license_manager.py activate <license_key>")
            sys.exit(1)
        license_key = sys.argv[2]
        success = manager.activate(license_key)
        sys.exit(0 if success else 1)

    elif command == "status":
        manager.status()

    elif command == "deactivate":
        manager.deactivate()

    else:
        print(f"❌ 未知命令：{command}")
        sys.exit(1)
