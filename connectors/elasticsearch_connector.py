"""
Elasticsearch Connector

Fetches logs and metrics from Elasticsearch for RCA analysis.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .base import BaseConnector, ConnectorConfig
from core.signal_normalizer import SignalNormalizer, NormalizedSignal, SignalType

logger = logging.getLogger(__name__)


class ElasticsearchConnector(BaseConnector):
    """
    Connector for Elasticsearch.

    Supports:
    - Elasticsearch logs
    - ELK stack integration
    - APM data
    - Custom indices
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.client = None
        self.log_index_pattern = config.filters.get('log_index', 'logs-*')
        self.metric_index_pattern = config.filters.get('metric_index', 'metrics-*')

    async def connect(self) -> bool:
        """Connect to Elasticsearch"""
        try:
            from elasticsearch import AsyncElasticsearch

            auth = None
            if self.config.credentials:
                auth = (
                    self.config.credentials.get('username'),
                    self.config.credentials.get('password')
                )

            self.client = AsyncElasticsearch(
                [self.config.endpoint],
                basic_auth=auth,
                verify_certs=self.config.filters.get('verify_ssl', True)
            )

            # Test connection
            info = await self.client.info()
            logger.info(f"Connected to Elasticsearch cluster: {info['cluster_name']}")

            return True

        except ImportError:
            raise ImportError(
                "elasticsearch not installed. Install with: pip install elasticsearch"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Elasticsearch"""
        if self.client:
            await self.client.close()
        logger.info("Disconnected from Elasticsearch")

    async def fetch_logs(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[NormalizedSignal]:
        """
        Fetch logs from Elasticsearch.

        Args:
            start_time: Start of time range
            end_time: End of time range
            filters: Additional filters (service, level, etc.)

        Returns:
            List of normalized log signals
        """
        if not self.client:
            raise RuntimeError("Not connected to Elasticsearch")

        # Build Elasticsearch query
        query = {
            "bool": {
                "must": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": start_time.isoformat(),
                                "lte": end_time.isoformat(),
                            }
                        }
                    }
                ],
                "should": [],
                "minimum_should_match": 0
            }
        }

        # Add filters
        if filters:
            for key, value in filters.items():
                if key == "service":
                    query["bool"]["must"].append({"term": {"service.name": value}})
                elif key == "level":
                    query["bool"]["must"].append({"term": {"log.level": value}})
                elif key == "query":
                    query["bool"]["must"].append({"query_string": {"query": value}})

        try:
            # Search logs
            response = await self.client.search(
                index=self.log_index_pattern,
                body={
                    "query": query,
                    "sort": [{"@timestamp": {"order": "desc"}}],
                    "size": 10000  # Max results
                }
            )

            signals = []

            for hit in response['hits']['hits']:
                source = hit['_source']

                # Extract log fields (support multiple formats)
                message = source.get('message', source.get('log', {}).get('message', ''))
                level = source.get('level', source.get('log', {}).get('level', 'info'))
                timestamp_str = source.get('@timestamp', source.get('timestamp'))

                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')) \
                    if timestamp_str else datetime.utcnow()

                # Determine service name
                service = source.get('service', {}).get('name', 'unknown') if isinstance(source.get('service'), dict) \
                    else source.get('service', 'unknown')

                # Map level to severity
                severity_map = {
                    'debug': 'low',
                    'info': 'low',
                    'warn': 'medium',
                    'warning': 'medium',
                    'error': 'high',
                    'fatal': 'critical',
                    'critical': 'critical',
                }
                severity = severity_map.get(level.lower(), 'medium')

                signal = NormalizedSignal(
                    signal_type=SignalType.LOG,
                    title=f"Log: {message[:50]}...",
                    description=message,
                    timestamp=timestamp,
                    source=service,
                    severity=severity,
                    raw_data=source,
                    metadata={
                        'log_level': level,
                        'index': hit['_index'],
                        'id': hit['_id'],
                        'elasticsearch_source': True
                    },
                    tags=source.get('tags', {}) if isinstance(source.get('tags'), dict) else {}
                )

                signals.append(signal)

            logger.info(f"Fetched {len(signals)} log signals from Elasticsearch")
            return signals

        except Exception as e:
            logger.error(f"Failed to fetch logs from Elasticsearch: {e}")
            return []

    async def fetch_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        metric_names: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[NormalizedSignal]:
        """
        Fetch metrics from Elasticsearch.

        Args:
            start_time: Start of time range
            end_time: End of time range
            metric_names: Specific metrics to fetch
            filters: Additional filters

        Returns:
            List of normalized metric signals
        """
        if not self.client:
            raise RuntimeError("Not connected to Elasticsearch")

        # Build aggregation query for metrics
        aggs = {}

        if metric_names:
            for metric_name in metric_names:
                aggs[metric_name] = {
                    "date_histogram": {
                        "field": "@timestamp",
                        "interval": "1m"
                    },
                    "aggs": {
                        "value": {"avg": {"field": metric_name}}
                    }
                }

        query = {
            "bool": {
                "must": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": start_time.isoformat(),
                                "lte": end_time.isoformat(),
                            }
                        }
                    }
                ]
            }
        }

        try:
            response = await self.client.search(
                index=self.metric_index_pattern,
                body={
                    "query": query,
                    "aggs": aggs,
                    "size": 0  # We only want aggregations
                }
            )

            signals = []

            # Parse aggregations
            for metric_name, agg_result in response.get('aggregations', {}).items():
                for bucket in agg_result.get('buckets', []):
                    timestamp = datetime.fromtimestamp(bucket['key'] / 1000)
                    value = bucket.get('value', {}).get('value', 0)

                    if value is not None:
                        signal = NormalizedSignal(
                            signal_type=SignalType.METRIC,
                            title=f"Metric: {metric_name}",
                            description=f"{metric_name} = {value}",
                            timestamp=timestamp,
                            source="elasticsearch",
                            severity="low",
                            metadata={
                                'metric_name': metric_name,
                                'value': value,
                                'datasource': 'elasticsearch'
                            }
                        )
                        signals.append(signal)

            logger.info(f"Fetched {len(signals)} metric signals from Elasticsearch")
            return signals

        except Exception as e:
            logger.error(f"Failed to fetch metrics from Elasticsearch: {e}")
            return []

    async def fetch_config_changes(
        self,
        start_time: datetime,
        end_time: datetime,
        components: Optional[List[str]] = None
    ) -> List[NormalizedSignal]:
        """
        Fetch configuration changes from Elasticsearch.

        Looks for audit logs or config change events.
        """
        if not self.client:
            return []

        query = {
            "bool": {
                "must": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": start_time.isoformat(),
                                "lte": end_time.isoformat(),
                            }
                        }
                    },
                    {
                        "term": {"event.category": "configuration"}
                    }
                ]
            }
        }

        try:
            response = await self.client.search(
                index="audit-*",
                body={"query": query, "size": 1000}
            )

            signals = []

            for hit in response['hits']['hits']:
                source = hit['_source']

                signal = NormalizedSignal(
                    signal_type=SignalType.CONFIG_CHANGE,
                    title=source.get('event', {}).get('action', 'Config change'),
                    description=source.get('message', 'Configuration change detected'),
                    timestamp=datetime.fromisoformat(source['@timestamp'].replace('Z', '+00:00')),
                    source=source.get('user', {}).get('name', 'unknown'),
                    severity='medium',
                    metadata={
                        'component': source.get('resource', {}).get('name'),
                        'change_type': source.get('event', {}).get('action'),
                        'elasticsearch_source': True
                    }
                )
                signals.append(signal)

            return signals

        except Exception as e:
            logger.error(f"Failed to fetch config changes: {e}")
            return []

    async def search_logs(
        self,
        query_string: str,
        start_time: datetime,
        end_time: datetime,
        size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search logs with query string.

        Args:
            query_string: Lucene query string
            start_time: Start time
            end_time: End time
            size: Number of results

        Returns:
            List of log documents
        """
        if not self.client:
            return []

        try:
            response = await self.client.search(
                index=self.log_index_pattern,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"query_string": {"query": query_string}},
                                {
                                    "range": {
                                        "@timestamp": {
                                            "gte": start_time.isoformat(),
                                            "lte": end_time.isoformat()
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    "sort": [{"@timestamp": {"order": "desc"}}],
                    "size": size
                }
            )

            return [hit['_source'] for hit in response['hits']['hits']]

        except Exception as e:
            logger.error(f"Log search failed: {e}")
            return []
