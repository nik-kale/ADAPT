"""
Enhanced Logging Manager for ADAPT Framework

Provides centralized logging configuration, log level management,
and progress tracking for long-running operations.
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import os
from enum import Enum

from core.observability import StructuredLogger, configure_logging


class LogLevel(str, Enum):
    """Supported log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LoggingManager:
    """
    Centralized logging management for ADAPT framework.
    
    Features:
    - Environment-based log level configuration
    - File and console logging
    - Progress tracking for batch operations
    - Structured JSON logging support
    - Per-module log level overrides
    """
    
    _instance: Optional['LoggingManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        """Singleton pattern to ensure one logging manager"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize logging manager (only once)"""
        if not LoggingManager._initialized:
            self.loggers: Dict[str, logging.Logger] = {}
            self.log_level = self._get_log_level_from_env()
            self.log_file: Optional[Path] = None
            self.json_format = self._get_json_format_from_env()
            LoggingManager._initialized = True
    
    @staticmethod
    def _get_log_level_from_env() -> str:
        """
        Get log level from environment variable.
        
        Returns:
            Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        env_level = os.getenv('ADAPT_LOG_LEVEL', 'INFO').upper()
        
        # Validate log level
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if env_level not in valid_levels:
            print(
                f"WARNING: Invalid log level '{env_level}' in ADAPT_LOG_LEVEL. "
                f"Using INFO. Valid levels: {', '.join(valid_levels)}",
                file=sys.stderr
            )
            return 'INFO'
        
        return env_level
    
    @staticmethod
    def _get_json_format_from_env() -> bool:
        """
        Check if JSON formatting should be used.
        
        Returns:
            True if JSON format enabled, False otherwise
        """
        return os.getenv('ADAPT_LOG_FORMAT', 'json').lower() == 'json'
    
    def configure(
        self,
        level: Optional[str] = None,
        log_file: Optional[str] = None,
        json_format: Optional[bool] = None
    ) -> None:
        """
        Configure global logging settings.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Optional path to log file
            json_format: Whether to use JSON formatting
        """
        if level:
            if level.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                raise ValueError(
                    f"Invalid log level: {level}. "
                    "Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL"
                )
            self.log_level = level.upper()
        
        if log_file:
            self.log_file = Path(log_file)
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        if json_format is not None:
            self.json_format = json_format
        
        # Apply configuration
        configure_logging(level=self.log_level, json_format=self.json_format)
        
        # Add file handler if specified
        if self.log_file:
            self._add_file_handler()
    
    def _add_file_handler(self) -> None:
        """Add file handler to root logger"""
        root_logger = logging.getLogger()
        
        # Check if file handler already exists
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                if handler.baseFilename == str(self.log_file.absolute()):
                    return  # Already configured
        
        # Add new file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(getattr(logging, self.log_level))
        
        if self.json_format:
            from core.observability import JsonFormatter
            file_handler.setFormatter(JsonFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
        
        root_logger.addHandler(file_handler)
    
    def get_logger(self, name: str, structured: bool = True) -> Any:
        """
        Get or create a logger for a module.
        
        Args:
            name: Logger name (usually __name__)
            structured: Whether to return structured logger
            
        Returns:
            StructuredLogger if structured=True, else standard logger
        """
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)
        
        if structured:
            return StructuredLogger(name)
        else:
            return self.loggers[name]
    
    def set_module_log_level(self, module_name: str, level: str) -> None:
        """
        Set log level for a specific module.
        
        Args:
            module_name: Module name (e.g., 'agents.log_analyzer')
            level: Log level for this module
        """
        logger = logging.getLogger(module_name)
        logger.setLevel(getattr(logging, level.upper()))
    
    def log_progress(
        self,
        current: int,
        total: int,
        operation: str,
        logger: Optional[StructuredLogger] = None
    ) -> None:
        """
        Log progress for long-running operations.
        
        Args:
            current: Current progress count
            total: Total count
            operation: Description of operation
            logger: Optional specific logger to use
        """
        if logger is None:
            logger = self.get_logger('progress')
        
        percentage = (current / total * 100) if total > 0 else 0
        
        # Log at intervals: 10%, 25%, 50%, 75%, 100%
        if current == total or current % max(1, total // 10) == 0:
            logger.info(
                f"Progress: {operation}",
                current=current,
                total=total,
                percentage=round(percentage, 2),
                operation=operation
            )


class ProgressTracker:
    """
    Context manager for tracking progress of batch operations.
    
    Example:
        with ProgressTracker("Processing events", total=1000) as tracker:
            for i, event in enumerate(events):
                process(event)
                tracker.update(i + 1)
    """
    
    def __init__(
        self,
        operation: str,
        total: int,
        logger_name: str = 'progress',
        log_interval: int = 10
    ):
        """
        Initialize progress tracker.
        
        Args:
            operation: Description of operation
            total: Total number of items to process
            logger_name: Name for logger
            log_interval: Percentage interval for logging (default: 10%)
        """
        self.operation = operation
        self.total = total
        self.current = 0
        self.logger = LoggingManager().get_logger(logger_name)
        self.log_interval = log_interval
        self.start_time = None
        self.last_logged_percentage = 0
    
    def __enter__(self):
        """Start progress tracking"""
        self.start_time = datetime.utcnow()
        self.logger.info(
            f"Started: {self.operation}",
            total=self.total,
            operation=self.operation
        )
        return self
    
    def update(self, current: int) -> None:
        """
        Update progress.
        
        Args:
            current: Current progress count
        """
        self.current = current
        percentage = (current / self.total * 100) if self.total > 0 else 0
        
        # Log at specified intervals
        if percentage - self.last_logged_percentage >= self.log_interval:
            elapsed = (datetime.utcnow() - self.start_time).total_seconds()
            rate = current / elapsed if elapsed > 0 else 0
            
            self.logger.info(
                f"Progress: {self.operation}",
                current=current,
                total=self.total,
                percentage=round(percentage, 2),
                elapsed_seconds=round(elapsed, 2),
                rate_per_second=round(rate, 2)
            )
            self.last_logged_percentage = int(percentage / self.log_interval) * self.log_interval
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Complete progress tracking"""
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        
        if exc_type is None:
            self.logger.info(
                f"Completed: {self.operation}",
                total=self.total,
                elapsed_seconds=round(elapsed, 2),
                success=True
            )
        else:
            self.logger.error(
                f"Failed: {self.operation}",
                total=self.total,
                current=self.current,
                elapsed_seconds=round(elapsed, 2),
                error=str(exc_val),
                success=False
            )
        
        return False  # Don't suppress exceptions


# Global singleton instance
_logging_manager = LoggingManager()


def get_logging_manager() -> LoggingManager:
    """Get the global logging manager instance"""
    return _logging_manager


def get_logger(name: str, structured: bool = True) -> Any:
    """
    Convenience function to get a logger.
    
    Args:
        name: Logger name
        structured: Whether to return structured logger
        
    Returns:
        Logger instance
    """
    return _logging_manager.get_logger(name, structured=structured)

