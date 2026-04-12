# Phoenix Bot 能力快速参考

**更新时间**: 2026-04-11

---

## 📊 一页纸速查

| Bot | 核心能力 | 专属工具 | 产出物 |
|-----|---------|---------|--------|
| **场控** 🎮 | 数据监控、气氛调节 | 直播仪表盘、记忆写入 | 数据报告、流量密码 |
| **运营** 📊 | 数据分析、流量诊断 | 趋势图、竞品对比 | 日报、优化建议 |
| **编导** 📝 | 内容策划、脚本创作 | 热点 API、脚本模板 | 直播脚本、选题列表 |
| **剪辑** 🎬 | 视频切片、格式转换 | FFmpeg、视频处理 API | 切片视频、完整版回放 |
| **客服** 💬 | 粉丝运营、问题解决 | 粉丝列表、社群数据 | 问题汇总、社群 SOP |
| **渠道** 🌐 | 多平台分发、引流 | 渠道矩阵、分发 API | 全网发布、引流数据 |
| **美工** 🎨 | 视觉设计、品牌打造 | 设计模板、品牌资产 | 封面、海报、VI 规范 |
| **小小谦** 🤖 | 任务调度、跨 bot 协调 | 总控所有 bot | 任务分配、进度追踪 |

---

## 🔌 专属 API 速查

### 场控
```
GET  /api/agent/dashboard       # 实时直播数据
GET  /api/agent/learning-data   # 历史流量模式
POST /api/agent/analysis        # 提交分析结果
POST /api/agent/memory          # 写入记忆
```

### 运营
```
GET  /api/agent/dashboard       # 完整直播数据
GET  /api/agent/trends          # 流量趋势图
GET  /api/agent/comparison      # 竞品对比
POST /api/agent/report          # 提交数据报告
```

### 编导
```
GET  /api/agent/trending        # 热点话题
GET  /api/agent/script-templates # 脚本模板
POST /api/agent/content-plan    # 提交内容方案
POST /api/agent/script          # 提交直播脚本
```

### 剪辑
```
POST /api/agent/video/cut       # 直播切片
POST /api/agent/video/convert   # 格式转换
POST /api/agent/video/compress  # 视频压缩
GET  /api/agent/video/highlights # 获取高光时刻
```

### 客服
```
GET  /api/agent/fan-list        # 粉丝列表
GET  /api/agent/fan-profile     # 粉丝画像
POST /api/agent/fan-tag         # 打标签分类
GET  /api/agent/community-data  # 社群数据
```

### 渠道
```
GET  /api/agent/channel-list    # 渠道列表
GET  /api/agent/channel-data    # 渠道数据
POST /api/agent/distribute      # 内容分发
GET  /api/agent/partner-list    # 合作伙伴
```

### 美工
```
GET  /api/agent/templates       # 设计模板
GET  /api/agent/brand-assets    # 品牌资产
POST /api/agent/design-task     # 提交设计任务
GET  /api/agent/inspiration     # 设计灵感
```

### 小小谦
```
总控所有 Bot，无专属 API，负责调度协调
```

---

## 📋 回复格式模板

### 通用格式
```
@小小谦 [指令类型 | 请求 ID|Bot 名] 内容
```

### 指令类型

| 类型 | 含义 | 示例 |
|------|------|------|
| `CONFIRM` | 确认收到 | `@小小谦 [CONFIRM|R001| 场控] 已收到` |
| `REPORT` | 进展汇报 | `@小小谦 [REPORT|R001| 场控] 当前直播间 500 人` |
| `DONE` | 任务完成 | `@小小谦 [DONE|R001| 剪辑] 已生成 3 个切片` |
| `FAIL` | 任务失败 | `@小小谦 [FAIL|R001| 运营] 无法完成，数据缺失` |
| `ASK` | 请求协助 | `@小小谦 [ASK|R001| 编导] 需要@场控 提供互动话题` |

---

## 🎯 各 Bot 核心场景

### 场控 🎮
- ✅ 直播中实时监控数据
- ✅ 发现异常立即预警
- ✅ 写入关键节点到 memory/
- ✅ 提炼流量密码到 MEMORY.md
- ❌ 不能直接命令其他 bot

### 运营 📊
- ✅ 读取直播仪表盘
- ✅ 分析流量模式
- ✅ 生成日报/周报
- ✅ 用户画像分析
- ❌ 不能直接命令其他 bot

### 编导 📝
- ✅ 获取热点趋势
- ✅ 创作直播脚本
- ✅ 设计互动环节
- ✅ IP 人设策划
- ❌ 不能直接命令其他 bot

### 剪辑 🎬
- ✅ FFmpeg 视频处理
- ✅ 制作 30-60 秒切片
- ✅ 格式转换/压缩
- ✅ 提取音频
- ❌ 不能直接命令其他 bot

### 客服 💬
- ✅ 粉丝问题解答
- ✅ 私域社群运营
- ✅ 问题收集反馈
- ✅ 新粉入群 SOP
- ❌ 不能直接命令其他 bot

### 渠道 🌐
- ✅ 多平台内容分发
- ✅ 渠道效果分析
- ✅ 最佳时间发布
- ✅ BD 合作对接
- ❌ 不能直接命令其他 bot

### 美工 🎨
- ✅ 直播封面设计
- ✅ 品牌 VI 设计
- ✅ OBS 直播间包装
- ✅ 设计规范制定
- ❌ 不能直接命令其他 bot

### 小小谦 🤖
- ✅ 接收所有 bot 汇报
- ✅ 分配任务给对应 bot
- ✅ 跨 bot 协调
- ✅ 任务优先级管理
- ✅ Discord 调度

---

## 🔗 典型协作链路

### 直播前
```
小小谦 → 编导 (策划) → 美工 (设计) → 渠道 (预热) → 场控 (准备)
```

### 直播中
```
场控 (监控) → 小小谦 → 编导 (调整脚本) → 剪辑 (实时切片) → 渠道 (发布)
```

### 直播后
```
场控 (总结) → 运营 (分析) → 剪辑 (切片) → 渠道 (分发) → 客服 (反馈)
```

---

## 📁 文件位置

```
workspaces/
├── 场控/
│   ├── IDENTITY.md      # 职责、工具、协作规则
│   ├── SOUL.md          # 核心配置
│   ├── AGENTS.md        # Agent 配置
│   ├── MEMORY.md        # 流量密码沉淀
│   └── memory/          # 每场直播记录
├── 运营/
├── 编导/
├── 剪辑/
├── 客服/
├── 渠道/
├── 美工/
└── 小小谦/
```

---

## 🚨 总控模式红线

### 必须遵守
- ✅ 所有正式任务必须来自 @小小谦
- ✅ 任务格式：`@Bot [ASK|DO|请求 ID| 小小谦] 内容`
- ✅ 回复必须带上请求 ID 和 bot 名
- ✅ 跨 bot 需求通过小小谦协调

### 严格禁止
- ❌ 跨 bot 派单（如 [运营] @剪辑 做视频）
- ❌ 没有请求 ID 的任务
- ❌ 非小小谦发起的正式任务
- ❌ 不确认接收者的广播消息

---

## 💡 提示

1. **bot 差异化**：每个 bot 有专属 API 和工具，不能越权
2. **记忆沉淀**：场控负责写入 memory/，提炼流量密码
3. **数据驱动**：场控/运营用数据说话，不凭感觉
4. **快速响应**：直播中秒级响应，不等待
5. **总控协调**：小小谦是唯一调度者

---

_Phoenix Core Bot 团队 - 专业分工，高效协作_
