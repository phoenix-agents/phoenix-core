#!/usr/bin/env python3
"""
Knowledge Graph - Cross-Bot Knowledge Sharing and Association

Features:
1. Extract universal patterns from bot-specific knowledge
2. Map knowledge to target bot context
3. Establish knowledge associations
4. Track knowledge propagation paths

Usage:
    graph = KnowledgeGraph()
    graph.share_learning(from_bot="编导", to_bots=["场控", "运营"], knowledge_id="xyz")
"""

import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

# AI config for knowledge mapping
KNOWLEDGE_GRAPH_CONFIG = {
    "base_url": "https://coding.dashscope.aliyuncs.com/v1",
    "api_key": os.environ.get("DASHSCOPE_API_KEY"),
    "model": "qwen3-coder-next",
    "max_tokens": 2500,
    "temperature": 0.2
}


class KnowledgeNode:
    """Represents a node in the knowledge graph."""

    def __init__(self, node_data: Dict[str, Any]):
        self.id = node_data.get('id', '')
        self.type = node_data.get('type', 'knowledge')  # knowledge, pattern, skill
        self.content = node_data.get('content', '')
        self.source_bot = node_data.get('source_bot', '')
        self.created_at = node_data.get('created_at', '')
        self.tags = node_data.get('tags', [])
        self.metadata = node_data.get('metadata', {})

        # Connections
        self.connected_to: Set[str] = set(node_data.get('connected_to', []))
        self.propagated_to: List[str] = node_data.get('propagated_to', [])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'type': self.type,
            'content': self.content,
            'source_bot': self.source_bot,
            'created_at': self.created_at,
            'tags': self.tags,
            'connected_to': list(self.connected_to),
            'propagated_to': self.propagated_to,
            'metadata': self.metadata
        }


