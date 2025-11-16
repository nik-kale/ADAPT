"""
Log Analyzer Agent

Analyzes log signals to identify error patterns, anomalies, and correlations.
"""

import re
from typing import Dict, List, Any
from datetime import datetime, timedelta
from collections import Counter, defaultdict

from .base import BaseAgent, AgentResult
from core.signal_normalizer import SignalType


class LogAnalyzerAgent(BaseAgent):
    """
    Agent specialized in analyzing log data for RCA.

    This agent:
    1. Identifies error patterns and spikes
    2. Detects anomalous log patterns
    3. Correlates errors across services
    4. Extracts stack traces and error codes
    5. Identifies temporal patterns (e.g., errors started at specific time)
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the log analyzer agent."""
        super().__init__(name='log_analyzer', config=config)
        self.error_patterns = self._load_error_patterns()

    def _load_error_patterns(self) -> List[Dict[str, Any]]:
        """Load common error patterns to look for."""
        return [
            {
                'pattern': r'connection.*timeout',
                'category': 'connectivity',
                'severity': 'high',
            },
            {
                'pattern': r'out of memory|oom',
                'category': 'resource',
                'severity': 'critical',
            },
            {
                'pattern': r'authentication.*failed',
                'category': 'auth',
                'severity': 'high',
            },
            {
                'pattern': r'database.*error|sql.*exception',
                'category': 'database',
                'severity': 'high',
            },
            {
                'pattern': r'rate limit.*exceeded',
                'category': 'throttling',
                'severity': 'medium',
            },
            {
                'pattern': r'disk.*full|no space left',
                'category': 'resource',
                'severity': 'critical',
            },
        ]

    async def execute(self, context: Any) -> AgentResult:
        """
        Execute log analysis.

        Args:
            context: OrchestrationContext with signals

        Returns:
            AgentResult with findings about log patterns
        """
        start_time = datetime.utcnow()

        try:
            # Filter log signals
            log_signals = [s for s in context.signals if s.signal_type == SignalType.LOG]

            if not log_signals:
                return AgentResult(
                    agent_name=self.name,
                    metadata={'message': 'No log signals to analyze'},
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                )

            findings = []
            hypotheses = []

            # Analysis 1: Error rate spike detection
            error_spike_findings = self._detect_error_spikes(log_signals)
            findings.extend(error_spike_findings)

            # Analysis 2: Pattern matching
            pattern_findings = self._analyze_error_patterns(log_signals)
            findings.extend(pattern_findings)

            # Analysis 3: Temporal correlation
            temporal_findings = self._analyze_temporal_patterns(log_signals)
            findings.extend(temporal_findings)

            # Analysis 4: Service correlation
            service_findings = self._analyze_service_correlation(log_signals)
            findings.extend(service_findings)

            # Generate hypotheses based on findings
            if error_spike_findings:
                hypotheses.append(
                    self._create_hypothesis(
                        hypothesis_id='log_hyp_1',
                        title='Sudden increase in error rate',
                        description='A spike in error logs suggests a recent change or incident',
                        requires_tests=['check_recent_deployments', 'check_infrastructure_changes'],
                    )
                )

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                findings=findings,
                hypotheses=hypotheses,
                metadata={
                    'total_logs_analyzed': len(log_signals),
                    'error_logs': len([s for s in log_signals if s.severity in ['high', 'critical']]),
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

    def _detect_error_spikes(self, log_signals: List[Any]) -> List[Dict[str, Any]]:
        """Detect spikes in error rates."""
        findings = []

        # Group logs by time buckets (e.g., 5-minute intervals)
        time_buckets = defaultdict(list)
        for signal in log_signals:
            bucket = signal.timestamp.replace(second=0, microsecond=0)
            bucket = bucket.replace(minute=(bucket.minute // 5) * 5)
            time_buckets[bucket].append(signal)

        # Calculate error rates per bucket
        error_rates = {}
        for bucket, signals in time_buckets.items():
            error_count = len([s for s in signals if s.severity in ['high', 'critical']])
            error_rates[bucket] = error_count / len(signals) if signals else 0

        # Detect spikes (error rate > 2x average)
        if error_rates:
            avg_error_rate = sum(error_rates.values()) / len(error_rates)
            for bucket, rate in error_rates.items():
                if rate > avg_error_rate * 2 and rate > 0.1:  # At least 10% errors
                    findings.append(
                        self._create_finding(
                            finding_id=f'log_finding_spike_{bucket.isoformat()}',
                            title='Error rate spike detected',
                            description=f'Error rate spiked to {rate:.1%} at {bucket.isoformat()} (avg: {avg_error_rate:.1%})',
                            confidence=0.8,
                            metadata={
                                'timestamp': bucket.isoformat(),
                                'error_rate': rate,
                                'average_error_rate': avg_error_rate,
                            }
                        )
                    )

        return findings

    def _analyze_error_patterns(self, log_signals: List[Any]) -> List[Dict[str, Any]]:
        """Analyze logs for known error patterns."""
        findings = []

        error_logs = [s for s in log_signals if s.severity in ['high', 'critical']]

        # Count pattern matches
        pattern_matches = defaultdict(list)
        for signal in error_logs:
            message = signal.description.lower()
            for pattern_def in self.error_patterns:
                if re.search(pattern_def['pattern'], message, re.IGNORECASE):
                    pattern_matches[pattern_def['category']].append(signal)

        # Create findings for significant patterns
        for category, matching_signals in pattern_matches.items():
            if len(matching_signals) >= 3:  # Threshold: at least 3 occurrences
                pattern_def = next(p for p in self.error_patterns if p['category'] == category)
                findings.append(
                    self._create_finding(
                        finding_id=f'log_finding_pattern_{category}',
                        title=f'{category.capitalize()} errors detected',
                        description=f'Found {len(matching_signals)} {category}-related errors',
                        confidence=0.7,
                        metadata={
                            'category': category,
                            'count': len(matching_signals),
                            'pattern': pattern_def['pattern'],
                            'example_messages': [s.description for s in matching_signals[:3]],
                        }
                    )
                )

        return findings

    def _analyze_temporal_patterns(self, log_signals: List[Any]) -> List[Dict[str, Any]]:
        """Analyze temporal patterns in logs."""
        findings = []

        error_logs = [s for s in log_signals if s.severity in ['high', 'critical']]

        if error_logs:
            # Find first error occurrence
            first_error = min(error_logs, key=lambda s: s.timestamp)
            findings.append(
                self._create_finding(
                    finding_id='log_finding_first_error',
                    title='First error timestamp identified',
                    description=f'First error occurred at {first_error.timestamp.isoformat()}: {first_error.description[:100]}',
                    confidence=0.9,
                    metadata={
                        'first_error_time': first_error.timestamp.isoformat(),
                        'first_error_message': first_error.description,
                        'first_error_source': first_error.source,
                    }
                )
            )

        return findings

    def _analyze_service_correlation(self, log_signals: List[Any]) -> List[Dict[str, Any]]:
        """Analyze correlation of errors across services."""
        findings = []

        # Group errors by source/service
        errors_by_source = defaultdict(list)
        for signal in log_signals:
            if signal.severity in ['high', 'critical']:
                errors_by_source[signal.source].append(signal)

        # Identify services with multiple errors
        affected_services = {
            source: logs for source, logs in errors_by_source.items()
            if len(logs) >= 2
        }

        if len(affected_services) > 1:
            findings.append(
                self._create_finding(
                    finding_id='log_finding_multi_service',
                    title='Multiple services affected',
                    description=f'{len(affected_services)} services showing errors',
                    confidence=0.75,
                    metadata={
                        'affected_services': list(affected_services.keys()),
                        'error_counts': {k: len(v) for k, v in affected_services.items()},
                    }
                )
            )

        return findings
