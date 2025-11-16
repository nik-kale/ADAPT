"""
Prometheus Connector

Fetches metrics from Prometheus for RCA analysis.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .base import BaseConnector, ConnectorConfig
from core.signal_normalizer import SignalNormalizer, NormalizedSignal, SignalType

logger = logging.getLogger(__name__)


class PrometheusConnector(BaseConnector):
    """
    Connector for Prometheus metrics platform.

    Requires: pip install prometheus-api-client
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.client = None

    async def connect(self) -> bool:
        """Connect to Prometheus"""
        try:
            from prometheus_api_client import PrometheusConnect

            self.client = PrometheusConnect(
                url=self.config.endpoint, disable_ssl=False
            )

            # Test connection
            self.client.check_prometheus_connection()

            logger.info(f"Connected to Prometheus at {self.config.endpoint}")
            return True

        except ImportError:
            raise ImportError(
                "prometheus-api-client not installed. "
                "Install with: pip install prometheus-api-client"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Prometheus: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Prometheus"""
        self.client = None
        logger.info("Disconnected from Prometheus")

    async def fetch_logs(
        self, start_time: datetime, end_time: datetime, filters: Optional[Dict[str, Any]] = None
    ) -> List[NormalizedSignal]:
        """Prometheus doesn't have logs, return empty list"""
        return []

    async def fetch_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        metric_names: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[NormalizedSignal]:
        """
        Fetch metrics from Prometheus.

        Args:
            start_time: Start of time range
            end_time: End of time range
            metric_names: Specific metrics to fetch (None = common SRE metrics)
            filters: Additional label filters

        Returns:
            List of normalized metric signals
        """
        if not self.client:
            raise RuntimeError("Not connected to Prometheus")

        # Default to common SRE metrics if not specified
        if metric_names is None:
            metric_names = [
                # Availability
                "up",
                # Request metrics
                "http_requests_total",
                "http_request_duration_seconds",
                # Resource metrics
                "node_cpu_seconds_total",
                "node_memory_MemAvailable_bytes",
                "node_disk_io_time_seconds_total",
                # Application metrics
                "process_cpu_seconds_total",
                "process_resident_memory_bytes",
                # Error rates
                "http_requests_errors_total",
            ]

        signals = []

        for metric_name in metric_names:
            try:
                # Build query
                query = metric_name

                # Add label filters
                if filters:
                    label_filters = ",".join([f'{k}="{v}"' for k, v in filters.items()])
                    query = f"{metric_name}{{{label_filters}}}"

                # Query range
                result = self.client.custom_query_range(
                    query=query,
                    start_time=start_time,
                    end_time=end_time,
                    step="30s",  # 30 second resolution
                )

                # Convert to normalized signals
                for series in result:
                    metric_labels = series.get("metric", {})
                    instance = metric_labels.get("instance", "unknown")

                    for timestamp, value in series.get("values", []):
                        try:
                            value_float = float(value)
                        except (ValueError, TypeError):
                            continue

                        # Determine severity based on metric type and value
                        severity = self._calculate_severity(
                            metric_name, value_float, metric_labels
                        )

                        signal = NormalizedSignal(
                            signal_type=SignalType.METRIC,
                            title=f"Metric: {metric_name}",
                            description=f"{metric_name} = {value_float}",
                            timestamp=datetime.fromtimestamp(timestamp),
                            source=instance,
                            severity=severity,
                            metadata={
                                "metric_name": metric_name,
                                "value": value_float,
                                "labels": metric_labels,
                                "datasource": "prometheus",
                            },
                            tags=metric_labels,
                        )

                        signals.append(signal)

            except Exception as e:
                logger.warning(f"Failed to fetch metric {metric_name}: {e}")
                continue

        logger.info(f"Fetched {len(signals)} metric signals from Prometheus")
        return signals

    async def fetch_config_changes(
        self,
        start_time: datetime,
        end_time: datetime,
        components: Optional[List[str]] = None,
    ) -> List[NormalizedSignal]:
        """
        Prometheus doesn't track config changes directly.
        Could potentially detect changes by querying prometheus_config_last_reload_success_timestamp
        """
        return []

    def _calculate_severity(
        self, metric_name: str, value: float, labels: Dict[str, str]
    ) -> str:
        """Calculate severity based on metric name and value"""

        # Up metric (0 = down, 1 = up)
        if metric_name == "up":
            return "critical" if value == 0 else "low"

        # CPU usage (normalize from seconds)
        if "cpu" in metric_name.lower():
            # High CPU usage
            if value > 0.9:  # 90%+
                return "high"
            elif value > 0.7:  # 70%+
                return "medium"

        # Memory
        if "memory" in metric_name.lower() or "mem" in metric_name.lower():
            # Low available memory
            if "available" in metric_name.lower():
                if value < 1e9:  # < 1GB
                    return "high"
                elif value < 5e9:  # < 5GB
                    return "medium"

        # Errors
        if "error" in metric_name.lower():
            if value > 10:
                return "high"
            elif value > 0:
                return "medium"

        # HTTP duration (in seconds)
        if "duration" in metric_name.lower() or "latency" in metric_name.lower():
            if value > 5.0:  # > 5 seconds
                return "high"
            elif value > 1.0:  # > 1 second
                return "medium"

        return "low"
