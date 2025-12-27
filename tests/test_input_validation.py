"""
Tests for Enhanced Input Validation
"""

import pytest
import tempfile
from pathlib import Path

from core.input_validation import (
    ValidationError,
    ValidationResult,
    FileValidator,
    NumericValidator,
    StringValidator,
    validate_config_value
)


class TestValidationError:
    """Tests for ValidationError class"""
    
    def test_basic_error(self):
        """Test basic error creation"""
        error = ValidationError("Test error")
        assert str(error) == "Validation error: Test error"
    
    def test_error_with_field(self):
        """Test error with field name"""
        error = ValidationError("Invalid value", field="config_value")
        assert "config_value" in str(error)
    
    def test_error_with_details(self):
        """Test error with details"""
        error = ValidationError("Test error", details={"key": "value"})
        assert error.details == {"key": "value"}


class TestValidationResult:
    """Tests for ValidationResult class"""
    
    def test_default_valid(self):
        """Test default validation result is valid"""
        result = ValidationResult()
        assert result.valid is True
        assert len(result.errors) == 0
    
    def test_add_error_invalidates(self):
        """Test adding error invalidates result"""
        result = ValidationResult()
        result.add_error("Test error")
        
        assert result.valid is False
        assert "Test error" in result.errors
    
    def test_add_warning_keeps_valid(self):
        """Test adding warning keeps result valid"""
        result = ValidationResult()
        result.add_warning("Test warning")
        
        assert result.valid is True
        assert "Test warning" in result.warnings
    
    def test_raise_if_invalid(self):
        """Test raise_if_invalid raises when invalid"""
        result = ValidationResult()
        result.add_error("Test error")
        
        with pytest.raises(ValidationError):
            result.raise_if_invalid()
    
    def test_raise_if_invalid_no_error_when_valid(self):
        """Test raise_if_invalid doesn't raise when valid"""
        result = ValidationResult()
        result.raise_if_invalid()  # Should not raise


