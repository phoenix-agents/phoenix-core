#!/usr/bin/env python3
"""
Phoenix Core Context Manager - 上下文管理模块

功能:
1. 对话历史存储
2. 实体提取 (支持 LLM 增强)
3. 隐式引用解析
4. 上下文持久化
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# 可选的 LLM 调用 (用于增强实体提取)
try:
    from phoenix_core.intent_recognition import call_llm
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    logger.warning("LLM 模块不可用，将使用正则实体提取")


@dataclass
class Message:
    """对话消息"""
    role: str           # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict = field(default_factory=dict)


@dataclass
class TaskContext:
    """单个任务的上下文"""
    user_id: str
    request_id: str
    initial_query: str
    history: List[Message] = field(default_factory=list)
    entities: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_access: datetime = field(default_factory=datetime.now)
    task_id: Optional[str] = None  # 关联的任务 ID
    status: str = "active"  # active, completed, cancelled

    def add_message(self, role: str, content: str, metadata: Dict = None):
        """添加消息到历史"""
        self.history.append(Message(role=role, content=content, metadata=metadata or {}))
        self.last_access = datetime.now()

        # 自动提取实体
        self._extract_entities(content)

    def _extract_entities(self, text: str):
        """从文本中提取实体 (正则版本)"""
        # 订单号：4-10 位数字或字母数字组合
        patterns = {
            "order_id": r"订单 [号 #]?\s*([A-Z0-9]{4,10})",
            "amount": r"(\d+(?:\.\d{1,2})?)\s*元",
            "date": r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
            "phone": r"(1[3-9]\d{9})",
            "email": r"([\w.-]+@[\w.-]+\.\w+)",
        }

        for entity_type, pattern in patterns.items():
            match = re.search(pattern, text, re.I)
            if match and entity_type not in self.entities:
                self.entities[entity_type] = match.group(1)
                logger.debug(f"提取实体：{entity_type}={match.group(1)}")

    def extract_entities_with_llm(self):
        """使用 LLM 提取实体 (更准确)"""
        if not LLM_AVAILABLE:
            return

        # 拼接最近 5 轮对话
        recent_history = "\n".join(
            f"{m.role}: {m.content}" for m in self.history[-5:]
        )

        prompt = f"""
从以下对话中提取实体，返回 JSON 格式：

{recent_history}

需要提取的实体类型:
- order_id: 订单号
- amount: 金额
- product: 商品名称
- date: 日期/时间
- user_id: 用户 ID
- address: 地址
- phone: 手机号
- email: 邮箱

只返回 JSON，不要其他内容。
"""
        try:
            result = call_llm(prompt)
            entities = json.loads(result)
            for k, v in entities.items():
                if v and k not in self.entities:
                    self.entities[k] = v
        except Exception as e:
            logger.warning(f"LLM 实体提取失败：{e}")

    def resolve_reference(self, query: str) -> str:
        """
        解析隐式引用

        示例:
        - "帮我退了吧" + 上下文有 order_id → "退订单 {order_id}"
        - "它多少钱" + 上下文有 product → "{product} 多少钱"
        """
        resolved = query

        # 常见代词映射
        pronouns = {
            "这个": "当前",
            "这个": "当前",
            "它": "该",
            "那个": "上述",
        }

        # 检查是否有隐式引用
        has_pronoun = any(p in query for p in pronouns.keys())
        has_action = any(a in query for a in ["退", "查", "看", "改", "删", "创建", "下单"])

        if has_pronoun and has_action:
            # 尝试用上下文中最近的实体填充
            if "order_id" in self.entities:
                for pronoun in pronouns.keys():
                    resolved = resolved.replace(pronoun, f"订单 {self.entities['order_id']}")
            elif "product" in self.entities:
                for pronoun in pronouns.keys():
                    resolved = resolved.replace(pronoun, self.entities["product"])

        return resolved

    def resolve_reference_with_llm(self, query: str) -> str:
        """使用 LLM 解析隐式引用 (更准确)"""
        if not LLM_AVAILABLE:
            return self.resolve_reference(query)

        prompt = f"""
用户说："{query}"

当前上下文中的实体:
{json.dumps(self.entities, ensure_ascii=False)}

最近对话历史:
{chr(10).join(f"- {m.role}: {m.content}" for m in self.history[-3:])}

