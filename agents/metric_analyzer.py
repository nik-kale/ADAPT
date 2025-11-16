"""
Metric Analyzer Agent

Analyzes metric signals to identify anomalies, trends, and threshold breaches.
"""

from typing import Dict, List, Any
from datetime import datetime
from collections import defaultdict
import statistics

from .base import BaseAgent, AgentResult
from core.signal_normalizer import SignalType


class MetricAnalyzerAgent(BaseAgent):
    """
    Agent specialized in analyzing metric data for RCA.

    This agent:
    1. Detects metric anomalies (spikes, drops, flatlines)
    2. Identifies threshold breaches
    3. Analyzes metric trends
    4. Correlates related metrics
    5. Identifies cascading metric failures
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the metric analyzer agent."""
        super().__init__(name='metric_analyzer', config=config)
        self.anomaly_threshold = config.get('anomaly_threshold', 2.0) if config else 2.0

    async def execute(self, context: Any) -> AgentResult:
        """
        Execute metric analysis.

        Args:
            context: OrchestrationContext with signals

        Returns:
            AgentResult with findings about metric anomalies
        """
        start_time = datetime.utcnow()

        try:
            # Filter metric signals
            metric_signals = [s for s in context.signals if s.signal_type == SignalType.METRIC]

            if not metric_signals:
                return AgentResult(
                    agent_name=self.name,
                    metadata={'message': 'No metric signals to analyze'},
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                )

            findings = []
            hypotheses = []

            # Analysis 1: Anomaly detection
            anomaly_findings = self._detect_anomalies(metric_signals)
            findings.extend(anomaly_findings)

            # Analysis 2: Threshold breaches
            threshold_findings = self._detect_threshold_breaches(metric_signals)
            findings.extend(threshold_findings)

            # Analysis 3: Trend analysis
            trend_findings = self._analyze_trends(metric_signals)
            findings.extend(trend_findings)

            # Analysis 4: Metric correlation
            correlation_findings = self._analyze_metric_correlation(metric_signals)
            findings.extend(correlation_findings)

            # Generate hypotheses
            if anomaly_findings:
                hypotheses.append(
                    self._create_hypothesis(
                        hypothesis_id='metric_hyp_1',
                        title='Performance degradation detected',
                        description='Metric anomalies suggest performance issues',
                        requires_tests=['check_resource_utilization', 'check_scaling_policies'],
                    )
                )

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                findings=findings,
                hypotheses=hypotheses,
                metadata={
                    'total_metrics_analyzed': len(metric_signals),
                    'unique_metric_names': len(set(s.metadata.get('metric_name') for s in metric_signals)),
                },
                execution_time=execution_time,
                success=True,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                execution_time=execution_time,
                success=False,
                error=str(e),
            )

    def _detect_anomalies(self, metric_signals: List[Any]) -> List[Dict[str, Any]]:
        """Detect anomalies in metric values using statistical methods."""
        findings = []

        # Group metrics by name
        metrics_by_name = defaultdict(list)
        for signal in metric_signals:
            metric_name = signal.metadata.get('metric_name', 'unknown')
            value = signal.metadata.get('value', 0)
            metrics_by_name[metric_name].append({
                'timestamp': signal.timestamp,
                'value': value,
                'signal': signal,
            })

        # Analyze each metric
        for metric_name, data_points in metrics_by_name.items():
            if len(data_points) < 3:
                continue

            values = [dp['value'] for dp in data_points]
            mean = statistics.mean(values)
            stdev = statistics.stdev(values) if len(values) > 1 else 0

            # Find anomalies (values > threshold * stdev from mean)
            for dp in data_points:
                if stdev > 0:
                    z_score = abs((dp['value'] - mean) / stdev)
                    if z_score > self.anomaly_threshold:
                        findings.append(
                            self._create_finding(
                                finding_id=f'metric_finding_anomaly_{metric_name}_{dp["timestamp"].isoformat()}',
                                title=f'Anomaly detected in {metric_name}',
                                description=f'{metric_name} = {dp["value"]:.2f} (mean: {mean:.2f}, stdev: {stdev:.2f}, z-score: {z_score:.2f})',
                                confidence=min(0.9, 0.5 + (z_score / 10)),
                                metadata={
                                    'metric_name': metric_name,
                                    'value': dp['value'],
                                    'mean': mean,
                                    'stdev': stdev,
                                    'z_score': z_score,
                                    'timestamp': dp['timestamp'].isoformat(),
                                }
                            )
                        )

        return findings

    def _detect_threshold_breaches(self, metric_signals: List[Any]) -> List[Dict[str, Any]]:
        """Detect metrics that exceed their thresholds."""
        findings = []

        high_severity_metrics = [s for s in metric_signals if s.severity in ['high', 'critical']]

        for signal in high_severity_metrics:
            metric_name = signal.metadata.get('metric_name', 'unknown')
            value = signal.metadata.get('value', 0)

            findings.append(
                self._create_finding(
                    finding_id=f'metric_finding_threshold_{metric_name}_{signal.timestamp.isoformat()}',
                    title=f'Threshold breach: {metric_name}',
                    description=f'{metric_name} exceeded threshold with value {value}',
                    confidence=0.85,
                    metadata={
                        'metric_name': metric_name,
                        'value': value,
                        'severity': signal.severity,
                        'timestamp': signal.timestamp.isoformat(),
                    }
                )
            )

        return findings

    def _analyze_trends(self, metric_signals: List[Any]) -> List[Dict[str, Any]]:
        """Analyze trends in metrics over time."""
        findings = []

        # Group metrics by name
        metrics_by_name = defaultdict(list)
        for signal in metric_signals:
            metric_name = signal.metadata.get('metric_name', 'unknown')
            metrics_by_name[metric_name].append({
                'timestamp': signal.timestamp,
                'value': signal.metadata.get('value', 0),
            })

        # Analyze trends
        for metric_name, data_points in metrics_by_name.items():
            if len(data_points) < 5:
                continue

            # Sort by timestamp
            data_points.sort(key=lambda x: x['timestamp'])
            values = [dp['value'] for dp in data_points]

            # Simple trend detection: compare first half vs second half
            mid = len(values) // 2
            first_half_avg = statistics.mean(values[:mid])
            second_half_avg = statistics.mean(values[mid:])

            if first_half_avg > 0:
                change_percent = ((second_half_avg - first_half_avg) / first_half_avg) * 100

                # Report significant trends (>20% change)
                if abs(change_percent) > 20:
                    trend_direction = 'increasing' if change_percent > 0 else 'decreasing'
                    findings.append(
                        self._create_finding(
                            finding_id=f'metric_finding_trend_{metric_name}',
                            title=f'{metric_name} is {trend_direction}',
                            description=f'{metric_name} changed by {change_percent:.1f}% over the analysis period',
                            confidence=0.7,
                            metadata={
                                'metric_name': metric_name,
                                'trend_direction': trend_direction,
                                'change_percent': change_percent,
                                'first_half_avg': first_half_avg,
                                'second_half_avg': second_half_avg,
                            }
                        )
                    )

        return findings

    def _analyze_metric_correlation(self, metric_signals: List[Any]) -> List[Dict[str, Any]]:
        """Analyze correlation between related metrics."""
        findings = []

        # Define metric relationships to check
        correlation_pairs = [
            ('cpu_usage_percent', 'http_request_latency_ms'),
            ('memory_usage_percent', 'error_rate_percent'),
            ('requests_per_second', 'cpu_usage_percent'),
        ]

        # Group metrics by name
        metrics_by_name = defaultdict(list)
        for signal in metric_signals:
            metric_name = signal.metadata.get('metric_name', 'unknown')
            metrics_by_name[metric_name].append(signal)

        # Check for simultaneous spikes in correlated metrics
        for metric1_name, metric2_name in correlation_pairs:
            if metric1_name in metrics_by_name and metric2_name in metrics_by_name:
                high_metric1 = [s for s in metrics_by_name[metric1_name] if s.severity in ['high', 'critical']]
                high_metric2 = [s for s in metrics_by_name[metric2_name] if s.severity in ['high', 'critical']]

                if high_metric1 and high_metric2:
                    findings.append(
                        self._create_finding(
                            finding_id=f'metric_finding_correlation_{metric1_name}_{metric2_name}',
                            title=f'Correlated metrics affected: {metric1_name} and {metric2_name}',
                            description=f'Both {metric1_name} and {metric2_name} showing anomalies',
                            confidence=0.8,
                            metadata={
                                'metric1': metric1_name,
                                'metric2': metric2_name,
                                'metric1_anomalies': len(high_metric1),
                                'metric2_anomalies': len(high_metric2),
                            }
                        )
                    )

        return findings
