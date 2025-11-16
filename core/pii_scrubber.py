"""
PII Scrubbing for Data Privacy and Compliance

Automatically detects and redacts Personally Identifiable Information (PII)
to ensure GDPR, HIPAA, and SOC2 compliance.
"""

from typing import Dict, Any, List, Optional
import re
import hashlib
import logging

from core.signal_normalizer import NormalizedSignal

logger = logging.getLogger(__name__)


class PIIPattern:
    """PII detection pattern"""
    def __init__(self, name: str, pattern: str, replacement: str, severity: str = "high"):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.replacement = replacement
        self.severity = severity


class PIIScrubber:
    """
    Comprehensive PII scrubbing system.

    Detects and redacts:
    - Email addresses
    - Phone numbers
    - Social Security Numbers (SSN)
    - Credit card numbers
    - IP addresses (optional)
    - API keys and tokens
    - Passwords
    - URLs with sensitive data
    - Names (optional, with ML)
    - Addresses (optional, with ML)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        self.scrub_ip_addresses = self.config.get('scrub_ip_addresses', False)
        self.hash_pii = self.config.get('hash_pii', True)  # Hash instead of fully redacting
        self.patterns = self._initialize_patterns()
        self.stats = {'total_scrubbed': 0, 'by_type': {}}

    def _initialize_patterns(self) -> List[PIIPattern]:
        """Initialize PII detection patterns"""
        patterns = [
            # Email addresses
            PIIPattern(
                name="email",
                pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                replacement='[EMAIL_REDACTED]',
                severity="high"
            ),

            # Phone numbers (US and international)
            PIIPattern(
                name="phone",
                pattern=r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
                replacement='[PHONE_REDACTED]',
                severity="high"
            ),

            # SSN (US)
            PIIPattern(
                name="ssn",
                pattern=r'\b\d{3}-\d{2}-\d{4}\b',
                replacement='[SSN_REDACTED]',
                severity="critical"
            ),

            # Credit card numbers
            PIIPattern(
                name="credit_card",
                pattern=r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
                replacement='[CREDIT_CARD_REDACTED]',
                severity="critical"
            ),

            # API keys and tokens (generic patterns)
            PIIPattern(
                name="api_key",
                pattern=r'(api[_-]?key|token|secret)["\s:=]+["\']?([A-Za-z0-9_\-]{20,})["\']?',
                replacement=r'\1: [API_KEY_REDACTED]',
                severity="critical"
            ),

            # AWS Access Keys
            PIIPattern(
                name="aws_access_key",
                pattern=r'AKIA[0-9A-Z]{16}',
                replacement='[AWS_KEY_REDACTED]',
                severity="critical"
            ),

            # Passwords in URLs or configs
            PIIPattern(
                name="password",
                pattern=r'(password|passwd|pwd)["\s:=]+["\']?([^\s"\']{6,})["\']?',
                replacement=r'\1: [PASSWORD_REDACTED]',
                severity="critical"
            ),

            # JWT tokens
            PIIPattern(
                name="jwt",
                pattern=r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}',
                replacement='[JWT_REDACTED]',
                severity="high"
            ),

            # IPv4 addresses (optional)
            PIIPattern(
                name="ipv4",
                pattern=r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
                replacement='[IP_REDACTED]',
                severity="medium"
            ) if self.scrub_ip_addresses else None,

            # MAC addresses
            PIIPattern(
                name="mac_address",
                pattern=r'\b([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})\b',
                replacement='[MAC_REDACTED]',
                severity="medium"
            ),

            # URLs with sensitive parameters
            PIIPattern(
                name="url_with_token",
                pattern=r'https?://[^\s]+[?&](token|key|password|secret)=[^\s&]+',
                replacement='[URL_WITH_SENSITIVE_DATA_REDACTED]',
                severity="high"
            ),
        ]

        return [p for p in patterns if p is not None]

    def scrub_text(self, text: str, track_stats: bool = True) -> str:
        """
        Scrub PII from text.

        Args:
            text: Text to scrub
            track_stats: Whether to track scrubbing statistics

        Returns:
            Scrubbed text
        """
        if not self.enabled or not text:
            return text

        scrubbed_text = text
        scrubbed_count = 0

        for pattern in self.patterns:
            matches = pattern.pattern.findall(scrubbed_text)

            if matches:
                if self.hash_pii and pattern.name in ['email', 'phone']:
                    # Hash PII for analytics while maintaining privacy
                    for match in matches:
                        match_str = match if isinstance(match, str) else match[0]
                        hashed = self._hash_pii(match_str, pattern.name)
                        scrubbed_text = scrubbed_text.replace(match_str, hashed)
                else:
                    # Fully redact
                    scrubbed_text = pattern.pattern.sub(pattern.replacement, scrubbed_text)

                scrubbed_count += len(matches)

                if track_stats:
                    self.stats['by_type'][pattern.name] = \
                        self.stats['by_type'].get(pattern.name, 0) + len(matches)

        if scrubbed_count > 0 and track_stats:
            self.stats['total_scrubbed'] += scrubbed_count

        return scrubbed_text

    def scrub_dict(self, data: Dict[str, Any], recursive: bool = True) -> Dict[str, Any]:
        """
        Scrub PII from dictionary values.

        Args:
            data: Dictionary to scrub
            recursive: Whether to recursively scrub nested dicts

        Returns:
            Scrubbed dictionary
        """
        if not self.enabled:
            return data

        scrubbed = {}

        for key, value in data.items():
            if isinstance(value, str):
                scrubbed[key] = self.scrub_text(value)
            elif isinstance(value, dict) and recursive:
                scrubbed[key] = self.scrub_dict(value, recursive=True)
            elif isinstance(value, list) and recursive:
                scrubbed[key] = [
                    self.scrub_text(item) if isinstance(item, str)
                    else self.scrub_dict(item, recursive=True) if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                scrubbed[key] = value

        return scrubbed

    def scrub_signal(self, signal: NormalizedSignal) -> NormalizedSignal:
        """
        Scrub PII from a normalized signal.

        Args:
            signal: Signal to scrub

        Returns:
            Scrubbed signal (new instance)
        """
        if not self.enabled:
            return signal

        return NormalizedSignal(
            signal_type=signal.signal_type,
            title=self.scrub_text(signal.title),
            description=self.scrub_text(signal.description),
            timestamp=signal.timestamp,
            source=signal.source,  # Don't scrub source
            severity=signal.severity,
            raw_data=self.scrub_dict(signal.raw_data) if signal.raw_data else None,
            metadata=self.scrub_dict(signal.metadata),
            tags=self.scrub_dict(signal.tags),
        )

    def scrub_signals(self, signals: List[NormalizedSignal]) -> List[NormalizedSignal]:
        """Scrub PII from multiple signals"""
        return [self.scrub_signal(s) for s in signals]

    def _hash_pii(self, pii_value: str, pii_type: str) -> str:
        """
        Hash PII value for analytics while maintaining privacy.

        Args:
            pii_value: PII value to hash
            pii_type: Type of PII

        Returns:
            Hashed value with type prefix
        """
        # Use SHA256 for strong hashing
        hashed = hashlib.sha256(pii_value.encode()).hexdigest()[:12]
        return f"[{pii_type.upper()}_HASH_{hashed}]"

    def get_stats(self) -> Dict[str, Any]:
        """Get PII scrubbing statistics"""
        return {
            'enabled': self.enabled,
            'total_scrubbed': self.stats['total_scrubbed'],
            'by_type': self.stats['by_type'],
            'patterns_active': len(self.patterns)
        }

    def reset_stats(self):
        """Reset scrubbing statistics"""
        self.stats = {'total_scrubbed': 0, 'by_type': {}}


class AdvancedPIIScrubber(PIIScrubber):
    """
    Advanced PII scrubber with ML-based detection.

    Uses pre-trained models to detect:
    - Person names
    - Locations/addresses
    - Organization names
    - Custom entity types
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.use_ner = config.get('use_ner', False) if config else False
        self.ner_model = None

        if self.use_ner:
            self._initialize_ner()

    def _initialize_ner(self):
        """Initialize Named Entity Recognition model"""
        try:
            import spacy
            self.ner_model = spacy.load("en_core_web_sm")
            logger.info("Loaded spaCy NER model for advanced PII detection")
        except Exception as e:
            logger.warning(f"Could not load NER model: {e}")
            self.use_ner = False

    def scrub_text(self, text: str, track_stats: bool = True) -> str:
        """
        Scrub text with ML-based entity detection.
        """
        # First run pattern-based scrubbing
        scrubbed = super().scrub_text(text, track_stats)

        # Then run NER if enabled
        if self.use_ner and self.ner_model:
            scrubbed = self._scrub_with_ner(scrubbed, track_stats)

        return scrubbed

    def _scrub_with_ner(self, text: str, track_stats: bool) -> str:
        """Use NER to detect and scrub person names, locations, etc."""
        if not self.ner_model:
            return text

        doc = self.ner_model(text)
        scrubbed = text

        for ent in doc.ents:
            if ent.label_ == "PERSON":
                if self.hash_pii:
                    hashed = self._hash_pii(ent.text, "person")
                    scrubbed = scrubbed.replace(ent.text, hashed)
                else:
                    scrubbed = scrubbed.replace(ent.text, "[PERSON_REDACTED]")

                if track_stats:
                    self.stats['by_type']['person'] = \
                        self.stats['by_type'].get('person', 0) + 1

            elif ent.label_ in ["GPE", "LOC"]:  # Geo-political entity, Location
                if self.hash_pii:
                    hashed = self._hash_pii(ent.text, "location")
                    scrubbed = scrubbed.replace(ent.text, hashed)
                else:
                    scrubbed = scrubbed.replace(ent.text, "[LOCATION_REDACTED]")

                if track_stats:
                    self.stats['by_type']['location'] = \
                        self.stats['by_type'].get('location', 0) + 1

        return scrubbed


# Global PII scrubber instance
_pii_scrubber: Optional[PIIScrubber] = None


def get_pii_scrubber() -> PIIScrubber:
    """Get global PII scrubber"""
    global _pii_scrubber
    if _pii_scrubber is None:
        _pii_scrubber = PIIScrubber()
    return _pii_scrubber


def set_pii_scrubber(scrubber: PIIScrubber):
    """Set global PII scrubber"""
    global _pii_scrubber
    _pii_scrubber = scrubber


def scrub_for_compliance(data: Any) -> Any:
    """
    Convenience function to scrub data for compliance.

    Args:
        data: Data to scrub (str, dict, or NormalizedSignal)

    Returns:
        Scrubbed data
    """
    scrubber = get_pii_scrubber()

    if isinstance(data, str):
        return scrubber.scrub_text(data)
    elif isinstance(data, dict):
        return scrubber.scrub_dict(data)
    elif isinstance(data, NormalizedSignal):
        return scrubber.scrub_signal(data)
    elif isinstance(data, list):
        if all(isinstance(item, NormalizedSignal) for item in data):
            return scrubber.scrub_signals(data)
        return [scrub_for_compliance(item) for item in data]
    else:
        return data
