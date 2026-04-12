#!/usr/bin/env python3
"""
Skill Comparison Module - Cross-Bot Skill Analysis and Knowledge Flow Tracking

Features:
1. get_bot_skill_matrix(bot_name) - Generate skill matrix for a bot
2. compare_bots(bot1, bot2) - Compare skills between two bots
3. get_knowledge_flow() - Analyze knowledge propagation paths
4. identify_skill_gaps() - Identify team capability gaps

Usage:
    from skill_comparison import SkillComparator

    comparator = SkillComparator()
    matrix = comparator.get_bot_skill_matrix("编导")
    comparison = comparator.compare_bots("编导", "运营")
    flow = comparator.get_knowledge_flow()
    gaps = comparator.identify_skill_gaps()
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

# Bot definitions (from bot_manager.py)
BOTS = {
    "编导": {"model": "deepseek-ai/DeepSeek-V3.2", "provider": "compshare", "role": "content"},
    "剪辑": {"model": "gpt-5.1", "provider": "compshare", "role": "video"},
    "美工": {"model": "gpt-5.1", "provider": "compshare", "role": "design"},
    "场控": {"model": "claude-haiku-4-5-20251001", "provider": "compshare", "role": "control"},
    "客服": {"model": "qwen3.5-plus", "provider": "coding-plan", "role": "support"},
    "运营": {"model": "claude-sonnet-4-6", "provider": "compshare", "role": "operation"},
    "渠道": {"model": "gpt-5.1", "provider": "compshare", "role": "business"},
    "小小谦": {"model": "kimi-k2.5", "provider": "moonshot", "role": "coordinator"},
}

# Skill categories for analysis
SKILL_CATEGORIES = {
    "technical": ["API", "integration", "automation", "script", "code", "debug", "deploy"],
    "content": ["writing", "creative", "script", "story", "copy", "content", "narrative"],
    "data": ["analysis", "metrics", "statistics", "report", "dashboard", "trends", "kpi"],
    "communication": ["response", "reply", "engagement", "interaction", "feedback", "support"],
    "visual": ["design", "visual", "layout", "color", "aesthetic", "graphic", "image"],
    "video": ["editing", "video", "clip", "transition", "effect", "render", "timeline"],
    "management": ["planning", "coordination", "schedule", "workflow", "process", "optimize"],
    "business": ["partnership", "collaboration", "revenue", "monetization", "channel", "deal"],
}

# Bot relationship map (from knowledge_graph.py)
BOT_RELATIONSHIPS = {
    "编导": ["场控", "运营", "剪辑", "美工"],
    "场控": ["编导", "运营", "客服"],
    "剪辑": ["编导", "美工", "运营"],
    "美工": ["编导", "剪辑", "运营"],
    "客服": ["运营", "渠道", "编导"],
    "运营": ["客服", "渠道", "编导", "场控"],
    "渠道": ["运营", "客服"],
    "小小谦": ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道"],
}

# Workspaces directory
WORKSPACES_DIR = Path(__file__).parent / "workspaces"


class SkillComparator:
    """
    Cross-bot skill comparison and analysis.

    Capabilities:
    1. Generate skill matrices for each bot
    2. Compare skills between bots
    3. Track knowledge flow paths
    4. Identify team skill gaps
    """

    def __init__(self):
        self._skills_dir = Path(__file__).parent / "skills"
        self._knowledge_graph_dir = Path(__file__).parent / "knowledge_graph"
        self._bot_skills: Dict[str, List[Dict]] = {}
        self._load_bot_skills()

    def _load_bot_skills(self):
        """Load skills from each bot's workspace."""
        for bot_name in BOTS.keys():
            skills = self._collect_bot_skills(bot_name)
            self._bot_skills[bot_name] = skills

    def _collect_bot_skills(self, bot_name: str) -> List[Dict]:
        """Collect all skills for a specific bot."""
        skills = []

        # Check bot's DYNAMIC/skills directory
        bot_skills_dir = WORKSPACES_DIR / bot_name / "DYNAMIC" / "skills"
        if bot_skills_dir.exists():
            for skill_file in bot_skills_dir.glob("*.md"):
                skill_data = self._parse_skill_file(skill_file, bot_name)
                if skill_data:
                    skills.append(skill_data)

        # Check bot's memory/知识库 for cross-bot learning
        memory_dir = WORKSPACES_DIR / bot_name / "memory" / "知识库"
        if memory_dir.exists():
            for kb_file in memory_dir.glob("*.md"):
                if "跨 Bot 学习" in kb_file.name or "skill" in kb_file.name.lower():
                    skill_data = self._parse_knowledge_file(kb_file, bot_name)
                    if skill_data:
                        skills.append(skill_data)

        # Check global skills directory for shared skills
        if self._skills_dir.exists():
            skill_file = self._skills_dir / "SKILL.md"
            if skill_file.exists():
                global_skills = self._parse_global_skills(skill_file, bot_name)
                skills.extend(global_skills)

        return skills

    def _parse_skill_file(self, file_path: Path, bot_name: str) -> Optional[Dict]:
        """Parse a skill markdown file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            skill_data = {
                "name": file_path.stem,
                "file": str(file_path),
                "bot": bot_name,
                "content": content,
                "categories": self._categorize_content(content),
                "created_at": self._get_file_date(file_path),
                "type": "bot_specific"
            }
            return skill_data
        except Exception as e:
            logger.error(f"Failed to parse skill file {file_path}: {e}")
            return None

    def _parse_knowledge_file(self, file_path: Path, bot_name: str) -> Optional[Dict]:
        """Parse a knowledge file for skills."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract skill-related content
            skill_data = {
                "name": file_path.stem,
                "file": str(file_path),
                "bot": bot_name,
                "content": content[:500],  # Truncate for categorization
                "categories": self._categorize_content(content),
                "created_at": self._get_file_date(file_path),
                "type": "cross_bot_learning"
            }
            return skill_data
        except Exception as e:
            logger.error(f"Failed to parse knowledge file {file_path}: {e}")
            return None

    def _parse_global_skills(self, file_path: Path, bot_name: str) -> List[Dict]:
        """Parse global SKILL.md and filter for relevant skills."""
        skills = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Split by delimiter
            entries = content.split("\n§\n")
            for i, entry in enumerate(entries):
                if entry.strip():
                    skill_data = {
                        "name": f"global_skill_{i}",
                        "file": str(file_path),
                        "bot": bot_name,
                        "content": entry.strip(),
                        "categories": self._categorize_content(entry),
                        "created_at": self._get_file_date(file_path),
                        "type": "global"
                    }
                    skills.append(skill_data)
        except Exception as e:
            logger.error(f"Failed to parse global skills: {e}")

        return skills

    def _get_file_date(self, file_path: Path) -> str:
        """Get file modification date."""
        try:
            mtime = os.path.getmtime(file_path)
            return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        except Exception:
            return "unknown"

    def _categorize_content(self, content: str) -> List[str]:
        """Categorize content based on keywords."""
        content_lower = content.lower()
        categories = []

        for category, keywords in SKILL_CATEGORIES.items():
            if any(kw in content_lower for kw in keywords):
                categories.append(category)

        return categories if categories else ["general"]

    def get_bot_skill_matrix(self, bot_name: str) -> Dict[str, Any]:
        """
        Generate a skill matrix for a specific bot.

        Args:
            bot_name: Name of the bot

        Returns:
            Skill matrix with categories and proficiency levels
        """
        if bot_name not in BOTS:
            return {
                "success": False,
                "error": f"Unknown bot: {bot_name}",
                "available_bots": list(BOTS.keys())
            }

        skills = self._bot_skills.get(bot_name, [])

        # Calculate category distribution
        category_counts = defaultdict(int)
        type_counts = defaultdict(int)
        skill_names = []

        for skill in skills:
            for category in skill.get("categories", []):
                category_counts[category] += 1
            type_counts[skill.get("type", "unknown")] += 1
            skill_names.append({
                "name": skill.get("name", "Unknown"),
                "categories": skill.get("categories", []),
                "type": skill.get("type", "unknown"),
                "created_at": skill.get("created_at", "unknown")
            })

        # Calculate proficiency (based on skill count per category)
        total_skills = len(skills)
        proficiency = {}
        for category, count in category_counts.items():
            if count >= 10:
                proficiency[category] = "expert"
            elif count >= 5:
                proficiency[category] = "proficient"
            elif count >= 2:
                proficiency[category] = "developing"
            else:
                proficiency[category] = "beginner"

        matrix = {
            "success": True,
            "bot_name": bot_name,
            "bot_info": BOTS[bot_name],
            "total_skills": total_skills,
            "category_distribution": dict(category_counts),
            "proficiency_levels": proficiency,
            "skill_types": dict(type_counts),
            "skill_list": skill_names,
            "generated_at": datetime.now().isoformat()
        }

        return matrix

    def compare_bots(self, bot1: str, bot2: str) -> Dict[str, Any]:
        """
        Compare skills between two bots.

        Args:
            bot1: First bot name
            bot2: Second bot name

        Returns:
            Comparison result with shared/unique skills
        """
        if bot1 not in BOTS:
            return {"success": False, "error": f"Unknown bot: {bot1}"}
        if bot2 not in BOTS:
            return {"success": False, "error": f"Unknown bot: {bot2}"}

        matrix1 = self.get_bot_skill_matrix(bot1)
        matrix2 = self.get_bot_skill_matrix(bot2)

        if not matrix1.get("success") or not matrix2.get("success"):
            return {"success": False, "error": "Failed to generate skill matrices"}

        # Compare category distribution
        all_categories = set(matrix1["category_distribution"].keys()) | set(matrix2["category_distribution"].keys())

        category_comparison = {}
        for cat in all_categories:
            count1 = matrix1["category_distribution"].get(cat, 0)
            count2 = matrix2["category_distribution"].get(cat, 0)
            category_comparison[cat] = {
                bot1: count1,
                bot2: count2,
                "difference": count1 - count2,
                "stronger": bot1 if count1 > count2 else (bot2 if count2 > count1 else "equal")
            }

        # Compare proficiency
        shared_categories = set(matrix1["proficiency_levels"].keys()) & set(matrix2["proficiency_levels"].keys())
        proficiency_comparison = {}
        for cat in shared_categories:
            prof1 = matrix1["proficiency_levels"].get(cat, "unknown")
            prof2 = matrix2["proficiency_levels"].get(cat, "unknown")
            proficiency_comparison[cat] = {
                bot1: prof1,
                bot2: prof2
            }

        # Find unique and shared skill types
        skills1_names = {s["name"] for s in matrix1["skill_list"]}
        skills2_names = {s["name"] for s in matrix2["skill_list"]}

        comparison = {
            "success": True,
            "bots_compared": [bot1, bot2],
            "bot1_info": {
                "name": bot1,
                "total_skills": matrix1["total_skills"],
                "categories": matrix1["category_distribution"],
                "model": BOTS[bot1]["model"]
            },
            "bot2_info": {
                "name": bot2,
                "total_skills": matrix2["total_skills"],
                "categories": matrix2["category_distribution"],
                "model": BOTS[bot2]["model"]
            },
            "category_comparison": category_comparison,
            "proficiency_comparison": proficiency_comparison,
            "unique_to_bot1": list(skills1_names - skills2_names)[:10],
            "unique_to_bot2": list(skills2_names - skills1_names)[:10],
            "skill_overlap": len(skills1_names & skills2_names),
            "recommendation": self._generate_comparison_recommendation(bot1, bot2, category_comparison),
            "generated_at": datetime.now().isoformat()
        }

        return comparison

    def _generate_comparison_recommendation(
        self,
        bot1: str,
        bot2: str,
        category_comparison: Dict
    ) -> str:
        """Generate a recommendation based on comparison."""
        bot1_strengths = [cat for cat, data in category_comparison.items() if data["stronger"] == bot1]
        bot2_strengths = [cat for cat, data in category_comparison.items() if data["stronger"] == bot2]

        recommendations = []

        if bot1_strengths:
            recommendations.append(f"{bot1} excels in: {', '.join(bot1_strengths)}")
        if bot2_strengths:
            recommendations.append(f"{bot2} excels in: {', '.join(bot2_strengths)}")

        # Suggest knowledge sharing
        if bot1_strengths and bot2_strengths:
            recommendations.append(
                f"Consider sharing knowledge: {bot1} can teach {', '.join(bot1_strengths[:2])} to {bot2}, "
                f"and {bot2} can teach {', '.join(bot2_strengths[:2])} to {bot1}"
            )

        return " | ".join(recommendations) if recommendations else "Both bots have similar skill distributions"

    def get_knowledge_flow(self) -> Dict[str, Any]:
        """
        Analyze knowledge propagation paths across bots.

        Returns:
            Knowledge flow analysis with paths and patterns
        """
        # Load knowledge graph if available
        graph_file = self._knowledge_graph_dir / "graph.json"

        if not graph_file.exists():
            # Build from cross-bot learning files
            return self._build_knowledge_flow_from_files()

        try:
            with open(graph_file, "r", encoding="utf-8") as f:
                graph_data = json.load(f)

            # Analyze propagation paths
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])

            # Count propagation by source bot
            source_counts = defaultdict(int)
            target_counts = defaultdict(int)
            propagation_pairs = defaultdict(int)

            for node in nodes:
                source_bot = node.get("source_bot", "unknown")
                source_counts[source_bot] += 1

                propagated_to = node.get("propagated_to", [])
                for target in propagated_to:
                    target_counts[target] += 1
                    propagation_pairs[(source_bot, target)] += 1

            # Find most active knowledge sources
            top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:5]

            # Find knowledge receivers
            top_receivers = sorted(target_counts.items(), key=lambda x: x[1], reverse=True)[:5]

            # Find most common propagation paths
            top_paths = sorted(propagation_pairs.items(), key=lambda x: x[1], reverse=True)[:10]

            flow = {
                "success": True,
                "total_knowledge_nodes": len(nodes),
                "total_edges": len(edges),
                "knowledge_sources": {bot: count for bot, count in top_sources},
                "knowledge_receivers": {bot: count for bot, count in top_receivers},
                "propagation_paths": [{"from": p[0], "to": p[1], "count": c} for (p, c) in top_paths],
                "bot_relationships": BOT_RELATIONSHIPS,
                "knowledge_flow_visualization": self._generate_flow_ascii(top_paths),
                "generated_at": datetime.now().isoformat()
            }

            return flow

        except Exception as e:
            logger.error(f"Failed to analyze knowledge graph: {e}")
            return self._build_knowledge_flow_from_files()

    def _build_knowledge_flow_from_files(self) -> Dict[str, Any]:
        """Build knowledge flow from cross-bot learning files."""
        flow_data = {
            "success": True,
            "source": "file_system_scan",
            "knowledge_sources": {},
            "knowledge_receivers": {},
            "propagation_paths": [],
            "cross_bot_learning_files": []
        }

        for bot_name in BOTS.keys():
            memory_dir = WORKSPACES_DIR / bot_name / "memory" / "知识库"
            if memory_dir.exists():
                cross_bot_files = list(memory_dir.glob("跨 Bot 学习*.md"))
                if cross_bot_files:
                    flow_data["cross_bot_learning_files"].append({
                        "bot": bot_name,
                        "file_count": len(cross_bot_files),
                        "files": [f.name for f in cross_bot_files[:5]]
                    })

                    # Extract source bot from file names
                    for f in cross_bot_files:
                        # Parse file name like "跨 Bot 学习 - 编导.md"
                        parts = f.stem.split("-")
                        if len(parts) >= 2:
                            source_bot = parts[-1].strip()
                            flow_data["knowledge_sources"][source_bot] = \
                                flow_data["knowledge_sources"].get(source_bot, 0) + 1
                            flow_data["knowledge_receivers"][bot_name] = \
                                flow_data["knowledge_receivers"].get(bot_name, 0) + 1
                            flow_data["propagation_paths"].append({
                                "from": source_bot,
                                "to": bot_name,
                                "file": f.name
                            })

        return flow_data

    def _generate_flow_ascii(self, paths: List[Tuple[Tuple[str, str], int]]) -> str:
        """Generate ASCII visualization of knowledge flow."""
        if not paths:
            return "No knowledge flow data available"

        lines = ["Knowledge Flow Visualization:", "=" * 50]

        # Group by source
        sources = defaultdict(list)
        for (src, tgt), count in paths:
            sources[src].append((tgt, count))

        for source, targets in sorted(sources.items()):
            lines.append(f"\n{source} (source)")
            for target, count in sorted(targets, key=lambda x: x[1], reverse=True):
                lines.append(f"  --> {target} ({count} knowledge transfers)")

        return "\n".join(lines)

    def identify_skill_gaps(self) -> Dict[str, Any]:
        """
        Identify skill gaps across the bot team.

        Returns:
            Skill gap analysis with recommendations
        """
        # Aggregate all skills by category
        team_skills = defaultdict(set)
        bot_category_skills = {}

        for bot_name in BOTS.keys():
            matrix = self.get_bot_skill_matrix(bot_name)
            if matrix.get("success"):
                bot_category_skills[bot_name] = matrix["category_distribution"]
                for category in matrix["category_distribution"].keys():
                    team_skills[category].add(bot_name)

        # Identify categories with low coverage
        skill_gaps = []
        skill_concentrations = []

        for category, keywords in SKILL_CATEGORIES.items():
            bots_with_skill = team_skills.get(category, set())
            coverage = len(bots_with_skill) / len(BOTS)

            if coverage < 0.3:  # Less than 30% coverage
                skill_gaps.append({
                    "category": category,
                    "coverage": f"{coverage * 100:.1f}%",
                    "bots_with_skill": list(bots_with_skill),
                    "severity": "high" if coverage < 0.15 else "medium",
                    "keywords": keywords
                })
            elif coverage > 0.7:  # More than 70% coverage
                skill_concentrations.append({
                    "category": category,
                    "coverage": f"{coverage * 100:.1f}%",
                    "bots_with_skill": list(bots_with_skill),
                    "strength": "team strength"
                })

        # Find skill concentration (single point of failure)
        single_points = []
        for category, bots in team_skills.items():
            if len(bots) == 1:
                single_points.append({
                    "category": category,
                    "only_bot": list(bots)[0],
                    "risk": "single point of failure"
                })

        # Generate recommendations
        recommendations = self._generate_gap_recommendations(skill_gaps, single_points, bot_category_skills)

        result = {
            "success": True,
            "team_size": len(BOTS),
            "skill_gaps": skill_gaps,
            "skill_concentrations": skill_concentrations,
            "single_points_of_failure": single_points,
            "bot_skill_summary": bot_category_skills,
            "recommendations": recommendations,
            "generated_at": datetime.now().isoformat()
        }

        return result

    def _generate_gap_recommendations(
        self,
        skill_gaps: List[Dict],
        single_points: List[Dict],
        bot_category_skills: Dict[str, Dict]
    ) -> List[str]:
        """Generate recommendations for addressing skill gaps."""
        recommendations = []

        # Address high severity gaps
        high_severity = [g for g in skill_gaps if g.get("severity") == "high"]
        if high_severity:
            gap_categories = [g["category"] for g in high_severity]
            recommendations.append(
                f"CRITICAL: Team lacks skills in: {', '.join(gap_categories)}. "
                "Consider training or knowledge sharing."
            )

        # Address single points of failure
        for sp in single_points:
            category = sp["category"]
            only_bot = sp["only_bot"]

            # Find related bots that could learn
            related_bots = BOT_RELATIONSHIPS.get(only_bot, [])
            if related_bots:
                recommendations.append(
                    f"RISK: {category} skill only exists in {only_bot}. "
                    f"Recommend knowledge transfer to: {', '.join(related_bots[:3])}"
                )

        # General team development recommendations
        if len(skill_gaps) > 3:
            recommendations.append(
                "Multiple skill gaps detected. Consider cross-training sessions "
                "between bots with complementary skills."
            )

        # Identify best knowledge sharers
        if bot_category_skills:
            most_skilled_bot = max(
                bot_category_skills.items(),
                key=lambda x: sum(x[1].values())
            )
            if most_skilled_bot:
                recommendations.append(
                    f"{most_skilled_bot[0]} has the most skills "
                    f"({sum(most_skilled_bot[1].values())} total). "
                    "Consider as primary knowledge source."
                )

        return recommendations if recommendations else ["Team skill distribution looks healthy"]

    def generate_skill_heatmap_data(self) -> Dict[str, Any]:
        """
        Generate data for skill heatmap visualization.

        Returns:
            Heatmap data with bots as rows and categories as columns
        """
        heatmap_data = {
            "success": True,
            "bots": list(BOTS.keys()),
            "categories": list(SKILL_CATEGORIES.keys()),
            "data": {},
            "generated_at": datetime.now().isoformat()
        }

        for bot_name in BOTS.keys():
            matrix = self.get_bot_skill_matrix(bot_name)
            if matrix.get("success"):
                heatmap_data["data"][bot_name] = {}
                for category in SKILL_CATEGORIES.keys():
                    count = matrix["category_distribution"].get(category, 0)
                    heatmap_data["data"][bot_name][category] = count

        return heatmap_data


