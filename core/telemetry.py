"""
OpenTelemetry Integration

Comprehensive observability with traces, metrics, and logs.
"""

from typing import Optional, Dict, Any
import logging
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# Context variables for tracing
_trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
_span_id_var: ContextVar[Optional[str]] = ContextVar('span_id', default=None)


class OpenTelemetryConfig:
    """Configuration for OpenTelemetry"""
    def __init__(
        self,
        service_name: str = "adapt-rca",
        otlp_endpoint: Optional[str] = None,
        enable_tracing: bool = True,
        enable_metrics: bool = True,
        enable_logging: bool = True,
        sample_rate: float = 1.0
    ):
        self.service_name = service_name
        self.otlp_endpoint = otlp_endpoint or "http://localhost:4317"
        self.enable_tracing = enable_tracing
        self.enable_metrics = enable_metrics
        self.enable_logging = enable_logging
        self.sample_rate = sample_rate


def setup_telemetry(config: Optional[OpenTelemetryConfig] = None):
    """
    Initialize OpenTelemetry instrumentation.

    Args:
        config: Telemetry configuration
    """
    if config is None:
        config = OpenTelemetryConfig()

    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.resources import Resource

        # Create resource
        resource = Resource(attributes={
            "service.name": config.service_name,
            "service.version": "3.0.0",
        })

        # Setup tracing
        if config.enable_tracing:
            tracer_provider = TracerProvider(resource=resource)
            otlp_span_exporter = OTLPSpanExporter(endpoint=config.otlp_endpoint)
            span_processor = BatchSpanProcessor(otlp_span_exporter)
            tracer_provider.add_span_processor(span_processor)
            trace.set_tracer_provider(tracer_provider)

            logger.info(f"OpenTelemetry tracing initialized (endpoint: {config.otlp_endpoint})")

        # Setup metrics
        if config.enable_metrics:
            otlp_metric_exporter = OTLPMetricExporter(endpoint=config.otlp_endpoint)
            metric_reader = PeriodicExportingMetricReader(otlp_metric_exporter)
            meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[metric_reader]
            )
            metrics.set_meter_provider(meter_provider)

            logger.info("OpenTelemetry metrics initialized")

        return True

    except ImportError:
        logger.warning(
            "OpenTelemetry not installed. "
            "Install with: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-exporter-otlp"
        )
        return False
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
        return False


def get_tracer(name: str = "adapt"):
    """Get OpenTelemetry tracer"""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return NoOpTracer()


def get_meter(name: str = "adapt"):
    """Get OpenTelemetry meter"""
    try:
        from opentelemetry import metrics
        return metrics.get_meter(name)
    except ImportError:
        return NoOpMeter()


class InstrumentedOrchestrator:
    """
    RCA Orchestrator with OpenTelemetry instrumentation.
    """

    def __init__(self, base_orchestrator):
        self.base_orchestrator = base_orchestrator
        self.tracer = get_tracer("adapt.orchestrator")
        self.meter = get_meter("adapt.orchestrator")

        # Define metrics
        try:
            self.rca_duration = self.meter.create_histogram(
                "adapt.rca.duration",
                unit="s",
                description="RCA execution duration"
            )
            self.rca_counter = self.meter.create_counter(
                "adapt.rca.total",
                unit="1",
                description="Total RCA executions"
            )
            self.agent_counter = self.meter.create_counter(
                "adapt.agent.executions",
                unit="1",
                description="Agent execution count"
            )
        except AttributeError:
            # Metrics not available
            pass

    async def run_rca(self, incident_id: str, signals, **kwargs):
        """Run RCA with distributed tracing"""
        import time

        with self.tracer.start_as_current_span("rca.execute") as span:
            span.set_attribute("incident.id", incident_id)
            span.set_attribute("signals.count", len(signals))
            span.set_attribute("execution_mode", kwargs.get('execution_mode', 'adaptive'))

            # Set trace context
            trace_id = format(span.get_span_context().trace_id, '032x')
            span_id = format(span.get_span_context().span_id, '016x')

            _trace_id_var.set(trace_id)
            _span_id_var.set(span_id)

            start_time = time.time()

            try:
                context = await self.base_orchestrator.run_rca(
                    incident_id=incident_id,
                    signals=signals,
                    **kwargs
                )

                # Record success metrics
                duration = time.time() - start_time

                try:
                    self.rca_duration.record(
                        duration,
                        {"incident_id": incident_id, "status": "success"}
                    )
                    self.rca_counter.add(1, {"status": "success"})
                except AttributeError:
                    pass

                span.set_attribute("rca.status", "success")
                span.set_attribute("rca.duration", duration)
                span.set_attribute("rca.root_causes", len(context.graph.get_root_causes()))

                return context

            except Exception as e:
                # Record failure metrics
                duration = time.time() - start_time

                try:
                    self.rca_duration.record(
                        duration,
                        {"incident_id": incident_id, "status": "failure"}
                    )
                    self.rca_counter.add(1, {"status": "failure"})
                except AttributeError:
                    pass

                span.set_attribute("rca.status", "error")
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e))
                span.record_exception(e)

                raise


class InstrumentedAgent:
    """
    Agent wrapper with OpenTelemetry instrumentation.
    """

    def __init__(self, base_agent, agent_name: str):
        self.base_agent = base_agent
        self.agent_name = agent_name
        self.tracer = get_tracer(f"adapt.agent.{agent_name}")

    async def execute(self, context):
        """Execute agent with tracing"""
        import time

        with self.tracer.start_as_current_span(f"agent.{self.agent_name}.execute") as span:
            span.set_attribute("agent.name", self.agent_name)
            span.set_attribute("incident.id", context.incident_id)

            start_time = time.time()

            try:
                result = await self.base_agent.execute(context)

                duration = time.time() - start_time

                span.set_attribute("agent.status", "success")
                span.set_attribute("agent.duration", duration)
                span.set_attribute("agent.findings", len(result.findings) if hasattr(result, 'findings') else 0)

                return result

            except Exception as e:
                span.set_attribute("agent.status", "error")
                span.record_exception(e)
                raise


class NoOpTracer:
    """No-op tracer when OpenTelemetry is not available"""

    def start_as_current_span(self, name: str, **kwargs):
        return NoOpSpan()


class NoOpSpan:
    """No-op span"""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def set_attribute(self, key: str, value: Any):
        pass

    def record_exception(self, exception: Exception):
        pass

    def get_span_context(self):
        return NoOpSpanContext()


class NoOpSpanContext:
    """No-op span context"""

    @property
    def trace_id(self):
        return 0

    @property
    def span_id(self):
        return 0


class NoOpMeter:
    """No-op meter"""

    def create_histogram(self, name: str, **kwargs):
        return NoOpInstrument()

    def create_counter(self, name: str, **kwargs):
        return NoOpInstrument()

    def create_gauge(self, name: str, **kwargs):
        return NoOpInstrument()


class NoOpInstrument:
    """No-op instrument"""

    def record(self, value: float, attributes: Optional[Dict] = None):
        pass

    def add(self, value: float, attributes: Optional[Dict] = None):
        pass


def get_current_trace_id() -> Optional[str]:
    """Get current trace ID from context"""
    return _trace_id_var.get()


def get_current_span_id() -> Optional[str]:
    """Get current span ID from context"""
    return _span_id_var.get()
