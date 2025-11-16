"""
Change Correlator Agent

Correlates configuration changes, deployments, and infrastructure
changes with incident symptoms to identify potential root causes.
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta

from .base import BaseAgent, AgentResult
from core.signal_normalizer import SignalType


class ChangeCorrelatorAgent(BaseAgent):
    """
    Agent specialized in correlating changes with incidents.

    This agent:
    1. Identifies recent changes (config, deployments, infrastructure)
    2. Correlates change timing with symptom onset
    3. Analyzes change impact scope
    4. Detects rollback opportunities
    5. Identifies change clusters (multiple simultaneous changes)
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the change correlator agent."""
        super().__init__(name='change_correlator', config=config)
        self.correlation_window = timedelta(minutes=30)  # Look for changes within 30 min of symptoms

    async def execute(self, context: Any) -> AgentResult:
        """
        Execute change correlation analysis.

        Args:
            context: OrchestrationContext with signals

        Returns:
            AgentResult with findings about change correlations
        """
        start_time = datetime.utcnow()

        try:
            findings = []
            hypotheses = []

            # Get change signals
            change_signals = [s for s in context.signals if s.signal_type == SignalType.CONFIG_CHANGE]

            if not change_signals:
                return AgentResult(
                    agent_name=self.name,
                    metadata={'message': 'No configuration changes to correlate'},
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                )

            # Get symptom onset time
            symptoms = context.graph.get_nodes_by_type(
                __import__('core.rca_graph', fromlist=['NodeType']).NodeType.SYMPTOM
            ) if hasattr(context, 'graph') else []

            symptom_times = []
            if symptoms:
                symptom_times = [
                    datetime.fromisoformat(s.metadata.get('timestamp', s.created_at.isoformat()))
                    for s in symptoms
                ]

            # Analysis 1: Temporal correlation
            temporal_findings = self._correlate_temporal(change_signals, symptom_times)
            findings.extend(temporal_findings)

            # Analysis 2: Change clusters
            cluster_findings = self._detect_change_clusters(change_signals)
            findings.extend(cluster_findings)

            # Analysis 3: High-risk changes
            risk_findings = self._identify_high_risk_changes(change_signals)
            findings.extend(risk_findings)

            # Analysis 4: Rollback opportunities
            rollback_findings = self._identify_rollback_opportunities(change_signals, symptom_times)
            findings.extend(rollback_findings)

            # Generate hypotheses
            if temporal_findings:
                hypotheses.append(
                    self._create_hypothesis(
                        hypothesis_id='change_hyp_1',
                        title='Recent change may have triggered the incident',
                        description='Configuration or deployment changes coincide with symptom onset',
                        requires_tests=['validate_change_impact', 'test_rollback_scenario'],
                    )
                )

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                findings=findings,
                hypotheses=hypotheses,
                metadata={
                    'total_changes': len(change_signals),
                    'changes_in_correlation_window': len(temporal_findings),
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

    def _correlate_temporal(
        self,
        change_signals: List[Any],
        symptom_times: List[datetime]
    ) -> List[Dict[str, Any]]:
        """Correlate changes with symptom timing."""
        findings = []

        if not symptom_times:
            return findings

        earliest_symptom = min(symptom_times)

        # Find changes that occurred shortly before the first symptom
        correlated_changes = []
        for change in change_signals:
            time_diff = earliest_symptom - change.timestamp
            if timedelta(0) <= time_diff <= self.correlation_window:
                correlated_changes.append({
                    'change': change,
                    'time_before_symptom': time_diff.total_seconds(),
                })

        if correlated_changes:
            # Sort by proximity to symptom
            correlated_changes.sort(key=lambda x: x['time_before_symptom'])

            for item in correlated_changes:
                change = item['change']
                time_diff_minutes = item['time_before_symptom'] / 60

                findings.append(
                    self._create_finding(
                        finding_id=f'change_finding_temporal_{change.metadata.get("component")}',
                        title=f'Change detected before symptom onset: {change.metadata.get("component")}',
                        description=f'{change.description} occurred {time_diff_minutes:.1f} minutes before first symptom',
                        confidence=0.85 - (time_diff_minutes / 60),  # Higher confidence for more recent changes
                        metadata={
                            'component': change.metadata.get('component'),
                            'change_type': change.metadata.get('change_type'),
                            'change_timestamp': change.timestamp.isoformat(),
                            'symptom_timestamp': earliest_symptom.isoformat(),
                            'time_diff_minutes': time_diff_minutes,
                            'changed_by': change.metadata.get('changed_by'),
                        }
                    )
                )

        return findings

    def _detect_change_clusters(self, change_signals: List[Any]) -> List[Dict[str, Any]]:
        """Detect clusters of simultaneous or near-simultaneous changes."""
        findings = []

        if len(change_signals) < 2:
            return findings

        # Sort changes by timestamp
        sorted_changes = sorted(change_signals, key=lambda x: x.timestamp)

        # Find clusters (changes within 10 minutes of each other)
        cluster_window = timedelta(minutes=10)
        clusters = []
        current_cluster = [sorted_changes[0]]

        for i in range(1, len(sorted_changes)):
            if sorted_changes[i].timestamp - current_cluster[-1].timestamp <= cluster_window:
                current_cluster.append(sorted_changes[i])
            else:
                if len(current_cluster) >= 2:
                    clusters.append(current_cluster)
                current_cluster = [sorted_changes[i]]

        if len(current_cluster) >= 2:
            clusters.append(current_cluster)

        # Create findings for clusters
        for idx, cluster in enumerate(clusters):
            components = [c.metadata.get('component', 'unknown') for c in cluster]
            findings.append(
                self._create_finding(
                    finding_id=f'change_finding_cluster_{idx}',
                    title=f'Change cluster detected: {len(cluster)} simultaneous changes',
                    description=f'Multiple changes occurred within a short time window: {", ".join(components)}',
                    confidence=0.75,
                    metadata={
                        'cluster_size': len(cluster),
                        'components': components,
                        'time_span_minutes': (cluster[-1].timestamp - cluster[0].timestamp).total_seconds() / 60,
                        'first_change': cluster[0].timestamp.isoformat(),
                        'last_change': cluster[-1].timestamp.isoformat(),
                    }
                )
            )

        return findings

    def _identify_high_risk_changes(self, change_signals: List[Any]) -> List[Dict[str, Any]]:
        """Identify changes to high-risk components."""
        findings = []

        # Define high-risk components
        high_risk_components = {
            'database', 'cache-layer', 'api-gateway', 'auth-service',
            'load-balancer', 'networking', 'security'
        }

        for change in change_signals:
            component = change.metadata.get('component', '').lower()

            # Check if component or any part of it matches high-risk components
            if any(risk_comp in component for risk_comp in high_risk_components):
                findings.append(
                    self._create_finding(
                        finding_id=f'change_finding_high_risk_{component}',
                        title=f'High-risk component changed: {component}',
                        description=f'Change to critical component {component} detected',
                        confidence=0.8,
                        metadata={
                            'component': component,
                            'change_type': change.metadata.get('change_type'),
                            'timestamp': change.timestamp.isoformat(),
                            'changed_by': change.metadata.get('changed_by'),
                        }
                    )
                )

        return findings

    def _identify_rollback_opportunities(
        self,
        change_signals: List[Any],
        symptom_times: List[datetime]
    ) -> List[Dict[str, Any]]:
        """Identify recent changes that could potentially be rolled back."""
        findings = []

        if not symptom_times:
            return findings

        earliest_symptom = min(symptom_times)

        # Find recent changes that have before/after states
        rollback_candidates = []
        for change in change_signals:
            if change.timestamp < earliest_symptom:
                before = change.metadata.get('before')
                after = change.metadata.get('after')

                if before and after:
                    rollback_candidates.append({
                        'change': change,
                        'component': change.metadata.get('component'),
                        'before': before,
                        'after': after,
                    })

        if rollback_candidates:
            findings.append(
                self._create_finding(
                    finding_id='change_finding_rollback_opportunities',
                    title=f'{len(rollback_candidates)} rollback opportunities identified',
                    description=f'Found {len(rollback_candidates)} changes with rollback capability',
                    confidence=0.7,
                    metadata={
                        'rollback_count': len(rollback_candidates),
                        'components': [rc['component'] for rc in rollback_candidates],
                        'changes': [
                            {
                                'component': rc['component'],
                                'before': rc['before'],
                                'after': rc['after'],
                                'timestamp': rc['change'].timestamp.isoformat(),
                            }
                            for rc in rollback_candidates
                        ],
                    }
                )
            )

        return findings
