"""
Predictive Incident Detection

Machine learning-based system to predict potential incidents before they occur.
Analyzes trends, patterns, and anomalies to provide early warnings.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger(__name__)


class PredictionSeverity(str, Enum):
    """Severity of predicted incident"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class IncidentPrediction:
    """Prediction of a potential incident"""
    prediction_id: str
    predicted_type: str
    severity: PredictionSeverity
    confidence: float
    time_to_incident: timedelta  # Estimated time until incident occurs
    affected_services: List[str]
    contributing_factors: List[Dict[str, Any]]
    recommended_actions: List[str]
    metadata: Dict[str, Any]
    created_at: datetime


class PredictiveDetector:
    """
    Predictive incident detection using ML models.

    Features:
    - Time series forecasting for metrics
    - Anomaly trend analysis
    - Pattern recognition from historical incidents
    - Multi-signal correlation for early warning
    """

    def __init__(
        self,
        prediction_window: timedelta = timedelta(hours=1),
        min_confidence: float = 0.6
    ):
        self.prediction_window = prediction_window
        self.min_confidence = min_confidence
        self.models = {}
        self._initialized = False

    async def initialize(self, historical_data: Optional[List[Dict]] = None) -> bool:
        """
        Initialize predictive models.

        Args:
            historical_data: Historical incident data for training

        Returns:
            True if initialization successful
        """
        try:
            from sklearn.ensemble import RandomForestClassifier, IsolationForest
            from sklearn.preprocessing import StandardScaler

            # Initialize models
            self.models['incident_classifier'] = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )

            self.models['anomaly_detector'] = IsolationForest(
                contamination=0.1,
                random_state=42
            )

            self.models['scaler'] = StandardScaler()

            # Train models if historical data provided
            if historical_data:
                await self._train_models(historical_data)

            logger.info("Predictive detector initialized")
            self._initialized = True
            return True

        except ImportError:
            logger.warning(
                "Predictive detection dependencies not installed. "
                "Install with: pip install scikit-learn"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to initialize predictive detector: {e}")
            return False

    async def predict_incidents(
        self,
        current_metrics: List[Dict[str, Any]],
        recent_signals: List[Any],
        service_topology: Optional[Dict] = None
    ) -> List[IncidentPrediction]:
        """
        Predict potential incidents based on current state.

        Args:
            current_metrics: Current metric values
            recent_signals: Recent signals (logs, alerts, etc.)
            service_topology: Service dependency graph

        Returns:
            List of incident predictions
        """
        if not self._initialized:
            logger.warning("Predictive detector not initialized")
            return []

        predictions = []

        try:
            # Extract features from current state
            features = self._extract_features(current_metrics, recent_signals)

            # Detect anomalies
            anomaly_predictions = await self._detect_anomaly_trends(features)
            predictions.extend(anomaly_predictions)

            # Predict incident types
            type_predictions = await self._predict_incident_types(features, recent_signals)
            predictions.extend(type_predictions)

            # Cascade failure prediction
            if service_topology:
                cascade_predictions = await self._predict_cascade_failures(
                    current_metrics,
                    service_topology
                )
                predictions.extend(cascade_predictions)

            # Filter by confidence threshold
            predictions = [
                p for p in predictions
                if p.confidence >= self.min_confidence
            ]

            # Sort by severity and confidence
            predictions.sort(
                key=lambda p: (
                    self._severity_to_int(p.severity),
                    p.confidence
                ),
                reverse=True
            )

            logger.info(f"Generated {len(predictions)} incident predictions")
            return predictions

        except Exception as e:
            logger.error(f"Failed to predict incidents: {e}")
            return []

    async def _detect_anomaly_trends(
        self,
        features: np.ndarray
    ) -> List[IncidentPrediction]:
        """Detect trends that indicate impending incidents"""
        predictions = []

        try:
            # Use isolation forest to detect anomalies
            anomaly_scores = self.models['anomaly_detector'].score_samples(features)

            # Find severe anomalies (low scores indicate anomalies)
            threshold = np.percentile(anomaly_scores, 10)
            anomaly_indices = np.where(anomaly_scores < threshold)[0]

            if len(anomaly_indices) > 0:
                # Calculate severity based on anomaly score
                avg_anomaly_score = np.mean(anomaly_scores[anomaly_indices])
                severity = self._score_to_severity(avg_anomaly_score)

                # Estimate time to incident based on trend
                time_to_incident = self._estimate_time_to_incident(features)

                prediction = IncidentPrediction(
                    prediction_id=f"pred_anomaly_{datetime.utcnow().timestamp()}",
                    predicted_type="anomaly_trend",
                    severity=severity,
                    confidence=min(0.95, abs(avg_anomaly_score) * 2),
                    time_to_incident=time_to_incident,
                    affected_services=["unknown"],  # Would be extracted from features
                    contributing_factors=[
                        {
                            'factor': 'metric_anomaly_trend',
                            'description': f'Detected {len(anomaly_indices)} anomalous patterns',
                            'severity': severity
                        }
                    ],
                    recommended_actions=[
                        "Review recent metric changes",
                        "Check for resource saturation",
                        "Inspect recent deployments"
                    ],
                    metadata={
                        'anomaly_count': len(anomaly_indices),
                        'avg_anomaly_score': float(avg_anomaly_score),
                        'detection_method': 'isolation_forest'
                    },
                    created_at=datetime.utcnow()
                )

                predictions.append(prediction)

        except Exception as e:
            logger.error(f"Anomaly trend detection failed: {e}")

        return predictions

    async def _predict_incident_types(
        self,
        features: np.ndarray,
        recent_signals: List[Any]
    ) -> List[IncidentPrediction]:
        """Predict specific incident types based on patterns"""
        predictions = []

        try:
            # Analyze signal patterns
            error_rate = self._calculate_error_rate(recent_signals)
            metric_degradation = self._calculate_metric_degradation(features)

            # Predict application errors
            if error_rate > 0.05:  # More than 5% error rate
                confidence = min(0.9, error_rate * 10)
                severity = PredictionSeverity.HIGH if error_rate > 0.2 else PredictionSeverity.MEDIUM

                predictions.append(IncidentPrediction(
                    prediction_id=f"pred_app_error_{datetime.utcnow().timestamp()}",
                    predicted_type="application_error",
                    severity=severity,
                    confidence=confidence,
                    time_to_incident=timedelta(minutes=15),
                    affected_services=self._extract_affected_services(recent_signals),
                    contributing_factors=[
                        {
                            'factor': 'increasing_error_rate',
                            'description': f'Error rate at {error_rate*100:.1f}%',
                            'severity': severity
                        }
                    ],
                    recommended_actions=[
                        "Review application logs for error patterns",
                        "Check recent code deployments",
                        "Verify external service dependencies"
                    ],
                    metadata={
                        'error_rate': error_rate,
                        'signal_count': len(recent_signals)
                    },
                    created_at=datetime.utcnow()
                ))

            # Predict performance degradation
            if metric_degradation > 0.3:  # 30% degradation
                confidence = min(0.85, metric_degradation)
                severity = PredictionSeverity.HIGH if metric_degradation > 0.5 else PredictionSeverity.MEDIUM

                predictions.append(IncidentPrediction(
                    prediction_id=f"pred_perf_deg_{datetime.utcnow().timestamp()}",
                    predicted_type="performance_degradation",
                    severity=severity,
                    confidence=confidence,
                    time_to_incident=timedelta(minutes=30),
                    affected_services=["unknown"],
                    contributing_factors=[
                        {
                            'factor': 'metric_degradation',
                            'description': f'{metric_degradation*100:.1f}% performance degradation detected',
                            'severity': severity
                        }
                    ],
                    recommended_actions=[
                        "Scale up resources proactively",
                        "Review resource utilization trends",
                        "Check for memory leaks or CPU spikes"
                    ],
                    metadata={
                        'degradation_level': metric_degradation
                    },
                    created_at=datetime.utcnow()
                ))

        except Exception as e:
            logger.error(f"Incident type prediction failed: {e}")

        return predictions

    async def _predict_cascade_failures(
        self,
        current_metrics: List[Dict[str, Any]],
        service_topology: Dict
    ) -> List[IncidentPrediction]:
        """Predict potential cascade failures in service dependencies"""
        predictions = []

        try:
            # Identify degraded services
            degraded_services = []
            for metric in current_metrics:
                service = metric.get('service', 'unknown')
                if self._is_service_degraded(metric):
                    degraded_services.append(service)

            # Find dependent services
            at_risk_services = set()
            for degraded in degraded_services:
                dependents = self._find_dependent_services(degraded, service_topology)
                at_risk_services.update(dependents)

            if at_risk_services:
                severity = PredictionSeverity.CRITICAL if len(at_risk_services) > 5 else PredictionSeverity.HIGH

                predictions.append(IncidentPrediction(
                    prediction_id=f"pred_cascade_{datetime.utcnow().timestamp()}",
                    predicted_type="cascade_failure",
                    severity=severity,
                    confidence=0.75,
                    time_to_incident=timedelta(minutes=10),
                    affected_services=list(at_risk_services),
                    contributing_factors=[
                        {
                            'factor': 'service_degradation',
                            'description': f'{len(degraded_services)} services degraded, {len(at_risk_services)} at risk',
                            'severity': severity
                        }
                    ],
                    recommended_actions=[
                        f"Investigate degraded services: {', '.join(degraded_services)}",
                        "Enable circuit breakers for dependent services",
                        "Consider scaling at-risk services preemptively",
                        "Review service dependency graph for single points of failure"
                    ],
                    metadata={
                        'degraded_services': degraded_services,
                        'at_risk_count': len(at_risk_services)
                    },
                    created_at=datetime.utcnow()
                ))

        except Exception as e:
            logger.error(f"Cascade failure prediction failed: {e}")

        return predictions

    def _extract_features(
        self,
        current_metrics: List[Dict[str, Any]],
        recent_signals: List[Any]
    ) -> np.ndarray:
        """Extract feature vector from current state"""
        features = []

        # Metric-based features
        if current_metrics:
            # Calculate statistical features
            values = [m.get('value', 0) for m in current_metrics if 'value' in m]
            if values:
                features.extend([
                    np.mean(values),
                    np.std(values),
                    np.max(values),
                    np.min(values),
                    len(values)
                ])
            else:
                features.extend([0, 0, 0, 0, 0])
        else:
            features.extend([0, 0, 0, 0, 0])

        # Signal-based features
        error_count = len([s for s in recent_signals if hasattr(s, 'severity') and s.severity in ['high', 'critical']])
        features.append(error_count)

        # Convert to numpy array
        return np.array(features).reshape(1, -1)

    def _calculate_error_rate(self, recent_signals: List[Any]) -> float:
        """Calculate error rate from recent signals"""
        if not recent_signals:
            return 0.0

        error_count = len([
            s for s in recent_signals
            if hasattr(s, 'severity') and s.severity in ['high', 'critical']
        ])

        return error_count / len(recent_signals)

    def _calculate_metric_degradation(self, features: np.ndarray) -> float:
        """Calculate metric degradation level"""
        # Simple heuristic: compare current vs expected
        # In production, would compare against baseline
        if features.shape[1] >= 3:
            mean_val = features[0, 0]
            max_val = features[0, 2]
            if max_val > 0:
                return min(1.0, mean_val / max_val)
        return 0.0

    def _extract_affected_services(self, recent_signals: List[Any]) -> List[str]:
        """Extract affected services from signals"""
        services = set()
        for signal in recent_signals:
            if hasattr(signal, 'source'):
                services.add(signal.source)
        return list(services) if services else ["unknown"]

    def _is_service_degraded(self, metric: Dict[str, Any]) -> bool:
        """Check if service is degraded based on metrics"""
        # Simple heuristic - would be more sophisticated in production
        metric_name = metric.get('metric_name', '').lower()
        value = metric.get('value', 0)

        if 'error' in metric_name and value > 0.1:
            return True
        if 'latency' in metric_name and value > 1000:  # > 1 second
            return True
        if 'cpu' in metric_name and value > 80:  # > 80% CPU
            return True
        if 'memory' in metric_name and value > 90:  # > 90% memory
            return True

        return False

    def _find_dependent_services(
        self,
        service: str,
        topology: Dict
    ) -> List[str]:
        """Find services that depend on the given service"""
        dependents = []

        # Simple dependency lookup
        for svc, deps in topology.items():
            if isinstance(deps, list) and service in deps:
                dependents.append(svc)

        return dependents

    def _estimate_time_to_incident(self, features: np.ndarray) -> timedelta:
        """Estimate time until incident occurs based on trends"""
        # Simple heuristic - would use time series analysis in production
        # Return random time within prediction window
        return timedelta(minutes=30)

    def _severity_to_int(self, severity: PredictionSeverity) -> int:
        """Convert severity to int for sorting"""
        severity_map = {
            PredictionSeverity.LOW: 1,
            PredictionSeverity.MEDIUM: 2,
            PredictionSeverity.HIGH: 3,
            PredictionSeverity.CRITICAL: 4
        }
        return severity_map.get(severity, 0)

    def _score_to_severity(self, score: float) -> PredictionSeverity:
        """Convert anomaly score to severity"""
        abs_score = abs(score)
        if abs_score > 0.8:
            return PredictionSeverity.CRITICAL
        elif abs_score > 0.6:
            return PredictionSeverity.HIGH
        elif abs_score > 0.4:
            return PredictionSeverity.MEDIUM
        else:
            return PredictionSeverity.LOW

    async def _train_models(self, historical_data: List[Dict]) -> None:
        """Train predictive models on historical data"""
        try:
            # Extract training features
            X = []
            y = []

            for incident in historical_data:
                features = incident.get('features', [])
                incident_type = incident.get('type', 'unknown')

                if features:
                    X.append(features)
                    y.append(incident_type)

            if X and y:
                X = np.array(X)
                X_scaled = self.models['scaler'].fit_transform(X)

                # Train classifier
                self.models['incident_classifier'].fit(X_scaled, y)

                # Train anomaly detector
                self.models['anomaly_detector'].fit(X_scaled)

                logger.info(f"Trained models on {len(X)} historical incidents")

        except Exception as e:
            logger.error(f"Model training failed: {e}")


class PredictiveMonitor:
    """
    Continuous monitoring system that generates predictions.
    """

    def __init__(
        self,
        detector: PredictiveDetector,
        check_interval: timedelta = timedelta(minutes=5)
    ):
        self.detector = detector
        self.check_interval = check_interval
        self.active_predictions: Dict[str, IncidentPrediction] = {}

    async def monitor(
        self,
        metric_fetcher,
        signal_fetcher,
        topology_provider=None,
        callback=None
    ) -> None:
        """
        Continuously monitor and generate predictions.

        Args:
            metric_fetcher: Function to fetch current metrics
            signal_fetcher: Function to fetch recent signals
            topology_provider: Function to get service topology
            callback: Function to call with new predictions
        """
        import asyncio

        logger.info("Starting predictive monitoring")

        while True:
            try:
                # Fetch current state
                current_metrics = await metric_fetcher()
                recent_signals = await signal_fetcher()
                topology = await topology_provider() if topology_provider else None

                # Generate predictions
                predictions = await self.detector.predict_incidents(
                    current_metrics=current_metrics,
                    recent_signals=recent_signals,
                    service_topology=topology
                )

                # Process new predictions
                for prediction in predictions:
                    if prediction.prediction_id not in self.active_predictions:
                        self.active_predictions[prediction.prediction_id] = prediction

                        logger.warning(
                            f"New incident prediction: {prediction.predicted_type} "
                            f"(severity={prediction.severity}, confidence={prediction.confidence:.2f})"
                        )

                        # Call callback if provided
                        if callback:
                            await callback(prediction)

                # Clean up old predictions
                cutoff = datetime.utcnow() - timedelta(hours=1)
                self.active_predictions = {
                    k: v for k, v in self.active_predictions.items()
                    if v.created_at > cutoff
                }

                # Wait for next check
                await asyncio.sleep(self.check_interval.total_seconds())

            except Exception as e:
                logger.error(f"Predictive monitoring error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
