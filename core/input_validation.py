"""
Enhanced Input Validation and Error Handling

Provides comprehensive validation for user inputs, configuration values,
file paths, and API requests with helpful error messages.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors with helpful messages"""
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize validation error.
        
        Args:
            message: Human-readable error message
            field: Optional field name that failed validation
            details: Optional additional details about the error
        """
        self.message = message
        self.field = field
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """Format error message"""
        if self.field:
            return f"Validation error for '{self.field}': {self.message}"
        return f"Validation error: {self.message}"


@dataclass
class ValidationResult:
    """
    Result of a validation operation.
    
    Attributes:
        valid: Whether validation passed
        errors: List of error messages
        warnings: List of warning messages
        details: Additional validation details
    """
    valid: bool = True
    errors: List[str] = None
    warnings: List[str] = None
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.details is None:
            self.details = {}
    
    def add_error(self, message: str) -> None:
        """Add an error message"""
        self.errors.append(message)
        self.valid = False
    
    def add_warning(self, message: str) -> None:
        """Add a warning message"""
        self.warnings.append(message)
    
    def raise_if_invalid(self) -> None:
        """Raise ValidationError if validation failed"""
        if not self.valid:
            raise ValidationError("\n".join(self.errors), details=self.details)


class FileValidator:
    """Validates file paths and operations"""
    
    @staticmethod
    def validate_file_exists(
        file_path: Union[str, Path],
        file_type: str = "file",
        max_size_mb: Optional[float] = None
    ) -> ValidationResult:
        """
        Validate that a file exists and is readable.
        
        Args:
            file_path: Path to file
            file_type: Description of file type for error messages
            max_size_mb: Optional maximum file size in MB
            
        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult()
        path = Path(file_path)
        
        # Check existence
        if not path.exists():
            result.add_error(
                f"{file_type.capitalize()} not found: {file_path}\n"
                f"Please check that the path is correct and the file exists."
            )
            return result
        
        # Check if it's a file (not directory)
        if not path.is_file():
            result.add_error(
                f"Path is not a file: {file_path}\n"
                f"Expected a {file_type}, but path points to a directory."
            )
            return result
        
        # Check readability
        if not os.access(path, os.R_OK):
            result.add_error(
                f"Cannot read {file_type}: {file_path}\n"
                f"Permission denied. Check file permissions."
            )
            return result
        
        # Check file size
        if max_size_mb:
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > max_size_mb:
                result.add_warning(
                    f"File size ({size_mb:.2f} MB) exceeds recommended limit ({max_size_mb} MB). "
                    "Processing may be slow or consume significant memory."
                )
            result.details['size_mb'] = round(size_mb, 2)
        
        return result
    
    @staticmethod
    def validate_directory_exists(
        dir_path: Union[str, Path],
        create_if_missing: bool = False
    ) -> ValidationResult:
        """
        Validate that a directory exists.
        
        Args:
            dir_path: Path to directory
            create_if_missing: Whether to create directory if missing
            
        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult()
        path = Path(dir_path)
        
        if not path.exists():
            if create_if_missing:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    result.add_warning(f"Created directory: {dir_path}")
                except Exception as e:
                    result.add_error(
                        f"Cannot create directory: {dir_path}\n"
                        f"Error: {str(e)}"
                    )
            else:
                result.add_error(
                    f"Directory not found: {dir_path}\n"
                    f"Please create the directory or check the path."
                )
        elif not path.is_dir():
            result.add_error(
                f"Path is not a directory: {dir_path}\n"
                f"Expected a directory, but path points to a file."
            )
        
        return result
    
    @staticmethod
    def validate_file_format(
        file_path: Union[str, Path],
        expected_extensions: List[str]
    ) -> ValidationResult:
        """
        Validate file has expected extension.
        
        Args:
            file_path: Path to file
            expected_extensions: List of valid extensions (e.g., ['.json', '.yaml'])
            
        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult()
        path = Path(file_path)
        
        if path.suffix.lower() not in [ext.lower() for ext in expected_extensions]:
            result.add_error(
                f"Invalid file format: {path.suffix}\n"
                f"Expected one of: {', '.join(expected_extensions)}\n"
                f"File: {file_path}"
            )
        
        return result


