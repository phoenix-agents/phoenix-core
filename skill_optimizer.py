#!/usr/bin/env python3
"""
Skill Optimization Module - Learning from Execution Results

This module analyzes skill execution results and automatically
optimizes skills based on success/failure patterns.

Key Features:
1. Execution result tracking
2. Failure pattern analysis with clustering
3. AI-powered skill optimization
4. Version control for skills
5. Actionable repair plan generation

Usage:
    optimizer = SkillOptimizer(memory_manager)

    # After execution
    optimizer.record_execution(execution_result)

    # Analyze and optimize
    if optimizer.should_optimize(skill_name):
        optimizer.optimize_skill(skill_name)
"""

import json
import logging
import os
import urllib.request
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

# Coding Plan API config
CODING_PLAN_CONFIG = {
    "base_url": "https://coding.dashscope.aliyuncs.com/v1",
    "api_key": os.environ.get("DASHSCOPE_API_KEY"),
    "model": "qwen3-coder-next",
    "max_tokens": 3500,
    "temperature": 0.2
}


class SkillOptimizer:
    """
    Optimizes skills based on execution results.

    Process:
    1. Record execution results
    2. Analyze failure patterns
    3. Identify optimization opportunities
    4. Use AI to generate improvements
    5. Save optimized skill versions
    """

    def __init__(self, memory_manager=None):
        self._memory_manager = memory_manager
        self._execution_records = []
        self._api_config = CODING_PLAN_CONFIG

        # Optimization thresholds
        self._min_failures_for_optimize = 3
        self._min_executions_for_analysis = 5
        self._success_rate_threshold = 0.7  # Below this triggers optimization

        # Failure pattern clustering
        self._failure_patterns_cache: Dict[str, Any] = {}

    def record_execution(self, skill_name: str, result: Dict[str, Any],
                        user_feedback: Dict[str, Any] = None):
        """
        Record a skill execution result.

        Args:
            skill_name: Name of the executed skill
            result: Execution result dictionary
            user_feedback: Optional user feedback
        """
        record = {
            "skill_name": skill_name,
            "timestamp": datetime.now().isoformat(),
            "success": result.get('success', False),
            "total_steps": result.get('total_steps', 0),
            "success_count": result.get('success_count', 0),
            "error_count": result.get('error_count', 0),
            "failed_step": self._get_failed_step(result),
            "error_message": self._get_error_message(result),
            "execution_time": result.get('execution_time', 0),
            "user_feedback": user_feedback
        }

        self._execution_records.append(record)
        logger.info(f"Recorded execution: {skill_name} - success={record['success']}")

    def _get_failed_step(self, result: Dict) -> Optional[int]:
        """Get the step number that failed."""
        step_results = result.get('step_results', [])
        for i, step in enumerate(step_results):
            if not step.get('success', True):
                return i + 1
        return None

    def _get_error_message(self, result: Dict) -> Optional[str]:
        """Get error message from failed execution."""
        step_results = result.get('step_results', [])
        for step in step_results:
            if not step.get('success', True):
                return step.get('error', 'Unknown error')
        return None

    def get_skill_stats(self, skill_name: str, limit: int = 50) -> Dict[str, Any]:
        """
        Get execution statistics for a skill.

        Args:
            skill_name: Name of the skill
            limit: Max records to analyze

        Returns:
            Statistics dictionary
        """
        # Filter records for this skill
        records = [r for r in self._execution_records[-limit:]
                  if r['skill_name'] == skill_name]

        if not records:
            return {"skill_name": skill_name, "total_executions": 0}

        # Calculate stats
        total = len(records)
        successes = sum(1 for r in records if r['success'])
        failures = total - successes
        success_rate = successes / total if total > 0 else 0

        # Find common failure points
        failure_steps = [r['failed_step'] for r in records if r['failed_step']]
        common_failure_step = self._find_mode(failure_steps) if failure_steps else None

        # Analyze error patterns
        error_messages = [r['error_message'] for r in records if r['error_message']]
        common_error = self._find_common_pattern(error_messages) if error_messages else None

        return {
            "skill_name": skill_name,
            "total_executions": total,
            "successes": successes,
            "failures": failures,
            "success_rate": round(success_rate, 2),
            "common_failure_step": common_failure_step,
            "common_error": common_error,
            "avg_success_count": sum(r['success_count'] for r in records) / total,
            "avg_total_steps": sum(r['total_steps'] for r in records) / total,
            "needs_optimization": self._needs_optimization(success_rate, failures)
        }

    def _find_mode(self, values: List) -> Optional[Any]:
        """Find the most common value in a list."""
        if not values:
            return None
        from collections import Counter
        counter = Counter(values)
        return counter.most_common(1)[0][0]

    def _find_common_pattern(self, messages: List[str]) -> Optional[str]:
        """Find common pattern in error messages."""
        if not messages:
            return None

        # Simple: find common substring
        common = messages[0]
        for msg in messages[1:]:
            # Find common substring
            common = self._longest_common_substring(common, msg)

        return common if len(common) > 5 else None

    def _longest_common_substring(self, s1: str, s2: str) -> str:
        """Find longest common substring."""
        m = len(s1)
        n = len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        max_len = 0
        end_pos = 0

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                    if dp[i][j] > max_len:
                        max_len = dp[i][j]
                        end_pos = i

        return s1[end_pos - max_len:end_pos]

    def _needs_optimization(self, success_rate: float, failures: int) -> bool:
        """Determine if skill needs optimization."""
        return (success_rate < self._success_rate_threshold and
                failures >= self._min_failures_for_optimize)

    def analyze_failure_patterns(self, skill_name: str,
                                  limit: int = 50) -> Dict[str, Any]:
        """
        Analyze failure patterns for a skill with clustering.

        Args:
            skill_name: Name of the skill
            limit: Max records to analyze

        Returns:
            Comprehensive failure analysis including:
            - Clustered failure modes
            - Common characteristics
            - AI-generated optimization suggestions
            - Executable repair plans
        """
        # Get failure records
        records = [r for r in self._execution_records[-limit:]
                  if r['skill_name'] == skill_name and not r['success']]

        if not records:
            return {
                "skill_name": skill_name,
                "analysis_success": False,
                "reason": "No failure records found",
                "failure_clusters": [],
                "suggestions": [],
                "repair_plan": None
            }

        logger.info(f"Analyzing {len(records)} failure records for {skill_name}")

        # Step 1: Cluster failures by characteristics
        clusters = self._cluster_failures(records)

        # Step 2: Identify common characteristics per cluster
        cluster_analysis = self._analyze_clusters(clusters, records)

        # Step 3: Generate AI-powered suggestions
        suggestions = self._generate_ai_suggestions(skill_name, cluster_analysis, records)

        # Step 4: Create executable repair plan
        repair_plan = self._create_repair_plan(skill_name, cluster_analysis, suggestions)

        result = {
            "skill_name": skill_name,
            "analysis_success": True,
            "total_failures_analyzed": len(records),
            "failure_clusters": cluster_analysis,
            "suggestions": suggestions,
            "repair_plan": repair_plan,
            "timestamp": datetime.now().isoformat()
        }

        # Cache for future use
        self._failure_patterns_cache[skill_name] = result

        logger.info(f"Failure analysis complete: {len(cluster_analysis)} clusters identified")
        return result

    def _cluster_failures(self, records: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Cluster failures by common characteristics.

        Clustering dimensions:
        1. Failed step number
        2. Error type/category
        3. Error message patterns
        """
        clusters = defaultdict(list)

        for record in records:
            # Create cluster key based on characteristics
            step = record.get('failed_step')
            error = record.get('error_message', '')
            error_type = self._categorize_error(error)

            # Primary clustering by step, secondary by error type
            if step:
                cluster_key = f"step_{step}_{error_type}"
            else:
                cluster_key = f"error_{error_type}"

            clusters[cluster_key].append(record)

        # Sort clusters by size (largest first)
        sorted_clusters = dict(
            sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)
        )

        return sorted_clusters

    def _categorize_error(self, error_message: str) -> str:
        """Categorize error into types."""
        if not error_message:
            return "unknown"

        error_lower = error_message.lower()

        # Network/connectivity errors
        if any(kw in error_lower for kw in ['timeout', 'connection', 'network', 'refused']):
            return "connectivity"

        # Authentication errors
        if any(kw in error_lower for kw in ['auth', 'permission', 'denied', 'unauthorized']):
            return "authorization"

        # Resource errors
        if any(kw in error_lower for kw in ['not found', 'missing', '404', 'does not exist']):
            return "resource_missing"

        # Rate limiting
        if any(kw in error_lower for kw in ['rate limit', 'too many', 'throttl']):
            return "rate_limit"

        # Parsing/format errors
        if any(kw in error_lower for kw in ['parse', 'format', 'invalid', 'malformed']):
            return "format_error"

        # Server errors
        if any(kw in error_lower for kw in ['500', '502', '503', 'server error']):
            return "server_error"

        return "general"

    def _analyze_clusters(self, clusters: Dict[str, List[Dict]],
                         all_records: List[Dict]) -> List[Dict[str, Any]]:
        """
        Analyze each cluster to identify characteristics.

        Returns list of cluster analyses with:
        - Cluster ID and description
        - Failure count and percentage
        - Common error pattern
        - Representative errors
        """
        total_failures = len(all_records)
        cluster_analyses = []

        for cluster_id, records in clusters.items():
            if not records:
                continue

            # Extract common characteristics
            error_messages = [r.get('error_message', '') for r in records]
            common_error = self._find_common_pattern(error_messages)

            # Get step information
            failed_steps = [r.get('failed_step') for r in records if r.get('failed_step')]
            most_common_step = self._find_mode(failed_steps) if failed_steps else None

            # Calculate cluster statistics
            failure_rate = len(records) / total_failures if total_failures > 0 else 0

            # Identify error type from cluster ID
            error_type = cluster_id.split('_')[-1] if '_' in cluster_id else 'unknown'

            cluster_analysis = {
                "cluster_id": cluster_id,
                "error_type": error_type,
                "failure_count": len(records),
                "failure_percentage": round(failure_rate * 100, 1),
                "common_step": most_common_step,
                "common_error_pattern": common_error,
                "representative_errors": list(set(error_messages))[:3],
                "severity": self._assess_severity(len(records), failure_rate)
            }

            cluster_analyses.append(cluster_analysis)

        return cluster_analyses

    def _assess_severity(self, count: int, percentage: float) -> str:
        """Assess severity of a failure cluster."""
        if percentage >= 50 or count >= 10:
            return "critical"
        elif percentage >= 25 or count >= 5:
            return "high"
        elif percentage >= 10 or count >= 3:
            return "medium"
        else:
            return "low"

    def _generate_ai_suggestions(self, skill_name: str,
                                  cluster_analysis: List[Dict],
                                  failure_records: List[Dict]) -> List[Dict[str, Any]]:
        """
        Use AI to generate specific optimization suggestions.

        Args:
            skill_name: Name of the skill
            cluster_analysis: Analyzed failure clusters
            failure_records: Raw failure records

        Returns:
            List of AI-generated suggestions with:
            - Suggestion description
            - Target cluster
            - Priority level
            - Implementation hint
        """
        # Get current skill definition
        skill = self._get_skill(skill_name) or {}

        # Build detailed prompt for AI analysis
        prompt = self._build_analysis_prompt(skill_name, skill, cluster_analysis, failure_records)

        # Call AI for suggestions
        suggestions = self._call_ai_for_suggestions(prompt)

        if not suggestions:
            # Fallback: generate heuristic suggestions
            suggestions = self._generate_heuristic_suggestions(cluster_analysis)

        return suggestions

    def _build_analysis_prompt(self, skill_name: str, skill: Dict,
                               cluster_analysis: List[Dict],
                               failure_records: List[Dict]) -> str:
        """Build detailed prompt for AI analysis."""
        cluster_summary = "\n".join([
            f"- Cluster '{c['cluster_id']}': {c['failure_count']} failures "
            f"({c['failure_percentage']}%), step {c['common_step']}, "
            f"pattern: {c['common_error_pattern'][:50] if c['common_error_pattern'] else 'N/A'}"
            for c in cluster_analysis[:5]  # Top 5 clusters
        ])

        sample_errors = "\n".join([
            f"- {r.get('error_message', 'Unknown')[:100]}"
            for r in failure_records[:5]
        ])

        prompt = f"""Analyze this skill's failure patterns and generate specific optimization suggestions.

**Skill**: {skill_name}
**Current Definition**:
{json.dumps(skill, indent=2) if skill else "Not available"}

**Failure Analysis Summary**:
{cluster_summary}

**Sample Error Messages**:
{sample_errors}

**Task**: Generate 3-5 specific, actionable optimization suggestions.

For each suggestion, provide:
1. `title`: Brief title (e.g., "Add retry mechanism for network timeouts")
2. `description`: Detailed description of what to change
3. `target_cluster`: Which failure cluster this addresses
4. `priority`: "high", "medium", or "low"
5. `implementation_hint`: Concrete code/step change suggestion

Return JSON in this format:
{{
    "suggestions": [
        {{
            "title": "...",
            "description": "...",
            "target_cluster": "cluster_id",
            "priority": "high",
            "implementation_hint": "..."
        }}
    ]
}}
"""
        return prompt

    def _call_ai_for_suggestions(self, prompt: str) -> List[Dict[str, Any]]:
        """Call AI to generate suggestions."""
        request_data = {
            "model": self._api_config["model"],
            "messages": [
                {"role": "system", "content": "Output valid JSON only. Focus on practical, implementable suggestions."},
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

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result["choices"][0]["message"]["content"]

                # Clean and parse
                content = content.strip()
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                content = content.strip()

                parsed = json.loads(content)
                suggestions = parsed.get('suggestions', [])

                logger.info(f"AI generated {len(suggestions)} suggestions")
                return suggestions

        except Exception as e:
            logger.error(f"AI suggestion generation failed: {e}")
            return []

    def _generate_heuristic_suggestions(self, cluster_analysis: List[Dict]) -> List[Dict[str, Any]]:
        """Generate suggestions based on heuristics when AI fails."""
        suggestions = []

        for cluster in cluster_analysis[:3]:  # Top 3 clusters
            error_type = cluster.get('error_type', 'unknown')
            step = cluster.get('common_step')

            # Heuristic suggestions based on error type
            if error_type == 'connectivity':
                suggestions.append({
                    "title": "Add exponential backoff retry",
                    "description": "Implement retry with exponential backoff for network operations",
                    "target_cluster": cluster['cluster_id'],
                    "priority": "high",
                    "implementation_hint": f"Add retry logic before step {step}: wait 2^n seconds between attempts, max 3 retries"
                })
            elif error_type == 'rate_limit':
                suggestions.append({
                    "title": "Implement rate limiting handling",
                    "description": "Add delay and retry logic when rate limit is hit",
                    "target_cluster": cluster['cluster_id'],
                    "priority": "high",
                    "implementation_hint": "Check response headers for rate limit, wait reset time before retry"
                })
            elif error_type == 'authorization':
                suggestions.append({
                    "title": "Add authentication refresh",
                    "description": "Check and refresh authentication before operations",
                    "target_cluster": cluster['cluster_id'],
                    "priority": "high",
                    "implementation_hint": "Add pre-flight auth check, refresh token if expired"
                })
            elif error_type == 'resource_missing':
                suggestions.append({
                    "title": "Add resource existence check",
                    "description": "Verify resource exists before operating on it",
                    "target_cluster": cluster['cluster_id'],
                    "priority": "medium",
                    "implementation_hint": f"Add precondition check before step {step}: verify resource exists"
                })
            else:
                suggestions.append({
                    "title": "Add error handling and logging",
                    "description": "Improve error handling for this failure mode",
                    "target_cluster": cluster['cluster_id'],
                    "priority": "medium",
                    "implementation_hint": f"Add try-catch around step {step}, log detailed context"
                })

        return suggestions

    def _create_repair_plan(self, skill_name: str,
                           cluster_analysis: List[Dict],
                           suggestions: List[Dict]) -> Dict[str, Any]:
        """
        Create an executable repair plan.

        Returns:
            Repair plan with:
            - Prioritized actions
            - Implementation steps
            - Success criteria
            - Rollback plan
        """
        if not suggestions:
            return None

        # Sort suggestions by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_suggestions = sorted(
            suggestions,
            key=lambda x: priority_order.get(x.get('priority', 'low'), 2)
        )

        # Build repair plan
        repair_plan = {
            "skill_name": skill_name,
            "generated_at": datetime.now().isoformat(),
            "total_suggestions": len(sorted_suggestions),
            "actions": [],
            "implementation_order": [],
            "success_criteria": [],
            "rollback_available": True
        }

        for i, suggestion in enumerate(sorted_suggestions):
            action = {
                "action_id": f"action_{i+1}",
                "title": suggestion.get('title', 'Unknown action'),
                "description": suggestion.get('description', ''),
                "priority": suggestion.get('priority', 'medium'),
                "target_cluster": suggestion.get('target_cluster', ''),
                "implementation_hint": suggestion.get('implementation_hint', ''),
                "estimated_impact": self._estimate_impact(suggestion, cluster_analysis)
            }
            repair_plan["actions"].append(action)
            repair_plan["implementation_order"].append(action["action_id"])

            # Add success criterion for this action
            if action["target_cluster"]:
                repair_plan["success_criteria"].append(
                    f"Reduce failures in '{action['target_cluster']}' by 50%"
                )

        # Overall success criterion
        repair_plan["success_criteria"].append(
            f"Improve overall success rate to >80%"
        )

        return repair_plan

    def _estimate_impact(self, suggestion: Dict,
                        cluster_analysis: List[Dict]) -> str:
        """Estimate impact of a suggestion."""
        target = suggestion.get('target_cluster', '')
        priority = suggestion.get('priority', 'medium')

        # Find target cluster
        target_cluster = None
        for c in cluster_analysis:
            if c['cluster_id'] == target:
                target_cluster = c
                break

        if not target_cluster:
            return "Unknown"

        failure_pct = target_cluster.get('failure_percentage', 0)

        if priority == 'high' and failure_pct > 30:
            return f"High - addresses {failure_pct:.0f}% of failures"
        elif priority == 'high' or failure_pct > 20:
            return f"Medium - addresses {failure_pct:.0f}% of failures"
        else:
            return f"Low - addresses {failure_pct:.0f}% of failures"

    def should_optimize(self, skill_name: str) -> bool:
        """
        Check if a skill should be optimized.

        Args:
            skill_name: Name of the skill

        Returns:
            True if optimization is recommended
        """
        stats = self.get_skill_stats(skill_name)
        return stats.get('needs_optimization', False)

    def optimize_skill(self, skill_name: str) -> Dict[str, Any]:
        """
        Optimize a skill using AI based on execution history.

        This method:
        1. Analyzes failure patterns with clustering
        2. Generates AI-powered optimization suggestions
        3. Creates executable repair plans
        4. Applies optimizations to create new skill version

        Args:
            skill_name: Name of the skill to optimize

        Returns:
            Comprehensive optimization result including:
            - Analysis results
            - Generated suggestions
            - Repair plan
            - Optimized skill (if successful)
        """
        # Get stats
        stats = self.get_skill_stats(skill_name)

        if not stats.get('needs_optimization', False):
            return {
                "success": False,
                "reason": "Skill does not need optimization",
                "stats": stats
            }

        # Get current skill
        skill = self._get_skill(skill_name)
        if not skill:
            return {
                "success": False,
                "reason": f"Skill '{skill_name}' not found"
            }

        # Step 1: Deep failure pattern analysis
        logger.info(f"Starting deep failure analysis for {skill_name}")
        failure_analysis = self.analyze_failure_patterns(skill_name)

        if not failure_analysis.get('analysis_success'):
            # Fallback to simple analysis
            logger.warning("Deep analysis failed, using fallback")
            failure_records = [r for r in self._execution_records
                             if r['skill_name'] == skill_name and not r['success']]
            return self._simple_optimize(skill, stats, failure_records)

        # Step 2: Use AI to optimize with full context
        logger.info(f"Optimizing skill with {len(failure_analysis.get('suggestions', []))} suggestions")
        optimized = self._ai_optimize_with_analysis(
            skill, stats, failure_analysis
        )

        if optimized:
            # Save as new version
            version_result = self._save_skill_version(skill_name, optimized)

            return {
                "success": True,
                "analysis": failure_analysis,
                "original_skill": skill,
                "optimized_skill": optimized,
                "version": version_result,
                "stats": stats,
                "optimization_summary": {
                    "clusters_identified": len(failure_analysis.get('failure_clusters', [])),
                    "suggestions_generated": len(failure_analysis.get('suggestions', [])),
                    "repair_plan_actions": len(failure_analysis.get('repair_plan', {}).get('actions', []))
                }
            }

        return {
            "success": False,
            "reason": "AI optimization failed",
            "analysis": failure_analysis
        }

    def _simple_optimize(self, skill: Dict, stats: Dict,
                        failure_records: List[Dict]) -> Dict[str, Any]:
        """Fallback simple optimization without deep analysis."""
        optimized = self._ai_optimize(skill, stats, failure_records)

        if optimized:
            version_result = self._save_skill_version(skill['name'], optimized)
            return {
                "success": True,
                "original_skill": skill,
                "optimized_skill": optimized,
                "version": version_result,
                "stats": stats
            }

        return {"success": False, "reason": "AI optimization failed"}

    def _get_skill(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get skill by name from SKILL.md."""
        if not self._memory_manager:
            return None

        result = self._memory_manager._skill_store.read()
        for entry in result.get('entries', []):
            if skill_name.lower() in entry.lower():
                return self._parse_skill_entry(entry)

        return None

    def _parse_skill_entry(self, entry: str) -> Dict[str, Any]:
        """Parse raw skill entry."""
        lines = entry.strip().split('\n')
        skill = {'name': '', 'description': '', 'triggers': '', 'steps': '', 'examples': ''}

        for line in lines:
            line = line.strip()
            if line.startswith('[SKILL]'):
                skill['name'] = line[7:].strip()
            elif line.startswith('Description:'):
                skill['description'] = line[12:].strip()
            elif line.startswith('Triggers:'):
                skill['triggers'] = line[9:].strip()
            elif line.startswith('Steps:'):
                skill['steps'] = line[6:].strip()
            elif line.startswith('Examples:'):
                skill['examples'] = line[9:].strip()

        return skill

    def _ai_optimize(self, skill: Dict, stats: Dict,
                    failures: List[Dict]) -> Optional[Dict]:
        """
        Use AI to optimize skill based on execution data.

        Args:
            skill: Current skill definition
            stats: Execution statistics
            failures: List of failure records

        Returns:
            Optimized skill or None
        """
        # Build prompt
        prompt = f"""Analyze this skill and optimize it based on execution failures.

Current Skill:
{json.dumps(skill, indent=2)}

Execution Statistics:
- Total executions: {stats['total_executions']}
- Success rate: {stats['success_rate']:.0%}
- Common failure step: {stats['common_failure_step']}
- Common error: {stats['common_error']}

Failure Records:
{json.dumps(failures[:5], indent=2)}

Optimize the skill by:
1. Adding error handling for common failures
2. Clarifying ambiguous steps
3. Adding preconditions/checks before critical steps
4. Making steps more specific and actionable

Return optimized skill as JSON with same structure."""

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

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result["choices"][0]["message"]["content"]

                # Clean and parse
                content = content.strip()
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                content = content.strip()

                optimized = json.loads(content)

                # Ensure required fields
                if 'name' not in optimized:
                    optimized['name'] = skill['name'] + " v2"

                logger.info(f"AI optimization complete for {skill['name']}")
                return optimized

        except Exception as e:
            logger.error(f"AI optimization failed: {e}")
            return None

    def _ai_optimize_with_analysis(self, skill: Dict, stats: Dict,
                                   failure_analysis: Dict) -> Optional[Dict]:
        """
        Use AI to optimize skill with full failure analysis context.

        Args:
            skill: Current skill definition
            stats: Execution statistics
            failure_analysis: Comprehensive failure analysis result

        Returns:
            Optimized skill or None
        """
        clusters = failure_analysis.get('failure_clusters', [])
        suggestions = failure_analysis.get('suggestions', [])
        repair_plan = failure_analysis.get('repair_plan', {})

        # Build detailed cluster summary
        cluster_summary = "\n".join([
            f"- {c['cluster_id']}: {c['failure_count']} failures ({c['failure_percentage']}%), "
            f"step {c.get('common_step', 'N/A')}, severity: {c['severity']}\n"
            f"  Pattern: {c.get('common_error_pattern', 'N/A')[:80]}\n"
            f"  Examples: {c.get('representative_errors', [])[:2]}"
            for c in clusters[:5]
        ])

        # Build suggestions summary
        suggestions_summary = "\n".join([
            f"- [{s.get('priority', 'medium').upper()}] {s.get('title', 'Unknown')}: "
            f"{s.get('implementation_hint', '')}"
            for s in suggestions[:5]
        ])

        # Build repair plan summary
        actions_summary = ""
        if repair_plan:
            actions = repair_plan.get('actions', [])
            actions_summary = "\n".join([
                f"- {a.get('action_id')}: {a.get('title')} "
                f"(impact: {a.get('estimated_impact', 'unknown')})"
                for a in actions[:5]
            ])

        prompt = f"""Analyze this skill and create an optimized version based on comprehensive failure analysis.

**Current Skill**:
{json.dumps(skill, indent=2)}

**Execution Statistics**:
- Total executions: {stats['total_executions']}
- Success rate: {stats['success_rate']:.0%}
- Needs optimization: {stats.get('needs_optimization', False)}

**Failure Pattern Analysis**:
{cluster_summary}

**AI-Generated Suggestions**:
{suggestions_summary}

**Recommended Repair Plan**:
{actions_summary}

**Optimization Tasks**:
1. Address the highest priority failure clusters first
2. Implement the suggested fixes (retry logic, error handling, preconditions)
3. Make steps more specific and actionable
4. Add explicit error handling for identified failure modes
5. Preserve the skill's original intent while improving robustness

Return optimized skill as JSON with this structure:
{{
    "name": "Original Skill Name v2",
    "description": "Updated description reflecting improvements",
    "triggers": "Refined triggers",
    "steps": "Improved steps with error handling",
    "examples": "Updated examples"
}}

Focus on practical, implementable changes that directly address the identified failure patterns."""

        request_data = {
            "model": self._api_config["model"],
            "messages": [
                {"role": "system", "content": "Output valid JSON only. Focus on practical improvements."},
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

        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result["choices"][0]["message"]["content"]

                # Clean and parse
                content = content.strip()
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                content = content.strip()

                optimized = json.loads(content)

                # Ensure required fields
                if 'name' not in optimized:
                    optimized['name'] = f"{skill.get('name', 'Skill')} v2"

                logger.info(f"AI optimization with analysis complete for {skill.get('name')}")
                return optimized

        except Exception as e:
            logger.error(f"AI optimization with analysis failed: {e}")
            return None

    def _save_skill_version(self, skill_name: str, optimized: Dict) -> Dict[str, Any]:
        """
        Save optimized skill as new version.

        Args:
            skill_name: Original skill name
            optimized: Optimized skill definition

        Returns:
            Save result
        """
        # Add version suffix if not present
        if 'v2' not in optimized.get('name', ''):
            optimized['name'] = f"{skill_name} v2"

        # Format for storage
        skill_content = f"""[SKILL] {optimized['name']}
Description: {optimized.get('description', 'Optimized version')}
Triggers: {optimized.get('triggers', 'N/A')}
Steps: {optimized.get('steps', 'N/A')}
Examples: {optimized.get('examples', 'N/A')}
Note: Auto-optimized based on execution analysis"""

        if self._memory_manager:
            result = self._memory_manager.add_skill(skill_content)
            return {
                "success": result,
                "skill_name": optimized['name'],
                "content": skill_content
            }

        return {"success": False, "error": "No memory manager"}

    def get_all_stats(self) -> Dict[str, Any]:
        """Get stats for all skills."""
        skill_names = set(r['skill_name'] for r in self._execution_records)

        return {
            "total_skills_tracked": len(skill_names),
            "total_executions": len(self._execution_records),
            "skills": {name: self.get_skill_stats(name) for name in skill_names}
        }

    def get_optimization_candidates(self) -> List[Dict[str, Any]]:
        """Get list of skills that need optimization."""
        candidates = []
        skill_names = set(r['skill_name'] for r in self._execution_records)

        for name in skill_names:
            stats = self.get_skill_stats(name)
            if stats.get('needs_optimization', False):
                candidates.append({
                    "skill_name": name,
                    "stats": stats,
                    "recommendation": "Optimize skill based on failure analysis"
                })

        return candidates
