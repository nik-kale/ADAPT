"""
Remediation Planner Agent

Generates structured remediation plans based on RCA findings.
Transforms root causes into actionable steps with risk assessments.
"""

from typing import Dict, List, Any
from datetime import datetime

from .base import BaseAgent, AgentResult


class RemediationPlannerAgent(BaseAgent):
    """
    Agent specialized in generating remediation plans.

    This agent:
    1. Analyzes identified root causes
    2. Generates remediation actions
    3. Assesses risk for each action
    4. Prioritizes actions
    5. Provides rollback procedures
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the remediation planner agent."""
        super().__init__(name='remediation_planner', config=config)
        self.remediation_templates = self._load_remediation_templates()

    def _load_remediation_templates(self) -> Dict[str, Any]:
        """Load remediation action templates."""
        return {
            'connectivity': {
                'actions': [
                    {
                        'title': 'Check network connectivity',
                        'description': 'Verify network connectivity between affected services',
                        'risk': 'low',
                        'estimated_time': '5 minutes',
                    },
                    {
                        'title': 'Restart affected services',
                        'description': 'Restart services experiencing connection issues',
                        'risk': 'medium',
                        'estimated_time': '10 minutes',
                    },
                    {
                        'title': 'Review firewall rules',
                        'description': 'Check if recent firewall changes blocked required connections',
                        'risk': 'low',
                        'estimated_time': '15 minutes',
                    },
                ],
            },
            'resource': {
                'actions': [
                    {
                        'title': 'Scale up resources',
                        'description': 'Increase CPU/memory allocation for affected services',
                        'risk': 'low',
                        'estimated_time': '10 minutes',
                    },
                    {
                        'title': 'Clear disk space',
                        'description': 'Remove old logs and temporary files to free up disk space',
                        'risk': 'low',
                        'estimated_time': '15 minutes',
                    },
                    {
                        'title': 'Restart services to clear memory leaks',
                        'description': 'Restart services showing memory growth',
                        'risk': 'medium',
                        'estimated_time': '10 minutes',
                    },
                ],
            },
            'database': {
                'actions': [
                    {
                        'title': 'Check database connections',
                        'description': 'Verify database connection pool status',
                        'risk': 'low',
                        'estimated_time': '5 minutes',
                    },
                    {
                        'title': 'Analyze slow queries',
                        'description': 'Identify and optimize slow database queries',
                        'risk': 'low',
                        'estimated_time': '20 minutes',
                    },
                    {
                        'title': 'Restart database connection pools',
                        'description': 'Reset connection pools to clear stale connections',
                        'risk': 'medium',
                        'estimated_time': '10 minutes',
                    },
                ],
            },
            'config_change': {
                'actions': [
                    {
                        'title': 'Review recent configuration changes',
                        'description': 'Examine recent config changes for errors',
                        'risk': 'low',
                        'estimated_time': '10 minutes',
                    },
                    {
                        'title': 'Rollback recent changes',
                        'description': 'Revert recent configuration or deployment changes',
                        'risk': 'medium',
                        'estimated_time': '15 minutes',
                    },
                    {
                        'title': 'Validate configuration',
                        'description': 'Run configuration validation checks',
                        'risk': 'low',
                        'estimated_time': '5 minutes',
                    },
                ],
            },
            'performance': {
                'actions': [
                    {
                        'title': 'Enable caching',
                        'description': 'Enable or increase cache TTL to reduce load',
                        'risk': 'low',
                        'estimated_time': '10 minutes',
                    },
                    {
                        'title': 'Implement rate limiting',
                        'description': 'Add rate limiting to protect against traffic spikes',
                        'risk': 'medium',
                        'estimated_time': '20 minutes',
                    },
                    {
                        'title': 'Scale horizontally',
                        'description': 'Add more service instances to handle load',
                        'risk': 'low',
                        'estimated_time': '15 minutes',
                    },
                ],
            },
        }

    async def execute(self, context: Any) -> AgentResult:
        """
        Execute remediation planning.

        Args:
            context: OrchestrationContext with RCA graph and findings

        Returns:
            AgentResult with remediation plan
        """
        start_time = datetime.utcnow()

        try:
            findings = []
            remediation_plan = self._generate_remediation_plan(context)

            # Create a finding that contains the full remediation plan
            findings.append(
                self._create_finding(
                    finding_id='remediation_plan',
                    title='Remediation Plan Generated',
                    description=f'Generated {len(remediation_plan.get("actions", []))} remediation actions',
                    confidence=0.75,
                    metadata=remediation_plan,
                )
            )

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return AgentResult(
                agent_name=self.name,
                findings=findings,
                metadata={
                    'remediation_plan': remediation_plan,
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

    def _generate_remediation_plan(self, context: Any) -> Dict[str, Any]:
        """Generate a complete remediation plan based on findings."""
        plan = {
            'incident_id': context.incident_id,
            'generated_at': datetime.utcnow().isoformat(),
            'actions': [],
            'rollback_procedures': [],
            'validation_steps': [],
        }

        # Analyze all agent findings to determine remediation categories
        categories_identified = set()

        # Check log analyzer findings
        if 'log_analyzer' in context.agent_results:
            log_findings = context.agent_results['log_analyzer'].get('findings', [])
            for finding in log_findings:
                metadata = finding.get('metadata', {})
                category = metadata.get('category')
                if category:
                    categories_identified.add(category)

        # Check change correlator findings
        if 'change_correlator' in context.agent_results:
            change_findings = context.agent_results['change_correlator'].get('findings', [])
            if change_findings:
                categories_identified.add('config_change')

        # Check metric analyzer findings
        if 'metric_analyzer' in context.agent_results:
            metric_findings = context.agent_results['metric_analyzer'].get('findings', [])
            if metric_findings:
                categories_identified.add('performance')

        # If no specific categories identified, use general troubleshooting
        if not categories_identified:
            categories_identified.add('general')

        # Generate actions for each identified category
        action_priority = 1
        for category in categories_identified:
            if category in self.remediation_templates:
                template_actions = self.remediation_templates[category]['actions']
                for action_template in template_actions:
                    action = {
                        'priority': action_priority,
                        'category': category,
                        **action_template,
                    }
                    plan['actions'].append(action)
                    action_priority += 1

        # Add rollback procedures if changes were detected
        if 'config_change' in categories_identified:
            plan['rollback_procedures'].append({
                'step': 'Prepare rollback plan',
                'description': 'Document current state and prepare rollback steps for recent changes',
                'risk': 'low',
            })
            plan['rollback_procedures'].append({
                'step': 'Execute rollback',
                'description': 'If remediation actions fail, rollback recent configuration/deployment changes',
                'risk': 'medium',
            })

        # Add validation steps
        plan['validation_steps'] = [
            {
                'step': 'Verify symptoms resolved',
                'description': 'Check that original symptoms (errors, latency, etc.) have cleared',
                'estimated_time': '10 minutes',
            },
            {
                'step': 'Monitor key metrics',
                'description': 'Monitor system metrics for 30 minutes to ensure stability',
                'estimated_time': '30 minutes',
            },
            {
                'step': 'Check dependent services',
                'description': 'Verify that all dependent services are functioning normally',
                'estimated_time': '10 minutes',
            },
            {
                'step': 'Update incident documentation',
                'description': 'Document the incident, root cause, and remediation steps taken',
                'estimated_time': '15 minutes',
            },
        ]

        # Calculate total estimated time
        total_time = 0
        for action in plan['actions']:
            time_str = action.get('estimated_time', '0 minutes')
            minutes = int(time_str.split()[0])
            total_time += minutes

        for step in plan['validation_steps']:
            time_str = step.get('estimated_time', '0 minutes')
            minutes = int(time_str.split()[0])
            total_time += minutes

        plan['total_estimated_time'] = f'{total_time} minutes'
        plan['risk_assessment'] = self._assess_overall_risk(plan['actions'])

        return plan

    def _assess_overall_risk(self, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess the overall risk of the remediation plan."""
        risk_counts = {'low': 0, 'medium': 0, 'high': 0}

        for action in actions:
            risk = action.get('risk', 'medium')
            risk_counts[risk] += 1

        # Determine overall risk level
        if risk_counts['high'] > 0:
            overall_risk = 'high'
        elif risk_counts['medium'] > 2:
            overall_risk = 'medium'
        else:
            overall_risk = 'low'

        return {
            'overall_risk': overall_risk,
            'risk_distribution': risk_counts,
            'recommendation': self._get_risk_recommendation(overall_risk),
        }

    def _get_risk_recommendation(self, overall_risk: str) -> str:
        """Get recommendation based on risk level."""
        recommendations = {
            'low': 'Safe to proceed with remediation actions. Monitor during execution.',
            'medium': 'Review actions carefully. Execute during business hours with team available.',
            'high': 'High-risk actions detected. Consider staging environment testing first. Ensure rollback plan is ready.',
        }
        return recommendations.get(overall_risk, 'Review carefully before executing.')