class NumericValidator:
    """Validates numeric inputs"""
    
    @staticmethod
    def validate_range(
        value: Union[int, float],
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        field_name: str = "value"
    ) -> ValidationResult:
        """
        Validate that a number is within specified range.
        
        Args:
            value: Value to validate
            min_value: Minimum allowed value (inclusive)
            max_value: Maximum allowed value (inclusive)
            field_name: Name of field for error messages
            
        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult()
        
        if min_value is not None and value < min_value:
            result.add_error(
                f"{field_name} must be >= {min_value}, got {value}"
            )
        
        if max_value is not None and value > max_value:
            result.add_error(
                f"{field_name} must be <= {max_value}, got {value}"
            )
        
        return result
    
    @staticmethod
    def validate_positive(
        value: Union[int, float],
        field_name: str = "value",
        allow_zero: bool = False
    ) -> ValidationResult:
        """
        Validate that a number is positive.
        
        Args:
            value: Value to validate
            field_name: Name of field for error messages
            allow_zero: Whether zero is considered valid
            
        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult()
        
        if allow_zero:
            if value < 0:
                result.add_error(
                    f"{field_name} must be >= 0, got {value}"
                )
        else:
            if value <= 0:
                result.add_error(
                    f"{field_name} must be > 0, got {value}"
                )
        
        return result
    
    @staticmethod
    def parse_int_safe(
        value: Any,
        default: Optional[int] = None,
        field_name: str = "value"
    ) -> int:
        """
        Safely parse integer with helpful error message.
        
        Args:
            value: Value to parse
            default: Default value if parsing fails
            field_name: Name of field for error messages
            
        Returns:
            Parsed integer
            
        Raises:
            ValidationError: If parsing fails and no default provided
        """
        try:
            return int(value)
        except (ValueError, TypeError) as e:
            if default is not None:
                logger.warning(
                    f"Could not parse {field_name} as integer: {value}. "
                    f"Using default: {default}"
                )
                return default
            raise ValidationError(
                f"Invalid integer value for {field_name}: {value}\n"
                f"Expected a whole number, got: {type(value).__name__}",
                field=field_name
            ) from e


class StringValidator:
    """Validates string inputs"""
    
    @staticmethod
    def validate_not_empty(
        value: str,
        field_name: str = "value"
    ) -> ValidationResult:
        """
        Validate that a string is not empty.
        
        Args:
            value: String to validate
            field_name: Name of field for error messages
            
        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult()
        
        if not value or not value.strip():
            result.add_error(
                f"{field_name} cannot be empty"
            )
        
        return result
    
    @staticmethod
    def validate_enum(
        value: str,
        allowed_values: List[str],
        field_name: str = "value",
        case_sensitive: bool = True
    ) -> ValidationResult:
        """
        Validate that a string is one of allowed values.
        
        Args:
            value: Value to validate
            allowed_values: List of valid values
            field_name: Name of field for error messages
            case_sensitive: Whether comparison is case-sensitive
            
        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult()
        
        comparison_value = value if case_sensitive else value.lower()
        comparison_allowed = (
            allowed_values if case_sensitive
            else [v.lower() for v in allowed_values]
        )
        
        if comparison_value not in comparison_allowed:
            result.add_error(
                f"Invalid value for {field_name}: {value}\n"
                f"Must be one of: {', '.join(allowed_values)}"
            )
        
        return result


def validate_config_value(
    value: Any,
    value_type: type,
    field_name: str,
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None,
    allowed_values: Optional[List[Any]] = None
) -> Any:
    """
    Comprehensive validation for configuration values.
    
    Args:
        value: Value to validate
        value_type: Expected type
        field_name: Configuration field name
        min_value: Optional minimum value (for numbers)
        max_value: Optional maximum value (for numbers)
        allowed_values: Optional list of allowed values (for enums)
        
    Returns:
        Validated (and possibly coerced) value
        
    Raises:
        ValidationError: If validation fails
    """
    result = ValidationResult()
    
    # Type validation
    if not isinstance(value, value_type):
        try:
            value = value_type(value)
        except (ValueError, TypeError):
            raise ValidationError(
                f"Invalid type for {field_name}: expected {value_type.__name__}, "
                f"got {type(value).__name__}",
                field=field_name
            )
    
    # Range validation for numbers
    if isinstance(value, (int, float)):
        range_result = NumericValidator.validate_range(
            value, min_value, max_value, field_name
        )
        if not range_result.valid:
            result.errors.extend(range_result.errors)
    
    # Enum validation
    if allowed_values:
        if value not in allowed_values:
            result.add_error(
                f"Invalid value for {field_name}: {value}\n"
                f"Must be one of: {', '.join(map(str, allowed_values))}"
            )
    
    result.raise_if_invalid()
    return value

