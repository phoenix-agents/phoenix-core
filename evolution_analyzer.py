#!/usr/bin/env python3
"""
Evolution Trend Analyzer - Analyze skill evolution trends

Generates reports on:
1. Success rate improvements
2. Performance trends over time
3. Most improved skills
4. Evolution frequency analysis

Usage:
    analyzer = EvolutionTrendAnalyzer()
    report = analyzer.generate_report()
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class EvolutionTrendAnalyzer:
    """Analyze and report on skill evolution trends."""

    def __init__(self):
        self.evolution_dir = Path(__file__).parent / "skill_evolution"
        self.report_dir = Path(__file__).parent / "evolution_reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def load_evolution_history(self) -> List[Dict[str, Any]]:
        """Load evolution history from log file."""
        log_file = self.evolution_dir / 'evolution_log.md'

        if not log_file.exists():
            return []

        history = []
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse markdown entries
        entries = content.split('## ')[1:]  # Split by section headers

        for entry in entries:
            lines = entry.strip().split('\n')
            if len(lines) < 5:
                continue

            try:
                timestamp = lines[0].strip()
                data = {'timestamp': timestamp}

                for line in lines[1:]:
                    if line.startswith('- **Skill**'):
                        data['skill_name'] = line.split('**')[1]
                    elif line.startswith('- **Version**'):
                        version_info = line.split('**')[1].split('→')
                        data['from_version'] = version_info[0].strip()
                        data['to_version'] = version_info[1].strip()
                    elif line.startswith('- **Reason**'):
                        data['reason'] = line.split('**')[1]
                    elif line.startswith('- **Success Rate**'):
                        rates = line.split('**')[1].split('→')
                        data['old_success_rate'] = self._parse_rate(rates[0])
                        data['new_success_rate'] = self._parse_rate(rates[1])

                history.append(data)
            except Exception as e:
                logger.warning(f"Failed to parse entry: {e}")

        return history

    def _parse_rate(self, rate_str: str) -> float:
        """Parse success rate string to float."""
        try:
            rate_str = rate_str.strip().rstrip('%')
            return float(rate_str) / 100
        except:
            return 0.0

    def analyze_trends(self, days: int = 7) -> Dict[str, Any]:
        """
        Analyze evolution trends over specified period.

        Args:
            days: Number of days to analyze

        Returns:
            Trend analysis results
        """
        history = self.load_evolution_history()

        if not history:
            return {'error': 'No evolution history found'}

        # Filter by date range
        cutoff = datetime.now() - timedelta(days=days)
        filtered = [
            e for e in history
            if self._parse_timestamp(e.get('timestamp', '')) > cutoff
        ]

        if not filtered:
            return {'error': f'No evolutions in last {days} days'}

        # Calculate metrics
        total_evolutions = len(filtered)
        avg_improvement = self._calculate_avg_improvement(filtered)
        most_improved = self._find_most_improved(filtered)
        evolution_frequency = self._calculate_frequency(filtered)
        trends_by_skill = self._group_by_skill(filtered)

        return {
            'period_days': days,
            'total_evolutions': total_evolutions,
            'avg_improvement': avg_improvement,
            'most_improved': most_improved,
            'evolution_frequency': evolution_frequency,
            'trends_by_skill': trends_by_skill,
            'raw_data': filtered
        }

    def _parse_timestamp(self, ts: str) -> datetime:
        """Parse ISO timestamp."""
        try:
            return datetime.fromisoformat(ts)
        except:
            return datetime.now()

    def _calculate_avg_improvement(self, evolutions: List[Dict]) -> float:
        """Calculate average success rate improvement."""
        improvements = [
            e['new_success_rate'] - e['old_success_rate']
            for e in evolutions
            if 'new_success_rate' in e and 'old_success_rate' in e
        ]

        if not improvements:
            return 0.0

        return sum(improvements) / len(improvements)

    def _find_most_improved(self, evolutions: List[Dict]) -> List[Dict]:
        """Find skills with biggest improvements."""
        improvements = []

        for e in evolutions:
            if 'new_success_rate' in e and 'old_success_rate' in e:
                improvements.append({
                    'skill_name': e.get('skill_name', 'unknown'),
                    'improvement': e['new_success_rate'] - e['old_success_rate'],
                    'from_rate': e['old_success_rate'],
                    'to_rate': e['new_success_rate']
                })

        # Sort by improvement
        improvements.sort(key=lambda x: x['improvement'], reverse=True)
        return improvements[:5]  # Top 5

    def _calculate_frequency(self, evolutions: List[Dict]) -> Dict[str, Any]:
        """Calculate evolution frequency metrics."""
        if not evolutions:
            return {}

        # Group by date
        by_date = defaultdict(int)
        for e in evolutions:
            date = e.get('timestamp', '')[:10]  # YYYY-MM-DD
            by_date[date] += 1

        if not by_date:
            return {}

        dates = list(by_date.keys())
        daily_counts = list(by_date.values())

        return {
            'evolutions_per_day': sum(daily_counts) / len(dates),
            'max_day': max(daily_counts),
            'min_day': min(daily_counts),
            'daily_breakdown': dict(by_date)
        }

    def _group_by_skill(self, evolutions: List[Dict]) -> Dict[str, List[Dict]]:
        """Group evolutions by skill."""
        by_skill = defaultdict(list)

        for e in evolutions:
            skill = e.get('skill_name', 'unknown')
            by_skill[skill].append(e)

        return dict(by_skill)

    def generate_report(self, days: int = 7) -> str:
        """
        Generate human-readable trend report.

        Args:
            days: Number of days to analyze

        Returns:
            Markdown formatted report
        """
        trends = self.analyze_trends(days)

        if 'error' in trends:
            return f"# Evolution Trend Report\n\n⚠️ {trends['error']}"

        report = f"""# Evolution Trend Report

