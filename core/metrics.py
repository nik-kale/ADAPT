"""
Metrics collection and monitoring for ADAPT framework.

Tracks performance metrics, success rates, and operational statistics.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict
import statistics
import json


@dataclass
class MetricsCollector:
    """
    Collect and aggregate framework performance metrics.

    Tracks:
    - Agent execution times and success rates
    - RCA workflow durations
    - Signal processing statistics
    - Finding accuracy metrics
    """

    agent_execution_times: Dict[str, List[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    agent_success_rates: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: {'success': 0, 'failure': 0})
    )
    rca_durations: List[float] = field(default_factory=list)
    signal_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    finding_confidences: List[float] = field(default_factory=list)

    def record_agent_execution(
        self,
        agent_name: str,
        duration: float,
        success: bool,
        findings_count: int = 0
    ):
        """
        Record agent execution metrics.

        Args:
            agent_name: Name of the agent
            duration: Execution duration in seconds
            success: Whether execution succeeded
            findings_count: Number of findings produced
        """
        self.agent_execution_times[agent_name].append(duration)

        if success:
            self.agent_success_rates[agent_name]['success'] += 1
        else:
            self.agent_success_rates[agent_name]['failure'] += 1

    def record_rca_duration(self, duration: float):
        """
        Record total RCA workflow duration.

        Args:
            duration: Duration in seconds
        """
        self.rca_durations.append(duration)

    def record_signals_processed(self, signal_type: str, count: int):
        """
        Record number of signals processed.

        Args:
            signal_type: Type of signal (log, metric, etc.)
            count: Number of signals
        """
        self.signal_counts[signal_type] += count

    def record_finding_confidence(self, confidence: float):
        """
        Record confidence score of a finding.

        Args:
            confidence: Confidence score (0.0 to 1.0)
        """
        if 0.0 <= confidence <= 1.0:
            self.finding_confidences.append(confidence)

    def get_agent_stats(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a specific agent.

        Args:
            agent_name: Name of the agent

        Returns:
            Dictionary of agent statistics or None if no data
        """
        if agent_name not in self.agent_execution_times:
            return None

        times = self.agent_execution_times[agent_name]
        rates = self.agent_success_rates[agent_name]
        total = rates['success'] + rates['failure']

        return {
            'avg_duration_seconds': statistics.mean(times),
            'min_duration_seconds': min(times),
            'max_duration_seconds': max(times),
            'p95_duration_seconds': self._calculate_percentile(times, 0.95),
            'p99_duration_seconds': self._calculate_percentile(times, 0.99),
            'success_rate': rates['success'] / total if total > 0 else 0,
            'total_executions': total,
            'success_count': rates['success'],
            'failure_count': rates['failure'],
        }

    def get_overall_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics across all metrics.

        Returns:
            Dictionary of overall statistics
        """
        stats = {
            'agents': {},
            'rca_workflow': {},
            'signals': dict(self.signal_counts),
            'findings': {},
            'timestamp': datetime.utcnow().isoformat(),
        }

        # Agent stats
        for agent_name in self.agent_execution_times.keys():
            agent_stats = self.get_agent_stats(agent_name)
            if agent_stats:
                stats['agents'][agent_name] = agent_stats

        # RCA workflow stats
        if self.rca_durations:
            stats['rca_workflow'] = {
                'avg_duration_seconds': statistics.mean(self.rca_durations),
                'min_duration_seconds': min(self.rca_durations),
                'max_duration_seconds': max(self.rca_durations),
                'p95_duration_seconds': self._calculate_percentile(self.rca_durations, 0.95),
                'p99_duration_seconds': self._calculate_percentile(self.rca_durations, 0.99),
                'total_rcas': len(self.rca_durations),
            }

        # Finding stats
        if self.finding_confidences:
            stats['findings'] = {
                'avg_confidence': statistics.mean(self.finding_confidences),
                'min_confidence': min(self.finding_confidences),
                'max_confidence': max(self.finding_confidences),
                'total_findings': len(self.finding_confidences),
                'high_confidence_count': len([c for c in self.finding_confidences if c >= 0.8]),
            }

        return stats

    def _calculate_percentile(self, values: List[float], percentile: float) -> float:
        """
        Calculate percentile value.

        Args:
            values: List of values
            percentile: Percentile to calculate (0.0 to 1.0)

        Returns:
            Percentile value
        """
        if not values:
            return 0.0

        if len(values) == 1:
            return values[0]

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def export_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines = []

        # Agent execution times
        for agent_name, times in self.agent_execution_times.items():
            if times:
                lines.append(f'# HELP adapt_agent_duration_seconds Agent execution duration')
                lines.append(f'# TYPE adapt_agent_duration_seconds summary')
                avg_time = statistics.mean(times)
                lines.append(f'adapt_agent_duration_seconds{{agent="{agent_name}"}} {avg_time}')

        # Agent success rates
        for agent_name, rates in self.agent_success_rates.items():
            total = rates['success'] + rates['failure']
            if total > 0:
                success_rate = rates['success'] / total
                lines.append(f'# HELP adapt_agent_success_rate Agent success rate')
                lines.append(f'# TYPE adapt_agent_success_rate gauge')
                lines.append(f'adapt_agent_success_rate{{agent="{agent_name}"}} {success_rate}')

        # RCA durations
        if self.rca_durations:
            avg_duration = statistics.mean(self.rca_durations)
            lines.append(f'# HELP adapt_rca_duration_seconds RCA workflow duration')
            lines.append(f'# TYPE adapt_rca_duration_seconds summary')
            lines.append(f'adapt_rca_duration_seconds {avg_duration}')

        return '\n'.join(lines)

    def to_json(self, indent: int = 2) -> str:
        """
        Export metrics as JSON.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string of all metrics
        """
        return json.dumps(self.get_overall_stats(), indent=indent)

    def reset(self):
        """Reset all metrics"""
        self.agent_execution_times.clear()
        self.agent_success_rates.clear()
        self.rca_durations.clear()
        self.signal_counts.clear()
        self.finding_confidences.clear()


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    return _metrics_collector
