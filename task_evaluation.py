#!/usr/bin/env python3
"""
Task Evaluation System - Phoenix Core-style Learning Assessment

This module evaluates completed tasks to determine if the process
is worth preserving as a skill. It implements Phoenix Core-style quality
assessment and value judgment.

Key Features:
1. Task completion detection
2. Quality assessment (reusability, complexity, effectiveness)
3. Value judgment (is this worth preserving?)
4. Skill extraction recommendation

Usage:
    evaluator = TaskEvaluator(memory_manager)

    # After task completes
    evaluation = evaluator.evaluate_task(
        task_type="memory_configuration",
        steps_taken=[...],
        result=success,
        user_satisfaction=0.8
    )

    if evaluation.worth_preserving:
        evaluator.extract_skill(task_type, steps_taken)
"""

import json
import logging
import urllib.request
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TaskOutcome(Enum):
    """Task outcome classification."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


class TaskEvaluator:
    """
    Evaluates completed tasks for skill preservation.

    Phoenix Core-style evaluation criteria:
    1. Reusability - Can this be applied to similar tasks?
    2. Complexity - Is this non-trivial (worth memorizing)?
    3. Effectiveness - Did it work well?
    4. Generality - Does it generalize beyond this specific case?
    """

    def __init__(self, memory_manager=None):
        self._memory_manager = memory_manager
        self._evaluation_history = []

        # Thresholds for skill preservation
        self._min_reusability = 0.6      # Must be reusable
        self._min_complexity = 0.3       # Must be non-trivial
        self._min_effectiveness = 0.7    # Must work well
        self._min_preservation_score = 0.5  # Overall threshold

    def evaluate_task(
        self,
        task_type: str,
        steps_taken: List[str],
        outcome: TaskOutcome,
        user_satisfaction: float = 0.5,
        time_taken_seconds: float = 0,
        retries: int = 0,
        context: Dict[str, Any] = None
    ) -> 'TaskEvaluation':
        """
        Evaluate a completed task for skill preservation.

        Args:
            task_type: Type/category of task (e.g., "memory_configuration")
            steps_taken: List of steps that were executed
            outcome: Task outcome (success/partial/failure)
            user_satisfaction: User satisfaction score (0.0 - 1.0)
            time_taken_seconds: Time taken to complete
            retries: Number of retries needed
            context: Additional context about the task

        Returns:
            TaskEvaluation object with scores and recommendation
        """
        evaluation = TaskEvaluation(
            task_type=task_type,
            steps_taken=steps_taken,
            outcome=outcome,
        )

        # Calculate individual scores
        evaluation.reusability = self._assess_reusability(task_type, steps_taken, context)
        evaluation.complexity = self._assess_complexity(steps_taken)
        evaluation.effectiveness = self._assess_effectiveness(outcome, user_satisfaction, retries)
        evaluation.generality = self._assess_generality(task_type, steps_taken)

        # Calculate overall preservation score
        evaluation.preservation_score = self._calculate_preservation_score(evaluation)

        # Determine if worth preserving
        evaluation.worth_preserving = self._should_preserve(evaluation)

        # Generate reasoning
        evaluation.reasoning = self._generate_reasoning(evaluation)

        # Log evaluation
        logger.info(f"Task evaluation: {task_type} -> score={evaluation.preservation_score:.2f}, "
                   f"preserve={evaluation.worth_preserving}")

        self._evaluation_history.append(evaluation)

        return evaluation

    def _assess_reusability(self, task_type: str, steps: List[str], context: Dict = None) -> float:
        """
        Assess how reusable this task pattern is.

        Criteria:
        - Is this a common task type?
        - Can the steps be applied to other situations?
        - Is it not too specific to this exact context?

        Returns: 0.0 - 1.0
        """
        score = 0.5  # Base score

        # Common task types are more reusable
        common_types = [
            "configuration", "setup", "troubleshooting", "debugging",
            "analysis", "transformation", "migration", "deployment"
        ]

        task_lower = task_type.lower()
        for common in common_types:
            if common in task_lower:
                score += 0.15
                break

        # More steps can indicate a reusable process
        if len(steps) >= 3:
            score += 0.1
        if len(steps) >= 5:
            score += 0.1

        # Check for reusable patterns in steps
        reusable_patterns = [
            "check", "verify", "configure", "setup", "initialize",
            "validate", "test", "deploy", "restart", "update"
        ]

        step_text = " ".join(steps).lower()
        pattern_matches = sum(1 for p in reusable_patterns if p in step_text)

        if pattern_matches >= 2:
            score += 0.15
        if pattern_matches >= 4:
            score += 0.1

        return min(1.0, max(0.0, score))

    def _assess_complexity(self, steps: List[str]) -> float:
        """
        Assess task complexity.

        Criteria:
        - Number of steps (more steps = more complex)
        - Step diversity (different types of actions)
        - Decision points (if/then branches)

        Returns: 0.0 - 1.0
        """
        score = 0.0

        # Base complexity from step count
        if len(steps) >= 2:
            score += 0.2
        if len(steps) >= 4:
            score += 0.2
        if len(steps) >= 6:
            score += 0.2

        # Check for decision points
        step_text = " ".join(steps).lower()
        decision_keywords = ["if", "then", "else", "when", "depending", "condition"]

        decisions = sum(1 for kw in decision_keywords if kw in step_text)
        if decisions >= 1:
            score += 0.15
        if decisions >= 2:
            score += 0.1

        # Check for diverse actions (unique verbs)
        action_verbs = [
            "start", "stop", "restart", "configure", "check", "verify",
            "create", "delete", "update", "read", "write", "send",
            "receive", "connect", "disconnect", "test", "validate"
        ]

        actions_found = sum(1 for v in action_verbs if v in step_text)
        if actions_found >= 3:
            score += 0.1
        if actions_found >= 5:
            score += 0.1

        return min(1.0, max(0.0, score))

    def _assess_effectiveness(
        self,
        outcome: TaskOutcome,
        user_satisfaction: float,
        retries: int
    ) -> float:
        """
        Assess how effective the solution was.

        Criteria:
        - Did it succeed?
        - Was the user satisfied?
        - Did it require many retries?

        Returns: 0.0 - 1.0
        """
        score = 0.0

        # Outcome weight (50%)
        if outcome == TaskOutcome.SUCCESS:
            score += 0.5
        elif outcome == TaskOutcome.PARTIAL:
            score += 0.25
        # Failure = 0

        # User satisfaction weight (30%)
        score += user_satisfaction * 0.3

        # Retries penalty (20%)
        if retries == 0:
            score += 0.2
        elif retries == 1:
            score += 0.1
        # Multiple retries = 0

        return min(1.0, max(0.0, score))

    def _assess_generality(self, task_type: str, steps: List[str]) -> float:
        """
        Assess how general/applicable this pattern is.

        Criteria:
        - Does it avoid overly specific references?
        - Can it apply to similar but different contexts?

        Returns: 0.0 - 1.0
        """
        score = 0.5  # Base score

        step_text = " ".join(steps).lower()

        # Penalize overly specific references
        specific_patterns = [
            r"port\s*4321",  # Specific port numbers
            r"v[0-9]+\.[0-9]+",  # Specific versions
            r"2026-04-09",  # Specific dates
            r"session-[a-z0-9]+",  # Specific session IDs
        ]

        specific_count = sum(1 for p in specific_patterns if re.search(p, step_text))

        if specific_count == 0:
            score += 0.3
        elif specific_count == 1:
            score += 0.15

        # Reward abstract/parameterized steps
        abstract_keywords = [
            "required", "appropriate", "relevant", "target",
            "configured", "specified", "given"
        ]

        abstract_count = sum(1 for kw in abstract_keywords if kw in step_text)
        if abstract_count >= 2:
            score += 0.15

        return min(1.0, max(0.0, score))

    def _calculate_preservation_score(self, evaluation: 'TaskEvaluation') -> float:
        """
        Calculate overall preservation score.

        Weighted average:
        - Reusability: 30%
        - Complexity: 20%
        - Effectiveness: 35%
        - Generality: 15%
        """
        return (
            evaluation.reusability * 0.30 +
            evaluation.complexity * 0.20 +
            evaluation.effectiveness * 0.35 +
            evaluation.generality * 0.15
        )

    def _should_preserve(self, evaluation: 'TaskEvaluation') -> bool:
        """
        Determine if this task is worth preserving as a skill.

        Criteria:
        - Overall score above threshold
        - Individual minimums met
        - Outcome was successful or partial
        """
        # Must meet overall threshold
        if evaluation.preservation_score < self._min_preservation_score:
            return False

        # Must meet minimum reusability
        if evaluation.reusability < self._min_reusability:
            return False

        # Must meet minimum effectiveness
        if evaluation.effectiveness < self._min_effectiveness:
            return False

        # Must have some complexity (not trivial)
        if evaluation.complexity < self._min_complexity:
            return False

        return True

    def _generate_reasoning(self, evaluation: 'TaskEvaluation') -> str:
        """Generate human-readable reasoning for the evaluation."""
        reasons = []

        if evaluation.reusability >= 0.7:
            reasons.append("Highly reusable pattern")
        elif evaluation.reusability < 0.5:
            reasons.append("Limited reusability")

        if evaluation.complexity >= 0.6:
            reasons.append("Non-trivial complexity")
        elif evaluation.complexity < 0.3:
            reasons.append("Relatively simple task")

        if evaluation.effectiveness >= 0.8:
            reasons.append("Highly effective solution")
        elif evaluation.effectiveness < 0.5:
            reasons.append("Effectiveness concerns")

        if evaluation.generality >= 0.7:
            reasons.append("Generalizes well")

        if evaluation.worth_preserving:
            verdict = "WORTH PRESERVING as skill"
        else:
            verdict = "NOT worth preserving"

        return f"{verdict} - Score: {evaluation.preservation_score:.2f} - " + "; ".join(reasons)

    def get_evaluation_summary(self) -> Dict[str, Any]:
        """Get summary of all evaluations."""
        if not self._evaluation_history:
            return {"total": 0, "preserved": 0, "rate": 0}

        preserved = sum(1 for e in self._evaluation_history if e.worth_preserving)

        return {
            "total": len(self._evaluation_history),
            "preserved": preserved,
            "rejected": len(self._evaluation_history) - preserved,
            "preservation_rate": preserved / len(self._evaluation_history),
            "average_score": sum(e.preservation_score for e in self._evaluation_history) / len(self._evaluation_history)
        }


class TaskEvaluation:
    """Result of task evaluation."""

    def __init__(
        self,
        task_type: str,
        steps_taken: List[str],
        outcome: TaskOutcome
    ):
        self.task_type = task_type
        self.steps_taken = steps_taken
        self.outcome = outcome

        # Scores (calculated by evaluator)
        self.reusability = 0.0
        self.complexity = 0.0
        self.effectiveness = 0.0
        self.generality = 0.0
        self.preservation_score = 0.0

        # Decision
        self.worth_preserving = False
        self.reasoning = ""

        # Metadata
        self.evaluated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert evaluation to dictionary."""
        return {
            "task_type": self.task_type,
            "steps_taken": self.steps_taken,
            "outcome": self.outcome.value,
            "scores": {
                "reusability": self.reusability,
                "complexity": self.complexity,
                "effectiveness": self.effectiveness,
                "generality": self.generality,
                "preservation_score": self.preservation_score,
            },
            "worth_preserving": self.worth_preserving,
            "reasoning": self.reasoning,
            "evaluated_at": self.evaluated_at,
        }
