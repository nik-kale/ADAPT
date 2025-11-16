"""
RCA Orchestration Engine

Coordinates multiple diagnostic agents, manages the RCA workflow,
and aggregates findings into the RCA graph.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import logging

from .rca_graph import RCAGraph, RCANode, RCAEdge, NodeType, EdgeType
from .config import ADAPTConfig
from .signal_normalizer import NormalizedSignal

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationContext:
    """
    Context object that holds state during an RCA orchestration session.

    Attributes:
        incident_id: Unique identifier for the incident
        graph: The RCA graph being built
        signals: Normalized input signals (logs, metrics, traces)
        agent_results: Results from each diagnostic agent
        start_time: When orchestration began
        end_time: When orchestration completed
        metadata: Additional context
    """
    incident_id: str
    graph: RCAGraph
    signals: List[NormalizedSignal] = field(default_factory=list)
    agent_results: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class RCAOrchestrator:
    """
    The main orchestration engine that coordinates RCA workflow.

    This orchestrator:
    1. Accepts input signals (logs, metrics, traces, config changes)
    2. Routes signals to appropriate diagnostic agents
    3. Aggregates agent findings into the RCA graph
    4. Manages execution flow (sequential, parallel, or adaptive)
    5. Invokes remediation planning
    """

    def __init__(self, config: ADAPTConfig):
        """
        Initialize the orchestrator.

        Args:
            config: ADAPT configuration object
        """
        self.config = config
        self.agents: Dict[str, Any] = {}  # Will hold agent instances
        self.execution_mode = config.execution_mode  # 'sequential', 'parallel', 'adaptive'

    def register_agent(self, agent_name: str, agent_instance: Any) -> None:
        """
        Register a diagnostic agent with the orchestrator.

        Args:
            agent_name: Unique name for the agent
            agent_instance: The agent instance (must implement execute() method)
        """
        self.agents[agent_name] = agent_instance
        logger.info(f"Registered agent: {agent_name}")

    async def run_rca(
        self,
        incident_id: str,
        signals: List[NormalizedSignal],
        playbook: Optional[Dict[str, Any]] = None
    ) -> OrchestrationContext:
        """
        Execute the complete RCA workflow.

        Args:
            incident_id: Unique identifier for the incident
            signals: List of normalized input signals
            playbook: Optional playbook to guide the RCA process

        Returns:
            OrchestrationContext containing the completed RCA graph
        """
        logger.info(f"Starting RCA for incident: {incident_id}")

        # Initialize context
        graph = RCAGraph(incident_id)
        context = OrchestrationContext(
            incident_id=incident_id,
            graph=graph,
            signals=signals,
            metadata={'playbook': playbook.get('name') if playbook else None}
        )

        # Phase 1: Initial symptom identification
        await self._identify_symptoms(context)

        # Phase 2: Run diagnostic agents
        if self.execution_mode == 'sequential':
            await self._run_agents_sequential(context)
        elif self.execution_mode == 'parallel':
            await self._run_agents_parallel(context)
        else:  # adaptive
            await self._run_agents_adaptive(context)

        # Phase 3: Synthesize findings
        await self._synthesize_findings(context)

        # Phase 4: Identify root causes
        await self._identify_root_causes(context)

        # Phase 5: Generate remediation plan
        if 'remediation_planner' in self.agents:
            await self._generate_remediation_plan(context)

        context.end_time = datetime.utcnow()
        logger.info(f"RCA completed for incident: {incident_id}")

        return context

    async def _identify_symptoms(self, context: OrchestrationContext) -> None:
        """
        Identify initial symptoms from input signals.

        Args:
            context: The orchestration context
        """
        logger.info("Identifying symptoms from signals")

        # Group signals by type and severity
        high_severity_signals = [s for s in context.signals if s.severity == 'high']

        for i, signal in enumerate(high_severity_signals):
            symptom = RCANode(
                id=f"symptom_{i}",
                type=NodeType.SYMPTOM,
                title=signal.title,
                description=signal.description,
                metadata={
                    'signal_type': signal.signal_type,
                    'source': signal.source,
                    'timestamp': signal.timestamp.isoformat(),
                    'severity': signal.severity,
                }
            )
            context.graph.add_node(symptom)

        logger.info(f"Identified {len(high_severity_signals)} symptoms")

    async def _run_agents_sequential(self, context: OrchestrationContext) -> None:
        """
        Run diagnostic agents sequentially.

        Args:
            context: The orchestration context
        """
        logger.info("Running agents sequentially")

        for agent_name, agent in self.agents.items():
            if agent_name == 'remediation_planner':
                continue  # Skip remediation planner in diagnostic phase

            logger.info(f"Executing agent: {agent_name}")
            try:
                result = await agent.execute(context)
                context.agent_results[agent_name] = result
            except Exception as e:
                logger.error(f"Agent {agent_name} failed: {e}")
                context.agent_results[agent_name] = {'error': str(e)}

    async def _run_agents_parallel(self, context: OrchestrationContext) -> None:
        """
        Run diagnostic agents in parallel.

        Args:
            context: The orchestration context
        """
        logger.info("Running agents in parallel")

        tasks = []
        agent_names = []

        for agent_name, agent in self.agents.items():
            if agent_name == 'remediation_planner':
                continue

            agent_names.append(agent_name)
            tasks.append(agent.execute(context))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for agent_name, result in zip(agent_names, results):
            if isinstance(result, Exception):
                logger.error(f"Agent {agent_name} failed: {result}")
                context.agent_results[agent_name] = {'error': str(result)}
            else:
                context.agent_results[agent_name] = result

    async def _run_agents_adaptive(self, context: OrchestrationContext) -> None:
        """
        Run agents adaptively based on intermediate results.

        Args:
            context: The orchestration context
        """
        logger.info("Running agents in adaptive mode")

        # Start with log analyzer and metric analyzer in parallel
        priority_agents = ['log_analyzer', 'metric_analyzer']
        for agent_name in priority_agents:
            if agent_name in self.agents:
                result = await self.agents[agent_name].execute(context)
                context.agent_results[agent_name] = result

        # Based on initial results, determine which agents to run next
        # TODO: Implement adaptive agent selection logic
        remaining_agents = [
            name for name in self.agents.keys()
            if name not in priority_agents and name != 'remediation_planner'
        ]

        for agent_name in remaining_agents:
            result = await self.agents[agent_name].execute(context)
            context.agent_results[agent_name] = result

    async def _synthesize_findings(self, context: OrchestrationContext) -> None:
        """
        Synthesize findings from all agent results.

        Args:
            context: The orchestration context
        """
        logger.info("Synthesizing findings from agent results")

        # Aggregate findings from all agents
        for agent_name, result in context.agent_results.items():
            if isinstance(result, dict) and 'findings' in result:
                for finding_data in result['findings']:
                    finding = RCANode(
                        id=finding_data.get('id', f"finding_{agent_name}_{len(context.graph.nodes)}"),
                        type=NodeType.FINDING,
                        title=finding_data.get('title', 'Untitled Finding'),
                        description=finding_data.get('description', ''),
                        confidence=finding_data.get('confidence', 0.5),
                        metadata={'agent': agent_name, **finding_data.get('metadata', {})}
                    )
                    context.graph.add_node(finding)

    async def _identify_root_causes(self, context: OrchestrationContext) -> None:
        """
        Identify root causes from findings and create causal links.

        Args:
            context: The orchestration context
        """
        logger.info("Identifying root causes")

        # Get all findings sorted by confidence
        findings = context.graph.get_nodes_by_type(NodeType.FINDING)
        high_confidence_findings = [f for f in findings if f.confidence >= 0.7]

        for finding in high_confidence_findings:
            # Promote high-confidence findings to root causes
            root_cause = RCANode(
                id=f"root_cause_{finding.id}",
                type=NodeType.ROOT_CAUSE,
                title=finding.title,
                description=finding.description,
                confidence=finding.confidence,
                metadata=finding.metadata
            )
            context.graph.add_node(root_cause)

            # Link to symptoms
            symptoms = context.graph.get_nodes_by_type(NodeType.SYMPTOM)
            for symptom in symptoms:
                edge = RCAEdge(
                    source=root_cause.id,
                    target=symptom.id,
                    type=EdgeType.CAUSES,
                    weight=finding.confidence,
                    metadata={'via_finding': finding.id}
                )
                context.graph.add_edge(edge)

    async def _generate_remediation_plan(self, context: OrchestrationContext) -> None:
        """
        Generate remediation plan using the remediation planner agent.

        Args:
            context: The orchestration context
        """
        logger.info("Generating remediation plan")

        if 'remediation_planner' in self.agents:
            planner = self.agents['remediation_planner']
            result = await planner.execute(context)
            context.agent_results['remediation_planner'] = result
