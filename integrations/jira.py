"""
Jira Integration

Create tickets from RCA findings, track incidents, and link deployments.

v5.0: Advanced integration ecosystem expansion
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import os
import aiohttp
import base64

from core.signals import NormalizedSignal, SignalType

logger = logging.getLogger(__name__)


class JiraIntegration:
    """
    Jira integration for ADAPT (v5.0).

    Features:
    - Create issues/tickets from RCA findings
    - Update existing tickets with RCA results
    - Search for related incidents
    - Track incident lifecycle
    - Link to deployments and changes
    """

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        api_token: Optional[str] = None,
        project_key: Optional[str] = None
    ):
        """
        Initialize Jira integration.

        Args:
            url: Jira instance URL (e.g., https://company.atlassian.net)
            username: Jira username/email
            api_token: Jira API token
            project_key: Default project key (e.g., OPS, INCIDENT)
        """
        self.url = (url or os.getenv("JIRA_URL", "")).rstrip("/")
        self.username = username or os.getenv("JIRA_USERNAME")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN")
        self.project_key = project_key or os.getenv("JIRA_PROJECT_KEY")

        # Create basic auth header
        if self.username and self.api_token:
            credentials = f"{self.username}:{self.api_token}"
            b64_credentials = base64.b64encode(credentials.encode()).decode()
            self.headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Basic {b64_credentials}",
            }
        else:
            self.headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            logger.warning(
                "Jira credentials not configured. Set JIRA_USERNAME and JIRA_API_TOKEN."
            )

    async def create_incident_from_rca(
        self,
        rca_context,
        issue_type: str = "Incident",
        priority: str = "High",
        assignee: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a Jira incident from RCA findings (v5.0).

        Args:
            rca_context: OrchestrationContext from RCA
            issue_type: Jira issue type (Incident, Bug, Task)
            priority: Priority level (Highest, High, Medium, Low, Lowest)
            assignee: Jira username to assign

        Returns:
            Jira issue key (e.g., OPS-123) if successful
        """
        if not self.url or not self.username or not self.project_key:
            logger.error("Jira not fully configured (need url, username, project_key)")
            return None

        # Build issue summary and description
        root_causes = rca_context.graph.get_root_causes()

        summary = f"RCA: {rca_context.incident_id}"

        if root_causes:
            top_cause = max(root_causes, key=lambda x: x.confidence)
            summary = f"RCA: {top_cause.title[:80]}"

        # Build description with ADF (Atlassian Document Format)
        description = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [
                        {"type": "text", "text": f"Root Cause Analysis: {rca_context.incident_id}"}
                    ],
                },
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": f"Incident ID: ", "marks": [{"type": "strong"}]},
                        {"type": "text", "text": rca_context.incident_id},
                    ],
                },
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": f"Analysis Time: ", "marks": [{"type": "strong"}]},
                        {"type": "text", "text": rca_context.start_time.strftime('%Y-%m-%d %H:%M:%S')},
                    ],
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Root Causes"}],
                },
            ],
        }

        # Add root causes
        if root_causes:
            for rc in sorted(root_causes, key=lambda x: x.confidence, reverse=True):
                confidence_emoji = "✅" if rc.confidence > 0.8 else "⚠️" if rc.confidence > 0.6 else "❌"

                description["content"].append({
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": f"{confidence_emoji} ", "marks": [{"type": "strong"}]},
                        {"type": "text", "text": rc.title, "marks": [{"type": "strong"}]},
                        {"type": "text", "text": f" ({rc.confidence:.0%})"},
                    ],
                })

                description["content"].append({
                    "type": "paragraph",
                    "content": [{"type": "text", "text": rc.description}],
                })
        else:
            description["content"].append({
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "⚠️ No high-confidence root causes identified"}
                ],
            })

        # Add key findings
        all_findings = []
        for result in rca_context.agent_results.values():
            if isinstance(result, dict) and result.get("success"):
                all_findings.extend(result.get("findings", []))

        if all_findings:
            description["content"].append({
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Key Findings"}],
            })

            bullet_list = {"type": "bulletList", "content": []}

            for finding in sorted(
                all_findings, key=lambda x: x.get("confidence", 0), reverse=True
            )[:5]:
                bullet_list["content"].append({
                    "type": "listItem",
                    "content": [{
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": finding.get('title', 'Unknown'), "marks": [{"type": "strong"}]},
                            {"type": "text", "text": f" ({finding.get('confidence', 0):.0%})"},
                        ],
                    }],
                })

            description["content"].append(bullet_list)

        # Create issue
        url = f"{self.url}/rest/api/3/issue"

        data = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
            }
        }

        if assignee:
            data["fields"]["assignee"] = {"name": assignee}

        # Add labels
        data["fields"]["labels"] = ["rca", "adapt", "automated"]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=data) as response:
                    if response.status == 201:
                        issue_data = await response.json()
                        issue_key = issue_data.get("key")
                        issue_url = f"{self.url}/browse/{issue_key}"
                        logger.info(f"Created Jira issue: {issue_key} ({issue_url})")
                        return issue_key
                    else:
                        logger.error(f"Failed to create Jira issue: {response.status}")
                        error_text = await response.text()
                        logger.error(f"Error: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Failed to create Jira issue: {e}")
            return None

    async def add_comment(
        self,
        issue_key: str,
        comment_text: str
    ) -> bool:
        """
        Add a comment to a Jira issue (v5.0).

        Args:
            issue_key: Jira issue key (e.g., OPS-123)
            comment_text: Comment text

        Returns:
            True if successful
        """
        if not self.url:
            return False

        url = f"{self.url}/rest/api/3/issue/{issue_key}/comment"

        # Format comment as ADF
        data = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment_text}],
                    }
                ],
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=data) as response:
                    if response.status == 201:
                        logger.info(f"Added comment to {issue_key}")
                        return True
                    else:
                        logger.error(f"Failed to add comment: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Failed to add comment: {e}")
            return False

    async def update_issue_status(
        self,
        issue_key: str,
        transition_name: str
    ) -> bool:
        """
        Update issue status (v5.0).

        Args:
            issue_key: Jira issue key
            transition_name: Transition name (e.g., "Resolve", "Close")

        Returns:
            True if successful
        """
        if not self.url:
            return False

        # Get available transitions
        transitions_url = f"{self.url}/rest/api/3/issue/{issue_key}/transitions"

        try:
            async with aiohttp.ClientSession() as session:
                # Get transitions
                async with session.get(transitions_url, headers=self.headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to get transitions: {response.status}")
                        return False

                    transitions_data = await response.json()
                    transitions = transitions_data.get("transitions", [])

                    # Find matching transition
                    transition_id = None
                    for transition in transitions:
                        if transition.get("name", "").lower() == transition_name.lower():
                            transition_id = transition.get("id")
                            break

                    if not transition_id:
                        logger.error(f"Transition '{transition_name}' not found")
                        return False

                # Perform transition
                data = {"transition": {"id": transition_id}}

                async with session.post(transitions_url, headers=self.headers, json=data) as response:
                    if response.status == 204:
                        logger.info(f"Updated {issue_key} status to '{transition_name}'")
                        return True
                    else:
                        logger.error(f"Failed to update status: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Failed to update status: {e}")
            return False

    async def search_related_issues(
        self,
        keywords: List[str],
        project_key: Optional[str] = None,
        issue_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for related issues using JQL (v5.0).

        Args:
            keywords: Keywords to search for
            project_key: Project to search in (defaults to configured project)
            issue_type: Filter by issue type
            limit: Maximum results

        Returns:
            List of related issues
        """
        if not self.url:
            return []

        # Build JQL query
        jql_parts = []

        project = project_key or self.project_key
        if project:
            jql_parts.append(f"project = {project}")

        if issue_type:
            jql_parts.append(f"issuetype = '{issue_type}'")

        if keywords:
            text_search = " OR ".join([f'text ~ "{kw}"' for kw in keywords])
            jql_parts.append(f"({text_search})")

        jql = " AND ".join(jql_parts)

        url = f"{self.url}/rest/api/3/search"

        params = {
            "jql": jql,
            "maxResults": limit,
            "fields": "key,summary,status,priority,created,updated",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        issues = data.get("issues", [])
                        logger.info(f"Found {len(issues)} related Jira issues")
                        return issues
                    else:
                        logger.error(f"Failed to search Jira issues: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Failed to search Jira issues: {e}")
            return []
