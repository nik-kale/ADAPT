"""
Tests for PII Scrubbing
"""

import pytest
from core.pii_scrubber import PIIScrubber, PIIPattern


@pytest.fixture
def pii_scrubber():
    """Create PII scrubber instance"""
    return PIIScrubber(hash_pii=False)


@pytest.fixture
def pii_scrubber_with_hashing():
    """Create PII scrubber with hashing enabled"""
    return PIIScrubber(hash_pii=True)


class TestPIIScrubber:
    """Test PII scrubbing functionality"""

    def test_scrub_email(self, pii_scrubber):
        """Test scrubbing email addresses"""
        text = "Contact john.doe@example.com for more info"
        scrubbed = pii_scrubber.scrub_text(text)

        assert "john.doe@example.com" not in scrubbed
        assert "[EMAIL_REDACTED]" in scrubbed

    def test_scrub_ssn(self, pii_scrubber):
        """Test scrubbing Social Security Numbers"""
        text = "SSN: 123-45-6789"
        scrubbed = pii_scrubber.scrub_text(text)

        assert "123-45-6789" not in scrubbed
        assert "[SSN_REDACTED]" in scrubbed

    def test_scrub_credit_card(self, pii_scrubber):
        """Test scrubbing credit card numbers"""
        text = "Card: 4532-1234-5678-9010"
        scrubbed = pii_scrubber.scrub_text(text)

        assert "4532-1234-5678-9010" not in scrubbed
        assert "[CREDIT_CARD_REDACTED]" in scrubbed

    def test_scrub_phone_number(self, pii_scrubber):
        """Test scrubbing phone numbers"""
        text = "Call me at (555) 123-4567"
        scrubbed = pii_scrubber.scrub_text(text)

        assert "(555) 123-4567" not in scrubbed
        assert "[PHONE_REDACTED]" in scrubbed

    def test_scrub_ip_address(self, pii_scrubber):
        """Test scrubbing IP addresses"""
        text = "Server IP: 192.168.1.100"
        scrubbed = pii_scrubber.scrub_text(text)

        assert "192.168.1.100" not in scrubbed
        assert "[IP_REDACTED]" in scrubbed

    def test_scrub_api_key(self, pii_scrubber):
        """Test scrubbing API keys"""
        text = 'api_key: "sk_live_1234567890abcdef"'
        scrubbed = pii_scrubber.scrub_text(text)

        assert "sk_live_1234567890abcdef" not in scrubbed
        assert "[API_KEY_REDACTED]" in scrubbed

    def test_scrub_aws_secret(self, pii_scrubber):
        """Test scrubbing AWS secrets"""
        text = "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        scrubbed = pii_scrubber.scrub_text(text)

        assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in scrubbed
        assert "[AWS_SECRET_REDACTED]" in scrubbed

    def test_scrub_jwt_token(self, pii_scrubber):
        """Test scrubbing JWT tokens"""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        scrubbed = pii_scrubber.scrub_text(text)

        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in scrubbed
        assert "[JWT_REDACTED]" in scrubbed

    def test_scrub_multiple_pii_types(self, pii_scrubber):
        """Test scrubbing multiple PII types in same text"""
        text = """
        User: john.doe@example.com
        SSN: 123-45-6789
        Phone: (555) 123-4567
        """
        scrubbed = pii_scrubber.scrub_text(text)

        assert "john.doe@example.com" not in scrubbed
        assert "123-45-6789" not in scrubbed
        assert "(555) 123-4567" not in scrubbed
        assert "[EMAIL_REDACTED]" in scrubbed
        assert "[SSN_REDACTED]" in scrubbed
        assert "[PHONE_REDACTED]" in scrubbed

    def test_scrub_with_hashing(self, pii_scrubber_with_hashing):
        """Test scrubbing with hashing enabled"""
        text = "Contact john.doe@example.com"
        scrubbed = pii_scrubber_with_hashing.scrub_text(text)

        # Should not contain original email
        assert "john.doe@example.com" not in scrubbed

        # Should contain hash prefix
        assert "[EMAIL:" in scrubbed

    def test_scrub_preserves_non_pii(self, pii_scrubber):
        """Test that non-PII text is preserved"""
        text = "The application is running normally on server web-01"
        scrubbed = pii_scrubber.scrub_text(text)

        assert scrubbed == text

    def test_scrub_dict(self, pii_scrubber):
        """Test scrubbing dictionary values"""
        data = {
            "username": "john.doe",
            "email": "john.doe@example.com",
            "message": "Error occurred",
            "nested": {
                "ssn": "123-45-6789"
            }
        }

        scrubbed = pii_scrubber.scrub_dict(data)

        assert scrubbed["email"] == "[EMAIL_REDACTED]"
        assert scrubbed["nested"]["ssn"] == "[SSN_REDACTED]"
        assert scrubbed["message"] == "Error occurred"

    def test_scrub_list(self, pii_scrubber):
        """Test scrubbing list of strings"""
        data = [
            "User email: john@example.com",
            "Normal log message",
            "SSN found: 123-45-6789"
        ]

        scrubbed = pii_scrubber.scrub_list(data)

        assert "john@example.com" not in scrubbed[0]
        assert scrubbed[1] == "Normal log message"
        assert "123-45-6789" not in scrubbed[2]

    def test_custom_pattern(self):
        """Test adding custom PII pattern"""
        scrubber = PIIScrubber()

        # Add custom pattern for employee IDs
        custom_pattern = PIIPattern(
            name="employee_id",
            pattern=r'EMP\d{6}',
            replacement='[EMPLOYEE_ID_REDACTED]'
        )
        scrubber.patterns.append(custom_pattern)

        text = "Employee EMP123456 accessed the system"
        scrubbed = scrubber.scrub_text(text)

        assert "EMP123456" not in scrubbed
        assert "[EMPLOYEE_ID_REDACTED]" in scrubbed

    def test_scrub_with_context(self, pii_scrubber):
        """Test scrubbing while preserving context"""
        text = "User john.doe@example.com logged in from 192.168.1.100 at 10:30 AM"
        scrubbed = pii_scrubber.scrub_text(text)

        # PII should be removed
        assert "john.doe@example.com" not in scrubbed
        assert "192.168.1.100" not in scrubbed

        # Context should be preserved
        assert "User" in scrubbed
        assert "logged in from" in scrubbed
        assert "at 10:30 AM" in scrubbed

    def test_case_insensitive_patterns(self, pii_scrubber):
        """Test that patterns work regardless of case"""
        text = "API_KEY: ABC123 and api_key: XYZ789"
        scrubbed = pii_scrubber.scrub_text(text)

        # Both should be redacted
        assert "ABC123" not in scrubbed
        assert "XYZ789" not in scrubbed


