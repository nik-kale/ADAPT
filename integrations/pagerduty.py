"""
PagerDuty Integration

Create and update PagerDuty incidents with RCA findings.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


class PagerDutyIntegration:
    """
    PagerDuty integration for ADAPT.

    Requires: pip install pdpyras
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize PagerDuty integration.

        Args:
            api_key: PagerDuty API key
        """
        self.api_key = api_key or os.getenv("PAGERDUTY_API_KEY")
        self.session = None

        if self.api_key:
            try:
                import pdpyras

                self.session = pdpyras.APISession(self.api_key)
                logger.info("Initialized PagerDuty API session")
            except ImportError:
                logger.warning(
                    "pdpyras not installed. Install with: pip install pdpyras"
                )

    def create_incident_with_rca(
        self,
        rca_context,
        service_id: str,
        urgency: str = "high",
        escalation_policy_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Create PagerDuty incident with RCA findings.

        Args:
            rca_context: OrchestrationContext from RCA
            service_id: PagerDuty service ID
            urgency: Incident urgency (low/high)
            escalation_policy_id: Optional escalation policy

        Returns:
            Created incident data or None
        """
        if not self.session:
            logger.error("PagerDuty not configured")
            return None

        # Build incident details
        root_causes = rca_context.graph.get_root_causes()
        title = f"RCA: {rca_context.incident_id}"

        if root_causes:
            top_rc = max(root_causes, key=lambda x: x.confidence)
            title = f"RCA: {top_rc.title}"

        # Get narrative
        narrative = rca_context.graph.export_narrative()

        try:
            incident_payload = {
                "incident": {
                    "type": "incident",
                    "title": title,
                    "service": {"id": service_id, "type": "service_reference"},
                    "urgency": urgency,
                    "body": {"type": "incident_body", "details": narrative[:4000]},
                }
            }

            if escalation_policy_id:
                incident_payload["incident"]["escalation_policy"] = {
                    "id": escalation_policy_id,
                    "type": "escalation_policy_reference",
                }

            incident = self.session.rpost("/incidents", json=incident_payload)

            logger.info(f"Created PagerDuty incident: {incident['id']}")

            # Add notes with root causes and findings
            self._add_rca_notes(incident["id"], rca_context)

            return incident

        except Exception as e:
            logger.error(f"Failed to create PagerDuty incident: {e}")
            return None

    def _add_rca_notes(self, incident_id: str, rca_context) -> None:
        """Add RCA findings as incident notes"""
        if not self.session:
            return

        try:
            # Add root causes
            root_causes = rca_context.graph.get_root_causes()
            for rc in sorted(root_causes, key=lambda x: x.confidence, reverse=True):
                note_content = f"🎯 Root Cause ({rc.confidence:.0%}): {rc.title}\n\n{rc.description}"

                self.session.rpost(
                    f"/incidents/{incident_id}/notes",
                    json={"note": {"content": note_content}},
                )

            # Add agent findings summary
            findings_count = 0
            for result in rca_context.agent_results.values():
                if isinstance(result, dict) and result.get("success"):
                    findings_count += len(result.get("findings", []))

            summary = f"📊 RCA Summary:\n"
            summary += f"- Agents executed: {len(rca_context.agent_results)}\n"
            summary += f"- Findings: {findings_count}\n"
            summary += f"- Root causes: {len(root_causes)}\n"
            summary += f"- Duration: {(rca_context.end_time - rca_context.start_time).total_seconds():.1f}s\n"

            self.session.rpost(
                f"/incidents/{incident_id}/notes", json={"note": {"content": summary}}
            )

            logger.info(f"Added RCA notes to incident {incident_id}")

        except Exception as e:
            logger.warning(f"Failed to add notes to incident: {e}")

    def update_incident_status(
        self, incident_id: str, status: str, resolution: Optional[str] = None
    ) -> bool:
        """
        Update incident status.

        Args:
            incident_id: PagerDuty incident ID
            status: New status (acknowledged, resolved)
            resolution: Optional resolution notes

        Returns:
            True if updated successfully
        """
        if not self.session:
            return False

        try:
            payload = {"incident": {"type": "incident", "status": status}}

            self.session.rput(f"/incidents/{incident_id}", json=payload)

            if resolution and status == "resolved":
                self.session.rpost(
                    f"/incidents/{incident_id}/notes",
                    json={"note": {"content": f"Resolution: {resolution}"}},
                )

            logger.info(f"Updated incident {incident_id} status to {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to update incident status: {e}")
            return False

    def add_responders(
        self, incident_id: str, user_ids: list[str]
    ) -> bool:
        """
        Add responders to incident.

        Args:
            incident_id: PagerDuty incident ID
            user_ids: List of user IDs to add

        Returns:
            True if added successfully
        """
        if not self.session:
            return False

        try:
            for user_id in user_ids:
                self.session.rpost(
                    f"/incidents/{incident_id}/responder_requests",
                    json={
                        "responder_request": {
                            "type": "responder_request",
                            "message": "Your expertise is needed for this RCA",
                            "responder_request_targets": [
                                {
                                    "responder_request_target": {
                                        "type": "user_reference",
                                        "id": user_id,
                                    }
                                }
                            ],
                        }
                    },
                )

            logger.info(f"Added responders to incident {incident_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add responders: {e}")
            return False

    def trigger_event(
        self,
        routing_key: str,
        summary: str,
        severity: str = "error",
        source: str = "adapt-rca",
        custom_details: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Trigger a PagerDuty event (for events v2 API).

        Args:
            routing_key: Integration key
            summary: Event summary
            severity: Event severity (info, warning, error, critical)
            source: Event source
            custom_details: Optional additional details

        Returns:
            Dedup key or None
        """
        try:
            import requests

            payload = {
                "routing_key": routing_key,
                "event_action": "trigger",
                "payload": {
                    "summary": summary,
                    "severity": severity,
                    "source": source,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }

            if custom_details:
                payload["payload"]["custom_details"] = custom_details

            response = requests.post(
                "https://events.pagerduty.com/v2/enqueue", json=payload
            )
            response.raise_for_status()

            data = response.json()
            logger.info(f"Triggered PagerDuty event: {data.get('dedup_key')}")
            return data.get("dedup_key")

        except Exception as e:
            logger.error(f"Failed to trigger PagerDuty event: {e}")
            return None
