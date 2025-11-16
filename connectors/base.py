"""
Base Connector Interface

Abstract base class for all data connectors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

from core.signal_normalizer import NormalizedSignal, SignalType


@dataclass
class ConnectorConfig:
    """
    Configuration for a connector.

    Attributes:
        connector_type: Type of connector (synthetic, prometheus, elasticsearch, etc.)
        endpoint: Connection endpoint (URL, file path, etc.)
        credentials: Authentication credentials
        filters: Filters to apply when fetching data
        batch_size: Number of records to fetch per batch
    """
    connector_type: str
    endpoint: str = ""
    credentials: Optional[Dict[str, str]] = None
    filters: Dict[str, Any] = None
    batch_size: int = 100

    def __post_init__(self):
        if self.credentials is None:
            self.credentials = {}
        if self.filters is None:
            self.filters = {}


class BaseConnector(ABC):
    """
    Abstract base class for all telemetry data connectors.

    All connectors must implement methods to fetch and normalize
    logs, metrics, traces, and configuration changes.
    """

    def __init__(self, config: ConnectorConfig):
        """
        Initialize the connector.

        Args:
            config: Connector configuration
        """
        self.config = config

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the data source.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection to the data source."""
        pass

    @abstractmethod
    async def fetch_logs(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[NormalizedSignal]:
        """
        Fetch log entries within a time range.

        Args:
            start_time: Start of time window
            end_time: End of time window
            filters: Additional filters (service, severity, etc.)

        Returns:
            List of normalized log signals
        """
        pass

    @abstractmethod
    async def fetch_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        metric_names: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[NormalizedSignal]:
        """
        Fetch metrics within a time range.

        Args:
            start_time: Start of time window
            end_time: End of time window
            metric_names: Specific metrics to fetch (None = all)
            filters: Additional filters

        Returns:
            List of normalized metric signals
        """
        pass

    @abstractmethod
    async def fetch_config_changes(
        self,
        start_time: datetime,
        end_time: datetime,
        components: Optional[List[str]] = None
    ) -> List[NormalizedSignal]:
        """
        Fetch configuration changes within a time range.

        Args:
            start_time: Start of time window
            end_time: End of time window
            components: Specific components to check (None = all)

        Returns:
            List of normalized config change signals
        """
        pass

    async def fetch_all_signals(
        self,
        start_time: datetime,
        end_time: datetime,
        signal_types: Optional[List[SignalType]] = None
    ) -> List[NormalizedSignal]:
        """
        Fetch all available signals within a time range.

        Args:
            start_time: Start of time window
            end_time: End of time window
            signal_types: Types of signals to fetch (None = all)

        Returns:
            Combined list of all normalized signals
        """
        if signal_types is None:
            signal_types = [SignalType.LOG, SignalType.METRIC, SignalType.CONFIG_CHANGE]

        all_signals = []

        if SignalType.LOG in signal_types:
            logs = await self.fetch_logs(start_time, end_time)
            all_signals.extend(logs)

        if SignalType.METRIC in signal_types:
            metrics = await self.fetch_metrics(start_time, end_time)
            all_signals.extend(metrics)

        if SignalType.CONFIG_CHANGE in signal_types:
            changes = await self.fetch_config_changes(start_time, end_time)
            all_signals.extend(changes)

        # Sort by timestamp
        all_signals.sort(key=lambda s: s.timestamp)

        return all_signals
