"""
LLM-Enhanced Log Analyzer Agent

Uses large language models (Claude, GPT) for semantic log analysis.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import json

from .log_analyzer import LogAnalyzerAgent
from .base import AgentResult
from agents.llm_providers import get_llm_provider
from core.signal_normalizer import SignalType

logger = logging.getLogger(__name__)


class LLMLogAnalyzer(LogAnalyzerAgent):
    """
    Enhanced log analyzer that uses LLMs for semantic understanding.

    Capabilities:
    - Semantic pattern extraction
    - Natural language root cause explanations
    - Novel error detection
    - Contextual log correlation
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.use_llm = config.get("use_llm", True) if config else True
        self.llm_model = config.get("llm_model", "claude-3-5-sonnet-20241022") if config else "claude-3-5-sonnet-20241022"

    async def execute(self, context: Any) -> AgentResult:
        """
        Execute enhanced log analysis with LLM support.
        """
        # First run traditional analysis
        result = await super().execute(context)

        # If LLM is enabled and we have findings, enhance them
        if self.use_llm and result.success:
            llm_provider = get_llm_provider()

            if llm_provider:
                enhanced_findings = await self._enhance_findings_with_llm(
                    context, result.findings
                )
                result.findings.extend(enhanced_findings)

                # Add LLM-generated insights to metadata
                result.metadata["llm_enhanced"] = True
                result.metadata["llm_findings_count"] = len(enhanced_findings)

        return result

    async def _enhance_findings_with_llm(
        self, context: Any, existing_findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to extract additional insights from logs.
        """
        llm_provider = get_llm_provider()
        if not llm_provider:
            return []

        log_signals = [s for s in context.signals if s.signal_type == SignalType.LOG]

        if not log_signals:
            return []

        # Sample error logs for LLM analysis
        error_logs = [
            s for s in log_signals
            if s.severity in ['high', 'critical']
        ][:20]  # Limit to 20 most relevant

        if not error_logs:
            return []

        # Build prompt for LLM
        prompt = self._build_analysis_prompt(error_logs, existing_findings)

        try:
            # Get LLM analysis
            response = await llm_provider.complete_with_system(
                system_prompt="""You are an expert SRE analyzing production logs for root cause analysis.

Your task is to:
1. Identify patterns and correlations in error logs
2. Determine likely root causes
3. Explain the causal chain
4. Suggest investigation steps
5. Provide confidence scores (0.0-1.0)

Respond in JSON format with this structure:
{
  "root_cause": "Primary root cause explanation",
  "confidence": 0.85,
  "reasoning": "Detailed explanation of why this is the root cause",
  "supporting_evidence": ["Evidence 1", "Evidence 2"],
  "investigation_steps": ["Step 1", "Step 2"],
  "related_patterns": ["Pattern 1", "Pattern 2"]
}""",
                user_prompt=prompt,
                model=self.llm_model
            )

            # Parse LLM response
            llm_findings = self._parse_llm_response(response)
            return llm_findings

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return []

    def _build_analysis_prompt(
        self, error_logs: List[Any], existing_findings: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for LLM analysis."""

        prompt = "# Error Logs for Analysis\n\n"

        for i, log in enumerate(error_logs[:10], 1):
            prompt += f"## Log {i}\n"
            prompt += f"- **Timestamp**: {log.timestamp.isoformat()}\n"
            prompt += f"- **Source**: {log.source}\n"
            prompt += f"- **Severity**: {log.severity}\n"
            prompt += f"- **Message**: {log.description}\n\n"

        if existing_findings:
            prompt += "\n# Existing Findings from Traditional Analysis\n\n"
            for finding in existing_findings[:5]:
                prompt += f"- {finding.get('title')}: {finding.get('description')} "
                prompt += f"(confidence: {finding.get('confidence', 0):.2f})\n"

        prompt += "\n# Task\n\n"
        prompt += "Analyze these error logs and identify the root cause. "
        prompt += "Look for patterns, correlations, and causal relationships. "
        prompt += "Provide a detailed explanation with high confidence if the evidence is strong."

        return prompt

    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into findings."""
        findings = []

        try:
            # Try to parse as JSON
            data = json.loads(response)

            finding = self._create_finding(
                finding_id=f"llm_finding_{datetime.utcnow().timestamp()}",
                title=f"LLM Analysis: {data.get('root_cause', 'Unknown')[:50]}",
                description=data.get('reasoning', data.get('root_cause', '')),
                confidence=data.get('confidence', 0.7),
                metadata={
                    'source': 'llm',
                    'model': self.llm_model,
                    'root_cause': data.get('root_cause'),
                    'supporting_evidence': data.get('supporting_evidence', []),
                    'investigation_steps': data.get('investigation_steps', []),
                    'related_patterns': data.get('related_patterns', []),
                }
            )
            findings.append(finding)

        except json.JSONDecodeError:
            # Fallback: treat as plain text explanation
            finding = self._create_finding(
                finding_id=f"llm_finding_{datetime.utcnow().timestamp()}",
                title="LLM Analysis: See description for details",
                description=response[:500],  # Limit length
                confidence=0.6,
                metadata={
                    'source': 'llm',
                    'model': self.llm_model,
                    'raw_response': response,
                }
            )
            findings.append(finding)

        return findings


class LLMMetricAnalyzer:
    """
    LLM-enhanced metric analyzer for anomaly explanation.
    """

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    async def explain_anomaly(
        self,
        metric_name: str,
        current_value: float,
        expected_value: float,
        context: Dict[str, Any]
    ) -> str:
        """
        Use LLM to explain why a metric is anomalous.
        """
        prompt = f"""
Explain why this metric is anomalous:

- Metric: {metric_name}
- Current Value: {current_value}
- Expected Value: {expected_value}
- Deviation: {abs(current_value - expected_value) / expected_value * 100:.1f}%

Context:
{json.dumps(context, indent=2)}

Provide a concise explanation of:
1. Why this is anomalous
2. Likely causes
3. Impact on the system
4. Recommended investigation steps
"""

        response = await self.llm_provider.complete(prompt)
        return response


class LLMRemediationPlanner:
    """
    LLM-enhanced remediation planner.
    """

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    async def generate_remediation_plan(
        self,
        root_causes: List[Dict[str, Any]],
        incident_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate detailed remediation plan using LLM.
        """
        prompt = f"""
Generate a detailed remediation plan for this incident:

# Root Causes:
{json.dumps(root_causes, indent=2)}

# Incident Context:
{json.dumps(incident_context, indent=2)}

Provide a remediation plan with:
1. Immediate actions (stop the bleeding)
2. Short-term fixes (restore service)
3. Long-term fixes (prevent recurrence)
4. Risk assessment for each action
5. Rollback procedures

Format as JSON:
{{
  "immediate_actions": [
    {{"action": "...", "risk": "low|medium|high", "duration": "5m"}}
  ],
  "short_term_fixes": [...],
  "long_term_fixes": [...],
  "rollback_procedure": "...",
  "validation_steps": [...]
}}
"""

        response = await self.llm_provider.complete_with_system(
            system="You are an expert SRE creating remediation plans.",
            user_prompt=prompt
        )

        try:
            plan = json.loads(response)
            return plan
        except json.JSONDecodeError:
            return {"raw_plan": response}
