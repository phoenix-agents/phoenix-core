#!/usr/bin/env python3
"""
Memory Manager - Orchestrates memory storage and learning loop

Combines:
1. MemoryStore (MEMORY.md / USER.md) - curated memory
2. SessionStore (SQLite + FTS5) - conversation history
3. Learning loop triggers - iteration counting for skill creation
4. AutomaticLearner - auto analysis and pattern extraction
"""

import json
import logging
import threading
from typing import Dict, Any, List, Optional, Callable
from memory_store import MemoryStore, MEMORY_TOOL_SCHEMA, memory_tool
from session_store import SessionStore, SESSION_STORE_SCHEMA, session_store_tool
from skill_store import SkillStore, SKILL_TOOL_SCHEMA, skill_tool
from automatic_learner import AutomaticLearner, get_learner
from background_review import BackgroundReviewAgent
from skill_activation import SkillActivator
from task_evaluation import TaskEvaluator, TaskOutcome, TaskEvaluation
from skill_extractor import SkillExtractor
from skill_executor import SkillExecutor
from skill_risk_assessor import RiskAssessor
from skill_optimizer import SkillOptimizer
from auto_optimizer import AutoOptimizer
from skill_evolution import SkillEvolution, get_skill_evolution
from reflection_engine import ReflectionEngine, get_reflection_engine
from knowledge_graph import KnowledgeGraph, get_knowledge_graph, share_learning
from skill_ab_test import SkillABTest, get_ab_test, record_skill_execution
from evolution_analyzer import EvolutionTrendAnalyzer, generate_trend_report
from skills_guard import SkillsGuard, get_guard

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Orchestrates memory storage and learning loop.

    Usage in agent loop:
        self._memory_manager = MemoryManager()
        self._memory_manager.load()  # Load memory at session start

        # Pre-turn: get memory snapshot for system prompt
        memory_context = self._memory_manager.build_memory_context()

        # Post-turn: sync the conversation
        self._memory_manager.sync_turn(user_msg, assistant_msg)

        # Handle tool calls
        if tool_name == "memory":
            result = self._memory_manager.handle_tool_call(args)
    """

    def __init__(self):
        self._memory_store = MemoryStore()
        self._skill_store = SkillStore()
        self._session_store = SessionStore()
        self._session_id: Optional[str] = None

        # Learning components
        self._automatic_learner = AutomaticLearner(memory_manager=self)
        self._background_review = BackgroundReviewAgent(memory_manager=self)

        # Skill system
        self._skill_activator = SkillActivator(memory_manager=self)
        self._task_evaluator = TaskEvaluator(memory_manager=self)
        self._skill_extractor = SkillExtractor(memory_manager=self)
        self._skill_executor = SkillExecutor(memory_manager=self)
        self._skill_optimizer = SkillOptimizer(memory_manager=self)
        self._auto_optimizer = AutoOptimizer(memory_manager=self)
        self._skills_guard = SkillsGuard()

        # Phase 2: Self-evolution components
        self._skill_evolution = SkillEvolution(memory_manager=self)
        self._reflection_engine = ReflectionEngine(memory_manager=self)
        self._knowledge_graph = KnowledgeGraph()

        # Phase 3: Analytics and A/B testing (新添加)
        self._ab_test = SkillABTest()
        self._trend_analyzer = EvolutionTrendAnalyzer()

        # Learning loop counters
        self._iters_since_learning = 0
        self._learning_threshold = 10  # Trigger after 10 tool iterations

        # Auto-extraction setting
        self._auto_extract_skills = True  # Auto-extract when evaluation passes

        # Reflection trigger (every 100 iterations)
        self._iters_since_reflection = 0
        self._reflection_threshold = 100

        # A/B test tracking (Phase 3)
        self._ab_test_executions = 0

        # Callbacks for learning triggers
        self._on_learning_trigger: Optional[Callable] = None

    def load(self, session_id: str = None):
        """Load memory and initialize session store."""
        self._memory_store.load_from_disk()
        self._skill_store.load_from_disk()
        self._skill_activator.load_skills()  # Load skills for activation
        self._session_id = session_id

        if session_id:
            self._session_store.create_session(session_id)

        logger.info(f"Memory manager loaded for session {session_id}")

    def build_memory_context(self) -> str:
        """
        Build memory context block for system prompt injection.

        Returns fenced block that won't be treated as user input.
        """
        snapshot = self._memory_store.get_system_prompt_snapshot()
        skill_snapshot = self._skill_store.get_system_prompt_snapshot()
        parts = []

        if snapshot.get("memory"):
            parts.append(snapshot["memory"])
        if snapshot.get("user"):
            parts.append(snapshot["user"])
        if skill_snapshot.get("skills"):
            parts.append(skill_snapshot["skills"])

        if not parts:
            return ""

        content = "\n\n".join(parts)

        return (
            "<memory-context>\n"
            "[System note: The following is recalled memory context, "
            "NOT new user input. Treat as informational background data.]\n\n"
            f"{content}\n"
            "</memory-context>"
        )

    def build_skill_context(self, user_content: str, threshold: float = 0.5) -> str:
        """
        Build active skill context for system prompt injection.

        Args:
            user_content: Current user message
            threshold: Minimum relevance score to activate skill

        Returns:
            Formatted skill context or empty string if no skill matches
        """
        skill = self._skill_activator.get_active_skill(user_content, threshold=threshold)

        if not skill:
            return ""

        return self._skill_activator.format_skill_context(skill)

    def sync_turn(self, user_content: str, assistant_content: str,
                  tool_iterations: int = 0):
        """
        Sync a completed turn to memory.

        Args:
            user_content: The user's message
            assistant_content: The assistant's response
            tool_iterations: Number of tool calls in this turn
        """
        # Increment iteration counter
        self._iters_since_learning += tool_iterations
        self._iters_since_reflection += tool_iterations

        # Record interaction for automatic learning
        self._automatic_learner.record_interaction(
            user_content, assistant_content, tool_iterations
        )

        # ===== Task Evaluation Integration (Phoenix 6-stage loop) =====
        # Auto-evaluate every turn for continuous learning
        self._evaluate_and_extract(user_content, assistant_content, tool_iterations)

        # Check if we should trigger learning (legacy threshold-based)
        if self._iters_since_learning >= self._learning_threshold:
            self._trigger_learning(user_content, assistant_content)
            self._iters_since_learning = 0

        # Check if we should trigger reflection (Phase 2: deep reflection)
        if self._iters_since_reflection >= self._reflection_threshold:
            self._trigger_reflection()
            self._iters_since_reflection = 0

        # Store in session database
        if self._session_id:
            self._session_store.append_message(
                self._session_id,
                role="user",
                content=user_content
            )
            self._session_store.append_message(
                self._session_id,
                role="assistant",
                content=assistant_content
            )

    def _trigger_reflection(self):
        """Trigger deep reflection (Phase 2)."""
        logger.info("Triggering deep reflection...")

        try:
            # Run reflection analysis
            insights = self._reflection_engine.reflect(time_range="24h")

            if insights.get('success'):
                logger.info(f"Reflection complete: {insights.get('sessions_analyzed')} sessions analyzed")

                # Trigger skill evolution for low-performing skills
                for recommendation in insights.get('recommendations', []):
                    if recommendation.get('priority') == 'high':
                        logger.info(f"High priority recommendation: {recommendation.get('action')}")

                # Share insights across bots via knowledge graph
                if insights.get('insights'):
                    self._share_insights_via_graph(insights['insights'])
            else:
                logger.info(f"Reflection skipped: {insights.get('reason', 'unknown')}")
        except Exception as e:
            logger.error(f"Reflection failed: {e}")

    def _share_insights_via_graph(self, insights: Dict[str, Any]):
        """Share insights across bots via knowledge graph."""
        # Extract key insight
        insight_text = f"""
