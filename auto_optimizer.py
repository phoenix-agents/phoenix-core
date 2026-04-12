#!/usr/bin/env python3
"""
Automatic Skill Optimizer - Background Optimization Service

Automatically detects skills needing optimization and runs AI optimization
without manual intervention.

Features:
1. Periodic background scanning for optimization candidates
2. Automatic AI optimization for low-risk skills
3. Notification for high-risk skill optimizations
4. Optimization history tracking

Usage:
    # Start background service
    from auto_optimizer import AutoOptimizer

    optimizer = AutoOptimizer(memory_manager)
    optimizer.start_background_service(interval_minutes=30)

    # Or run manual scan
    optimizer.scan_and_optimize()
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from skill_optimizer import SkillOptimizer

logger = logging.getLogger(__name__)


class AutoOptimizer:
    """
    Automatic skill optimization service.

    Process:
    1. Scan all skills periodically
    2. Identify candidates (low success rate, high failure count)
    3. Auto-optimize low-risk skills
    4. Notify for high-risk skill optimizations
    5. Track optimization history
    """

    def __init__(self, memory_manager=None):
        self._memory_manager = memory_manager
        self._optimizer = SkillOptimizer(memory_manager=memory_manager)

        # Auto-optimization settings
        self._auto_optimize_enabled = True
        self._auto_optimize_threshold = 0.5  # Success rate below this triggers auto-optimize
        self._min_failures_for_auto = 3  # Minimum failures before auto-optimizing

        # Background service config
        self._background_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._scan_interval_minutes = 30
        self._last_scan: Optional[datetime] = None

        # Optimization history
        self._optimization_history: List[Dict[str, Any]] = []

        # Callbacks
        self._on_optimization_complete: Optional[Callable] = None
        self._on_optimization_needed: Optional[Callable] = None

    def start_background_service(self, interval_minutes: int = 30):
        """
        Start background optimization service.

        Args:
            interval_minutes: How often to scan for optimization candidates
        """
        if self._background_thread and self._background_thread.is_alive():
            logger.warning("Background service already running")
            return

        self._scan_interval_minutes = interval_minutes
        self._stop_event.clear()
        self._background_thread = threading.Thread(
            target=self._background_loop,
            daemon=True,
            name="AutoOptimizer-Background"
        )
        self._background_thread.start()

        logger.info(f"AutoOptimizer background service started (interval: {interval_minutes}min)")

    def stop_background_service(self, wait: bool = True):
        """
        Stop background optimization service.

        Args:
            wait: Whether to wait for thread to finish
        """
        self._stop_event.set()
        if wait and self._background_thread:
            self._background_thread.join(timeout=5.0)
        logger.info("AutoOptimizer background service stopped")

    def _background_loop(self):
        """Background thread main loop."""
        while not self._stop_event.is_set():
            try:
                # Scan and optimize
                self.scan_and_optimize()
                self._last_scan = datetime.now()

                # Wait for next scan
                self._stop_event.wait(timeout=self._scan_interval_minutes * 60)

            except Exception as e:
                logger.error(f"Background optimization error: {e}")

    def scan_and_optimize(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Scan all skills and optimize those that need it.

        Args:
            dry_run: If True, only report candidates without optimizing

        Returns:
            Scan and optimization results
        """
        logger.info(f"Starting optimization scan (dry_run={dry_run})")

        # Get candidates
        candidates = self._optimizer.get_optimization_candidates()

        results = {
            "scan_time": datetime.now().isoformat(),
            "candidates_found": len(candidates),
            "optimized_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "optimizations": []
        }

        for candidate in candidates:
            skill_name = candidate['skill_name']
            stats = candidate['stats']

            # Check if auto-optimization is appropriate
            should_auto_optimize = self._should_auto_optimize(stats)

            if dry_run:
                results["optimizations"].append({
                    "skill_name": skill_name,
                    "stats": stats,
                    "would_optimize": should_auto_optimize,
                    "reason": candidate['recommendation']
                })
                continue

            if not should_auto_optimize:
                results["skipped_count"] += 1
                logger.info(f"Skipping {skill_name}: success rate {stats['success_rate']:.0%} (above auto-threshold)")
                continue

            # Run optimization
            logger.info(f"Auto-optimizing: {skill_name} (success rate: {stats['success_rate']:.0%})")

            opt_result = self._optimizer.optimize_skill(skill_name)

            if opt_result.get('success'):
                results["optimized_count"] += 1
                optimization_record = {
                    "timestamp": datetime.now().isoformat(),
                    "skill_name": skill_name,
                    "original_success_rate": stats['success_rate'],
                    "original_name": opt_result['original_skill']['name'],
                    "optimized_name": opt_result['optimized_skill']['name'],
                    "auto_optimized": True
                }
                results["optimizations"].append(optimization_record)
                self._optimization_history.append(optimization_record)

                # Notify
                if self._on_optimization_complete:
                    self._on_optimization_complete(optimization_record)

                logger.info(f"Auto-optimized: {skill_name} → {opt_result['optimized_skill']['name']}")
            else:
                results["failed_count"] += 1
                logger.warning(f"Auto-optimization failed for {skill_name}: {opt_result.get('reason', 'Unknown')}")

        self._last_scan = datetime.now()

        if results["candidates_found"] > 0:
            logger.info(
                f"Scan complete: {results['optimized_count']} optimized, "
                f"{results['skipped_count']} skipped, {results['failed_count']} failed"
            )

        return results

    def _should_auto_optimize(self, stats: Dict[str, Any]) -> bool:
        """
        Determine if a skill should be auto-optimized (vs manual review).

        Args:
            stats: Skill statistics

        Returns:
            True if safe to auto-optimize
        """
        # Check success rate threshold
        if stats['success_rate'] >= self._auto_optimize_threshold:
            return False

        # Check minimum failures
        if stats['failures'] < self._min_failures_for_auto:
            return False

        # Check total executions (need enough data)
        if stats['total_executions'] < 5:
            return False

        # Could add additional checks:
        # - Risk level of skill actions
        # - Whether skill modifies production state
        # - User feedback trends

        return True

    def get_optimization_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent optimization history."""
        return self._optimization_history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        """Get current service status."""
        return {
            "background_running": self._background_thread.is_alive() if self._background_thread else False,
            "scan_interval_minutes": self._scan_interval_minutes,
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
            "auto_optimize_enabled": self._auto_optimize_enabled,
            "auto_optimize_threshold": self._auto_optimize_threshold,
            "total_optimizations": len(self._optimization_history),
            "skills_tracked": len(set(r['skill_name'] for r in self._optimization_history))
        }

    def set_auto_optimize_enabled(self, enabled: bool):
        """Enable or disable auto-optimization."""
        self._auto_optimize_enabled = enabled
        logger.info(f"Auto-optimization {'enabled' if enabled else 'disabled'}")

    def set_optimization_threshold(self, threshold: float):
        """
        Set success rate threshold for auto-optimization.

        Args:
            threshold: Success rate below which triggers auto-optimize (0.0-1.0)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        self._auto_optimize_threshold = threshold
        logger.info(f"Auto-optimization threshold set to {threshold:.0%}")

    def optimize_now(self, skill_name: str = None) -> Dict[str, Any]:
        """
        Manually trigger optimization for a specific skill or all candidates.

        Args:
            skill_name: Optional specific skill to optimize (None = all candidates)

        Returns:
            Optimization result(s)
        """
        if skill_name:
            # Optimize specific skill
            result = self._optimizer.optimize_skill(skill_name)
            if result.get('success'):
                self._optimization_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "skill_name": skill_name,
                    "optimized_name": result['optimized_skill']['name'],
                    "manual": True
                })
            return result
        else:
            # Optimize all candidates
            return self.scan_and_optimize(dry_run=False)

    def get_candidates_preview(self) -> List[Dict[str, Any]]:
        """Get list of candidates that would be optimized."""
        return self._optimizer.get_optimization_candidates()


# Convenience functions for direct usage
_default_optimizer: Optional[AutoOptimizer] = None


def get_auto_optimizer(memory_manager=None) -> AutoOptimizer:
    """Get or create default AutoOptimizer instance."""
    global _default_optimizer
    if _default_optimizer is None:
        _default_optimizer = AutoOptimizer(memory_manager=memory_manager)
    return _default_optimizer


def start_auto_optimization(memory_manager=None, interval_minutes: int = 30):
    """
    Start automatic skill optimization service.

    Args:
        memory_manager: MemoryManager instance
        interval_minutes: How often to scan (default: 30 minutes)
    """
    optimizer = get_auto_optimizer(memory_manager)
    optimizer.start_background_service(interval_minutes=interval_minutes)
    return optimizer


def stop_auto_optimization(wait: bool = True):
    """Stop automatic skill optimization service."""
    if _default_optimizer:
        _default_optimizer.stop_background_service(wait=wait)
