#!/usr/bin/env python3
"""
I18n - 国际多语言支持

Phoenix Core Phoenix v2.0 扩展模块

支持语言:
- zh_CN: 简体中文
- en_US: English (US)
- ja_JP: 日本語
- ko_KR: 한국어

Usage:
    from i18n import set_language, t

    set_language("en_US")
    print(t("welcome_message"))

    # 带参数
    print(t("bot_created", name="Bot 名称"))
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
I18N_DIR = Path(__file__).parent / "locales"
I18N_DIR.mkdir(parents=True, exist_ok=True)

# 默认语言
DEFAULT_LANGUAGE = "zh_CN"
CURRENT_LANGUAGE = DEFAULT_LANGUAGE

# 语言元数据
LANGUAGES = {
    "zh_CN": {"name": "简体中文", "native_name": "简体中文"},
    "en_US": {"name": "English (US)", "native_name": "English (US)"},
    "ja_JP": {"name": "日本語", "native_name": "日本語"},
    "ko_KR": {"name": "한국어", "native_name": "한국어"}
}

# 翻译内容
TRANSLATIONS = {
    "zh_CN": {
        # 通用
        "welcome_message": "欢迎使用 Phoenix Core Phoenix v2.0",
        "loading": "加载中...",
        "success": "成功",
        "error": "错误",
        "warning": "警告",
        "info": "信息",
        "confirm": "确认",
        "cancel": "取消",
        "yes": "是",
        "no": "否",
        "ok": "确定",

        # Bot 相关
        "bot_created": "Bot '{name}' 已创建",
        "bot_updated": "Bot '{name}' 已更新",
        "bot_deleted": "Bot '{name}' 已删除",
        "bot_not_found": "未找到 Bot '{name}'",
        "bot_list_title": "Phoenix Core Bots (共 {count} 个)",
        "bot_workspace": "工作空间",
        "bot_template": "模板",
        "bot_model": "模型",
        "bot_status": "状态",
        "bot_status_healthy": "健康",
        "bot_status_unhealthy": "异常",
        "bot_status_unknown": "未知",

        # 团队相关
        "team_created": "团队 '{name}' 已创建",
        "team_updated": "团队 '{name}' 已更新",
        "team_deleted": "团队 '{name}' 已删除",
        "team_list_title": "Phoenix Core 团队 (共 {count} 个)",
        "team_lead": "负责 Bot",
        "team_members": "成员",
        "team_skills": "技能",
        "bot_assigned": "Bot '{bot}' 已分配到团队 '{team}'",
        "bot_removed": "Bot '{bot}' 已从团队移除",

        # 技能相关
        "skill_installed": "技能 '{name}' 已安装",
        "skill_uninstalled": "技能 '{name}' 已卸载",
        "skill_not_found": "未找到技能 '{name}'",
        "skill_list_title": "可用技能 (共 {count} 个)",
        "skill_installed_title": "已安装技能 (共 {count} 个)",
        "skill_rating": "评分",
        "skill_downloads": "下载量",
        "skill_version": "版本",

        # 系统相关
        "system_health": "系统健康状态",
        "system_stats": "系统统计",
        "installation_complete": "安装完成",
        "configuration_saved": "配置已保存",
        "api_verified": "API Key 验证通过",
        "api_verification_failed": "API Key 验证失败",

        # CLI 命令
        "cmd_check_updates": "检查更新",
        "cmd_upgrade": "升级系统",
        "cmd_tech_radar": "技术雷达",
        "cmd_evaluate": "模型评估",
        "cmd_rollback": "版本回滚",
        "cmd_health": "健康检查",
        "cmd_skills": "技能管理",
        "cmd_config": "配置向导",
        "cmd_sandbox": "沙盒执行",
        "cmd_release": "版本发布",

        # 错误消息
        "err_permission_denied": "权限被拒绝",
        "err_file_not_found": "文件未找到：{path}",
        "err_invalid_argument": "无效参数：{arg}",
        "err_network_error": "网络错误",
        "err_timeout": "操作超时",
        "err_internal_error": "内部错误",

        # 进度消息
        "progress_initializing": "正在初始化...",
        "progress_loading": "正在加载...",
        "progress_saving": "正在保存...",
        "progress_installing": "正在安装...",
        "progress_uninstalling": "正在卸载...",
        "progress_updating": "正在更新...",
        "progress_downloading": "正在下载...",
        "progress_testing": "正在测试...",

        # 时间格式
        "time_just_now": "刚刚",
        "time_minutes_ago": "{n} 分钟前",
        "time_hours_ago": "{n} 小时前",
        "time_days_ago": "{n} 天前",
        "time_weeks_ago": "{n} 周前",
        "time_months_ago": "{n} 个月前",
    },

    "en_US": {
        # General
        "welcome_message": "Welcome to Phoenix Core Phoenix v2.0",
        "loading": "Loading...",
        "success": "Success",
        "error": "Error",
        "warning": "Warning",
        "info": "Info",
        "confirm": "Confirm",
        "cancel": "Cancel",
        "yes": "Yes",
        "no": "No",
        "ok": "OK",

        # Bot
        "bot_created": "Bot '{name}' created",
        "bot_updated": "Bot '{name}' updated",
        "bot_deleted": "Bot '{name}' deleted",
        "bot_not_found": "Bot '{name}' not found",
        "bot_list_title": "Phoenix Core Bots ({count} total)",
        "bot_workspace": "Workspace",
        "bot_template": "Template",
        "bot_model": "Model",
        "bot_status": "Status",
        "bot_status_healthy": "Healthy",
        "bot_status_unhealthy": "Unhealthy",
        "bot_status_unknown": "Unknown",

        # Team
        "team_created": "Team '{name}' created",
        "team_updated": "Team '{name}' updated",
        "team_deleted": "Team '{name}' deleted",
        "team_list_title": "Phoenix Core Teams ({count} total)",
        "team_lead": "Lead Bot",
        "team_members": "Members",
        "team_skills": "Skills",
        "bot_assigned": "Bot '{bot}' assigned to team '{team}'",
        "bot_removed": "Bot '{bot}' removed from team",

        # Skills
        "skill_installed": "Skill '{name}' installed",
        "skill_uninstalled": "Skill '{name}' uninstalled",
        "skill_not_found": "Skill '{name}' not found",
        "skill_list_title": "Available Skills ({count} total)",
        "skill_installed_title": "Installed Skills ({count} total)",
        "skill_rating": "Rating",
        "skill_downloads": "Downloads",
        "skill_version": "Version",

        # System
        "system_health": "System Health",
        "system_stats": "System Stats",
        "installation_complete": "Installation Complete",
        "configuration_saved": "Configuration Saved",
        "api_verified": "API Key Verified",
        "api_verification_failed": "API Key Verification Failed",

        # CLI Commands
        "cmd_check_updates": "Check Updates",
        "cmd_upgrade": "Upgrade System",
        "cmd_tech_radar": "Tech Radar",
        "cmd_evaluate": "Model Evaluation",
        "cmd_rollback": "Version Rollback",
        "cmd_health": "Health Check",
        "cmd_skills": "Skill Management",
        "cmd_config": "Configuration Wizard",
        "cmd_sandbox": "Sandbox Execution",
        "cmd_release": "Release Management",

        # Error Messages
        "err_permission_denied": "Permission denied",
        "err_file_not_found": "File not found: {path}",
        "err_invalid_argument": "Invalid argument: {arg}",
        "err_network_error": "Network error",
        "err_timeout": "Operation timed out",
        "err_internal_error": "Internal error",

        # Progress Messages
        "progress_initializing": "Initializing...",
        "progress_loading": "Loading...",
        "progress_saving": "Saving...",
        "progress_installing": "Installing...",
        "progress_uninstalling": "Uninstalling...",
        "progress_updating": "Updating...",
        "progress_downloading": "Downloading...",
        "progress_testing": "Testing...",

        # Time Format
        "time_just_now": "Just now",
        "time_minutes_ago": "{n} minutes ago",
        "time_hours_ago": "{n} hours ago",
        "time_days_ago": "{n} days ago",
        "time_weeks_ago": "{n} weeks ago",
        "time_months_ago": "{n} months ago",
    },

    "ja_JP": {
        # 一般
        "welcome_message": "Phoenix Core Phoenix v2.0 へようこそ",
        "loading": "読み込み中...",
        "success": "成功",
        "error": "エラー",
        "warning": "警告",
        "info": "情報",
        "confirm": "確認",
        "cancel": "キャンセル",
        "yes": "はい",
        "no": "いいえ",
        "ok": "OK",

        # Bot
        "bot_created": "Bot '{name}' を作成しました",
        "bot_updated": "Bot '{name}' を更新しました",
        "bot_deleted": "Bot '{name}' を削除しました",
        "bot_not_found": "Bot '{name}' が見つかりません",
        "bot_list_title": "Phoenix Core Bots (合計 {count} 個)",
        "bot_workspace": "ワークスペース",
        "bot_template": "テンプレート",
        "bot_model": "モデル",
        "bot_status": "ステータス",
        "bot_status_healthy": "正常",
        "bot_status_unhealthy": "異常",
        "bot_status_unknown": "不明",

        # Team
        "team_created": "チーム '{name}' を作成しました",
        "team_updated": "チーム '{name}' を更新しました",
        "team_deleted": "チーム '{name}' を削除しました",
        "team_list_title": "Phoenix Core チーム (合計 {count} 個)",
        "team_lead": "リーダー Bot",
        "team_members": "メンバー",
        "team_skills": "スキル",
        "bot_assigned": "Bot '{bot}' をチーム '{team}' に割り当てました",
        "bot_removed": "Bot '{bot}' をチームから削除しました",

        # Skills
        "skill_installed": "スキル '{name}' をインストールしました",
        "skill_uninstalled": "スキル '{name}' をアンインストールしました",
        "skill_not_found": "スキル '{name}' が見つかりません",
        "skill_list_title": "利用可能なスキル (合計 {count} 個)",
        "skill_installed_title": "インストール済みスキル (合計 {count} 個)",
        "skill_rating": "評価",
        "skill_downloads": "ダウンロード数",
        "skill_version": "バージョン",

        # System
        "system_health": "システムヘルス",
        "system_stats": "システム統計",
        "installation_complete": "インストール完了",
        "configuration_saved": "設定を保存しました",
        "api_verified": "API キーを検証しました",
        "api_verification_failed": "API キーの検証に失敗しました",

        # CLI Commands
        "cmd_check_updates": "更新を確認",
        "cmd_upgrade": "システムをアップグレード",
        "cmd_tech_radar": "技術レーダー",
        "cmd_evaluate": "モデル評価",
        "cmd_rollback": "バージョンロールバック",
        "cmd_health": "ヘルスチェック",
        "cmd_skills": "スキル管理",
        "cmd_config": "設定ウィザード",
        "cmd_sandbox": "サンドボックス実行",
        "cmd_release": "リリース管理",

        # Error Messages
        "err_permission_denied": "権限がありません",
        "err_file_not_found": "ファイルが見つかりません：{path}",
        "err_invalid_argument": "無効な引数：{arg}",
        "err_network_error": "ネットワークエラー",
        "err_timeout": "操作がタイムアウトしました",
        "err_internal_error": "内部エラー",

        # Progress Messages
        "progress_initializing": "初期化中...",
        "progress_loading": "読み込み中...",
        "progress_saving": "保存中...",
        "progress_installing": "インストール中...",
        "progress_uninstalling": "アンインストール中...",
        "progress_updating": "更新中...",
        "progress_downloading": "ダウンロード中...",
        "progress_testing": "テスト中...",

        # Time Format
        "time_just_now": "たった今",
        "time_minutes_ago": "{n} 分前",
        "time_hours_ago": "{n} 時間前",
        "time_days_ago": "{n} 日前",
        "time_weeks_ago": "{n} 週間前",
        "time_months_ago": "{n} ヶ月前",
    },

    "ko_KR": {
        # 일반
        "welcome_message": "Phoenix Core Phoenix v2.0 에 오신 것을 환영합니다",
        "loading": "로딩 중...",
        "success": "성공",
        "error": "오류",
        "warning": "경고",
        "info": "정보",
        "confirm": "확인",
        "cancel": "취소",
        "yes": "예",
        "no": "아니오",
        "ok": "확인",

        # Bot
        "bot_created": "Bot '{name}' 이 (가) 생성되었습니다",
        "bot_updated": "Bot '{name}' 이 (가) 업데이트되었습니다",
        "bot_deleted": "Bot '{name}' 이 (가) 삭제되었습니다",
        "bot_not_found": "Bot '{name}' 을 (를) 찾을 수 없습니다",
        "bot_list_title": "Phoenix Core Bots (총 {count} 개)",
        "bot_workspace": "워크스페이스",
        "bot_template": "템플릿",
        "bot_model": "모델",
        "bot_status": "상태",
        "bot_status_healthy": "정상",
        "bot_status_unhealthy": "비정상",
        "bot_status_unknown": "알 수 없음",

        # Team
        "team_created": "팀 '{name}' 이 (가) 생성되었습니다",
        "team_updated": "팀 '{name}' 이 (가) 업데이트되었습니다",
        "team_deleted": "팀 '{name}' 이 (가) 삭제되었습니다",
        "team_list_title": "Phoenix Core 팀 (총 {count} 개)",
        "team_lead": "리더 Bot",
        "team_members": "멤버",
        "team_skills": "스킬",
        "bot_assigned": "Bot '{bot}' 이 (가) 팀 '{team}' 에 할당되었습니다",
        "bot_removed": "Bot '{bot}' 이 (가) 팀에서 제거되었습니다",

        # Skills
        "skill_installed": "스킬 '{name}' 이 (가) 설치되었습니다",
        "skill_uninstalled": "스킬 '{name}' 이 (가) 제거되었습니다",
        "skill_not_found": "스킬 '{name}' 을 (를) 찾을 수 없습니다",
        "skill_list_title": "사용 가능한 스킬 (총 {count} 개)",
        "skill_installed_title": "설치된 스킬 (총 {count} 개)",
        "skill_rating": "평가",
        "skill_downloads": "다운로드",
        "skill_version": "버전",

        # System
        "system_health": "시스템 상태",
        "system_stats": "시스템 통계",
        "installation_complete": "설치 완료",
        "configuration_saved": "구성이 저장되었습니다",
        "api_verified": "API 키가 확인되었습니다",
        "api_verification_failed": "API 키 확인에 실패했습니다",

        # CLI Commands
        "cmd_check_updates": "업데이트 확인",
        "cmd_upgrade": "시스템 업그레이드",
        "cmd_tech_radar": "기술 레이더",
        "cmd_evaluate": "모델 평가",
        "cmd_rollback": "버전 롤백",
        "cmd_health": "상태 확인",
        "cmd_skills": "스킬 관리",
        "cmd_config": "구성 마법사",
        "cmd_sandbox": "샌드박스 실행",
        "cmd_release": "릴리스 관리",

        # Error Messages
        "err_permission_denied": "권한이 거부되었습니다",
        "err_file_not_found": "파일을 찾을 수 없습니다: {path}",
        "err_invalid_argument": "잘못된 인수: {arg}",
        "err_network_error": "네트워크 오류",
        "err_timeout": "작업 시간이 초과되었습니다",
        "err_internal_error": "내부 오류",

        # Progress Messages
        "progress_initializing": "초기화 중...",
        "progress_loading": "로딩 중...",
        "progress_saving": "저장 중...",
        "progress_installing": "설치 중...",
        "progress_uninstalling": "제거 중...",
        "progress_updating": "업데이트 중...",
        "progress_downloading": "다운로드 중...",
        "progress_testing": "테스트 중...",

        # Time Format
        "time_just_now": "방금",
        "time_minutes_ago": "{n} 분 전",
        "time_hours_ago": "{n} 시간 전",
        "time_days_ago": "{n} 일 전",
        "time_weeks_ago": "{n} 주 전",
        "time_months_ago": "{n} 개월 전",
    }
}


def set_language(lang: str) -> bool:
    """设置当前语言"""
    global CURRENT_LANGUAGE

    if lang in LANGUAGES:
        CURRENT_LANGUAGE = lang
        logger.info(f"Language set to {lang}")
        return True

    logger.warning(f"Unsupported language: {lang}, using {DEFAULT_LANGUAGE}")
    CURRENT_LANGUAGE = DEFAULT_LANGUAGE
    return False


def get_current_language() -> str:
    """获取当前语言"""
    return CURRENT_LANGUAGE


def get_available_languages() -> Dict:
    """获取可用语言列表"""
    return LANGUAGES


def t(key: str, **kwargs) -> str:
    """
    翻译函数

    Args:
        key: 翻译键
        **kwargs: 参数替换

    Returns:
        翻译后的字符串
    """
    lang_translations = TRANSLATIONS.get(CURRENT_LANGUAGE, TRANSLATIONS[DEFAULT_LANGUAGE])
    text = lang_translations.get(key, key)

    # 参数替换
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass

    return text


def t_with_fallback(key: str, fallback: str = "", **kwargs) -> str:
    """翻译函数（带后备文本）"""
    result = t(key, **kwargs)
    return result if result != key else fallback


def format_time_ago(timestamp: datetime) -> str:
    """格式化相对时间"""
    now = datetime.now()
    delta = now - timestamp

    if delta.total_seconds() < 60:
        return t("time_just_now")
    elif delta.total_seconds() < 3600:
        minutes = int(delta.total_seconds() / 60)
        return t("time_minutes_ago", n=minutes)
    elif delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() / 3600)
        return t("time_hours_ago", n=hours)
    elif delta.total_seconds() < 604800:
        days = int(delta.total_seconds() / 86400)
        return t("time_days_ago", n=days)
    elif delta.total_seconds() < 2592000:
        weeks = int(delta.total_seconds() / 604800)
        return t("time_weeks_ago", n=weeks)
    else:
        months = int(delta.total_seconds() / 2592000)
        return t("time_months_ago", n=months)


def export_translations():
    """导出翻译到 JSON 文件"""
    for lang, translations in TRANSLATIONS.items():
        output_file = I18N_DIR / f"{lang}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "language": lang,
                "language_info": LANGUAGES.get(lang, {}),
                "translations": translations
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"Exported translations to {output_file}")


def import_translations(lang: str, file_path: str) -> bool:
    """导入翻译文件"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "translations" in data:
            TRANSLATIONS[lang] = data["translations"]
            logger.info(f"Imported translations for {lang}")
            return True
    except Exception as e:
        logger.error(f"Failed to import translations: {e}")

    return False