Reflection Insights:
- Success Rate: {insights.get('statistics', {}).get('success_rate', 0):.0%}
- Sessions Analyzed: {insights.get('statistics', {}).get('total_sessions', 0)}
- Failure Patterns: {len(insights.get('failure_patterns', []))}
- Success Patterns: {len(insights.get('success_patterns', []))}
"""

        # Share from "system" to all bots
        all_bots = ['编导', '剪辑', '美工', '场控', '客服', '运营', '渠道']
        for bot in all_bots[:3]:  # Share to first 3 bots as demo
            try:
                share_learning(
                    from_bot='system',
                    to_bots=[bot],
                    knowledge=insight_text,
                    knowledge_type='insight'
                )
            except Exception as e:
                logger.warning(f"Failed to share to {bot}: {e}")

    # ========== Phase 3: A/B Testing and Analytics ==========

    def start_ab_test(self, skill_name: str, versions: List[str]) -> Dict[str, Any]:
        """Start A/B test for a skill."""
        return self._ab_test.start_test(skill_name, versions)

    def assign_skill_version(self, skill_name: str, user_id: str = None) -> Optional[str]:
        """Assign skill version via A/B test."""
        version = self._ab_test.assign_version(skill_name, user_id)
        if version:
            self._ab_test_executions += 1
        return version

    def record_skill_result(
        self,
        skill_name: str,
        version: str,
        success: bool,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Record skill execution result for A/B test."""
        result = self._ab_test.record_execution(skill_name, version, success, metadata)

        # Auto-end test if winner found
        if result.get('success'):
            test_results = self._ab_test.get_results(skill_name)
            if test_results and test_results.get('winner'):
                logger.info(f"A/B test winner: {test_results['winner']['version']}")

        return result

    def get_ab_test_results(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get A/B test results for a skill."""
        return self._ab_test.get_results(skill_name)

    def generate_trend_report(self, days: int = 7) -> str:
        """Generate evolution trend report."""
        return self._trend_analyzer.generate_report(days)

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        return {
            'learning': {
                'iterations_since_learning': self._iters_since_learning,
                'threshold': self._learning_threshold,
                'auto_extract_enabled': self._auto_extract_skills
            },
            'reflection': {
                'iterations_since_reflection': self._iters_since_reflection,
                'threshold': self._reflection_threshold
            },
            'ab_testing': {
                'active_tests': len([t for t in self._ab_test.list_tests() if t['is_active']]),
                'total_executions': self._ab_test_executions
            },
            'knowledge_graph': self._knowledge_graph.get_graph_stats()
        }

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Route a memory tool call to the correct handler."""
        if tool_name == "memory":
            action = args.get("action")
            target = args.get("target", "memory")

            if not action:
                return json.dumps({"success": False, "error": "Missing 'action'"})

            return memory_tool(
                action=action,
                target=target,
                store=self._memory_store,
                **{k: v for k, v in args.items() if k not in ["action", "target"]}
            )

        elif tool_name == "skill_manage":
            action = args.get("action")

            if not action:
                return json.dumps({"success": False, "error": "Missing 'action'"})

            return skill_tool(
                action=action,
                store=self._skill_store,
                **{k: v for k, v in args.items() if k != "action"}
            )

        elif tool_name == "session_store":
            action = args.get("action")

            if not action:
                return json.dumps({"success": False, "error": "Missing 'action'"})

            return session_store_tool(
                action=action,
                store=self._session_store,
                **{k: v for k, v in args.items() if k != "action"}
            )

        else:
            return json.dumps({"success": False, "error": f"Unknown tool: {tool_name}"})

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return tool schemas for the agent."""
        return [MEMORY_TOOL_SCHEMA, SKILL_TOOL_SCHEMA, SESSION_STORE_SCHEMA]

    def _trigger_learning(self, user_content: str, assistant_content: str):
        """
        Trigger the learning loop.

        This is called when the iteration threshold is exceeded.
        Spawns background review agent for skill creation.
        """
        logger.info(f"Learning trigger fired after {self._iters_since_learning} iterations")

        # Spawn background review agent
        self._spawn_background_review(user_content, assistant_content)

        # Also trigger callback if set
        if self._on_learning_trigger:
            try:
                self._on_learning_trigger(user_content, assistant_content)
            except Exception as e:
                logger.error(f"Learning trigger callback failed: {e}")

    def _spawn_background_review(self, user_content: str, assistant_content: str):
        """
        Spawn a background review agent to analyze conversation and create skills.

        Args:
            user_content: The user's message
            assistant_content: The assistant's response
        """
        # Get conversation buffer from automatic learner if available
        conversation_buffer = None
        if hasattr(self._automatic_learner, '_conversation_buffer'):
            conversation_buffer = self._automatic_learner._conversation_buffer.copy()

        # Spawn background review
        self._background_review.spawn_review(
            user_content=user_content,
            assistant_content=assistant_content,
            conversation_buffer=conversation_buffer
        )
        logger.info("Background review agent spawned")

    def _evaluate_and_extract(self, user_content: str, assistant_content: str,
                               tool_iterations: int = 0):
        """
        Evaluate the current turn and auto-extract skills if worthwhile.

        This implements the Phoenix 6-stage learning loop:闭环:
        1. Execute task (the conversation turn)
        2. Evaluate outcome (4-dimension scoring)
        3. Value judgment (decide if worth preserving)
        4. Skill extraction (if passing threshold)
        5. Store in memory (write to SKILL.md)
        6. Apply in future (skill activation)

        Args:
            user_content: The user's message
            assistant_content: The assistant's response
            tool_iterations: Number of tool calls (indicates complexity)
        """
        # Skip if evaluation is disabled
        if not self._auto_extract_skills:
            return

        # Analyze the turn for task characteristics
        task_analysis = self._analyze_turn(user_content, assistant_content, tool_iterations)

        # Only evaluate if we detect a meaningful task
        if not task_analysis.get('is_task'):
            logger.debug("No meaningful task detected, skipping evaluation")
            return

        # Perform task evaluation
        evaluation = self._task_evaluator.evaluate_task(
            task_type=task_analysis['task_type'],
            steps_taken=task_analysis['steps'],
            outcome=task_analysis['outcome'],
            user_satisfaction=task_analysis['satisfaction'],
            time_taken_seconds=0,  # Could be measured if needed
            retries=task_analysis.get('retries', 0)
        )

        logger.info(f"Turn evaluation: {task_analysis['task_type']} -> "
                   f"score={evaluation.preservation_score:.2f}, "
                   f"preserve={evaluation.worth_preserving}")

        # Auto-extract skill if evaluation passes (threshold: 0.7)
        if evaluation.worth_preserving and evaluation.preservation_score >= 0.7:
            self._extract_and_store_skill(evaluation)
        elif evaluation.worth_preserving:
            # Store evaluation for later batch processing
            logger.info(f"Task worth preserving but score < 0.7, logging for review")

    def _analyze_turn(self, user_content: str, assistant_content: str,
                      tool_iterations: int) -> Dict[str, Any]:
        """
        Analyze a conversation turn to extract task characteristics.

        Args:
            user_content: User message
            assistant_content: Assistant response
            tool_iterations: Number of tool calls

        Returns:
            Task analysis dictionary
        """
        # Detect if this is a meaningful task (not just chat)
        is_task = False
        task_type = "general_conversation"
        steps = []
        outcome = TaskOutcome.SUCCESS
        satisfaction = 0.5
        retries = 0

        # Heuristic 1: Tool usage indicates task complexity
        if tool_iterations >= 2:
            is_task = True
            task_type = "tool_assisted_task"

        # Heuristic 2: Check for task-related keywords in user content
        task_keywords = [
            "create", "setup", "configure", "fix", "debug", "analyze",
            "migrate", "deploy", "build", "generate", "transform",
            "convert", "extract", "process", "implement"
        ]

        user_lower = user_content.lower()
        matched_keywords = [kw for kw in task_keywords if kw in user_lower]

        if matched_keywords:
            is_task = True
            # Infer task type from keywords
            if "config" in user_lower or "setup" in user_lower:
                task_type = "configuration_task"
            elif "debug" in user_lower or "fix" in user_lower or "error" in user_lower:
                task_type = "debugging_task"
            elif "create" in user_lower or "build" in user_lower or "generate" in user_lower:
                task_type = "creation_task"
            elif "analyze" in user_lower or "process" in user_lower:
                task_type = "analysis_task"
            elif "migrate" in user_lower or "convert" in user_lower or "transform" in user_lower:
                task_type = "transformation_task"
            else:
                task_type = f"{matched_keywords[0]}_task"

        # Heuristic 3: Check for success/failure indicators in response
        assistant_lower = assistant_content.lower()
        if "failed" in assistant_lower or "error" in assistant_lower or "couldn't" in assistant_lower:
            outcome = TaskOutcome.FAILURE
            satisfaction = 0.3
        elif "partial" in assistant_lower or "partially" in assistant_lower or "limitation" in assistant_lower:
            outcome = TaskOutcome.PARTIAL
            satisfaction = 0.6
        elif "success" in assistant_lower or "completed" in assistant_lower or "done" in assistant_lower:
            outcome = TaskOutcome.SUCCESS
            satisfaction = 0.85

        # Heuristic 4: Extract steps from tool calls if available
        if tool_iterations > 0:
            # Infer steps from the fact that tools were called
            steps = self._infer_steps_from_turn(user_content, assistant_content, tool_iterations)

        # If no meaningful steps, create a summary step
        if not steps and is_task:
            steps = [f"Process user request: {user_content[:100]}"]

        return {
            "is_task": is_task,
            "task_type": task_type,
            "steps": steps,
            "outcome": outcome,
            "satisfaction": satisfaction,
            "retries": retries
        }

    def _infer_steps_from_turn(self, user_content: str, assistant_content: str,
                                tool_iterations: int) -> List[str]:
        """
        Infer task steps from conversation turn.

        Args:
            user_content: User message
            assistant_content: Assistant response
            tool_iterations: Number of tool calls

        Returns:
            List of inferred steps
        """
        steps = []

        # Step 1: Understand request
        steps.append(f"Analyze request: {user_content[:50]}...")

        # Step 2-N: Tool calls (if any)
        if tool_iterations > 0:
            steps.append(f"Execute {tool_iterations} tool call(s)")

        # Final step: Generate response
        if len(assistant_content) > 100:
            steps.append(f"Generate comprehensive response ({len(assistant_content)} chars)")
        else:
            steps.append("Generate response")

        return steps

    def _extract_and_store_skill(self, evaluation: 'TaskEvaluation'):
        """
        Extract and store a skill from a high-value evaluation.

        Args:
            evaluation: Task evaluation with worth_preserving=True
        """
        try:
            extraction_result = self._skill_extractor.extract_skill(evaluation.to_dict())

            if extraction_result.get('success'):
                skill_name = extraction_result.get('skill', {}).get('name', 'Unknown')
                logger.info(f"Skill auto-extracted and stored: {skill_name}")
            else:
                error = extraction_result.get('error', 'Unknown error')
                logger.warning(f"Skill extraction failed: {error}")

        except Exception as e:
            logger.error(f"Skill extraction and storage failed: {e}")

    def set_learning_trigger_callback(self, callback: Callable):
        """
        Set callback for learning triggers.

        The callback receives (user_content, assistant_content) and should
        handle the background review/spawn logic.
        """
        self._on_learning_trigger = callback

    def add_memory(self, content: str, target: str = "memory") -> bool:
        """Convenience method to add a memory entry."""
        result = self._memory_store.add(target, content)
        return result.get("success", False)

    def add_skill(self, content: str) -> bool:
        """Convenience method to add a skill entry."""
        result = self._skill_store.add(content)
        return result.get("success", False)

    def search_skills(self, query: str, limit: int = 10) -> Dict:
        """Search skills by keyword."""
        return self._skill_store.search(query, limit)

    def recommend_skills(self, user_content: str, threshold: float = 0.3) -> List:
        """Recommend skills based on user input."""
        return self._skill_activator.recommend_skills(user_content, threshold=threshold)

    def get_active_skill(self, user_content: str, threshold: float = 0.5) -> Optional[Dict]:
        """Get the active skill for user input."""
        return self._skill_activator.get_active_skill(user_content, threshold=threshold)

    def get_skill_activator_status(self) -> Dict[str, Any]:
        """Get skill activator status."""
        return self._skill_activator.get_status()

    def evaluate_task(
        self,
        task_type: str,
        steps_taken: List[str],
        outcome: str = "success",
        user_satisfaction: float = 0.5,
        time_taken: float = 0,
        retries: int = 0,
        auto_extract: bool = None
    ) -> Dict[str, Any]:
        """
        Evaluate a completed task for skill preservation.

        Args:
            task_type: Type of task (e.g., "memory_configuration")
            steps_taken: List of steps that were executed
            outcome: "success", "partial", or "failure"
            user_satisfaction: 0.0 - 1.0
            time_taken: Seconds taken
            retries: Number of retries
            auto_extract: Override auto-extraction setting

        Returns:
            Evaluation result dictionary with skill extraction info
        """
        outcome_enum = TaskOutcome[outcome.upper()]
        evaluation = self._task_evaluator.evaluate_task(
            task_type=task_type,
            steps_taken=steps_taken,
            outcome=outcome_enum,
            user_satisfaction=user_satisfaction,
            time_taken_seconds=time_taken,
            retries=retries
        )

        result = evaluation.to_dict()

        # Auto-extract skill if evaluation passes
        should_extract = (
            self._auto_extract_skills if auto_extract is None
            else auto_extract
        )

        if should_extract and evaluation.worth_preserving:
            extraction_result = self._skill_extractor.extract_skill(evaluation.to_dict())
            result['skill_extraction'] = extraction_result

        return result

    def get_evaluation_summary(self) -> Dict[str, Any]:
        """Get task evaluation summary."""
        return self._task_evaluator.get_evaluation_summary()

    def get_skill_extractor_status(self) -> Dict[str, Any]:
        """Get skill extractor status."""
        return self._skill_extractor.get_status()

    def get_skill_executor_status(self) -> Dict[str, Any]:
        """Get skill executor status."""
        return self._skill_executor.get_status()

    def execute_skill(self, skill_name: str = None, user_input: str = None,
                      context: Dict[str, Any] = None, sandbox: bool = False) -> Dict[str, Any]:
        """
        Execute a skill workflow.

        Args:
            skill_name: Name of skill to execute (optional if user_input provided)
            user_input: User input to match skill against (optional if skill_name provided)
            context: Execution context variables
            sandbox: If True, simulate execution without side effects

        Returns:
            Execution result (or sandbox simulation result)
        """
        if user_input and not skill_name:
            # Find matching skill
            skill = self._skill_executor.find_matching_skill(user_input)
            if not skill:
                return {"success": False, "error": "No matching skill found"}
        elif skill_name:
            # Find skill by name
            skills = self._skill_store.read()
            skill = None
            for entry in skills.get('entries', []):
                if skill_name.lower() in entry.lower():
                    skill = self._parse_skill_entry(entry)
                    break
            if not skill:
                return {"success": False, "error": f"Skill '{skill_name}' not found"}
        else:
            return {"success": False, "error": "Provide skill_name or user_input"}

        return self._skill_executor.execute_skill(skill, context, sandbox=sandbox)

    def assess_skill_risk(self, skill_name: str = None, user_input: str = None) -> Dict[str, Any]:
        """
        Assess risk level of a skill without executing.

        Args:
            skill_name: Name of skill to assess
            user_input: User input to match skill against

        Returns:
            Risk assessment result
        """
        if user_input and not skill_name:
            skill = self._skill_executor.find_matching_skill(user_input)
            if not skill:
                return {"success": False, "error": "No matching skill found"}
        elif skill_name:
            skills = self._skill_store.read()
            skill = None
            for entry in skills.get('entries', []):
                if skill_name.lower() in entry.lower():
                    skill = self._parse_skill_entry(entry)
                    break
            if not skill:
                return {"success": False, "error": f"Skill '{skill_name}' not found"}
        else:
            return {"success": False, "error": "Provide skill_name or user_input"}

        return self._skill_executor._risk_assessor.assess_skill(skill)

    def _parse_skill_entry(self, entry: str) -> Dict[str, Any]:
        """Parse a raw skill entry into structured format."""
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

    def set_auto_extract(self, enabled: bool):
        """Enable or disable automatic skill extraction."""
        self._auto_extract_skills = enabled

    def record_skill_execution(self, skill_name: str, result: Dict[str, Any],
                               user_feedback: Dict[str, Any] = None):
        """Record a skill execution result for learning."""
        self._skill_optimizer.record_execution(skill_name, result, user_feedback)

    def get_skill_stats(self, skill_name: str) -> Dict[str, Any]:
        """Get execution statistics for a skill."""
        return self._skill_optimizer.get_skill_stats(skill_name)

    def should_optimize_skill(self, skill_name: str) -> bool:
        """Check if a skill needs optimization."""
        return self._skill_optimizer.should_optimize(skill_name)

    def optimize_skill(self, skill_name: str) -> Dict[str, Any]:
        """Optimize a skill based on execution history."""
        return self._skill_optimizer.optimize_skill(skill_name)

    def get_optimization_candidates(self) -> List[Dict[str, Any]]:
        """Get list of skills that need optimization."""
        return self._skill_optimizer.get_optimization_candidates()

    def get_all_execution_stats(self) -> Dict[str, Any]:
        """Get stats for all tracked skills."""
        return self._skill_optimizer.get_all_stats()

    # ========== Auto-Optimization Service ==========

    def start_auto_optimization(self, interval_minutes: int = 30):
        """
        Start automatic skill optimization background service.

        Args:
            interval_minutes: How often to scan for optimization candidates
        """
        self._auto_optimizer.start_background_service(interval_minutes=interval_minutes)
        logger.info(f"Auto-optimization started (interval: {interval_minutes}min)")

    def stop_auto_optimization(self, wait: bool = True):
        """Stop automatic skill optimization service."""
        self._auto_optimizer.stop_background_service(wait=wait)
        logger.info("Auto-optimization stopped")

    def scan_and_optimize(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Manually trigger optimization scan.

        Args:
            dry_run: If True, only report candidates without optimizing

        Returns:
            Scan and optimization results
        """
        return self._auto_optimizer.scan_and_optimize(dry_run=dry_run)

    def get_auto_optimizer_status(self) -> Dict[str, Any]:
        """Get auto-optimization service status."""
        return self._auto_optimizer.get_status()

    def set_auto_optimize_threshold(self, threshold: float):
        """
        Set success rate threshold for auto-optimization.

        Args:
            threshold: Success rate below which triggers auto-optimize (0.0-1.0)
        """
        self._auto_optimizer.set_optimization_threshold(threshold)

    def get_optimization_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent optimization history."""
        return self._auto_optimizer.get_optimization_history(limit=limit)

    def optimize_now(self, skill_name: str = None) -> Dict[str, Any]:
        """
        Manually trigger optimization for a specific skill or all candidates.

        Args:
            skill_name: Optional specific skill to optimize (None = all candidates)

        Returns:
            Optimization result(s)
        """
        return self._auto_optimizer.optimize_now(skill_name=skill_name)

    def get_optimization_candidates_preview(self) -> List[Dict[str, Any]]:
        """Get list of candidates that would be optimized."""
        return self._auto_optimizer.get_candidates_preview()

    # ========== Security (Skills Guard) ==========

    def set_user_role(self, role: str):
        """
        Set the current user's role for RBAC.

        Args:
            role: Role name (admin, developer, viewer)
        """
        self._skills_guard.set_current_role(role)

    def check_skill_execution(self, skill: Dict[str, Any],
                               risk_level: float = None) -> tuple[bool, str]:
        """
        Check if current user can execute a skill.

        Args:
            skill: Skill definition dictionary
            risk_level: Pre-calculated risk score

        Returns:
            (allowed, reason) tuple
        """
        return self._skills_guard.can_execute_skill(skill, risk_level=risk_level)

    def check_content_safety(self, content: str) -> tuple[bool, str]:
        """
        Check if content is safe to store in memory.

        Args:
            content: Content to validate

        Returns:
            (safe, reason) tuple
        """
        return self._skills_guard.check_content_safety(content)

    def requires_confirmation(self, skill: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Check if skill execution requires user confirmation.

        Args:
            skill: Skill definition dictionary

        Returns:
            (needs_confirmation, reasons) tuple
        """
        return self._skills_guard.requires_confirmation(skill)

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit log entries."""
        return self._skills_guard.get_audit_log(limit=limit)

    def get_skills_guard_status(self) -> Dict[str, Any]:
        """Get skills guard status."""
        return self._skills_guard.get_status()

    def search_sessions(self, query: str, limit: int = 10) -> List[Dict]:
        """Search past conversations."""
        return self._session_store.search(query, limit)

    def get_learner_status(self) -> Dict[str, Any]:
        """Get automatic learner status."""
        return self._automatic_learner.get_status()

    def get_background_review_status(self) -> Dict[str, Any]:
        """Get background review agent status."""
        return self._background_review.get_status()

    def end_session(self, input_tokens: int = 0, output_tokens: int = 0):
        """Mark the current session as ended."""
        if self._session_id:
            self._session_store.end_session(
                self._session_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

    def shutdown(self):
        """Clean up resources."""
        self._session_store.close()
        logger.info("Memory manager shutdown complete")


class LearningLoopMixin:
    """
    Mixin for adding Phoenix Core-style learning loop to an agent.

    Usage:
        class MyAgent(LearningLoopMixin, BaseAgent):
            def run_conversation(self, user_message, ...):
                # ... agent loop ...

                # Track iterations
                self._iters_since_skill += 1

                # After loop completes, check trigger
                self._check_learning_trigger(final_response)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._iters_since_skill = 0
        self._skill_nudge_interval = 10
        self._memory_manager: Optional[MemoryManager] = None

    def _check_learning_trigger(self, final_response: str):
        """Check if learning should trigger after a turn."""
        if (self._skill_nudge_interval > 0 and
            self._iters_since_skill >= self._skill_nudge_interval):

            self._spawn_learning_review(final_response)
            self._iters_since_skill = 0

    def _spawn_learning_review(self, response: str):
        """
        Spawn a background learning review.

        Override this to implement actual learning logic.
        Default implementation logs the trigger.
        """
        logger.info(f"Learning review triggered after {self._iters_since_skill} iterations")
        logger.info(f"Response summary: {response[:200]}...")

    def reset_learning_counter(self):
        """Reset the learning counter (called when a skill is used/created)."""
        self._iters_since_skill = 0
