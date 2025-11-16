"""
Observability infrastructure for ADAPT framework.

Provides structured logging, distributed tracing, and performance monitoring.
"""

import logging
import json
from contextvars import ContextVar
from typing import Any, Dict, Optional
import time
import uuid
from datetime import datetime

# Context variables for distributed tracing
trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')
span_id_var: ContextVar[str] = ContextVar('span_id', default='')


class StructuredLogger:
    """
    Structured JSON logging for better observability.

    Logs are emitted in JSON format with consistent fields for easier
    parsing and analysis in log aggregation systems.
    """

    def __init__(self, name: str):
        """
        Initialize structured logger.

        Args:
            name: Logger name (usually module name)
        """
        self.logger = logging.getLogger(name)
        self.name = name

    def _log(self, level: str, message: str, **kwargs):
        """
        Internal method to log structured JSON.

        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            message: Log message
            **kwargs: Additional fields to include in log
        """
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level,
            'logger': self.name,
            'message': message,
            'trace_id': trace_id_var.get() or '',
            'span_id': span_id_var.get() or '',
            **kwargs
        }

        log_method = getattr(self.logger, level.lower())
        log_method(json.dumps(log_data))

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log('DEBUG', message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log('INFO', message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log('WARNING', message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log('ERROR', message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log('CRITICAL', message, **kwargs)


class TracingContext:
    """
    Context manager for distributed tracing.

    Creates a trace span and sets context variables that will be
    included in all logs within the span.
    """

    def __init__(self, operation_name: str, parent_span_id: Optional[str] = None):
        """
        Initialize tracing context.

        Args:
            operation_name: Name of the operation being traced
            parent_span_id: Optional parent span ID for nested spans
        """
        self.operation_name = operation_name
        self.parent_span_id = parent_span_id
        self.span_id = str(uuid.uuid4())
        self.start_time = None
        self.trace_id_token = None
        self.span_id_token = None

    def __enter__(self):
        """Enter tracing context"""
        self.start_time = time.time()

        # Set or inherit trace ID
        current_trace = trace_id_var.get()
        if not current_trace:
            current_trace = str(uuid.uuid4())

        self.trace_id_token = trace_id_var.set(current_trace)
        self.span_id_token = span_id_var.set(self.span_id)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit tracing context"""
        duration = time.time() - self.start_time

        # Log span completion
        logger = StructuredLogger('tracing')
        logger.info(
            f"Span completed: {self.operation_name}",
            operation=self.operation_name,
            duration_seconds=duration,
            success=exc_type is None,
            error_type=exc_type.__name__ if exc_type else None,
            parent_span_id=self.parent_span_id
        )

        # Reset context
        if self.trace_id_token:
            trace_id_var.reset(self.trace_id_token)
        if self.span_id_token:
            span_id_var.reset(self.span_id_token)

        return False  # Don't suppress exceptions


def get_current_trace_id() -> str:
    """Get current trace ID from context"""
    return trace_id_var.get()


def get_current_span_id() -> str:
    """Get current span ID from context"""
    return span_id_var.get()


def set_trace_id(trace_id: str):
    """Set trace ID in context"""
    return trace_id_var.set(trace_id)


# Configure JSON logging format
class JsonFormatter(logging.Formatter):
    """Formatter that outputs JSON logs"""

    def format(self, record):
        """Format log record as JSON"""
        # If message is already JSON, return as-is
        try:
            json.loads(record.getMessage())
            return record.getMessage()
        except (json.JSONDecodeError, ValueError):
            # Not JSON, wrap in JSON structure
            log_data = {
                'timestamp': datetime.utcfromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
            }

            if record.exc_info:
                log_data['exception'] = self.formatException(record.exc_info)

            return json.dumps(log_data)


def configure_logging(level: str = 'INFO', json_format: bool = True):
    """
    Configure logging for ADAPT framework.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Whether to use JSON formatting
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler()

    if json_format:
        console_handler.setFormatter(JsonFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )

    root_logger.addHandler(console_handler)