# 便捷函数
def _t(key: str, **kwargs) -> str:
    """t 的别名"""
    return t(key, **kwargs)


def set_lang(lang: str) -> bool:
    """set_language 的别名"""
    return set_language(lang)


if __name__ == "__main__":
    import sys

    print("Phoenix Core I18n - 多语言支持\n")

    # 显示可用语言
    print("可用语言 / Available Languages:")
    for code, info in LANGUAGES.items():
        print(f"  {code}: {info['native_name']} ({info['name']})")

    # 测试翻译
    print("\n--- 翻译测试 / Translation Test ---\n")

    for lang in LANGUAGES.keys():
        set_language(lang)
        print(f"[{lang}]")
        print(f"  welcome: {t('welcome_message')}")
        print(f"  loading: {t('loading')}")
        print(f"  success: {t('success')}")
        print(f"  bot_created: {t('bot_created', name='测试 Bot')}")
        print()

    # CLI 命令
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "set":
            if len(sys.argv) > 2:
                lang = sys.argv[2]
                if set_language(lang):
                    print(f"Language set to {lang}")
                else:
                    print(f"Unsupported language: {lang}")
            else:
                print("Usage: i18n.py set <language>")

        elif command == "export":
            export_translations()
            print("Translations exported to locales/ directory")

        elif command == "list":
            print("\n可用语言:")
            for code, info in LANGUAGES.items():
                print(f"  {code}: {info['native_name']}")

        else:
            print(f"Unknown command: {command}")