请判断用户指的是哪个实体，并返回完整的查询。
如果用户说的是"退了吧"、"查一下"等省略句，请补充完整。
只返回补充后的完整查询，不要其他内容。
"""
        try:
            result = call_llm(prompt)
            return result.strip()
        except Exception as e:
            logger.warning(f"LLM 引用解析失败：{e}")
            return self.resolve_reference(query)

    def is_expired(self, ttl_minutes: int = 30) -> bool:
        """检查是否过期"""
        return datetime.now() - self.last_access > timedelta(minutes=ttl_minutes)

    def to_dict(self) -> Dict:
        """转为字典 (用于序列化)"""
        return {
            "user_id": self.user_id,
            "request_id": self.request_id,
            "initial_query": self.initial_query,
            "history": [(m.role, m.content) for m in self.history],
            "entities": self.entities,
            "created_at": self.created_at.isoformat(),
            "last_access": self.last_access.isoformat(),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TaskContext":
        """从字典加载"""
        ctx = cls(
            user_id=data["user_id"],
            request_id=data["request_id"],
            initial_query=data["initial_query"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_access=datetime.fromisoformat(data["last_access"]),
            status=data.get("status", "active"),
        )
        ctx.history = [Message(role=r, content=c) for r, c in data.get("history", [])]
        ctx.entities = data.get("entities", {})
        return ctx


@dataclass
class ConversationSummary:
    """对话摘要 (用于长对话压缩)"""
    summary: str
    key_points: List[str]
    entities: Dict[str, str]
    created_at: datetime = field(default_factory=datetime.now)


class ContextManager:
    """
    全局上下文管理器

    数据结构:
    self.contexts: user_id -> request_id -> TaskContext
    """

    def __init__(self, db_path: Optional[str] = None, ttl_minutes: int = 30):
        self.contexts: Dict[str, Dict[str, TaskContext]] = defaultdict(dict)
        self.ttl_minutes = ttl_minutes
        self.db_path = Path(db_path) if db_path else None

        # 可选：持久化到 SQLite
        if self.db_path:
            self._init_db()

    def _init_db(self):
        """初始化数据库"""
        import sqlite3
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS context (
                user_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (user_id, request_id)
            )
        """)
        conn.commit()
        conn.close()
        logger.info(f"上下文数据库初始化：{self.db_path}")

    def create_context(self, user_id: str, request_id: str, initial_query: str) -> TaskContext:
        """创建新上下文"""
        ctx = TaskContext(
            user_id=user_id,
            request_id=request_id,
            initial_query=initial_query
        )
        self.contexts[user_id][request_id] = ctx
        logger.info(f"创建上下文：user={user_id}, request={request_id}")
        return ctx

    def get_context(self, user_id: str, request_id: str) -> Optional[TaskContext]:
        """获取上下文"""
        return self.contexts.get(user_id, {}).get(request_id)

    def get_or_create_context(self, user_id: str, request_id: str,
                              initial_query: str = "") -> TaskContext:
        """获取或创建上下文"""
        existing = self.get_context(user_id, request_id)
        if existing:
            return existing
        return self.create_context(user_id, request_id, initial_query)

    def add_to_history(self, user_id: str, request_id: str,
                       role: str, content: str, metadata: Dict = None):
        """添加消息到历史"""
        ctx = self.get_context(user_id, request_id)
        if ctx:
            ctx.add_message(role, content, metadata)

    def resolve_implicit_reference(self, user_id: str, request_id: str,
                                   query: str, use_llm: bool = True) -> str:
        """解析隐式引用"""
        ctx = self.get_context(user_id, request_id)
        if not ctx:
            return query

        if use_llm and LLM_AVAILABLE:
            return ctx.resolve_reference_with_llm(query)
        return ctx.resolve_reference(query)

    def get_conversation_history(self, user_id: str, request_id: str,
                                 max_turns: int = 10) -> List[Tuple[str, str]]:
        """获取对话历史"""
        ctx = self.get_context(user_id, request_id)
        if not ctx:
            return []
        return [(m.role, m.content) for m in ctx.history[-max_turns:]]

    def get_entities(self, user_id: str, request_id: str) -> Dict[str, str]:
        """获取实体"""
        ctx = self.get_context(user_id, request_id)
        return ctx.entities if ctx else {}

    def update_context_status(self, user_id: str, request_id: str, status: str):
        """更新上下文状态"""
        ctx = self.get_context(user_id, request_id)
        if ctx:
            ctx.status = status

    def save_context(self, user_id: str, request_id: str):
        """保存上下文到数据库"""
        if not self.db_path:
            return

        ctx = self.get_context(user_id, request_id)
        if not ctx:
            return

        import sqlite3
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """INSERT OR REPLACE INTO context (user_id, request_id, data, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, request_id, json.dumps(ctx.to_dict()),
             ctx.created_at.timestamp(), datetime.now().timestamp())
        )
        conn.commit()
        conn.close()

    def load_context(self, user_id: str, request_id: str) -> Optional[TaskContext]:
        """从数据库加载上下文"""
        if not self.db_path:
            return None

        import sqlite3
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute(
            "SELECT data FROM context WHERE user_id = ? AND request_id = ?",
            (user_id, request_id)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            data = json.loads(row[0])
            return TaskContext.from_dict(data)
        return None

    def cleanup_expired(self) -> int:
        """清理过期上下文"""
        now = datetime.now()
        count = 0

        for user_id in list(self.contexts.keys()):
            for request_id in list(self.contexts[user_id].keys()):
                ctx = self.contexts[user_id][request_id]
                if now - ctx.last_access > timedelta(minutes=self.ttl_minutes):
                    del self.contexts[user_id][request_id]
                    count += 1

            if not self.contexts[user_id]:
                del self.contexts[user_id]

        if count > 0:
            logger.info(f"清理 {count} 个过期上下文")

        return count

    def get_active_requests(self, user_id: str) -> List[str]:
        """获取用户活跃请求"""
        result = []
        for request_id, ctx in self.contexts.get(user_id, {}).items():
            if ctx.status == "active":
                result.append(request_id)
        return result


# ============ 使用示例 ============

if __name__ == "__main__":
    # 测试上下文管理
    mgr = ContextManager()

    # 创建上下文
    ctx = mgr.create_context(
        user_id="user123",
        request_id="1234-20260417-001",
        initial_query="帮我查订单 #12345"
    )

    # 添加对话历史
    mgr.add_to_history("user123", "1234-20260417-001", "user", "帮我查订单 #12345")
    mgr.add_to_history("user123", "1234-20260417-001", "assistant", "订单 #12345 已签收")

    # 解析隐式引用
    query = "帮我退了吧"
    resolved = mgr.resolve_implicit_reference("user123", "1234-20260417-001", query)
    print(f"原始：{query}")
    print(f"解析后：{resolved}")

    # 获取实体
    entities = mgr.get_entities("user123", "1234-20260417-001")
    print(f"实体：{entities}")
