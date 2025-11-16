"""
Agent management API routes
"""

from fastapi import APIRouter, Depends
from typing import List
import logging

from ..models import AgentInfo
from ..auth import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/agents", response_model=List[AgentInfo])
async def list_agents(user: User = Depends(get_current_user)):
    """
    List all available diagnostic agents.

    Returns information about all registered agents in the system.
    """
    agents = [
        AgentInfo(
            name="log_analyzer",
            description="Analyzes log patterns and errors",
            purpose="Error detection, pattern matching, temporal correlation, service correlation",
            enabled=True,
        ),
        AgentInfo(
            name="metric_analyzer",
            description="Detects metric anomalies and trends",
            purpose="Statistical anomaly detection, threshold breaches, trend analysis, metric correlation",
            enabled=True,
        ),
        AgentInfo(
            name="topology_explainer",
            description="Maps service dependencies",
            purpose="Dependency mapping, failure propagation analysis, SPOF detection, service health correlation",
            enabled=True,
        ),
        AgentInfo(
            name="change_correlator",
            description="Correlates changes with incidents",
            purpose="Deployment correlation, change clustering, rollback detection, change impact analysis",
            enabled=True,
        ),
        AgentInfo(
            name="remediation_planner",
            description="Generates remediation plans",
            purpose="Risk-assessed action plans, validation steps, rollback procedures",
            enabled=True,
        ),
    ]

    return agents


@router.get("/agents/{agent_name}", response_model=AgentInfo)
async def get_agent_info(agent_name: str, user: User = Depends(get_current_user)):
    """
    Get detailed information about a specific agent.
    """
    agents_map = {
        "log_analyzer": AgentInfo(
            name="log_analyzer",
            description="Analyzes log patterns and errors",
            purpose="Error detection, pattern matching, temporal correlation, service correlation",
            enabled=True,
        ),
        "metric_analyzer": AgentInfo(
            name="metric_analyzer",
            description="Detects metric anomalies and trends",
            purpose="Statistical anomaly detection, threshold breaches, trend analysis, metric correlation",
            enabled=True,
        ),
        "topology_explainer": AgentInfo(
            name="topology_explainer",
            description="Maps service dependencies",
            purpose="Dependency mapping, failure propagation analysis, SPOF detection",
            enabled=True,
        ),
        "change_correlator": AgentInfo(
            name="change_correlator",
            description="Correlates changes with incidents",
            purpose="Deployment correlation, change clustering, rollback detection",
            enabled=True,
        ),
        "remediation_planner": AgentInfo(
            name="remediation_planner",
            description="Generates remediation plans",
            purpose="Risk-assessed action plans, validation steps, rollback procedures",
            enabled=True,
        ),
    }

    if agent_name not in agents_map:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    return agents_map[agent_name]
