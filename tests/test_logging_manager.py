"""
Tests for Enhanced Logging Manager
"""

import pytest
import logging
import os
from pathlib import Path
import tempfile
from datetime import datetime

from core.logging_manager import (
    LoggingManager,
    ProgressTracker,
    get_logging_manager,
    get_logger,
    LogLevel
)


class TestLoggingManager:
    """Tests for LoggingManager class"""

    def setup_method(self):
        """Reset logging manager for each test"""
        # Force reinitialization by resetting singleton
        LoggingManager._instance = None
        LoggingManager._initialized = False
        # Clear environment variables
        os.environ.pop('ADAPT_LOG_LEVEL', None)
        os.environ.pop('ADAPT_LOG_FORMAT', None)

    def test_singleton_pattern(self):
        """Test that LoggingManager is a singleton"""
        manager1 = LoggingManager()
        manager2 = LoggingManager()
        assert manager1 is manager2

    def test_default_log_level(self):
        """Test default log level is INFO"""
        manager = LoggingManager()
        assert manager.log_level == 'INFO'

    def test_env_log_level(self):
        """Test log level from environment variable"""
        os.environ['ADAPT_LOG_LEVEL'] = 'DEBUG'
        LoggingManager._instance = None
        LoggingManager._initialized = False

        manager = LoggingManager()
        assert manager.log_level == 'DEBUG'

    def test_invalid_env_log_level(self):
        """Test invalid log level falls back to INFO"""
        os.environ['ADAPT_LOG_LEVEL'] = 'INVALID'
        LoggingManager._instance = None
        LoggingManager._initialized = False

        manager = LoggingManager()
        assert manager.log_level == 'INFO'

    def test_configure_log_level(self):
        """Test configuring log level"""
        manager = LoggingManager()
        manager.configure(level='DEBUG')
        assert manager.log_level == 'DEBUG'

    def test_configure_invalid_log_level(self):
        """Test configuring with invalid log level raises error"""
        manager = LoggingManager()
        with pytest.raises(ValueError, match="Invalid log level"):
            manager.configure(level='INVALID')

    def test_configure_log_file(self):
        """Test configuring log file"""
        manager = LoggingManager()

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / 'test.log'
            manager.configure(log_file=str(log_file))

            assert manager.log_file == log_file
            # Log file directory should be created
            assert log_file.parent.exists()

    def test_get_logger_structured(self):
        """Test getting structured logger"""
        manager = LoggingManager()
        logger = manager.get_logger('test_module', structured=True)

        from core.observability import StructuredLogger
        assert isinstance(logger, StructuredLogger)

    def test_get_logger_standard(self):
        """Test getting standard logger"""
        manager = LoggingManager()
        logger = manager.get_logger('test_module', structured=False)

        assert isinstance(logger, logging.Logger)

    def test_set_module_log_level(self):
        """Test setting log level for specific module"""
        manager = LoggingManager()
        manager.set_module_log_level('test_module', 'DEBUG')

        logger = logging.getLogger('test_module')
        assert logger.level == logging.DEBUG

    def test_global_get_logger(self):
        """Test global get_logger function"""
        logger = get_logger('test_module')
        from core.observability import StructuredLogger
        assert isinstance(logger, StructuredLogger)

    def test_json_format_from_env(self):
        """Test JSON format configuration from environment"""
        os.environ['ADAPT_LOG_FORMAT'] = 'text'
        LoggingManager._instance = None
        LoggingManager._initialized = False

        manager = LoggingManager()
        assert manager.json_format is False


class TestProgressTracker:
    """Tests for ProgressTracker class"""

    def test_progress_tracking_success(self):
        """Test successful progress tracking"""
        with ProgressTracker("Test operation", total=100) as tracker:
            for i in range(100):
                tracker.update(i + 1)

        assert tracker.current == 100

    def test_progress_tracking_with_error(self):
        """Test progress tracking with error"""
        try:
            with ProgressTracker("Test operation", total=100) as tracker:
                for i in range(50):
                    tracker.update(i + 1)
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should have logged error
        assert tracker.current == 50

    def test_progress_percentage_calculation(self):
        """Test progress percentage calculation"""
        with ProgressTracker("Test operation", total=100) as tracker:
            tracker.update(25)
            # Should have logged 25%

            tracker.update(50)
            # Should have logged 50%

            tracker.update(75)
            # Should have logged 75%

            tracker.update(100)
            # Should have logged 100%

        assert tracker.current == 100

    def test_progress_zero_total(self):
        """Test progress with zero total (edge case)"""
        with ProgressTracker("Test operation", total=0) as tracker:
            tracker.update(0)

        assert tracker.current == 0

    def test_progress_custom_interval(self):
        """Test progress with custom logging interval"""
        with ProgressTracker(
            "Test operation",
            total=100,
            log_interval=25  # Log every 25%
        ) as tracker:
            for i in range(100):
                tracker.update(i + 1)

        assert tracker.current == 100


class TestLogLevel:
    """Tests for LogLevel enum"""

    def test_log_level_values(self):
        """Test LogLevel enum values"""
        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.ERROR == "ERROR"
        assert LogLevel.CRITICAL == "CRITICAL"

    def test_log_level_iteration(self):
        """Test iterating over log levels"""
        levels = [level.value for level in LogLevel]
        assert 'DEBUG' in levels
        assert 'INFO' in levels
        assert 'WARNING' in levels
        assert 'ERROR' in levels
        assert 'CRITICAL' in levels


class TestIntegration:
    """Integration tests for logging manager"""

    def test_file_logging_integration(self):
        """Test complete file logging integration"""
        LoggingManager._instance = None
        LoggingManager._initialized = False

        manager = LoggingManager()

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / 'adapt.log'
            manager.configure(
                level='DEBUG',
                log_file=str(log_file),
                json_format=False
            )

            # Get logger and log messages
            logger = manager.get_logger('test', structured=False)
            logger.info("Test message")

            # Check log file was created and contains message
            assert log_file.exists()
            content = log_file.read_text()
            assert 'Test message' in content

    def test_structured_logging_integration(self):
        """Test structured JSON logging integration"""
        LoggingManager._instance = None
        LoggingManager._initialized = False

        manager = LoggingManager()
        manager.configure(level='INFO', json_format=True)

        logger = manager.get_logger('test', structured=True)
        # Should not raise error
        logger.info("Test message", key="value")

