"""
Slack Integration

Post RCA summaries, alerts, and notifications to Slack channels.

v4.0: Enhanced with async HTTP for webhook integration
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import os
import aiohttp

logger = logging.getLogger(__name__)


class SlackIntegration:
    """
    Slack integration for ADAPT.

    Requires: pip install slack-sdk
    """

    def __init__(self, bot_token: Optional[str] = None, webhook_url: Optional[str] = None):
        """
        Initialize Slack integration.

        Args:
            bot_token: Slack bot token (for SDK)
            webhook_url: Slack webhook URL (for simple posting)
        """
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN")
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.client = None

        if self.bot_token:
            try:
                from slack_sdk.web.async_client import AsyncWebClient

                self.client = AsyncWebClient(token=self.bot_token)
                logger.info("Initialized Slack SDK client")
            except ImportError:
                logger.warning(
                    "slack-sdk not installed. Install with: pip install slack-sdk"
                )

    async def post_rca_summary(
        self, channel: str, rca_context, dashboard_url: Optional[str] = None
    ) -> bool:
        """
        Post RCA summary to Slack channel.

        Args:
            channel: Slack channel (#incidents, C1234567, etc.)
            rca_context: OrchestrationContext from RCA
            dashboard_url: Optional URL to RCA dashboard

        Returns:
            True if posted successfully
        """
        if not self.client and not self.webhook_url:
            logger.error("Slack not configured (need bot token or webhook URL)")
            return False

        # Build Slack blocks
        blocks = self._build_rca_blocks(rca_context, dashboard_url)

        try:
            if self.client:
                response = await self.client.chat_postMessage(
                    channel=channel, blocks=blocks, text=f"RCA Complete: {rca_context.incident_id}"
                )
                logger.info(f"Posted RCA summary to {channel}: {response['ts']}")
                return True
            elif self.webhook_url:
                # v4.0: Use async HTTP with aiohttp (no blocking)
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.webhook_url, json={"blocks": blocks}
                    ) as response:
                        if response.status == 200:
                            logger.info(f"Posted RCA summary via webhook")
                            return True
                        else:
                            logger.error(
                                f"Webhook returned status {response.status}"
                            )
                            return False

        except Exception as e:
            logger.error(f"Failed to post to Slack: {e}")
            return False

    def _build_rca_blocks(self, rca_context, dashboard_url: Optional[str] = None) -> List[Dict]:
        """Build Slack Block Kit blocks for RCA summary"""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🔍 RCA Complete: {rca_context.incident_id}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Duration:*\n{(rca_context.end_time - rca_context.start_time).total_seconds():.1f}s",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Agents Run:*\n{len(rca_context.agent_results)}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Signals Analyzed:*\n{len(rca_context.signals)}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Mode:*\n{rca_context.metadata.get('execution_mode', 'adaptive')}",
                    },
                ],
            },
            {"type": "divider"},
        ]

        # Add root causes
        root_causes = rca_context.graph.get_root_causes()
        if root_causes:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🎯 Root Causes ({len(root_causes)})*",
                    },
                }
            )

            for rc in sorted(root_causes, key=lambda x: x.confidence, reverse=True):
                confidence_emoji = "🟢" if rc.confidence > 0.8 else "🟡" if rc.confidence > 0.6 else "🔴"
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{confidence_emoji} *{rc.title}* ({rc.confidence:.0%})\n{rc.description[:200]}",
                        },
                    }
                )

        else:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "⚠️ *No high-confidence root causes identified*",
                    },
                }
            )

        # Add key findings
        all_findings = []
        for result in rca_context.agent_results.values():
            if isinstance(result, dict) and result.get("success"):
                all_findings.extend(result.get("findings", []))

        if all_findings:
            blocks.append({"type": "divider"})
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*📊 Key Findings ({len(all_findings)})*",
                    },
                }
            )

            # Show top 3 findings
            for finding in sorted(
                all_findings, key=lambda x: x.get("confidence", 0), reverse=True
            )[:3]:
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"• {finding.get('title', 'Unknown finding')} ({finding.get('confidence', 0):.0%})",
                        },
                    }
                )

        # Add action buttons
        elements = []

        if dashboard_url:
            elements.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Full RCA", "emoji": True},
                    "url": dashboard_url,
                    "style": "primary",
                }
            )

        elements.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Export Report", "emoji": True},
                "action_id": "export_rca_report",
            }
        )

        if elements:
            blocks.append({"type": "divider"})
            blocks.append({"type": "actions", "elements": elements})

        return blocks

    async def post_alert(
        self,
        channel: str,
        title: str,
        message: str,
        severity: str = "medium",
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Post an alert to Slack.

        Args:
            channel: Slack channel
            title: Alert title
            message: Alert message
            severity: Alert severity (low, medium, high, critical)
            details: Optional additional details

        Returns:
            True if posted successfully
        """
        if not self.client and not self.webhook_url:
            return False

        # Map severity to color and emoji
        severity_config = {
            "low": {"color": "#36a64f", "emoji": "ℹ️"},
            "medium": {"color": "#ffcc00", "emoji": "⚠️"},
            "high": {"color": "#ff6600", "emoji": "🚨"},
            "critical": {"color": "#ff0000", "emoji": "🔥"},
        }

        config = severity_config.get(severity, severity_config["medium"])

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{config['emoji']} {title}",
                    "emoji": True,
                },
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": message}},
        ]

        # Add details if provided
        if details:
            fields = []
            for key, value in details.items():
                fields.append({"type": "mrkdwn", "text": f"*{key}:*\n{value}"})

            blocks.append({"type": "section", "fields": fields})

        try:
            if self.client:
                response = await self.client.chat_postMessage(
                    channel=channel, blocks=blocks, text=title
                )
                return True
            elif self.webhook_url:
                # v4.0: Use async HTTP with aiohttp (no blocking)
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.webhook_url, json={"blocks": blocks}
                    ) as response:
                        return response.status == 200

        except Exception as e:
            logger.error(f"Failed to post alert to Slack: {e}")
            return False

    async def post_thread_reply(
        self, channel: str, thread_ts: str, message: str
    ) -> bool:
        """
        Reply to a thread.

        Args:
            channel: Slack channel
            thread_ts: Thread timestamp
            message: Reply message

        Returns:
            True if posted successfully
        """
        if not self.client:
            logger.error("Thread replies require Slack SDK client")
            return False

        try:
            await self.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts, text=message
            )
            return True
        except Exception as e:
            logger.error(f"Failed to post thread reply: {e}")
            return False
