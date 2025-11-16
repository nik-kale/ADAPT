"""
Synthetic Data Connector

Generates synthetic telemetry data for testing and demonstration.
Can load data from JSON files or generate programmatically.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import random

from .base import BaseConnector, ConnectorConfig
from core.signal_normalizer import NormalizedSignal, SignalNormalizer, SignalType


class SyntheticConnector(BaseConnector):
    """
    Connector that provides synthetic telemetry data.

    This connector can:
    1. Load pre-generated synthetic data from JSON files
    2. Generate random synthetic data on-the-fly
    3. Replay incident scenarios from playbook definitions
    """

    def __init__(self, config: ConnectorConfig, data_dir: Optional[str] = None):
        """
        Initialize the synthetic connector.

        Args:
            config: Connector configuration
            data_dir: Directory containing synthetic data files
        """
        super().__init__(config)
        self.data_dir = Path(data_dir) if data_dir else None
        self.loaded_data: Dict[str, List[Dict[str, Any]]] = {}

    async def connect(self) -> bool:
        """Load synthetic data if data_dir is specified."""
        if self.data_dir and self.data_dir.exists():
            await self._load_data()
        return True

    async def disconnect(self) -> None:
        """Clear loaded data."""
        self.loaded_data.clear()

    async def _load_data(self) -> None:
        """Load synthetic data from JSON files in data_dir."""
        if not self.data_dir:
            return

        # Load logs
        logs_file = self.data_dir / "logs.json"
        if logs_file.exists():
            with open(logs_file, 'r') as f:
                self.loaded_data['logs'] = json.load(f)

        # Load metrics
        metrics_file = self.data_dir / "metrics.json"
        if metrics_file.exists():
            with open(metrics_file, 'r') as f:
                self.loaded_data['metrics'] = json.load(f)

        # Load config changes
        changes_file = self.data_dir / "config_changes.json"
        if changes_file.exists():
            with open(changes_file, 'r') as f:
                self.loaded_data['config_changes'] = json.load(f)

    async def fetch_logs(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[NormalizedSignal]:
        """Fetch synthetic log entries."""
        if 'logs' in self.loaded_data:
            # Use pre-loaded data
            raw_logs = self._filter_by_time(
                self.loaded_data['logs'],
                start_time,
                end_time
            )
        else:
            # Generate synthetic logs
            raw_logs = self._generate_synthetic_logs(start_time, end_time)

        # Normalize
        signals = []
        for log in raw_logs:
            signal = SignalNormalizer.normalize_log_entry(
                log,
                source=self.config.endpoint or "synthetic"
            )
            signals.append(signal)

        # Apply additional filters
        if filters:
            signals = self._apply_filters(signals, filters)

        return signals

    async def fetch_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        metric_names: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[NormalizedSignal]:
        """Fetch synthetic metrics."""
        if 'metrics' in self.loaded_data:
            raw_metrics = self._filter_by_time(
                self.loaded_data['metrics'],
                start_time,
                end_time
            )
        else:
            raw_metrics = self._generate_synthetic_metrics(start_time, end_time)

        # Filter by metric names
        if metric_names:
            raw_metrics = [
                m for m in raw_metrics
                if m.get('name') in metric_names or m.get('metric') in metric_names
            ]

        # Normalize
        signals = []
        for metric in raw_metrics:
            signal = SignalNormalizer.normalize_metric(
                metric,
                source=self.config.endpoint or "synthetic"
            )
            signals.append(signal)

        # Apply additional filters
        if filters:
            signals = self._apply_filters(signals, filters)

        return signals

    async def fetch_config_changes(
        self,
        start_time: datetime,
        end_time: datetime,
        components: Optional[List[str]] = None
    ) -> List[NormalizedSignal]:
        """Fetch synthetic configuration changes."""
        if 'config_changes' in self.loaded_data:
            raw_changes = self._filter_by_time(
                self.loaded_data['config_changes'],
                start_time,
                end_time
            )
        else:
            raw_changes = self._generate_synthetic_config_changes(start_time, end_time)

        # Filter by components
        if components:
            raw_changes = [
                c for c in raw_changes
                if c.get('component') in components
            ]

        # Normalize
        signals = []
        for change in raw_changes:
            signal = SignalNormalizer.normalize_config_change(
                change,
                source=self.config.endpoint or "synthetic"
            )
            signals.append(signal)

        return signals

    def _filter_by_time(
        self,
        data: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Filter data by timestamp."""
        filtered = []
        for item in data:
            timestamp_str = item.get('timestamp', item.get('time'))
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if start_time <= timestamp <= end_time:
                        filtered.append(item)
                except (ValueError, AttributeError):
                    pass
        return filtered

    def _apply_filters(
        self,
        signals: List[NormalizedSignal],
        filters: Dict[str, Any]
    ) -> List[NormalizedSignal]:
        """Apply additional filters to signals."""
        filtered = signals

        if 'severity' in filters:
            filtered = [s for s in filtered if s.severity == filters['severity']]

        if 'source' in filters:
            filtered = [s for s in filtered if s.source == filters['source']]

        if 'tags' in filters:
            for key, value in filters['tags'].items():
                filtered = [s for s in filtered if s.tags.get(key) == value]

        return filtered

    def _generate_synthetic_logs(
        self,
        start_time: datetime,
        end_time: datetime,
        count: int = 50
    ) -> List[Dict[str, Any]]:
        """Generate random synthetic log entries."""
        logs = []
        time_delta = (end_time - start_time) / count

        log_templates = [
            ("info", "Request processed successfully"),
            ("info", "Database query executed in {}ms"),
            ("warn", "High memory usage detected: {}%"),
            ("error", "Connection timeout to service {}"),
            ("error", "Failed to authenticate user request"),
            ("fatal", "Critical system error: {}"),
        ]

        for i in range(count):
            timestamp = start_time + (time_delta * i)
            level, message_template = random.choice(log_templates)

            # Add some variation to messages
            if '{}' in message_template:
                if 'ms' in message_template:
                    message = message_template.format(random.randint(100, 5000))
                elif '%' in message_template:
                    message = message_template.format(random.randint(70, 95))
                else:
                    message = message_template.format(f"service-{random.randint(1, 5)}")
            else:
                message = message_template

            logs.append({
                'timestamp': timestamp.isoformat(),
                'level': level,
                'message': message,
                'logger': f'service-{random.randint(1, 3)}',
            })

        return logs

    def _generate_synthetic_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        count: int = 30
    ) -> List[Dict[str, Any]]:
        """Generate random synthetic metrics."""
        metrics = []
        time_delta = (end_time - start_time) / count

        metric_templates = [
            ('http_request_latency_ms', 100, 500),
            ('cpu_usage_percent', 20, 80),
            ('memory_usage_percent', 40, 85),
            ('error_rate_percent', 0, 5),
            ('requests_per_second', 100, 1000),
        ]

        for i in range(count):
            timestamp = start_time + (time_delta * i)

            for metric_name, min_val, max_val in metric_templates:
                value = random.uniform(min_val, max_val)
                metrics.append({
                    'timestamp': timestamp.isoformat(),
                    'name': metric_name,
                    'value': value,
                    'unit': 'ms' if 'latency' in metric_name else 'percent' if 'percent' in metric_name else 'count',
                    'tags': {'environment': 'production', 'region': 'us-west-2'},
                })

        return metrics

    def _generate_synthetic_config_changes(
        self,
        start_time: datetime,
        end_time: datetime,
        count: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate random synthetic configuration changes."""
        changes = []
        time_delta = (end_time - start_time) / count if count > 0 else timedelta(0)

        components = ['api-gateway', 'database', 'cache-layer', 'auth-service']
        change_types = ['update', 'create', 'delete']

        for i in range(count):
            timestamp = start_time + (time_delta * i)

            changes.append({
                'timestamp': timestamp.isoformat(),
                'component': random.choice(components),
                'change_type': random.choice(change_types),
                'changed_by': 'deployment-automation',
                'before': {'version': f'1.{i}.0'},
                'after': {'version': f'1.{i+1}.0'},
                'severity': 'medium',
            })

        return changes