class TestPIIPattern:
    """Test PIIPattern dataclass"""

    def test_pattern_creation(self):
        """Test creating a PII pattern"""
        pattern = PIIPattern(
            name="test_pattern",
            pattern=r'\d{3}-\d{2}-\d{4}',
            replacement='[REDACTED]'
        )

        assert pattern.name == "test_pattern"
        assert pattern.pattern.pattern == r'\d{3}-\d{2}-\d{4}'
        assert pattern.replacement == '[REDACTED]'


class TestPIIScrubbingIntegration:
    """Integration tests for PII scrubbing"""

    def test_scrub_signal(self, pii_scrubber):
        """Test scrubbing a normalized signal"""
        class MockSignal:
            def __init__(self):
                self.title = "API Error for user john@example.com"
                self.description = "Error occurred for SSN 123-45-6789"
                self.metadata = {
                    "user_email": "john@example.com",
                    "log": "Connection from 192.168.1.100"
                }

        signal = MockSignal()
        scrubbed = pii_scrubber.scrub_signal(signal)

        # Title should be scrubbed
        assert "john@example.com" not in scrubbed.title

        # Description should be scrubbed
        assert "123-45-6789" not in scrubbed.description

        # Metadata should be scrubbed
        assert "john@example.com" not in scrubbed.metadata.get("user_email", "")
        assert "192.168.1.100" not in scrubbed.metadata.get("log", "")

    def test_scrub_rca_context(self, pii_scrubber):
        """Test scrubbing an entire RCA context"""
        class MockSignal:
            def __init__(self, title, desc):
                self.title = title
                self.description = desc
                self.metadata = {}

        class MockContext:
            def __init__(self):
                self.signals = [
                    MockSignal("Error for john@example.com", "Details"),
                    MockSignal("SSN leak: 123-45-6789", "More details")
                ]
                self.metadata = {
                    "analyst_email": "analyst@company.com"
                }

        context = MockContext()
        scrubbed_context = pii_scrubber.scrub_rca_context(context)

        # Signals should be scrubbed
        assert "john@example.com" not in scrubbed_context.signals[0].title
        assert "123-45-6789" not in scrubbed_context.signals[1].title

        # Metadata should be scrubbed
        assert "analyst@company.com" not in scrubbed_context.metadata.get("analyst_email", "")

    def test_compliance_log_scrubbing(self, pii_scrubber):
        """Test scrubbing for compliance logging"""
        log_entry = {
            "timestamp": "2024-01-15T10:30:00Z",
            "level": "ERROR",
            "message": "Authentication failed for user john.doe@example.com from IP 192.168.1.100",
            "context": {
                "user_agent": "Mozilla/5.0",
                "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"
            }
        }

        scrubbed = pii_scrubber.scrub_dict(log_entry)

        # Verify PII is removed
        assert "john.doe@example.com" not in scrubbed["message"]
        assert "192.168.1.100" not in scrubbed["message"]
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in scrubbed["context"]["session_token"]

        # Verify structure is preserved
        assert scrubbed["timestamp"] == log_entry["timestamp"]
        assert scrubbed["level"] == log_entry["level"]
        assert "Authentication failed" in scrubbed["message"]
