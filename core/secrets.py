"""
Secrets management for ADAPT framework.

Provides abstraction for retrieving secrets from various providers
(environment variables, AWS Secrets Manager, HashiCorp Vault, etc.)
"""

import os
from typing import Optional, Dict
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class SecretProvider(ABC):
    """Abstract base class for secret providers"""

    @abstractmethod
    def get_secret(self, key: str) -> Optional[str]:
        """
        Get secret value by key.

        Args:
            key: Secret key/name

        Returns:
            Secret value or None if not found
        """
        pass

    @abstractmethod
    def get_secret_dict(self, key: str) -> Optional[Dict[str, str]]:
        """
        Get secret as dictionary (for structured secrets).

        Args:
            key: Secret key/name

        Returns:
            Dictionary of secret values or None if not found
        """
        pass


class EnvironmentSecretProvider(SecretProvider):
    """
    Get secrets from environment variables.

    This is the simplest provider and suitable for development.
    """

    def __init__(self, prefix: str = "ADAPT_"):
        """
        Initialize environment secret provider.

        Args:
            prefix: Prefix for environment variable names
        """
        self.prefix = prefix

    def get_secret(self, key: str) -> Optional[str]:
        """Get secret from environment variable"""
        env_key = f"{self.prefix}{key.upper()}"
        return os.getenv(env_key)

    def get_secret_dict(self, key: str) -> Optional[Dict[str, str]]:
        """
        Get multiple related secrets as dictionary.

        Looks for environment variables with pattern: PREFIX_KEY_*
        """
        env_key_prefix = f"{self.prefix}{key.upper()}_"
        secrets = {}

        for env_var, value in os.environ.items():
            if env_var.startswith(env_key_prefix):
                # Extract the sub-key after the prefix
                sub_key = env_var[len(env_key_prefix):].lower()
                secrets[sub_key] = value

        return secrets if secrets else None


class AWSSecretsManagerProvider(SecretProvider):
    """
    Get secrets from AWS Secrets Manager.

    Requires boto3 to be installed.
    """

    def __init__(self, region: str = 'us-west-2'):
        """
        Initialize AWS Secrets Manager provider.

        Args:
            region: AWS region

        Raises:
            ImportError: If boto3 is not installed
        """
        try:
            import boto3
            import botocore.exceptions
        except ImportError:
            raise ImportError("Install boto3: pip install boto3")

        self.client = boto3.client('secretsmanager', region_name=region)
        self.botocore_exceptions = botocore.exceptions

    def get_secret(self, key: str) -> Optional[str]:
        """
        Get secret from AWS Secrets Manager.

        Args:
            key: Secret name in AWS Secrets Manager

        Returns:
            Secret string or None if not found
        """
        try:
            response = self.client.get_secret_value(SecretId=key)
            return response.get('SecretString')
        except self.botocore_exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.warning(f"Secret not found: {key}")
                return None
            else:
                logger.error(f"Error retrieving secret {key}: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret {key}: {e}")
            return None

    def get_secret_dict(self, key: str) -> Optional[Dict[str, str]]:
        """
        Get secret as dictionary (for JSON-stored secrets).

        Args:
            key: Secret name

        Returns:
            Dictionary of secret values or None
        """
        import json

        secret_string = self.get_secret(key)
        if not secret_string:
            return None

        try:
            return json.loads(secret_string)
        except json.JSONDecodeError:
            logger.error(f"Secret {key} is not valid JSON")
            return None


class HashiCorpVaultProvider(SecretProvider):
    """
    Get secrets from HashiCorp Vault.

    Requires hvac to be installed.
    """

    def __init__(self, url: str, token: Optional[str] = None):
        """
        Initialize HashiCorp Vault provider.

        Args:
            url: Vault server URL
            token: Vault token (if None, tries VAULT_TOKEN env var)

        Raises:
            ImportError: If hvac is not installed
        """
        try:
            import hvac
        except ImportError:
            raise ImportError("Install hvac: pip install hvac")

        token = token or os.getenv('VAULT_TOKEN')
        self.client = hvac.Client(url=url, token=token)

        if not self.client.is_authenticated():
            raise ValueError("Vault authentication failed")

    def get_secret(self, key: str, mount_point: str = 'secret') -> Optional[str]:
        """
        Get secret from Vault.

        Args:
            key: Secret path in Vault
            mount_point: Vault mount point

        Returns:
            Secret value or None
        """
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=key,
                mount_point=mount_point
            )
            data = response['data']['data']

            # If data has a single 'value' key, return that
            if 'value' in data and len(data) == 1:
                return data['value']

            # Otherwise return the whole data dict as JSON string
            import json
            return json.dumps(data)

        except Exception as e:
            logger.error(f"Error retrieving secret {key} from Vault: {e}")
            return None

    def get_secret_dict(self, key: str, mount_point: str = 'secret') -> Optional[Dict[str, str]]:
        """
        Get secret as dictionary from Vault.

        Args:
            key: Secret path
            mount_point: Vault mount point

        Returns:
            Dictionary of secret values or None
        """
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=key,
                mount_point=mount_point
            )
            return response['data']['data']

        except Exception as e:
            logger.error(f"Error retrieving secret dict {key} from Vault: {e}")
            return None


class ChainedSecretProvider(SecretProvider):
    """
    Chain multiple secret providers with fallback logic.

    Tries providers in order until a secret is found.
    """

    def __init__(self, providers: list[SecretProvider]):
        """
        Initialize chained provider.

        Args:
            providers: List of providers to try in order
        """
        self.providers = providers

    def get_secret(self, key: str) -> Optional[str]:
        """Try each provider until secret is found"""
        for provider in self.providers:
            try:
                secret = provider.get_secret(key)
                if secret is not None:
                    return secret
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed for {key}: {e}")
                continue

        return None

    def get_secret_dict(self, key: str) -> Optional[Dict[str, str]]:
        """Try each provider until secret dict is found"""
        for provider in self.providers:
            try:
                secret_dict = provider.get_secret_dict(key)
                if secret_dict is not None:
                    return secret_dict
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed for {key}: {e}")
                continue

        return None


# Global secret provider instance
_secret_provider: Optional[SecretProvider] = None


def set_secret_provider(provider: SecretProvider):
    """
    Set the global secret provider.

    Args:
        provider: Secret provider to use globally
    """
    global _secret_provider
    _secret_provider = provider


def get_secret_provider() -> SecretProvider:
    """
    Get the global secret provider.

    Returns:
        Global secret provider (defaults to EnvironmentSecretProvider)
    """
    global _secret_provider

    if _secret_provider is None:
        _secret_provider = EnvironmentSecretProvider()

    return _secret_provider


def get_secret(key: str) -> Optional[str]:
    """
    Convenience function to get a secret.

    Args:
        key: Secret key

    Returns:
        Secret value or None
    """
    return get_secret_provider().get_secret(key)
