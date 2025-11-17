"""
RCA analysis API routes
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from typing import List
from datetime import datetime, timedelta
import asyncio
import logging

from ..models import (
    RCAStartRequest,
    RCAResponse,
    RCAListItem,
    NodeResponse,
    EdgeResponse,
    RCAGraphResponse,
    RootCauseResponse,
    FindingResponse,
)
from ..auth import get_current_user, require_run_rca, require_view_incidents, User
from core import RCAOrchestrator, ADAPTConfig, load_config, NormalizedSignal, SignalType
from core.streaming import StreamingOrchestrator, UpdateType
from agents import (
    LogAnalyzerAgent,
    MetricAnalyzerAgent,
    TopologyExplainerAgent,
    ChangeCorrelatorAgent,
    RemediationPlannerAgent,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def create_orchestrator(config: ADAPTConfig = None) -> RCAOrchestrator:
    """Create and configure RCA orchestrator"""
    if config is None:
        try:
            config = load_config("config.yaml")
        except (FileNotFoundError, ValueError) as e:
            # v4.0: Specific exception handling (P0 Issue 5.2)
            logger.debug(f"Config file not found or invalid, using defaults: {e}")
            config = ADAPTConfig()

    orchestrator = RCAOrchestrator(config)

    # Register agents
    orchestrator.register_agent("log_analyzer", LogAnalyzerAgent())
    orchestrator.register_agent("metric_analyzer", MetricAnalyzerAgent())
    orchestrator.register_agent("topology_explainer", TopologyExplainerAgent())
    orchestrator.register_agent("change_correlator", ChangeCorrelatorAgent())
    orchestrator.register_agent("remediation_planner", RemediationPlannerAgent())

    return orchestrator


def convert_signal_request_to_normalized(signal_req) -> NormalizedSignal:
    """Convert API signal request to NormalizedSignal"""
    return NormalizedSignal(
        signal_type=SignalType(signal_req.signal_type.value),
        title=signal_req.title,
        description=signal_req.description,
        timestamp=signal_req.timestamp,
        source=signal_req.source,
        severity=signal_req.severity,
        metadata=signal_req.metadata,
        tags=signal_req.tags,
    )


@router.post("/rca/analyze", response_model=RCAResponse)
async def analyze_incident(
    request: RCAStartRequest, user: User = Depends(require_run_rca)
):
    """
    Run RCA analysis on an incident.

    This endpoint starts a full RCA analysis workflow on the provided signals.
    """
    logger.info(f"Starting RCA for incident {request.incident_id} by user {user.username}")

    # Convert signal requests to normalized signals
    signals = [convert_signal_request_to_normalized(s) for s in request.signals]

    # Create orchestrator
    config = load_config() if not request.execution_mode else None
    orchestrator = create_orchestrator(config)
    orchestrator.execution_mode = request.execution_mode

    # v4.0: Get RCA execution timeout from config (P0 Issue 1.9)
    if config is None:
        config = load_config()
    timeout_seconds = config.rca_execution_timeout

    try:
        # Run RCA with timeout protection (v4.0)
        context = await asyncio.wait_for(
            orchestrator.run_rca(incident_id=request.incident_id, signals=signals),
            timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.error(
            f"RCA analysis for incident {request.incident_id} exceeded timeout "
            f"of {timeout_seconds} seconds"
        )
        raise HTTPException(
            status_code=504,
            detail=f"RCA analysis exceeded maximum execution time of {timeout_seconds} seconds. "
            "This may indicate a stuck analysis or resource contention. "
            "Try reducing signal count or increasing timeout in configuration."
        )
    except Exception as e:
        logger.error(f"RCA failed for incident {request.incident_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"RCA analysis failed: {str(e)}")

    # Convert to response model
    root_causes = [
        RootCauseResponse(
            id=rc.id,
            title=rc.title,
            description=rc.description,
            confidence=rc.confidence,
            metadata=rc.metadata,
        )
        for rc in context.graph.get_root_causes()
    ]

    # Collect all findings from agent results
    all_findings = []
    for agent_name, result in context.agent_results.items():
        if isinstance(result, dict) and result.get("success"):
            for finding_data in result.get("findings", []):
                all_findings.append(
                    FindingResponse(
                        id=finding_data.get("id", f"finding_{agent_name}"),
                        title=finding_data.get("title", ""),
                        description=finding_data.get("description", ""),
                        confidence=finding_data.get("confidence", 0.0),
                        agent=agent_name,
                        metadata=finding_data.get("metadata", {}),
                    )
                )

    # Build graph response
    nodes = [
        NodeResponse(
            id=node.id,
            type=node.type.value,
            title=node.title,
            description=node.description,
            confidence=node.confidence,
            metadata=node.metadata,
            created_at=node.created_at,
        )
        for node in context.graph.nodes.values()
    ]

    edges = [
        EdgeResponse(
            source=edge.source,
            target=edge.target,
            type=edge.type.value,
            weight=edge.weight,
            metadata=edge.metadata,
        )
        for edge in context.graph.edges
    ]

    graph = RCAGraphResponse(
        incident_id=context.incident_id,
        nodes=nodes,
        edges=edges,
        created_at=context.graph.created_at,
        metadata=context.graph.metadata,
    )

    execution_time = None
    if context.end_time and context.start_time:
        execution_time = (context.end_time - context.start_time).total_seconds()

    return RCAResponse(
        incident_id=context.incident_id,
        status="completed",
        start_time=context.start_time,
        end_time=context.end_time,
        execution_time_seconds=execution_time,
        root_causes=root_causes,
        findings=all_findings,
        graph=graph,
        narrative=context.graph.export_narrative(),
        metadata=context.metadata,
    )


@router.websocket("/rca/stream/{incident_id}")
async def stream_rca(websocket: WebSocket, incident_id: str):
    """
    Stream real-time RCA updates via WebSocket.

    This endpoint provides real-time updates as the RCA analysis progresses.
    """
    await websocket.accept()

    try:
        # Get signals from first message
        data = await websocket.receive_json()
        signal_requests = data.get("signals", [])

        signals = []
        for sig_data in signal_requests:
            signals.append(
                NormalizedSignal(
                    signal_type=SignalType(sig_data.get("signal_type")),
                    title=sig_data.get("title"),
                    description=sig_data.get("description"),
                    timestamp=datetime.fromisoformat(sig_data.get("timestamp")),
                    source=sig_data.get("source"),
                    severity=sig_data.get("severity", "medium"),
                    metadata=sig_data.get("metadata", {}),
                    tags=sig_data.get("tags", {}),
                )
            )

        # Create streaming orchestrator
        config = load_config()
        streaming_orch = StreamingOrchestrator(config)

        # v4.0: Apply timeout to streaming as well
        timeout_seconds = config.rca_execution_timeout

        try:
            # Stream updates with timeout protection
            async def stream_with_timeout():
                async for update in streaming_orch.run_rca_streaming(incident_id, signals):
                    await websocket.send_json(
                        {
                            "type": update.type.value,
                            "timestamp": update.timestamp.isoformat(),
                            "data": update.data,
                        }
                    )

            await asyncio.wait_for(stream_with_timeout(), timeout=timeout_seconds)

        except asyncio.TimeoutError:
            logger.error(f"Streaming RCA for incident {incident_id} exceeded timeout")
            await websocket.send_json(
                {
                    "type": "ERROR",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {
                        "error": f"RCA analysis exceeded maximum execution time of {timeout_seconds} seconds"
                    },
                }
            )
            await websocket.close()

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for incident {incident_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket stream: {e}", exc_info=True)
        await websocket.send_json(
            {
                "type": "ERROR",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {"error": str(e)},
            }
        )
        await websocket.close()


@router.get("/rca/{incident_id}", response_model=RCAResponse)
async def get_rca(incident_id: str, user: User = Depends(require_view_incidents)):
    """
    Get RCA results for a specific incident.

    Retrieves the complete RCA analysis results from storage.
    """
    from core import get_graph_storage

    storage = get_graph_storage()
    if not storage:
        raise HTTPException(
            status_code=503, detail="Graph storage not configured"
        )

    graph = await storage.load_graph(incident_id)
    if not graph:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    # Convert graph to response (similar to analyze_incident)
    root_causes = [
        RootCauseResponse(
            id=rc.id,
            title=rc.title,
            description=rc.description,
            confidence=rc.confidence,
            metadata=rc.metadata,
        )
        for rc in graph.get_root_causes()
    ]

    nodes = [
        NodeResponse(
            id=node.id,
            type=node.type.value,
            title=node.title,
            description=node.description,
            confidence=node.confidence,
            metadata=node.metadata,
            created_at=node.created_at,
        )
        for node in graph.nodes.values()
    ]

    edges = [
        EdgeResponse(
            source=edge.source,
            target=edge.target,
            type=edge.type.value,
            weight=edge.weight,
            metadata=edge.metadata,
        )
        for edge in graph.edges
    ]

    graph_response = RCAGraphResponse(
        incident_id=graph.incident_id,
        nodes=nodes,
        edges=edges,
        created_at=graph.created_at,
        metadata=graph.metadata,
    )

    return RCAResponse(
        incident_id=graph.incident_id,
        status="completed",
        start_time=graph.created_at,
        end_time=None,
        execution_time_seconds=None,
        root_causes=root_causes,
        findings=[],  # Not stored in graph
        graph=graph_response,
        narrative=graph.export_narrative(),
        metadata=graph.metadata,
    )