class TestFileValidator:
    """Tests for FileValidator class"""
    
    def test_validate_file_exists_success(self):
        """Test successful file validation"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"test content")
        
        try:
            result = FileValidator.validate_file_exists(temp_path)
            assert result.valid is True
        finally:
            temp_path.unlink()
    
    def test_validate_file_not_found(self):
        """Test file not found error"""
        result = FileValidator.validate_file_exists("/nonexistent/file.txt")
        
        assert result.valid is False
        assert "not found" in result.errors[0].lower()
    
    def test_validate_directory_as_file(self):
        """Test error when path is directory not file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = FileValidator.validate_file_exists(tmpdir)
            
            assert result.valid is False
            assert "not a file" in result.errors[0].lower()
    
    def test_validate_file_size_warning(self):
        """Test file size warning"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)
            # Write 2MB of data
            f.write(b"x" * (2 * 1024 * 1024))
        
        try:
            result = FileValidator.validate_file_exists(
                temp_path,
                max_size_mb=1.0
            )
            
            # Should have warning about size
            assert len(result.warnings) > 0
            assert result.valid is True  # Still valid, just warning
        finally:
            temp_path.unlink()
    
    def test_validate_directory_exists_success(self):
        """Test directory validation success"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = FileValidator.validate_directory_exists(tmpdir)
            assert result.valid is True
    
    def test_validate_directory_create_if_missing(self):
        """Test directory creation when missing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new_directory"
            
            result = FileValidator.validate_directory_exists(
                new_dir,
                create_if_missing=True
            )
            
            assert result.valid is True
            assert new_dir.exists()
            assert "Created directory" in result.warnings[0]
    
    def test_validate_file_format_success(self):
        """Test file format validation success"""
        result = FileValidator.validate_file_format(
            "test.json",
            expected_extensions=['.json', '.yaml']
        )
        assert result.valid is True
    
    def test_validate_file_format_failure(self):
        """Test file format validation failure"""
        result = FileValidator.validate_file_format(
            "test.txt",
            expected_extensions=['.json', '.yaml']
        )
        
        assert result.valid is False
        assert ".json" in result.errors[0]
        assert ".yaml" in result.errors[0]


class TestNumericValidator:
    """Tests for NumericValidator class"""
    
    def test_validate_range_success(self):
        """Test range validation success"""
        result = NumericValidator.validate_range(5, min_value=0, max_value=10)
        assert result.valid is True
    
    def test_validate_range_below_minimum(self):
        """Test value below minimum"""
        result = NumericValidator.validate_range(5, min_value=10)
        
        assert result.valid is False
        assert "must be >= 10" in result.errors[0]
    
    def test_validate_range_above_maximum(self):
        """Test value above maximum"""
        result = NumericValidator.validate_range(15, max_value=10)
        
        assert result.valid is False
        assert "must be <= 10" in result.errors[0]
    
    def test_validate_positive_success(self):
        """Test positive validation success"""
        result = NumericValidator.validate_positive(5)
        assert result.valid is True
    
    def test_validate_positive_failure(self):
        """Test negative value fails positive validation"""
        result = NumericValidator.validate_positive(-5)
        assert result.valid is False
    
    def test_validate_positive_allow_zero(self):
        """Test zero allowed when specified"""
        result = NumericValidator.validate_positive(0, allow_zero=True)
        assert result.valid is True
        
        result = NumericValidator.validate_positive(0, allow_zero=False)
        assert result.valid is False
    
    def test_parse_int_safe_success(self):
        """Test safe integer parsing"""
        assert NumericValidator.parse_int_safe("42") == 42
        assert NumericValidator.parse_int_safe(42.7) == 42
    
    def test_parse_int_safe_with_default(self):
        """Test safe parsing with default value"""
        result = NumericValidator.parse_int_safe("invalid", default=10)
        assert result == 10
    
    def test_parse_int_safe_no_default_raises(self):
        """Test parsing without default raises error"""
        with pytest.raises(ValidationError):
            NumericValidator.parse_int_safe("invalid")


class TestStringValidator:
    """Tests for StringValidator class"""
    
    def test_validate_not_empty_success(self):
        """Test non-empty string validation"""
        result = StringValidator.validate_not_empty("test")
        assert result.valid is True
    
    def test_validate_empty_string(self):
        """Test empty string fails validation"""
        result = StringValidator.validate_not_empty("")
        assert result.valid is False
    
    def test_validate_whitespace_only(self):
        """Test whitespace-only string fails validation"""
        result = StringValidator.validate_not_empty("   ")
        assert result.valid is False
    
    def test_validate_enum_success(self):
        """Test enum validation success"""
        result = StringValidator.validate_enum(
            "option1",
            allowed_values=["option1", "option2", "option3"]
        )
        assert result.valid is True
    
    def test_validate_enum_failure(self):
        """Test enum validation failure"""
        result = StringValidator.validate_enum(
            "invalid",
            allowed_values=["option1", "option2"]
        )
        
        assert result.valid is False
        assert "option1" in result.errors[0]
        assert "option2" in result.errors[0]
    
    def test_validate_enum_case_insensitive(self):
        """Test case-insensitive enum validation"""
        result = StringValidator.validate_enum(
            "OPTION1",
            allowed_values=["option1", "option2"],
            case_sensitive=False
        )
        assert result.valid is True


class TestValidateConfigValue:
    """Tests for validate_config_value function"""
    
    def test_type_coercion(self):
        """Test automatic type coercion"""
        result = validate_config_value("42", int, "test_field")
        assert result == 42
        assert isinstance(result, int)
    
    def test_type_validation_failure(self):
        """Test type validation failure"""
        with pytest.raises(ValidationError):
            validate_config_value("invalid", int, "test_field")
    
    def test_range_validation(self):
        """Test range validation in config"""
        # Should succeed
        validate_config_value(5, int, "test_field", min_value=0, max_value=10)
        
        # Should fail
        with pytest.raises(ValidationError):
            validate_config_value(15, int, "test_field", min_value=0, max_value=10)
    
    def test_enum_validation(self):
        """Test enum validation in config"""
        # Should succeed
        validate_config_value(
            "option1",
            str,
            "test_field",
            allowed_values=["option1", "option2"]
        )
        
        # Should fail
        with pytest.raises(ValidationError):
            validate_config_value(
                "invalid",
                str,
                "test_field",
                allowed_values=["option1", "option2"]
            )


class TestIntegration:
    """Integration tests for validation"""
    
    def test_complete_file_validation_workflow(self):
        """Test complete file validation workflow"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
            f.write(b'{"test": "data"}')
        
        try:
            # Validate exists
            result = FileValidator.validate_file_exists(temp_path)
            result.raise_if_invalid()
            
            # Validate format
            result = FileValidator.validate_file_format(
                temp_path,
                expected_extensions=['.json', '.yaml']
            )
            result.raise_if_invalid()
            
            # All validations passed
            assert True
        finally:
            temp_path.unlink()
    
    def test_config_validation_workflow(self):
        """Test configuration validation workflow"""
        # Validate multiple config values
        timeout = validate_config_value(300, int, "timeout", min_value=60, max_value=3600)
        assert timeout == 300
        
        log_level = validate_config_value(
            "INFO",
            str,
            "log_level",
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR"]
        )
        assert log_level == "INFO"

