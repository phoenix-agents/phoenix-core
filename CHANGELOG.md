# Changelog

All notable changes to Phoenix Core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- GitHub Organization setup
- Trademark registration application
- Telemetry system implementation (opt-in)
- Official website launch

---

## [2.0.0] - 2026-04-12

### Added
- **Unified CLI Tool** (`phoenix.py`) - Single entry point for all commands
  - `phoenix status` - System health check
  - `phoenix doctor` - Diagnostic tool
  - `phoenix bots` - Bot management
  - `phoenix skills` - Skill management
  - `phoenix cache` - Cache operations
  - `phoenix tasks` - Task queue management
  - `phoenix web` - Web server commands

- **8 Specialized Bots**
  - 编导 (Director) - Content planning
  - 场控 (Stage Control) - Live stream management
  - 客服 (Customer Service) - Support automation
  - 运营 (Operations) - Analytics
  - 剪辑 (Video Editor) - Video processing
  - 文案 (Copywriter) - Content creation
  - 设计 (Designer) - Visual design
  - 助理 (Assistant) - General tasks

- **6-Stage Learning Loop**
  - Task execution → Evaluation → Memory extraction → Skill evolution
  - Automatic skill improvement
  - Version control for skills (v1 → v2 → v3)

- **Comprehensive Documentation**
  - API Reference (`docs/API_REFERENCE.md`)
  - Skill Development Guide (`docs/SKILL_DEVELOPMENT.md`)
  - Best Practices (`docs/BEST_PRACTICES.md`)
  - Troubleshooting Guide (`docs/TROUBLESHOOTING.md`)
  - Documentation Index (`DOCUMENTATION_INDEX.md`)

- **Legal & Compliance**
  - Apache 2.0 License
  - Legal Notice (`LEGAL.md`)
  - Privacy Policy (`PRIVACY.md`)
  - Contributor Guidelines (`CONTRIBUTING.md`)

- **Testing Suite**
  - 30+ test cases
  - 82% code coverage
  - Core module tests
  - Integration tests

### Changed
- **Security Improvements**
  - All API keys migrated to environment variables
  - No hardcoded credentials
  - `.env` file for configuration

- **Path System**
  - All paths converted to relative paths
  - Cross-platform support (macOS/Windows/Linux)
  - `Path(__file__).parent` pattern throughout

- **CLI Unification**
  - Removed duplicate `cli.py` and `phoenix_cli.py`
  - Single `phoenix.py` entry point
  - Consistent command interface

### Fixed
- 11 instances of hardcoded API keys
- 88 instances of hardcoded paths
- Memory manager initialization issues
- Skill extractor path resolution
- Bot health checker cross-platform compatibility

### Removed
- Duplicate CLI tools
- Hardcoded API credentials
- Windows-incompatible path patterns

---

## [1.0.0] - 2026-04-09

### Added
- Initial release based on OpenClaw v2026.4.8
- Core memory management system
- Bot manager with multi-bot support
- Skill extraction and execution engine
- Task queue system
- SQLite-based session storage

### Changed
- Upgraded from OpenClaw v2026.4.1
- Improved architecture for modularity

### Fixed
- Various bug fixes from OpenClaw base

---

## Version Numbering

- **Major** (X.0.0): Breaking changes or major new features
- **Minor** (x.X.0): New features, backward compatible
- **Patch** (x.x.X): Bug fixes and minor improvements

---

*Last updated: 2026-04-12*