**Period**: Last {days} days
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 📊 Summary

| Metric | Value |
|--------|-------|
| Total Evolutions | {trends['total_evolutions']} |
| Avg Improvement | {trends['avg_improvement']:.1%} |
| Evolutions/Day | {trends['evolution_frequency'].get('evolutions_per_day', 0):.1f} |

---

## 🏆 Most Improved Skills

| Rank | Skill | Improvement | From | To |
|------|-------|-------------|------|-----|
"""

        for i, skill in enumerate(trends['most_improved'][:5], 1):
            report += f"| {i} | {skill['skill_name']} | +{skill['improvement']:.1%} | {skill['from_rate']:.0%} | {skill['to_rate']:.0%} |\n"

        report += """
---

## 📈 Daily Evolution Count

```
"""

        # ASCII chart
        daily = trends['evolution_frequency'].get('daily_breakdown', {})
        if daily:
            max_count = max(daily.values())
            for date, count in sorted(daily.items())[-7:]:  # Last 7 days
                bar = '█' * int(count / max_count * 20) if max_count > 0 else ''
                report += f"{date}: {bar} ({count})\n"

        report += """```

---

## 🔍 Trends by Skill

"""

        for skill, evolutions in trends['trends_by_skill'].items():
            if len(evolutions) >= 1:
                total_improvement = sum(
                    e.get('new_success_rate', 0) - e.get('old_success_rate', 0)
                    for e in evolutions
                )
                report += f"### {skill}\n"
                report += f"- Evolutions: {len(evolutions)}\n"
                report += f"- Total Improvement: {total_improvement:.1%}\n\n"

        report += """---

## 💡 Insights

"""

        # Generate insights
        if trends['avg_improvement'] > 0.2:
            report += "- ✅ High improvement rate: Evolution is effective\n"
        elif trends['avg_improvement'] > 0.1:
            report += "- 📈 Moderate improvement: Evolution is working\n"
        else:
            report += "- ⚠️ Low improvement: May need to review evolution strategy\n"

        if trends['total_evolutions'] > 10:
            report += "- 🔄 High evolution frequency: Active skill development\n"
        elif trends['total_evolutions'] > 3:
            report += "- 📝 Moderate evolution frequency: Steady improvement\n"
        else:
            report += "- 🐌 Low evolution frequency: Consider more frequent reviews\n"

        # Save report
        report_file = self.report_dir / f"trend_report_{datetime.now().strftime('%Y%m%d')}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"Report saved to {report_file}")
        return report


def generate_trend_report(days: int = 7) -> str:
    """Convenience function to generate trend report."""
    analyzer = EvolutionTrendAnalyzer()
    return analyzer.generate_report(days)


if __name__ == "__main__":
    report = generate_trend_report(7)
    print(report)