# Global instance
_default_comparator: Optional[SkillComparator] = None


def get_skill_comparator() -> SkillComparator:
    """Get or create SkillComparator instance."""
    global _default_comparator
    if _default_comparator is None:
        _default_comparator = SkillComparator()
    return _default_comparator


# Convenience functions
def get_bot_skill_matrix(bot_name: str) -> Dict[str, Any]:
    """Get skill matrix for a bot."""
    comparator = get_skill_comparator()
    return comparator.get_bot_skill_matrix(bot_name)


def compare_bots(bot1: str, bot2: str) -> Dict[str, Any]:
    """Compare skills between two bots."""
    comparator = get_skill_comparator()
    return comparator.compare_bots(bot1, bot2)


def get_knowledge_flow() -> Dict[str, Any]:
    """Get knowledge flow analysis."""
    comparator = get_skill_comparator()
    return comparator.get_knowledge_flow()


def identify_skill_gaps() -> Dict[str, Any]:
    """Identify team skill gaps."""
    comparator = get_skill_comparator()
    return comparator.identify_skill_gaps()


def generate_skill_heatmap() -> Dict[str, Any]:
    """Generate skill heatmap data."""
    comparator = get_skill_comparator()
    return comparator.generate_skill_heatmap_data()


if __name__ == "__main__":
    import sys

    comparator = get_skill_comparator()

    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage:")
        print("  python3 skill_comparison.py matrix <bot_name>     # Get bot skill matrix")
        print("  python3 skill_comparison.py compare <bot1> <bot2> # Compare two bots")
        print("  python3 skill_comparison.py flow                  # Get knowledge flow")
        print("  python3 skill_comparison.py gaps                  # Identify skill gaps")
        print("  python3 skill_comparison.py heatmap               # Generate heatmap data")
        sys.exit(1)

    command = sys.argv[1]

    if command == "matrix":
        if len(sys.argv) < 3:
            print("Usage: skill_comparison.py matrix <bot_name>")
            sys.exit(1)
        result = comparator.get_bot_skill_matrix(sys.argv[2])
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif command == "compare":
        if len(sys.argv) < 4:
            print("Usage: skill_comparison.py compare <bot1> <bot2>")
            sys.exit(1)
        result = comparator.compare_bots(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif command == "flow":
        result = comparator.get_knowledge_flow()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif command == "gaps":
        result = comparator.identify_skill_gaps()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif command == "heatmap":
        result = comparator.generate_skill_heatmap_data()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
