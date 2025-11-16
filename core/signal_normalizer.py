"""
Signal Normalization Layer

Provides a unified interface for ingesting and normalizing telemetry signals
from various sources (logs, metrics, traces, config changes).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class SignalType(Enum):
    """Types of telemetry signals"""
    LOG = "log"
    METRIC = "metric"
    TRACE = "trace"
    CONFIG_CHANGE = "config_change"
    ALERT = "alert"
    EVENT = "event"


@dataclass
class NormalizedSignal:
    """
    A normalized telemetry signal from any source.

    Attributes:
        signal_type: Type of signal (log, metric, trace, etc.)
        title: Short title for the signal
        description: Detailed description
        timestamp: When the signal was captured
        source: Origin of the signal (service, host, component)
        severity: Severity level (low, medium, high, critical)
        raw_data: Original raw data
        metadata: Additional structured metadata
        tags: Key-value tags for filtering and grouping
    """
    signal_type: SignalType
    title: str
    description: str
    timestamp: datetime
    source: str
    severity: str = "medium"
    raw_data: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert signal to dictionary"""
        return {
            'signal_type': self.signal_type.value,
            'title': self.title,
            'description': self.description,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'severity': self.severity,
            'metadata': self.metadata,
            'tags': self.tags,
        }


class SignalNormalizer:
    """
    Normalizes raw telemetry data into NormalizedSignal objects.

    This class provides adapters for different data formats and sources.
    """

    @staticmethod
    def normalize_log_entry(
        log_entry: Dict[str, Any],
        source: str = "unknown"
    ) -> NormalizedSignal:
        """
        Normalize a log entry into a NormalizedSignal.

        Args:
            log_entry: Raw log entry (dict with message, level, timestamp, etc.)
            source: Source identifier

        Returns:
            NormalizedSignal instance
        """
        # Extract standard log fields
        message = log_entry.get('message', log_entry.get('msg', 'No message'))
        level = log_entry.get('level', log_entry.get('severity', 'info')).lower()

        # Parse timestamp
        timestamp_str = log_entry.get('timestamp', log_entry.get('time'))
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()

        # Map log level to severity
        severity_map = {
            'debug': 'low',
            'info': 'low',
            'warn': 'medium',
            'warning': 'medium',
            'error': 'high',
            'fatal': 'critical',
            'critical': 'critical',
        }
        severity = severity_map.get(level, 'medium')

        return NormalizedSignal(
            signal_type=SignalType.LOG,
            title=f"Log: {message[:50]}...",
            description=message,
            timestamp=timestamp,
            source=source,
            severity=severity,
            raw_data=log_entry,
            metadata={
                'log_level': level,
                'logger': log_entry.get('logger', 'unknown'),
            },
            tags={k: str(v) for k, v in log_entry.items()
                  if k not in ['message', 'msg', 'timestamp', 'time', 'level', 'severity']}
        )

    @staticmethod
    def normalize_metric(
        metric_data: Dict[str, Any],
        source: str = "unknown"
    ) -> NormalizedSignal:
        """
        Normalize a metric data point into a NormalizedSignal.

        Args:
            metric_data: Raw metric data (name, value, timestamp, etc.)
            source: Source identifier

        Returns:
            NormalizedSignal instance
        """
        metric_name = metric_data.get('name', metric_data.get('metric', 'unknown_metric'))
        value = metric_data.get('value', 0)

        # Parse timestamp
        timestamp_str = metric_data.get('timestamp')
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()

        # Determine severity based on thresholds (if provided)
        threshold = metric_data.get('threshold')
        severity = 'low'
        if threshold:
            if value > threshold.get('critical', float('inf')):
                severity = 'critical'
            elif value > threshold.get('warning', float('inf')):
                severity = 'high'

        return NormalizedSignal(
            signal_type=SignalType.METRIC,
            title=f"Metric: {metric_name}",
            description=f"{metric_name} = {value}",
            timestamp=timestamp,
            source=source,
            severity=severity,
            raw_data=metric_data,
            metadata={
                'metric_name': metric_name,
                'value': value,
                'unit': metric_data.get('unit', ''),
            },
            tags=metric_data.get('tags', {})
        )

    @staticmethod
    def normalize_config_change(
        change_data: Dict[str, Any],
        source: str = "unknown"
    ) -> NormalizedSignal:
        """
        Normalize a configuration change event into a NormalizedSignal.

        Args:
            change_data: Raw change data (component, before, after, etc.)
            source: Source identifier

        Returns:
            NormalizedSignal instance
        """
        component = change_data.get('component', 'unknown')
        change_type = change_data.get('change_type', 'update')

        timestamp_str = change_data.get('timestamp')
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()

        # Config changes are typically medium severity unless flagged
        severity = change_data.get('severity', 'medium')

        return NormalizedSignal(
            signal_type=SignalType.CONFIG_CHANGE,
            title=f"Config Change: {component}",
            description=f"{change_type} in {component}",
            timestamp=timestamp,
            source=source,
            severity=severity,
            raw_data=change_data,
            metadata={
                'component': component,
                'change_type': change_type,
                'before': change_data.get('before'),
                'after': change_data.get('after'),
                'changed_by': change_data.get('changed_by', 'unknown'),
            },
            tags=change_data.get('tags', {})
        )

    @staticmethod
    def normalize_batch(
        raw_signals: List[Dict[str, Any]],
        signal_type: SignalType,
        source: str = "unknown"
    ) -> List[NormalizedSignal]:
        """
        Normalize a batch of raw signals.

        Args:
            raw_signals: List of raw signal data
            signal_type: Type of signals in the batch
            source: Source identifier

        Returns:
            List of NormalizedSignal instances
        """
        normalized = []

        for raw_signal in raw_signals:
            if signal_type == SignalType.LOG:
                normalized.append(
                    SignalNormalizer.normalize_log_entry(raw_signal, source)
                )
            elif signal_type == SignalType.METRIC:
                normalized.append(
                    SignalNormalizer.normalize_metric(raw_signal, source)
                )
            elif signal_type == SignalType.CONFIG_CHANGE:
                normalized.append(
                    SignalNormalizer.normalize_config_change(raw_signal, source)
                )
            # TODO: Add normalizers for traces, alerts, events

        return normalized