class KnowledgeGraph:
    """
    Cross-bot knowledge graph for knowledge sharing and association.

    Capabilities:
    1. Extract universal patterns from bot-specific knowledge
    2. Map knowledge to target bot context
    3. Establish knowledge associations
    4. Track knowledge propagation
    """

    def __init__(self):
        self._graph_dir = Path(__file__).parent / "knowledge_graph"
        self._graph_dir.mkdir(parents=True, exist_ok=True)

        self._graph_file = self._graph_dir / 'graph.json'
        self._nodes: Dict[str, KnowledgeNode] = {}
        self._edges: List[Dict[str, Any]] = []

        # Bot relationships
        self._bot_relationships = {
            '编导': ['场控', '运营'],  # 编导的知识适合分享给场控和运营
            '场控': ['编导', '运营'],
            '剪辑': ['美工', '编导'],
            '美工': ['剪辑', '编导'],
            '客服': ['运营', '渠道'],
            '运营': ['客服', '渠道', '编导'],
            '渠道': ['运营', '客服']
        }

        # Load existing graph
        self._load_graph()

    def _load_graph(self):
        """Load graph from disk."""
        if not self._graph_file.exists():
            return

        try:
            with open(self._graph_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for node_data in data.get('nodes', []):
                self._nodes[node_data['id']] = KnowledgeNode(node_data)

            self._edges = data.get('edges', [])

            logger.info(f"Loaded knowledge graph: {len(self._nodes)} nodes, {len(self._edges)} edges")
        except Exception as e:
            logger.error(f"Failed to load graph: {e}")

    def _save_graph(self):
        """Save graph to disk."""
        data = {
            'nodes': [node.to_dict() for node in self._nodes.values()],
            'edges': self._edges,
            'last_updated': datetime.now().isoformat()
        }

        with open(self._graph_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_node(self, node: KnowledgeNode) -> str:
        """Add a node to the graph."""
        self._nodes[node.id] = node
        self._save_graph()
        return node.id

    def add_edge(self, from_id: str, to_id: str, edge_type: str = 'related'):
        """Add an edge between two nodes."""
        if from_id not in self._nodes or to_id not in self._nodes:
            return

        self._nodes[from_id].connected_to.add(to_id)
        self._nodes[to_id].connected_to.add(from_id)

        self._edges.append({
            'from': from_id,
            'to': to_id,
            'type': edge_type,
            'created_at': datetime.now().isoformat()
        })

        self._save_graph()

    def share_learning(
        self,
        from_bot: str,
        to_bots: List[str],
        knowledge: str,
        knowledge_type: str = 'pattern'
    ) -> Dict[str, Any]:
        """
        Share knowledge from one bot to others.

        Args:
            from_bot: Source bot name
            to_bots: Target bot names
            knowledge: Knowledge content to share
            knowledge_type: Type of knowledge (pattern, skill, insight)

        Returns:
            Sharing result
        """
        logger.info(f"Sharing {knowledge_type} from {from_bot} to {to_bots}")

        # Create source node
        source_id = f"{from_bot}-{knowledge_type}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        source_node = KnowledgeNode({
            'id': source_id,
            'type': knowledge_type,
            'content': knowledge,
            'source_bot': from_bot,
            'created_at': datetime.now().isoformat(),
            'tags': [f'from:{from_bot}', knowledge_type]
        })

        self._nodes[source_id] = source_node

        # Map and share to each target bot
        propagated = []
        for target_bot in to_bots:
            if target_bot == from_bot:
                continue

            # Get related bots
            related_bots = self._bot_relationships.get(from_bot, [])
            if target_bot not in related_bots:
                logger.info(f"Skipping {target_bot}: not related to {from_bot}")
                continue

            # Map knowledge to target context
            mapped_knowledge = self._map_to_bot_context(knowledge, from_bot, target_bot)

            if mapped_knowledge:
                propagated.append({
                    'bot': target_bot,
                    'mapped_content': mapped_knowledge
                })

                # Create propagated node
                target_id = f"{target_bot}-{knowledge_type}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                target_node = KnowledgeNode({
                    'id': target_id,
                    'type': knowledge_type,
                    'content': mapped_knowledge,
                    'source_bot': target_bot,
                    'created_at': datetime.now().isoformat(),
                    'tags': [f'from:{from_bot}', f'propagated:{target_bot}', knowledge_type],
                    'propagated_to': [target_bot]
                })

                self._nodes[target_id] = target_node

                # Link to source
                self.add_edge(source_id, target_id, 'propagation')

        self._save_graph()

        # Write to target bot memory
        self._write_to_bot_memory(propagated, from_bot, knowledge_type)

        return {
            'success': True,
            'source_id': source_id,
            'propagated_count': len(propagated),
            'propagated_to': [p['bot'] for p in propagated]
        }

    def _map_to_bot_context(
        self,
        knowledge: str,
        from_bot: str,
        to_bot: str
    ) -> Optional[str]:
        """Map knowledge from source bot context to target bot context."""

        # Bot context descriptions
        bot_contexts = {
            '编导': '直播内容策划、创意构思、脚本编写',
            '场控': '直播现场控制、互动管理、节奏把控',
            '剪辑': '视频剪辑、后期制作、特效处理',
            '美工': '视觉设计、图片制作、美学规范',
            '客服': '粉丝服务、问题解答、关系维护',
            '运营': '数据分析、策略制定、用户增长',
            '渠道': '渠道拓展、商务合作、资源整合'
        }

        prompt = f"""Map this knowledge from {from_bot}'s context to {to_bot}'s context.

Source Bot ({from_bot}): {bot_contexts.get(from_bot, 'general work')}
Target Bot ({to_bot}): {bot_contexts.get(to_bot, 'general work')}

Original Knowledge:
{knowledge}

Rewrite the knowledge to be relevant and actionable for {to_bot}.
Keep the core insight but adapt the examples and applications.

Return the mapped knowledge as plain text."""

        try:
            request_data = {
                "model": self._api_config["model"],
                "messages": [
                    {"role": "system", "content": "You are a knowledge mapper. Adapt knowledge to different contexts."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self._api_config["temperature"],
                "max_tokens": self._api_config["max_tokens"]
            }

            url = f"{self._api_config['base_url']}/chat/completions"

            req = urllib.request.Request(
                url,
                data=json.dumps(request_data).encode('utf-8'),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_config['api_key']}"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Knowledge mapping failed: {e}")
            return None

    def _write_to_bot_memory(
        self,
        propagated: List[Dict],
        from_bot: str,
        knowledge_type: str
    ):
        """Write propagated knowledge to target bot memory."""
        for p in propagated:
            bot = p['bot']
            content = p['mapped_content']

            # Write to bot's memory file
            memory_dir = Path(__file__).parent / "workspaces/{bot}/memory/知识库"
            memory_dir.mkdir(parents=True, exist_ok=True)

            knowledge_file = memory_dir / f'跨 Bot 学习-{from_bot}.md'

            entry = f"""## {datetime.now().strftime('%Y-%m-%d %H:%M')} - 来自 {from_bot} Bot 的分享

**知识类型**: {knowledge_type}

**内容**:
{content}

---
"""

            with open(knowledge_file, 'a', encoding='utf-8') as f:
                f.write(entry)

            logger.info(f"Written to {bot}'s memory")

    def get_related_knowledge(
        self,
        bot_name: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get knowledge related to a bot."""
        related = []

        for node in self._nodes.values():
            if node.source_bot == bot_name or bot_name in node.propagated_to:
                related.append({
                    'id': node.id,
                    'type': node.type,
                    'content': node.content[:200],  # Truncate
                    'source_bot': node.source_bot,
                    'created_at': node.created_at
                })

        # Sort by recency
        related.sort(key=lambda x: x['created_at'], reverse=True)
        return related[:limit]

    def get_knowledge_propagation_path(self, node_id: str) -> List[str]:
        """Get the propagation path for a knowledge node."""
        if node_id not in self._nodes:
            return []

        node = self._nodes[node_id]
        path = [node_id]

        # BFS to find all connected nodes
        visited = {node_id}
        queue = list(node.connected_to)

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)
            path.append(current_id)

            if current_id in self._nodes:
                queue.extend(self._nodes[current_id].connected_to)

        return path

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        nodes_by_type = defaultdict(int)
        nodes_by_bot = defaultdict(int)

        for node in self._nodes.values():
            nodes_by_type[node.type] += 1
            nodes_by_bot[node.source_bot] += 1

        return {
            'total_nodes': len(self._nodes),
            'total_edges': len(self._edges),
            'nodes_by_type': dict(nodes_by_type),
            'nodes_by_bot': dict(nodes_by_bot),
            'avg_connections': len(self._edges) / len(self._nodes) if self._nodes else 0
        }

    # API config
    _api_config = KNOWLEDGE_GRAPH_CONFIG


# Global instance
_default_graph: Optional[KnowledgeGraph] = None


def get_knowledge_graph() -> KnowledgeGraph:
    """Get or create KnowledgeGraph instance."""
    global _default_graph
    if _default_graph is None:
        _default_graph = KnowledgeGraph()
    return _default_graph


def share_learning(
    from_bot: str,
    to_bots: List[str],
    knowledge: str,
    knowledge_type: str = 'pattern'
) -> Dict[str, Any]:
    """Convenience function to share learning."""
    graph = get_knowledge_graph()
    return graph.share_learning(from_bot, to_bots, knowledge, knowledge_type)
