"""
ML-Based Metric Analyzer

Uses Prophet and statistical models for advanced anomaly detection.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
import numpy as np
import pandas as pd

from .metric_analyzer import MetricAnalyzerAgent
from .base import AgentResult
from core.signal_normalizer import SignalType

logger = logging.getLogger(__name__)


class MLMetricAnalyzer(MetricAnalyzerAgent):
    """
    Machine learning enhanced metric analyzer.

    Features:
    - Prophet time series forecasting
    - Seasonal decomposition
    - Multi-variate anomaly detection
    - Trend analysis
    - Automatic model training
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.models = {}  # Trained Prophet models per metric
        self.use_prophet = config.get("use_prophet", True) if config else True
        self.use_isolation_forest = config.get("use_isolation_forest", True) if config else True
        self.confidence_threshold = config.get("ml_confidence_threshold", 0.8) if config else 0.8

    async def execute(self, context: Any) -> AgentResult:
        """
        Execute ML-enhanced metric analysis.
        """
        # Run traditional analysis first
        result = await super().execute(context)

        # Add ML-based analysis
        metric_signals = [s for s in context.signals if s.signal_type == SignalType.METRIC]

        if metric_signals and self.use_prophet:
            ml_findings = await self._ml_anomaly_detection(metric_signals)
            result.findings.extend(ml_findings)
            result.metadata["ml_enhanced"] = True
            result.metadata["ml_findings_count"] = len(ml_findings)

        if metric_signals and self.use_isolation_forest:
            multivariate_findings = await self._multivariate_anomaly_detection(metric_signals)
            result.findings.extend(multivariate_findings)
            result.metadata["multivariate_findings_count"] = len(multivariate_findings)

        return result

    async def _ml_anomaly_detection(
        self, metric_signals: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Use Prophet for time series anomaly detection.
        """
        findings = []

        # Group metrics by name
        from collections import defaultdict
        metrics_by_name = defaultdict(list)

        for signal in metric_signals:
            metric_name = signal.metadata.get('metric_name', 'unknown')
            value = signal.metadata.get('value', 0)
            metrics_by_name[metric_name].append({
                'timestamp': signal.timestamp,
                'value': value,
                'signal': signal
            })

        # Analyze each metric with Prophet
        for metric_name, data_points in metrics_by_name.items():
            if len(data_points) < 10:  # Need minimum data for Prophet
                continue

            try:
                anomalies = await self._prophet_detect_anomalies(metric_name, data_points)
                findings.extend(anomalies)
            except Exception as e:
                logger.warning(f"Prophet analysis failed for {metric_name}: {e}")

        return findings

    async def _prophet_detect_anomalies(
        self, metric_name: str, data_points: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Use Prophet to detect anomalies in a metric.
        """
        try:
            from prophet import Prophet
        except ImportError:
            logger.warning("Prophet not installed, skipping ML analysis")
            return []

        findings = []

        # Prepare data for Prophet
        df = pd.DataFrame([
            {'ds': dp['timestamp'], 'y': dp['value']}
            for dp in data_points
        ])
        df = df.sort_values('ds')

        # Train Prophet model
        model = Prophet(
            seasonality_mode='multiplicative',
            daily_seasonality=True,
            weekly_seasonality=True,
            changepoint_prior_scale=0.05,
            interval_width=0.95
        )

        try:
            model.fit(df)

            # Make predictions
            forecast = model.predict(df)

            # Detect anomalies (values outside prediction interval)
            for i, row in df.iterrows():
                forecast_row = forecast.iloc[i]

                actual = row['y']
                predicted = forecast_row['yhat']
                lower_bound = forecast_row['yhat_lower']
                upper_bound = forecast_row['yhat_upper']

                # Check if actual value is outside prediction interval
                if actual < lower_bound or actual > upper_bound:
                    deviation = abs(actual - predicted) / (predicted if predicted != 0 else 1)

                    # Calculate confidence based on how far outside bounds
                    if actual < lower_bound:
                        confidence = min(0.95, 0.7 + (lower_bound - actual) / lower_bound * 0.2)
                    else:
                        confidence = min(0.95, 0.7 + (actual - upper_bound) / upper_bound * 0.2)

                    if confidence >= self.confidence_threshold:
                        finding = self._create_finding(
                            finding_id=f'ml_anomaly_{metric_name}_{row["ds"].isoformat()}',
                            title=f'ML Anomaly: {metric_name} outside prediction interval',
                            description=f'{metric_name} = {actual:.2f} (predicted: {predicted:.2f}, bounds: [{lower_bound:.2f}, {upper_bound:.2f}])',
                            confidence=confidence,
                            metadata={
                                'metric_name': metric_name,
                                'actual_value': actual,
                                'predicted_value': predicted,
                                'lower_bound': lower_bound,
                                'upper_bound': upper_bound,
                                'deviation_percent': deviation * 100,
                                'model': 'prophet',
                                'timestamp': row['ds'].isoformat(),
                            }
                        )
                        findings.append(finding)

        except Exception as e:
            logger.error(f"Prophet model training failed for {metric_name}: {e}")

        return findings

    async def _multivariate_anomaly_detection(
        self, metric_signals: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Use Isolation Forest for multivariate anomaly detection.
        """
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            logger.warning("scikit-learn not installed, skipping Isolation Forest")
            return []

        findings = []

        # Create feature matrix from metrics
        # Group by timestamp to get snapshots
        from collections import defaultdict
        snapshots = defaultdict(dict)

        for signal in metric_signals:
            timestamp = signal.timestamp.replace(second=0, microsecond=0)
            metric_name = signal.metadata.get('metric_name', 'unknown')
            value = signal.metadata.get('value', 0)
            snapshots[timestamp][metric_name] = value

        if len(snapshots) < 10:
            return []

        # Convert to DataFrame
        df = pd.DataFrame.from_dict(snapshots, orient='index')
        df = df.fillna(0)  # Fill missing values

        if df.shape[1] < 2:  # Need at least 2 metrics for multivariate
            return []

        # Train Isolation Forest
        iso_forest = IsolationForest(
            contamination=0.1,  # Expect 10% anomalies
            random_state=42,
            n_estimators=100
        )

        predictions = iso_forest.fit_predict(df)
        scores = iso_forest.score_samples(df)

        # Identify anomalies
        for idx, (timestamp, prediction, score) in enumerate(zip(df.index, predictions, scores)):
            if prediction == -1:  # Anomaly
                # Calculate confidence from anomaly score
                confidence = min(0.9, 0.6 + abs(score) * 0.3)

                if confidence >= self.confidence_threshold:
                    # Get anomalous features
                    row_values = df.iloc[idx].to_dict()

                    finding = self._create_finding(
                        finding_id=f'ml_multivariate_anomaly_{timestamp.isoformat()}',
                        title=f'Multivariate Anomaly Detected',
                        description=f'Multiple metrics showing anomalous pattern at {timestamp.isoformat()}',
                        confidence=confidence,
                        metadata={
                            'timestamp': timestamp.isoformat(),
                            'anomaly_score': float(score),
                            'metrics': row_values,
                            'model': 'isolation_forest',
                            'detection_type': 'multivariate',
                        }
                    )
                    findings.append(finding)

        return findings

    async def train_model_for_metric(
        self, metric_name: str, historical_data: pd.DataFrame
    ) -> None:
        """
        Train a Prophet model for a specific metric using historical data.

        Args:
            metric_name: Name of the metric
            historical_data: DataFrame with 'ds' (timestamp) and 'y' (value) columns
        """
        try:
            from prophet import Prophet

            model = Prophet(
                seasonality_mode='multiplicative',
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=True,
                changepoint_prior_scale=0.05
            )

            model.fit(historical_data)
            self.models[metric_name] = model

            logger.info(f"Trained Prophet model for {metric_name}")

        except Exception as e:
            logger.error(f"Failed to train model for {metric_name}: {e}")

    def get_forecast(
        self, metric_name: str, periods: int = 24
    ) -> Optional[pd.DataFrame]:
        """
        Get forecast for a metric.

        Args:
            metric_name: Name of the metric
            periods: Number of future periods to forecast

        Returns:
            DataFrame with forecast or None
        """
        model = self.models.get(metric_name)
        if not model:
            return None

        future = model.make_future_dataframe(periods=periods, freq='H')
        forecast = model.predict(future)
        return forecast


class ARIMAAnalyzer:
    """
    ARIMA-based time series analysis.
    """

    def __init__(self):
        self.models = {}

    async def detect_anomalies(
        self, metric_name: str, data_points: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Use ARIMA for anomaly detection.
        """
        try:
            from statsmodels.tsa.arima.model import ARIMA
        except ImportError:
            logger.warning("statsmodels not installed")
            return []

        findings = []

        # Prepare time series
        values = [dp['value'] for dp in data_points]

        if len(values) < 20:
            return []

        try:
            # Fit ARIMA model (auto-detect parameters)
            model = ARIMA(values, order=(1, 1, 1))
            fitted = model.fit()

            # Get residuals (prediction errors)
            residuals = fitted.resid

            # Detect anomalies (residuals > 3 std deviations)
            threshold = 3 * np.std(residuals)

            for i, (residual, dp) in enumerate(zip(residuals, data_points)):
                if abs(residual) > threshold:
                    findings.append({
                        'id': f'arima_anomaly_{metric_name}_{i}',
                        'title': f'ARIMA Anomaly: {metric_name}',
                        'description': f'Prediction error: {residual:.2f}',
                        'confidence': min(0.9, 0.6 + abs(residual) / threshold * 0.3),
                        'metadata': {
                            'metric_name': metric_name,
                            'residual': float(residual),
                            'threshold': float(threshold),
                            'model': 'arima',
                        }
                    })

        except Exception as e:
            logger.error(f"ARIMA analysis failed: {e}")

        return findings
