"""
Topology Explainer Agent

Analyzes system topology and service dependencies to understand
how issues propagate through the architecture.
"""

from typing import Dict, List, Any, Set
from datetime import datetime
from collections import defaultdict

from .base import BaseAgent, AgentResult


class TopologyExplainerAgent(BaseAgent):
    """
    Agent specialized in analyzing system topology and dependencies.

    This agent:
    1. Maps service dependencies
    2. Identifies critical paths
    3. Analyzes failure propagation
    4. Detects single points of failure
    5. Explains cascading failures
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the topology explainer agent."""
        super().__init__(name='topology_explainer', config=config)
        self.topology_map = self._load_topology_map(config)

    def _load_topology_map(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Load service topology map.

        In production, this would load from a service mesh, config management,
        or discovery service. For now, we use a static example topology.
        """
        if config and 'topology_map' in config:
            return config['topology_map']

        # Default example topology
        return {
            'services': {
                'api-gateway': {
                    'type': 'gateway',
                    'dependencies': ['auth-service', 'order-service', 'user-service'],
                    'criticality': 'high',
                },
                'auth-service': {
                    'type': 'service',
                    'dependencies': ['database', 'cache-layer'],
                    'criticality': 'high',
                },
                'order-service': {
                    'type': 'service',
                    'dependencies': ['database', 'payment-service', 'inventory-service'],
                    'criticality': 'high',
                },
                'user-service': {
                    'type': 'service',
                    'dependencies': ['database', 'cache-layer'],
                    'criticality': 'medium',
                },
                'payment-service': {
                    'type': 'service',
                    'dependencies': ['external-payment-api'],
                    'criticality': 'high',
                },
                'inventory-service': {
                    'type': 'service',
                    'dependencies': ['database'],
                    'criticality': 'medium',
                },
                'database': {
                    'type': 'datastore',
                    'dependencies': [],
                    'criticality': 'critical',
                },
                'cache-layer': {
                    'type': 'cache',
                    'dependencies': [],
                    'criticality': 'high',
                },
            }
        }

    async def execute(self, context: Any) -> AgentResult:
        """
        Execute topology analysis.

        Args:
            context: OrchestrationContext with signals

        Returns:
            AgentResult with findings about topology and dependencies
        """
        start_time = datetime.utcnow()

        try:
            findings = []
            hypotheses = []

            # Extract affected services from signals
            affected_services = self._extract_affected_services(context.signals)

            if not affected_services:
                return AgentResult(
                    agent_name=self.name,
                    metadata={'message': 'No affected services identified'},
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                )

            # Analysis 1: Identify root services
            root_services = self._identify_root_services(affected_services)
            if root_services:
                findings.extend(root_services)

            # Analysis 2: Analyze failure propagation
            propagation = self._analyze_failure_propagation(affected_services)
            if propagation:
                findings.extend(propagation)

            # Analysis 3: Identify critical path issues
            critical_path = self._analyze_critical_paths(affected_services)
            if critical_path:
                findings.extend(critical_path)

            # Analysis 4: Detect single points of failure
            spof = self._detect_single_points_of_failure(affected_services)
            if spof:
                findings.extend(spof)

            # Generate hypotheses
            if root_services:
                hypotheses.append(
                    self._create_hypothesis(
                        hypothesis_id='topology_hyp_1',
                        title='Upstream service failure causing cascading issues',
                        description='Issues in foundational services may be causing downstream failures',
                        requires_tests=['check_service_health', 'check_dependency_chain'],
                    )
                )

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                findings=findings,
                hypotheses=hypotheses,
                metadata={
                    'affected_services': list(affected_services),
                    'total_services': len(self.topology_map.get('services', {})),
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

    def _extract_affected_services(self, signals: List[Any]) -> Set[str]:
        """Extract set of affected services from signals."""
        affected = set()
        for signal in signals:
            source = signal.source
            # Clean up source to match topology map keys
            service_name = source.split('.')[0] if '.' in source else source
            affected.add(service_name)
        return affected

    def _identify_root_services(self, affected_services: Set[str]) -> List[Dict[str, Any]]:
        """Identify services that are dependencies of other affected services."""
        findings = []
        services_map = self.topology_map.get('services', {})

        # Find services that are dependencies of affected services
        root_services = set()
        for service in affected_services:
            if service in services_map:
                deps = services_map[service].get('dependencies', [])
                for dep in deps:
                    if dep in affected_services:
                        root_services.add(dep)

        if root_services:
            findings.append(
                self._create_finding(
                    finding_id='topology_finding_root_services',
                    title='Root services identified',
                    description=f'Found {len(root_services)} foundational services that may be causing downstream issues: {", ".join(root_services)}',
                    confidence=0.8,
                    metadata={
                        'root_services': list(root_services),
                        'affected_dependents': [
                            s for s in affected_services
                            if any(dep in root_services for dep in services_map.get(s, {}).get('dependencies', []))
                        ],
                    }
                )
            )

        return findings

    def _analyze_failure_propagation(self, affected_services: Set[str]) -> List[Dict[str, Any]]:
        """Analyze how failures might propagate through the topology."""
        findings = []
        services_map = self.topology_map.get('services', {})

        # Build reverse dependency map (who depends on whom)
        dependents = defaultdict(list)
        for service, config in services_map.items():
            for dep in config.get('dependencies', []):
                dependents[dep].append(service)

        # Identify propagation chains
        for affected in affected_services:
            if affected in dependents:
                downstream = dependents[affected]
                downstream_affected = [s for s in downstream if s in affected_services]

                if downstream_affected:
                    findings.append(
                        self._create_finding(
                            finding_id=f'topology_finding_propagation_{affected}',
                            title=f'Failure propagation from {affected}',
                            description=f'{affected} failure propagated to {len(downstream_affected)} downstream services',
                            confidence=0.75,
                            metadata={
                                'source_service': affected,
                                'affected_downstream': downstream_affected,
                                'total_downstream': len(downstream),
                            }
                        )
                    )

        return findings

    def _analyze_critical_paths(self, affected_services: Set[str]) -> List[Dict[str, Any]]:
        """Identify if critical services are affected."""
        findings = []
        services_map = self.topology_map.get('services', {})

        critical_affected = [
            service for service in affected_services
            if services_map.get(service, {}).get('criticality') in ['high', 'critical']
        ]

        if critical_affected:
            findings.append(
                self._create_finding(
                    finding_id='topology_finding_critical_services',
                    title='Critical services affected',
                    description=f'{len(critical_affected)} critical services are experiencing issues',
                    confidence=0.9,
                    metadata={
                        'critical_services': critical_affected,
                        'criticality_levels': {
                            s: services_map[s].get('criticality')
                            for s in critical_affected if s in services_map
                        },
                    }
                )
            )

        return findings

    def _detect_single_points_of_failure(self, affected_services: Set[str]) -> List[Dict[str, Any]]:
        """Detect if single points of failure are affected."""
        findings = []
        services_map = self.topology_map.get('services', {})

        # Build dependency count
        dependents = defaultdict(int)
        for service, config in services_map.items():
            for dep in config.get('dependencies', []):
                dependents[dep] += 1

        # Identify services that many others depend on
        spofs = {
            service: count for service, count in dependents.items()
            if count >= 3 and service in affected_services
        }

        if spofs:
            for service, dependent_count in spofs.items():
                findings.append(
                    self._create_finding(
                        finding_id=f'topology_finding_spof_{service}',
                        title=f'Single point of failure affected: {service}',
                        description=f'{service} is a critical dependency for {dependent_count} services',
                        confidence=0.85,
                        metadata={
                            'service': service,
                            'dependent_count': dependent_count,
                        }
                    )
                )

        return findings
