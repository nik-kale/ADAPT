"""
GitHub Integration

Correlate incidents with code changes, create issues from RCA findings,
and track deployment-related failures.

v5.0: Advanced integration ecosystem expansion
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import os
import aiohttp

from core.signals import NormalizedSignal, SignalType

logger = logging.getLogger(__name__)


class GitHubIntegration:
    """
    GitHub integration for ADAPT (v5.0).

    Features:
    - Fetch recent commits and deployments
    - Correlate code changes with incidents
    - Create issues from RCA findings
    - Post RCA summaries as comments
    - Track deployment failures
    """

    def __init__(
        self,
        token: Optional[str] = None,
        org: Optional[str] = None,
        repo: Optional[str] = None
    ):
        """
        Initialize GitHub integration.

        Args:
            token: GitHub personal access token
            org: GitHub organization name
            repo: Repository name (without org)
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.org = org or os.getenv("GITHUB_ORG")
        self.repo = repo or os.getenv("GITHUB_REPO")

        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.token}" if self.token else "",
        }

        if not self.token:
            logger.warning(
                "GitHub token not configured. Set GITHUB_TOKEN environment variable."
            )

    async def fetch_recent_commits(
        self,
        start_time: datetime,
        end_time: datetime,
        branch: str = "main"
    ) -> List[NormalizedSignal]:
        """
        Fetch recent commits as change signals (v5.0).

        Helps correlate deployments with incidents.

        Args:
            start_time: Start of time window
            end_time: End of time window
            branch: Git branch to fetch from

        Returns:
            List of commit signals
        """
        if not self.token or not self.org or not self.repo:
            logger.error("GitHub not fully configured (need token, org, repo)")
            return []

        url = f"{self.base_url}/repos/{self.org}/{self.repo}/commits"

        params = {
            "sha": branch,
            "since": start_time.isoformat(),
            "until": end_time.isoformat(),
            "per_page": 100,
        }

        signals = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status != 200:
                        logger.error(f"GitHub API returned status {response.status}")
                        return []

                    commits = await response.json()

                    for commit in commits:
                        commit_data = commit.get("commit", {})
                        author = commit_data.get("author", {})

                        signal = NormalizedSignal(
                            signal_type=SignalType.CHANGE,
                            title=f"Code Change: {commit_data.get('message', 'Unknown').split(chr(10))[0][:100]}",
                            description=commit_data.get("message", ""),
                            timestamp=datetime.fromisoformat(
                                author.get("date", datetime.utcnow().isoformat()).replace("Z", "+00:00")
                            ),
                            source=f"github:{self.org}/{self.repo}",
                            severity="medium",
                            metadata={
                                "sha": commit.get("sha"),
                                "author": author.get("name"),
                                "author_email": author.get("email"),
                                "url": commit.get("html_url"),
                                "branch": branch,
                                "stats": commit.get("stats", {}),
                            },
                            tags={
                                "source": "github",
                                "type": "commit",
                                "repo": f"{self.org}/{self.repo}",
                                "branch": branch,
                            },
                        )

                        signals.append(signal)

            logger.info(f"Fetched {len(signals)} commits from GitHub")
            return signals

        except Exception as e:
            logger.error(f"Failed to fetch GitHub commits: {e}")
            return []

    async def fetch_recent_deployments(
        self,
        start_time: datetime,
        end_time: datetime,
        environment: str = "production"
    ) -> List[NormalizedSignal]:
        """
        Fetch recent deployments as change signals (v5.0).

        Args:
            start_time: Start of time window
            end_time: End of time window
            environment: Deployment environment

        Returns:
            List of deployment signals
        """
        if not self.token or not self.org or not self.repo:
            return []

        url = f"{self.base_url}/repos/{self.org}/{self.repo}/deployments"

        params = {
            "environment": environment,
            "per_page": 100,
        }

        signals = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status != 200:
                        logger.error(f"GitHub API returned status {response.status}")
                        return []

                    deployments = await response.json()

                    for deployment in deployments:
                        created_at = datetime.fromisoformat(
                            deployment.get("created_at", "").replace("Z", "+00:00")
                        )

                        # Filter by time window
                        if not (start_time <= created_at <= end_time):
                            continue

                        # Get deployment status
                        statuses_url = deployment.get("statuses_url")
                        status_info = await self._get_deployment_status(session, statuses_url)

                        severity = "high" if status_info.get("state") == "failure" else "medium"

                        signal = NormalizedSignal(
                            signal_type=SignalType.CHANGE,
                            title=f"Deployment to {environment}: {deployment.get('ref')}",
                            description=deployment.get("description", ""),
                            timestamp=created_at,
                            source=f"github:{self.org}/{self.repo}",
                            severity=severity,
                            metadata={
                                "deployment_id": deployment.get("id"),
                                "ref": deployment.get("ref"),
                                "sha": deployment.get("sha"),
                                "environment": environment,
                                "creator": deployment.get("creator", {}).get("login"),
                                "url": deployment.get("url"),
                                "status": status_info.get("state"),
                            },
                            tags={
                                "source": "github",
                                "type": "deployment",
                                "repo": f"{self.org}/{self.repo}",
                                "environment": environment,
                            },
                        )

                        signals.append(signal)

            logger.info(f"Fetched {len(signals)} deployments from GitHub")
            return signals

        except Exception as e:
            logger.error(f"Failed to fetch GitHub deployments: {e}")
            return []

    async def _get_deployment_status(
        self,
        session: aiohttp.ClientSession,
        statuses_url: str
    ) -> Dict[str, Any]:
        """Get the latest deployment status"""
        try:
            async with session.get(statuses_url, headers=self.headers) as response:
                if response.status == 200:
                    statuses = await response.json()
                    if statuses:
                        # Return the most recent status
                        return statuses[0]
        except Exception as e:
            logger.warning(f"Failed to get deployment status: {e}")

        return {"state": "unknown"}

    async def create_issue_from_rca(
        self,
        rca_context,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Create a GitHub issue from RCA findings (v5.0).

        Args:
            rca_context: OrchestrationContext from RCA
            labels: Issue labels
            assignees: GitHub usernames to assign

        Returns:
            Issue URL if successful, None otherwise
        """
        if not self.token or not self.org or not self.repo:
            logger.error("GitHub not fully configured")
            return None

        # Build issue title and body
        root_causes = rca_context.graph.get_root_causes()

        title = f"🔍 RCA: {rca_context.incident_id}"

        if root_causes:
            top_cause = max(root_causes, key=lambda x: x.confidence)
            title = f"🔍 RCA: {top_cause.title[:80]}"

        # Build issue body with findings
        body_parts = [
            f"# Root Cause Analysis: {rca_context.incident_id}",
            "",
            f"**Incident ID**: {rca_context.incident_id}",
            f"**Analysis Time**: {rca_context.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Execution Mode**: {rca_context.metadata.get('execution_mode', 'adaptive')}",
            "",
            "## Root Causes",
            "",
        ]

        if root_causes:
            for rc in sorted(root_causes, key=lambda x: x.confidence, reverse=True):
                confidence_emoji = "🟢" if rc.confidence > 0.8 else "🟡" if rc.confidence > 0.6 else "🔴"
                body_parts.append(f"{confidence_emoji} **{rc.title}** ({rc.confidence:.0%})")
                body_parts.append(f"   {rc.description}")
                body_parts.append("")
        else:
            body_parts.append("⚠️ No high-confidence root causes identified")
            body_parts.append("")

        # Add key findings
        all_findings = []
        for result in rca_context.agent_results.values():
            if isinstance(result, dict) and result.get("success"):
                all_findings.extend(result.get("findings", []))

        if all_findings:
            body_parts.append("## Key Findings")
            body_parts.append("")
            for finding in sorted(
                all_findings, key=lambda x: x.get("confidence", 0), reverse=True
            )[:5]:
                body_parts.append(f"- **{finding.get('title', 'Unknown')}** ({finding.get('confidence', 0):.0%})")
                body_parts.append(f"  {finding.get('description', '')[:200]}")

        body = "\n".join(body_parts)

        # Create issue
        url = f"{self.base_url}/repos/{self.org}/{self.repo}/issues"

        data = {
            "title": title,
            "body": body,
            "labels": labels or ["incident", "rca"],
            "assignees": assignees or [],
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=data) as response:
                    if response.status == 201:
                        issue_data = await response.json()
                        issue_url = issue_data.get("html_url")
                        logger.info(f"Created GitHub issue: {issue_url}")
                        return issue_url
                    else:
                        logger.error(f"Failed to create GitHub issue: {response.status}")
                        error_text = await response.text()
                        logger.error(f"Error: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Failed to create GitHub issue: {e}")
            return None

    async def post_comment(
        self,
        issue_number: int,
        comment: str
    ) -> bool:
        """
        Post a comment on a GitHub issue (v5.0).

        Args:
            issue_number: Issue number
            comment: Comment text

        Returns:
            True if successful
        """
        if not self.token or not self.org or not self.repo:
            return False

        url = f"{self.base_url}/repos/{self.org}/{self.repo}/issues/{issue_number}/comments"

        data = {"body": comment}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=data) as response:
                    if response.status == 201:
                        logger.info(f"Posted comment to issue #{issue_number}")
                        return True
                    else:
                        logger.error(f"Failed to post comment: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Failed to post comment: {e}")
            return False

    async def search_related_issues(
        self,
        keywords: List[str],
        labels: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for related issues (v5.0).

        Args:
            keywords: Keywords to search for
            labels: Filter by labels
            limit: Maximum results

        Returns:
            List of related issues
        """
        if not self.token or not self.org or not self.repo:
            return []

        # Build search query
        query_parts = [
            f"repo:{self.org}/{self.repo}",
            "is:issue",
        ]

        if keywords:
            query_parts.append(" ".join(keywords))

        if labels:
            for label in labels:
                query_parts.append(f"label:{label}")

        query = " ".join(query_parts)

        url = f"{self.base_url}/search/issues"

        params = {
            "q": query,
            "sort": "created",
            "order": "desc",
            "per_page": limit,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        issues = data.get("items", [])
                        logger.info(f"Found {len(issues)} related issues")
                        return issues
                    else:
                        logger.error(f"Failed to search issues: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Failed to search issues: {e}")
            return []
