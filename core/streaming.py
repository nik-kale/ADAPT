"""
Real-time streaming support for ADAPT framework.

Enables streaming RCA updates as analysis progresses, suitable for
WebSocket connections, real-time dashboards, and progressive UIs.
"""

import asyncio
from typing import AsyncIterator, Callable, List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .orchestrator import RCAOrchestrator
from .rca_graph import RCAGraph
from .config import ADAPTConfig
from .signal_normalizer import NormalizedSignal


class UpdateType(Enum):
    """Types of streaming updates"""
    STARTED = "started"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    SYMPTOM_IDENTIFIED = "symptom_identified"
    FINDING = "finding"
    HYPOTHESIS = "hypothesis"
    ROOT_CAUSE = "root_cause"
    REMEDIATION_PLAN = "remediation_plan"
    PROGRESS = "progress"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class StreamingUpdate:
    """
    Real-time update from RCA analysis.

    Attributes:
        type: Type of update
        data: Update payload
        timestamp: When the update occurred
        progress_percent: Overall progress (0-100)
    """
    type: UpdateType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    progress_percent: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'type': self.type.value,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'progress_percent': self.progress_percent
        }


class StreamingOrchestrator(RCAOrchestrator):
    """
    Orchestrator that streams updates in real-time.

    Extends RCAOrchestrator to emit progress updates as the analysis
    proceeds, enabling real-time UIs and streaming APIs.
    """

    def __init__(self, config: ADAPTConfig):
        """
        Initialize streaming orchestrator.

        Args:
            config: ADAPT configuration
        """
        super().__init__(config)
        self.update_callbacks: List[Callable[[StreamingUpdate], Any]] = []

    def subscribe(self, callback: Callable[[StreamingUpdate], Any]):
        """
        Subscribe to real-time updates.

        Args:
            callback: Function to call with each update (can be async)
        """
        self.update_callbacks.append(callback)

    def unsubscribe(self, callback: Callable[[StreamingUpdate], Any]):
        """
        Unsubscribe from updates.

        Args:
            callback: The callback to remove
        """
        if callback in self.update_callbacks:
            self.update_callbacks.remove(callback)

    async def _emit_update(self, update: StreamingUpdate):
        """
        Emit update to all subscribers.

        Args:
            update: The update to emit
        """
        for callback in self.update_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(update)
                else:
                    callback(update)
            except Exception as e:
                # Log but don't fail on callback errors
                import logging
                logging.error(f"Error in update callback: {e}")

    async def run_rca_streaming(
        self,
        incident_id: str,
        signals: List[NormalizedSignal],
        playbook: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[StreamingUpdate]:
        """
        Run RCA and yield updates as they happen.

        Args:
            incident_id: Incident identifier
            signals: Input signals
            playbook: Optional playbook to guide analysis

        Yields:
            StreamingUpdate objects as analysis progresses
        """

        # Calculate total steps for progress tracking
        total_agents = len(self.agents)
        steps_per_agent = 100 // (total_agents + 2) if total_agents > 0 else 30
        current_progress = 0

        # Emit start
        yield StreamingUpdate(
            type=UpdateType.STARTED,
            data={
                'incident_id': incident_id,
                'total_signals': len(signals),
                'total_agents': total_agents,
                'playbook': playbook.get('name') if playbook else None
            },
            progress_percent=current_progress
        )

        # Create context
        graph = RCAGraph(incident_id)
        from .orchestrator import OrchestrationContext
        context = OrchestrationContext(
            incident_id=incident_id,
            graph=graph,
            signals=signals,
            metadata={'playbook': playbook.get('name') if playbook else None}
        )

        # Phase 1: Identify symptoms
        current_progress += steps_per_agent
        await self._identify_symptoms(context)

        symptoms = context.graph.get_nodes_by_type(
            __import__('core.rca_graph', fromlist=['NodeType']).NodeType.SYMPTOM
        )

        for symptom in symptoms:
            yield StreamingUpdate(
                type=UpdateType.SYMPTOM_IDENTIFIED,
                data={
                    'symptom': {
                        'id': symptom.id,
                        'title': symptom.title,
                        'description': symptom.description,
                        'severity': symptom.metadata.get('severity', 'unknown')
                    }
                },
                progress_percent=current_progress
            )

        # Phase 2: Run agents
        agent_progress_start = current_progress

        for i, (agent_name, agent) in enumerate(self.agents.items()):
            if agent_name == 'remediation_planner':
                continue  # Run remediation planner last

            # Emit agent started
            yield StreamingUpdate(
                type=UpdateType.AGENT_STARTED,
                data={'agent': agent_name},
                progress_percent=current_progress
            )

            # Execute agent
            result = await agent.execute(context)
            context.agent_results[agent_name] = result

            # Update progress
            current_progress = agent_progress_start + (steps_per_agent * (i + 1))

            # Emit agent completed
            yield StreamingUpdate(
                type=UpdateType.AGENT_COMPLETED,
                data={
                    'agent': agent_name,
                    'success': result.success if hasattr(result, 'success') else True,
                    'findings_count': len(result.findings) if hasattr(result, 'findings') else 0
                },
                progress_percent=current_progress
            )

            # Emit findings
            if hasattr(result, 'findings'):
                for finding in result.findings:
                    yield StreamingUpdate(
                        type=UpdateType.FINDING,
                        data={
                            'agent': agent_name,
                            'finding': finding
                        },
                        progress_percent=current_progress
                    )

            # Emit hypotheses
            if hasattr(result, 'hypotheses'):
                for hypothesis in result.hypotheses:
                    yield StreamingUpdate(
                        type=UpdateType.HYPOTHESIS,
                        data={
                            'agent': agent_name,
                            'hypothesis': hypothesis
                        },
                        progress_percent=current_progress
                    )

        # Phase 3: Synthesize findings
        current_progress = 90
        await self._synthesize_findings(context)

        # Phase 4: Identify root causes
        await self._identify_root_causes(context)

        root_causes = context.graph.get_root_causes()
        for root_cause in root_causes:
            yield StreamingUpdate(
                type=UpdateType.ROOT_CAUSE,
                data={
                    'root_cause': {
                        'id': root_cause.id,
                        'title': root_cause.title,
                        'description': root_cause.description,
                        'confidence': root_cause.confidence
                    }
                },
                progress_percent=current_progress
            )

        # Phase 5: Generate remediation plan
        if 'remediation_planner' in self.agents:
            current_progress = 95
            await self._generate_remediation_plan(context)

            rem_result = context.agent_results.get('remediation_planner')
            if rem_result:
                rem_plan = rem_result.metadata.get('remediation_plan') if hasattr(rem_result, 'metadata') else {}

                yield StreamingUpdate(
                    type=UpdateType.REMEDIATION_PLAN,
                    data={'remediation_plan': rem_plan},
                    progress_percent=current_progress
                )

        # Emit completion
        context.end_time = datetime.utcnow()

        yield StreamingUpdate(
            type=UpdateType.COMPLETED,
            data={
                'incident_id': incident_id,
                'graph': context.graph.to_dict(),
                'duration_seconds': (context.end_time - context.start_time).total_seconds(),
                'total_nodes': len(context.graph.nodes),
                'total_edges': len(context.graph.edges),
                'root_causes_count': len(root_causes)
            },
            progress_percent=100
        )


# Example WebSocket server implementation
WEBSOCKET_EXAMPLE = """
Example FastAPI WebSocket server for real-time RCA streaming:

```python
from fastapi import FastAPI, WebSocket
from core.streaming import StreamingOrchestrator, UpdateType
from core import ADAPTConfig

app = FastAPI()

@app.websocket("/ws/rca/{incident_id}")
async def rca_websocket(websocket: WebSocket, incident_id: str):
    await websocket.accept()

    try:
        # Initialize streaming orchestrator
        orchestrator = StreamingOrchestrator(ADAPTConfig())

        # Register agents
        # ... (register your agents here)

        # Fetch signals
        # ... (fetch signals for the incident)

        # Stream updates
        async for update in orchestrator.run_rca_streaming(incident_id, signals):
            await websocket.send_json(update.to_dict())

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "data": {"error": str(e)},
            "timestamp": datetime.utcnow().isoformat()
        })
    finally:
        await websocket.close()
```
"""
