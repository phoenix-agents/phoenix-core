#!/usr/bin/env python3
"""
Reflection Engine - Deep Reflection and Pattern Discovery

Analyzes:
1. Success/failure patterns
2. Inefficient operations
3. Optimization opportunities
4. Cross-session insights

Generates:
1. Optimization strategies
2. New skill versions
3. Knowledge updates

Usage:
    engine = ReflectionEngine(memory_manager)
    insights = engine.reflect(bot_name="编导", time_range="24h")
"""

import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# AI config for reflection analysis
REFLECTION_CONFIG = {
    "base_url": "https://coding.dashscope.aliyuncs.com/v1",
    "api_key": os.environ.get("DASHSCOPE_API_KEY"),
    "model": "qwen3-coder-next",
    "max_tokens": 3000,
    "temperature": 0.15
}


class ReflectionEngine:
    """
    Deep reflection engine for agent self-improvement.

    Capabilities:
    1. Analyze success/failure patterns
    2. Identify inefficient operations
    3. Generate optimization strategies
    4. Discover cross-session insights
    5. Trigger skill evolution
    """

    def __init__(self, memory_manager=None):
        self._memory_manager = memory_manager
        self._api_config = REFLECTION_CONFIG

        # Reflection state
        self._last_reflection_time: Dict[str, datetime] = {}
        self._reflection_cooldown_hours = 1  # Min hours between reflections

        # Analysis cache
        self._pattern_cache: Dict[str, Any] = {}

    def reflect(
        self,
        bot_name: str = None,
        time_range: str = "24h",
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Run deep reflection analysis.

        Args:
            bot_name: Specific bot to analyze (None = all bots)
            time_range: Time range to analyze (e.g., "24h", "7d")
            force: Force reflection even if in cooldown

        Returns:
            Reflection insights and recommendations
        """
        # Check cooldown
        if not force and self._is_in_cooldown(bot_name or 'all'):
            logger.info("Reflection in cooldown, skipping")
            return {'success': False, 'reason': 'cooldown'}

        logger.info(f"Starting reflection for {bot_name or 'all bots'} ({time_range})")

        # Gather session data
        sessions = self._gather_sessions(bot_name, time_range)

        if not sessions:
            return {'success': False, 'reason': 'no_sessions'}

        # Analyze patterns
        insights = self._analyze_patterns(sessions)

        # Generate recommendations
        recommendations = self._generate_recommendations(insights)

        # Update memory with insights
        self._update_memory(insights, recommendations)

        # Record reflection
        self._record_reflection(bot_name or 'all', insights)

        # Update cooldown
        self._last_reflection_time[bot_name or 'all'] = datetime.now()

        return {
            'success': True,
            'insights': insights,
            'recommendations': recommendations,
            'sessions_analyzed': len(sessions)
        }

    def _is_in_cooldown(self, bot_name: str) -> bool:
        """Check if reflection is in cooldown."""
        last_time = self._last_reflection_time.get(bot_name)
        if not last_time:
            return False

        cooldown_end = last_time + timedelta(hours=self._reflection_cooldown_hours)
        return datetime.now() < cooldown_end

    def _gather_sessions(self, bot_name: str, time_range: str) -> List[Dict[str, Any]]:
        """Gather sessions for analysis."""
        if not self._memory_manager:
            return []

        # Parse time range
        hours = self._parse_time_range(time_range)
        since = datetime.now() - timedelta(hours=hours)

        # Get sessions from SessionStore
        session_store = self._memory_manager._session_store
        all_sessions = session_store.list_sessions(limit=1000)

        # Filter by bot and time
        sessions = []
        for session in all_sessions:
            # Check bot match
            if bot_name and bot_name not in session.get('session_id', ''):
                continue

            # Check time
            started_at = session.get('started_at', 0)
            if started_at < since.timestamp():
                continue

            # Get messages for this session
            messages = session_store.get_messages(session['session_id'])

            sessions.append({
                'session_id': session['session_id'],
                'started_at': session['started_at'],
                'status': session.get('status', 'unknown'),
                'input_tokens': session.get('input_tokens', 0),
                'output_tokens': session.get('output_tokens', 0),
                'messages': messages
            })

        return sessions

    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range string to hours."""
        if time_range.endswith('h'):
            return int(time_range[:-1])
        elif time_range.endswith('d'):
            return int(time_range[:-1]) * 24
        elif time_range.endswith('w'):
            return int(time_range[:-1]) * 24 * 7
        else:
            return 24  # Default to 24 hours

    def _analyze_patterns(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze sessions for patterns."""
        # Calculate basic statistics
        total_sessions = len(sessions)
        successful = sum(1 for s in sessions if s.get('status') == 'completed')
        total_tokens = sum(
            s.get('input_tokens', 0) + s.get('output_tokens', 0)
            for s in sessions
        )

        # Extract failure patterns
        failures = [s for s in sessions if s.get('status') != 'completed']
        failure_patterns = self._extract_failure_patterns(failures)

        # Extract success patterns
        successes = [s for s in sessions if s.get('status') == 'completed']
        success_patterns = self._extract_success_patterns(successes)

        # Identify inefficient operations (high token, low output)
        inefficient = self._identify_inefficient_operations(sessions)

        # Use AI for deeper pattern analysis
        ai_insights = self._ai_pattern_analysis(sessions[:10])  # Limit for speed

        return {
            'statistics': {
                'total_sessions': total_sessions,
                'successful': successful,
                'failed': len(failures),
                'success_rate': successful / total_sessions if total_sessions > 0 else 0,
                'total_tokens': total_tokens,
                'avg_tokens_per_session': total_tokens / total_sessions if total_sessions > 0 else 0
            },
            'failure_patterns': failure_patterns,
            'success_patterns': success_patterns,
            'inefficient_operations': inefficient,
            'ai_insights': ai_insights
        }

    def _extract_failure_patterns(self, failures: List[Dict]) -> List[str]:
        """Extract common failure patterns."""
        patterns = []

        # Analyze failure messages
        for failure in failures:
            messages = failure.get('messages', [])
            for msg in messages:
                content = msg.get('content', '')
                if 'error' in content.lower() or 'failed' in content.lower():
                    patterns.append(content[:200])  # Truncate

        # Deduplicate
        unique_patterns = list(set(patterns))[:5]  # Top 5
        return unique_patterns

    def _extract_success_patterns(self, successes: List[Dict]) -> List[str]:
        """Extract common success patterns."""
        patterns = []

        for success in successes:
            messages = success.get('messages', [])
            # Look for successful tool calls
            for msg in messages:
                if msg.get('role') == 'tool' and msg.get('tool_name'):
                    patterns.append(f"Tool '{msg.get('tool_name')}' succeeded")

        # Deduplicate
        unique_patterns = list(set(patterns))[:5]
        return unique_patterns

    def _identify_inefficient_operations(self, sessions: List[Dict]) -> List[Dict]:
        """Identify operations with high token usage but low value."""
        inefficient = []

        for session in sessions:
            input_tokens = session.get('input_tokens', 0)
            output_tokens = session.get('output_tokens', 0)

            # Heuristic: high input, low output = inefficient
            if input_tokens > 1000 and output_tokens < 100:
                inefficient.append({
                    'session_id': session['session_id'],
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'ratio': output_tokens / input_tokens if input_tokens > 0 else 0
                })

        return sorted(inefficient, key=lambda x: x['ratio'])[:5]

    def _ai_pattern_analysis(self, sessions: List[Dict]) -> Optional[Dict[str, Any]]:
        """Use AI to analyze patterns."""
        if not sessions:
            return None

        # Format sessions for AI
        session_summary = []
        for s in sessions[:5]:  # Limit to 5 sessions
            msg_count = len(s.get('messages', []))
            session_summary.append({
                'session_id': s['session_id'],
                'status': s.get('status', 'unknown'),
                'messages': msg_count,
                'tokens': s.get('input_tokens', 0) + s.get('output_tokens', 0)
            })

        prompt = f"""Analyze these session patterns and identify insights:

Sessions:
{json.dumps(session_summary, indent=2)}

Provide insights on:
1. What patterns indicate success?
2. What patterns indicate failure?
3. What optimizations would improve performance?

Return JSON:
{{
  "success_patterns": ["..."],
  "failure_patterns": ["..."],
  "optimizations": [{{"area": "...", "suggestion": "...", "priority": "high/medium/low"}}]
}}
"""

        try:
            request_data = {
                "model": self._api_config["model"],
                "messages": [
                    {"role": "system", "content": "Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self._api_config["temperature"],
                "max_tokens": self._api_config["max_tokens"],
                "response_format": {"type": "json_object"}
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
                content = result["choices"][0]["message"]["content"]

                # Parse JSON
                content = content.strip()
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                content = content.strip()

                return json.loads(content)
        except Exception as e:
            logger.error(f"AI pattern analysis failed: {e}")
            return None

    def _generate_recommendations(
        self,
        insights: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations."""
        recommendations = []

        # Based on failure patterns
        if insights.get('failure_patterns'):
            recommendations.append({
                'type': 'address_failures',
                'priority': 'high',
                'action': f"Address {len(insights['failure_patterns'])} failure patterns",
                'details': insights['failure_patterns'][:3]
            })

        # Based on inefficient operations
        if insights.get('inefficient_operations'):
            recommendations.append({
                'type': 'improve_efficiency',
                'priority': 'medium',
                'action': f"Optimize {len(insights['inefficient_operations'])} inefficient operations",
                'details': insights['inefficient_operations'][:3]
            })

        # Based on AI insights
        ai_insights = insights.get('ai_insights', {})
        if ai_insights and ai_insights.get('optimizations'):
            for opt in ai_insights['optimizations']:
                recommendations.append({
                    'type': 'optimization',
                    'priority': opt.get('priority', 'medium'),
                    'area': opt.get('area', 'unknown'),
                    'action': opt.get('suggestion', '')
                })

        return recommendations

    def _update_memory(
        self,
        insights: Dict[str, Any],
        recommendations: List[Dict[str, Any]]
    ):
        """Update memory with insights."""
        if not self._memory_manager:
            return

        # Add insight to memory
        insight_entry = f"""## Reflection Insights - {datetime.now().strftime('%Y-%m-%d %H:%M')}

**Statistics**:
- Success Rate: {insights.get('statistics', {}).get('success_rate', 0):.0%}
- Sessions Analyzed: {insights.get('statistics', {}).get('total_sessions', 0)}

**Key Insights**:
- Failure Patterns: {len(insights.get('failure_patterns', []))}
- Success Patterns: {len(insights.get('success_patterns', []))}
- Inefficient Operations: {len(insights.get('inefficient_operations', []))}

**Recommendations**: {len(recommendations)}
"""

        self._memory_manager._memory_store.add('memory', insight_entry)

    def _record_reflection(self, bot_name: str, insights: Dict[str, Any]):
        """Record reflection event."""
        log_file = Path(__file__).parent / "reflection_log.md"

        entry = f"""## Reflection - {datetime.now().strftime('%Y-%m-%d %H:%M')}

**Bot**: {bot_name}
**Success Rate**: {insights.get('statistics', {}).get('success_rate', 0):.0%}
**Sessions**: {insights.get('statistics', {}).get('total_sessions', 0)}

---
"""

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(entry)

    def trigger_skill_evolution(
        self,
        skill_name: str,
        insights: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger skill evolution based on insights."""
        from skill_evolution import get_skill_evolution

        evolution = get_skill_evolution(self._memory_manager)

        # Determine evolution reason from insights
        reason = "Reflection-driven improvement"
        if insights.get('failure_patterns'):
            reason = f"Addressing failure patterns ({len(insights['failure_patterns'])} found)"

        # Execute evolution
        return evolution.evolve_skill(skill_name, reason)


# Global instance
_default_engine: Optional[ReflectionEngine] = None


def get_reflection_engine(memory_manager=None) -> ReflectionEngine:
    """Get or create ReflectionEngine instance."""
    global _default_engine
    if _default_engine is None:
        _default_engine = ReflectionEngine(memory_manager)
    return _default_engine


def reflect(
    bot_name: str = None,
    time_range: str = "24h",
    force: bool = False
) -> Dict[str, Any]:
    """Convenience function to run reflection."""
    engine = get_reflection_engine()
    return engine.reflect(bot_name, time_range, force)
