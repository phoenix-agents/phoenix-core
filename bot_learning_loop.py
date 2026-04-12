#!/usr/bin/env python3
"""
Bot Learning Loop - Per-bot automatic learning system

Each bot has its own learning loop that:
1. Tracks tool call iterations
2. Triggers reflection at thresholds
3. Auto-creates/updates skills based on experience
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)


class BotLearningLoop:
    """
    Learning loop for a specific bot.

    Responsibilities:
    1. Track tool call iterations
    2. Trigger reflection at configurable thresholds
    3. Auto-update bot memory with learnings
    4. Create/update skills based on experience
    """

    def __init__(
        self,
        bot_name: str,
        reflection_threshold: int = 10,
        on_reflection: Callable[[str, List[Dict]], None] = None
    ):
        self.bot_name = bot_name
        self.reflection_threshold = reflection_threshold
        self.iteration_counter = 0
        self.session_history: List[Dict[str, Any]] = []
        self.on_reflection = on_reflection or self._default_reflection

        self.memory_dir = Path(f"workspaces/{bot_name}/memory/")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def sync_turn(
        self,
        user_msg: str,
        assistant_msg: str,
        tool_iterations: int = 1
    ):
        """
        Sync after a turn of conversation.

        Args:
            user_msg: User's message
            assistant_msg: Bot's response
            tool_iterations: Number of tool calls made
        """
        self.iteration_counter += tool_iterations

        # Record session history
        self.session_history.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_msg,
            "assistant": assistant_msg,
            "iterations": tool_iterations
        })

        # Check if reflection needed
        if self.iteration_counter >= self.reflection_threshold:
            self._trigger_reflection()
            self.iteration_counter = 0

    def _trigger_reflection(self):
        """Trigger reflection on recent experience."""
        logger.info(f"[{self.bot_name}] Triggering reflection...")

        # Analyze recent sessions
        learnings = self._analyze_sessions()

        # Call reflection handler
        self.on_reflection(self.bot_name, learnings)

        # Log daily summary
        self._write_daily_log()

    def _analyze_sessions(self) -> List[Dict[str, Any]]:
        """Analyze recent sessions for learnings."""
        learnings = []

        for session in self.session_history[-self.reflection_threshold:]:
            # Extract patterns
            learning = {
                "task": session["user"][:50] + "..." if len(session["user"]) > 50 else session["user"],
                "outcome": "completed" if session["assistant"] else "incomplete",
                "effort": session["iterations"],
                "timestamp": session["timestamp"]
            }
            learnings.append(learning)

        return learnings

    def _default_reflection(self, bot_name: str, learnings: List[Dict[str, Any]]):
        """
        Default reflection handler.

        Writes learnings to bot's memory.
        """
        # Write to MEMORY.md
        memory_file = Path(f"workspaces/{bot_name}/MEMORY.md")

        if memory_file.exists():
            with open(memory_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n## 学习总结 - {datetime.now().strftime('%Y-%m-%d')}\n")
                for learning in learnings:
                    f.write(f"- {learning['task']}: {learning['outcome']} "
                           f"(effort: {learning['effort']})\n")

        logger.info(f"[{bot_name}] Reflection written to memory")

    def _write_daily_log(self):
        """Write daily log entry."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.memory_dir / f"{today}.md"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n### [{self.bot_name}] 活动记录\n")
            f.write(f"- 完成任务数：{len(self.session_history)}\n")
            f.write(f"- 工具调用次数：{self.iteration_counter}\n")

        # Clear session history after logging
        self.session_history = []

    def reset(self):
        """Reset learning loop state."""
        self.iteration_counter = 0
        self.session_history = []
        logger.info(f"[{self.bot_name}] Learning loop reset")


class BotLearningManager:
    """
    Centralized learning management for all bots.

    Provides:
    1. Per-bot learning loops
    2. Cross-bot learning sharing
    3. Global learning analytics
    """

    def __init__(self, reflection_threshold: int = 10):
        self._loops: Dict[str, BotLearningLoop] = {}
        self.reflection_threshold = reflection_threshold

    def get_loop(self, bot_name: str) -> BotLearningLoop:
        """Get or create learning loop for a bot."""
        if bot_name not in self._loops:
            self._loops[bot_name] = BotLearningLoop(
                bot_name,
                reflection_threshold=self.reflection_threshold
            )
        return self._loops[bot_name]

    def sync_turn(
        self,
        bot_name: str,
        user_msg: str,
        assistant_msg: str,
        tool_iterations: int = 1
    ):
        """Sync turn for a specific bot."""
        loop = self.get_loop(bot_name)
        loop.sync_turn(user_msg, assistant_msg, tool_iterations)

    def get_all_loops(self) -> Dict[str, BotLearningLoop]:
        """Get all learning loops."""
        return self._loops.copy()

    def share_learning(
        self,
        from_bot: str,
        to_bots: List[str],
        learning: str
    ):
        """
        Share a learning from one bot to others.

        Args:
            from_bot: Source bot name
            to_bots: Target bot names
            learning: Learning content to share
        """
        logger.info(f"[{from_bot}] Sharing learning to {to_bots}")

        for bot in to_bots:
            if bot != from_bot:
                loop = self.get_loop(bot)
                # Add learning to target bot's memory
                self._add_learning_to_bot(bot, learning)

    def _add_learning_to_bot(self, bot_name: str, learning: str):
        """Add learning to a bot's memory."""
        memory_file = Path(f"workspaces/{bot_name}/MEMORY.md")

        if memory_file.exists():
            with open(memory_file, "a", encoding="utf-8") as f:
                f.write(f"\n## 跨 Bot 学习 - {datetime.now().strftime('%Y-%m-%d')}\n")
                f.write(f"- {learning}\n")


# Global instance
_learning_manager: BotLearningManager = None


def get_learning_manager() -> BotLearningManager:
    """Get global learning manager instance."""
    global _learning_manager
    if _learning_manager is None:
        _learning_manager = BotLearningManager()
    return _learning_manager


def get_bot_learning_loop(bot_name: str) -> BotLearningLoop:
    """Get learning loop for a specific bot."""
    return get_learning_manager().get_loop(bot_name)


def bot_sync_turn(
    bot_name: str,
    user_msg: str,
    assistant_msg: str,
    tool_iterations: int = 1
):
    """Sync turn for a bot."""
    get_learning_manager().sync_turn(
        bot_name, user_msg, assistant_msg, tool_iterations
    )
