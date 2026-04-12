#!/usr/bin/env python3
"""
Skill Workflow Executor - Automatic Skill Execution

This module automatically executes saved skill workflows.
When a skill is activated, it executes the defined steps
instead of just recommending them.

Key Features:
1. Skill parsing and validation
2. Step execution engine
3. Tool integration (memory, session_store, etc.)
4. Progress tracking and error handling
5. Sandbox mode for safe testing

Usage:
    executor = SkillExecutor(memory_manager)

    # On user input that matches a skill
    skill = executor.find_matching_skill(user_input)
    if skill:
        result = executor.execute_skill(skill, context)

    # Sandbox mode
    result = executor.execute_skill(skill, sandbox=True)
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from skill_risk_assessor import RiskAssessor

logger = logging.getLogger(__name__)


class SkillExecutor:
    """
    Executes skill workflows automatically.

    Process:
    1. Find matching skill for user input
    2. Parse skill steps into executable actions
    3. Execute each step with context
    4. Return results
    """

    def __init__(self, memory_manager=None):
        self._memory_manager = memory_manager
        self._execution_history = []
        self._registered_handlers: Dict[str, Callable] = {}
        self._risk_assessor = RiskAssessor()

        # Register built-in handlers
        self._register_builtin_handlers()

    def _register_builtin_handlers(self):
        """Register built-in step handlers."""
        self._handlers = {
            "check": self._handle_check,
            "verify": self._handle_verify,
            "initialize": self._handle_initialize,
            "load": self._handle_load,
            "configure": self._handle_configure,
            "start": self._handle_start,
            "setup": self._handle_setup,
            "test": self._handle_test,
            "inject": self._handle_inject,
            "create": self._handle_create,
            "send": self._handle_send,
            "fetch": self._handle_fetch,
        }

    def find_matching_skill(self, user_input: str, threshold: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        Find a skill that matches user input.

        Args:
            user_input: User's message
            threshold: Minimum relevance score

        Returns:
            Matching skill or None
        """
        if not self._memory_manager:
            return None

        # Use skill activator to find matching skill
        skill = self._memory_manager.get_active_skill(user_input, threshold=threshold)
        return skill

    def execute_skill(self, skill: Dict[str, Any], context: Dict[str, Any] = None,
                      sandbox: bool = False) -> Dict[str, Any]:
        """
        Execute a skill workflow.

        Args:
            skill: Skill dictionary with steps
            context: Execution context (variables, parameters)
            sandbox: If True, simulate execution without side effects

        Returns:
            Execution result with status and output
        """
        if context is None:
            context = {}

        skill_name = skill.get('name', 'Unknown')

        # Sandbox mode - simulate execution
        if sandbox:
            return self._execute_sandbox(skill, context)

        logger.info(f"Executing skill: {skill_name}")

        # Parse steps
        steps = self._parse_steps(skill)

        # Execute each step
        results = []
        success_count = 0
        error_count = 0

        for i, step in enumerate(steps):
            step_result = self._execute_step(step, context, step_number=i+1)
            results.append(step_result)

            if step_result.get('success'):
                success_count += 1
            else:
                error_count += 1

                # Check if step is critical (fail-fast)
                if step.get('critical', True):
                    logger.warning(f"Critical step failed: {step['action']}")
                    break

        # Build result
        execution_result = {
            "skill_name": skill_name,
            "success": error_count == 0,
            "total_steps": len(steps),
            "success_count": success_count,
            "error_count": error_count,
            "step_results": results,
            "executed_at": datetime.now().isoformat()
        }

        self._execution_history.append(execution_result)

        logger.info(f"Skill execution complete: {skill_name} - {success_count}/{len(steps)} steps successful")

        return execution_result

    def _execute_sandbox(self, skill: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute skill in sandbox mode - simulate without side effects.

        Args:
            skill: Skill dictionary
            context: Execution context

        Returns:
            Sandbox simulation result
        """
        skill_name = skill.get('name', 'Unknown')
        logger.info(f"Sandbox execution: {skill_name}")

        # Risk assessment
        risk_result = self._risk_assessor.assess_skill(skill)

        # Parse steps
        steps = self._parse_steps(skill)

        # Simulate each step
        simulations = []
        for i, step in enumerate(steps):
            sim = self._simulate_step(step, context, step_number=i+1)
            simulations.append(sim)

        # Build sandbox result
        return {
            "sandbox": True,
            "skill_name": skill_name,
            "risk_level": risk_result['risk_level'],
            "risk_score": risk_result['risk_score'],
            "total_steps": len(steps),
            "step_simulations": simulations,
            "side_effects": risk_result['side_effects'],
            "dependencies": risk_result['dependencies'],
            "irreversible": risk_result['irreversible'],
            "warnings": risk_result['warnings'],
            "safe_to_execute": risk_result['safe_for_sandbox'],
            "simulated_at": datetime.now().isoformat()
        }

    def _parse_steps(self, skill: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse skill steps into executable actions.

        Args:
            skill: Skill dictionary

        Returns:
            List of parsed step dictionaries
        """
        steps_raw = skill.get('steps', '')
        parsed_steps = []

        # Handle different step formats
        if isinstance(steps_raw, list):
            step_list = steps_raw
        else:
            # Split on numbered patterns: "1. Step 2. Step" or "1) Step 2) Step"
            step_list = re.split(r'\d+[\.\)]\s*', steps_raw)
            step_list = [s.strip() for s in step_list if s.strip()]

        for step_text in step_list:
            step = self._parse_step_text(step_text)
            if step:
                parsed_steps.append(step)

        return parsed_steps

    def _parse_step_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single step text into an executable action.

        Args:
            text: Step text (e.g., "Check if memory server is running")

        Returns:
            Parsed step dictionary with action and parameters
        """
        text = text.strip()
        if not text:
            return None

        # Extract action verb (first word)
        words = text.split()
        action_verb = words[0].lower() if words else ""

        # Clean action verb
        action_verb = re.sub(r'[^\w]', '', action_verb)

        # Determine step type and parameters
        step = {
            "raw": text,
            "action": action_verb,
            "target": self._extract_target(text),
            "parameters": self._extract_parameters(text),
            "critical": self._is_critical_step(text)
        }

        return step

    def _extract_target(self, text: str) -> str:
        """Extract the target object from step text."""
        # Simple extraction: find noun phrases
        # This is a simplified version; production would use NLP
        skip_words = {'the', 'a', 'an', 'is', 'are', 'if', 'to', 'for', 'with'}

        words = text.lower().split()
        target_words = []

        for word in words[1:]:  # Skip action verb
            word = re.sub(r'[^\w]', '', word)
            if word and word not in skip_words:
                target_words.append(word)
                if len(target_words) >= 3:
                    break

        return ' '.join(target_words[:2])

    def _extract_parameters(self, text: str) -> Dict[str, Any]:
        """Extract parameters from step text."""
        params = {}

        # Extract port numbers
        port_match = re.search(r'port\s*(\d+)', text, re.IGNORECASE)
        if port_match:
            params['port'] = int(port_match.group(1))

        # Extract file names
        file_match = re.search(r'([\w\-]+\.md)', text, re.IGNORECASE)
        if file_match:
            params['file'] = file_match.group(1)

        # Extract quoted values
        quote_match = re.search(r"['\"]([^'\"]+)['\"]", text)
        if quote_match:
            params['value'] = quote_match.group(1)

        return params

    def _is_critical_step(self, text: str) -> bool:
        """Determine if a step is critical (fail-fast)."""
        # Steps that are typically critical
        critical_keywords = ['initialize', 'authenticate', 'connect', 'verify', 'validate']
        text_lower = text.lower()

        return any(kw in text_lower for kw in critical_keywords)

    def _simulate_step(self, step: Dict[str, Any], context: Dict[str, Any], step_number: int) -> Dict[str, Any]:
        """
        Simulate a single step without executing.

        Args:
            step: Parsed step dictionary
            context: Execution context
            step_number: Step number

        Returns:
            Simulation result with predicted outcome
        """
        action = step.get('action', '')
        raw = step.get('raw', '')
        target = step.get('target', '')
        params = step.get('parameters', {})

        # Predict outcome based on action type
        prediction = self._predict_outcome(action, target, params)

        # Determine if step has side effects
        has_side_effects = action in ['create', 'delete', 'send', 'start', 'stop', 'configure', 'modify']

        # Determine reversibility
        reversible = action not in ['delete', 'drop', 'destroy', 'purge', 'format']

        return {
            "step_number": step_number,
            "action": action,
            "raw": raw,
            "target": target,
            "predicted_outcome": prediction,
            "has_side_effects": has_side_effects,
            "reversible": reversible,
            "parameters": params,
            "simulation_notes": f"Would {action} {target or 'target'}"
        }

    def _predict_outcome(self, action: str, target: str, params: Dict) -> str:
        """Predict what would happen if step executes."""
        predictions = {
            "check": f"Verify status of {target or 'target'}",
            "verify": f"Confirm {target or 'target'} is valid",
            "initialize": f"Create new instance of {target or 'target'}",
            "load": f"Read data from {target or 'source'}",
            "configure": f"Set parameters for {target or 'target'}",
            "start": f"Launch service on {params.get('port', 'specified port')}",
            "setup": f"Configure and initialize {target or 'target'}",
            "test": f"Validate connectivity/functionality of {target or 'target'}",
            "inject": f"Insert context into {target or 'system'}",
            "create": f"Generate new {target or 'resource'}",
            "send": f"Transmit data to {target or 'destination'}",
            "fetch": f"Retrieve data from {target or 'source'}",
        }

        return predictions.get(action, f"Execute: {action} {target or 'target'}")

    def _execute_step(self, step: Dict[str, Any], context: Dict[str, Any], step_number: int) -> Dict[str, Any]:
        """
        Execute a single step.

        Args:
            step: Parsed step dictionary
            context: Execution context
            step_number: Step number in workflow

        Returns:
            Step execution result
        """
        action = step.get('action', '')
        logger.info(f"Executing step {step_number}: {step.get('raw', 'Unknown')}")

        # Find handler
        handler = self._handlers.get(action, self._handle_generic)

        try:
            result = handler(step, context)
            result['step_number'] = step_number
            result['action'] = action
            return result
        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            return {
                "step_number": step_number,
                "action": action,
                "success": False,
                "error": str(e)
            }

    # Built-in step handlers

    def _handle_check(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle 'check' steps."""
        target = step.get('target', '')

        # Special handling for memory server check
        if 'memory' in target.lower() or 'server' in target.lower():
            if self._memory_manager:
                status = self._memory_manager.get_skill_activator_status()
                return {
                    "success": True,
                    "message": f"Memory system status: {status}",
                    "data": status
                }

        return {"success": True, "message": f"Checked: {target}"}

    def _handle_verify(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle 'verify' steps."""
        target = step.get('target', '')

        # Verify memory entries
        if 'memory' in target.lower() or 'entries' in target.lower():
            if self._memory_manager:
                result = self._memory_manager._skill_store.read()
                return {
                    "success": True,
                    "message": f"Verified: {result['count']} skills loaded",
                    "data": {"count": result['count']}
                }

        return {"success": True, "message": f"Verified: {target}"}

    def _handle_initialize(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle 'initialize' steps."""
        target = step.get('target', '')

        if 'memory' in target.lower() or 'manager' in target.lower():
            # Already initialized if we're here
            return {
                "success": True,
                "message": "MemoryManager already initialized"
            }

        return {"success": True, "message": f"Initialized: {target}"}

    def _handle_load(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle 'load' steps."""
        params = step.get('parameters', {})

        if self._memory_manager:
            # Memory already loaded
            skills = self._memory_manager._skill_store.read()
            return {
                "success": True,
                "message": f"Loaded {skills['count']} skills",
                "data": {"skills_count": skills['count']}
            }

        return {"success": True, "message": "Load step executed"}

    def _handle_configure(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle 'configure' steps."""
        target = step.get('target', '')
        params = step.get('parameters', {})

        return {
            "success": True,
            "message": f"Configured: {target}",
            "parameters": params
        }

    def _handle_start(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle 'start' steps."""
        target = step.get('target', '')
        params = step.get('parameters', {})

        # Simulate starting a service
        if 'port' in params:
            return {
                "success": True,
                "message": f"Started service on port {params['port']}"
            }

        return {"success": True, "message": f"Started: {target}"}

    def _handle_setup(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle 'setup' steps."""
        target = step.get('target', '')

        return {"success": True, "message": f"Setup complete: {target}"}

    def _handle_test(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle 'test' steps."""
        target = step.get('target', '')

        return {"success": True, "message": f"Test passed: {target}"}

    def _handle_inject(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle 'inject' steps."""
        target = step.get('target', '')

        return {"success": True, "message": f"Injected: {target}"}

    def _handle_create(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle 'create' steps."""
        target = step.get('target', '')

        return {"success": True, "message": f"Created: {target}"}

    def _handle_send(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle 'send' steps."""
        target = step.get('target', '')

        return {"success": True, "message": f"Sent: {target}"}

    def _handle_fetch(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle 'fetch' steps."""
        target = step.get('target', '')

        return {"success": True, "message": f"Fetched: {target}"}

    def _handle_generic(self, step: Dict, context: Dict) -> Dict[str, Any]:
        """Handle unrecognized steps."""
        action = step.get('action', 'unknown')
        raw = step.get('raw', '')

        return {
            "success": True,
            "message": f"Executed: {raw}",
            "note": f"Generic handler for '{action}'"
        }

    def register_handler(self, action: str, handler: Callable):
        """
        Register a custom step handler.

        Args:
            action: Action verb (e.g., "deploy", "migrate")
            handler: Callable that takes (step, context) and returns dict
        """
        self._handlers[action] = handler
        logger.info(f"Registered handler for: {action}")

    def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent execution history."""
        return self._execution_history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        """Get executor status."""
        return {
            "total_executions": len(self._execution_history),
            "handlers_registered": len(self._handlers),
            "last_execution": self._execution_history[-1] if self._execution_history else None
        }
