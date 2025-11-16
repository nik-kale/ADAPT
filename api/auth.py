"""
Authentication and Authorization for ADAPT API.
"""

from fastapi import Depends, HTTPException, status, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import jwt
import os
import secrets
import json
import logging

logger = logging.getLogger(__name__)


# Security schemes
security = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class Permission(str, Enum):
    """Available permissions"""
    VIEW_INCIDENTS = "view_incidents"
    RUN_RCA = "run_rca"
    MANAGE_PLAYBOOKS = "manage_playbooks"
    VIEW_METRICS = "view_metrics"
    MANAGE_USERS = "manage_users"
    ADMIN = "admin"


class Role(str, Enum):
    """Predefined roles"""
    VIEWER = "viewer"
    ANALYST = "analyst"
    ENGINEER = "engineer"
    ADMIN = "admin"


# Role to permissions mapping
ROLE_PERMISSIONS = {
    Role.VIEWER: [Permission.VIEW_INCIDENTS, Permission.VIEW_METRICS],
    Role.ANALYST: [Permission.VIEW_INCIDENTS, Permission.RUN_RCA, Permission.VIEW_METRICS],
    Role.ENGINEER: [
        Permission.VIEW_INCIDENTS,
        Permission.RUN_RCA,
        Permission.MANAGE_PLAYBOOKS,
        Permission.VIEW_METRICS,
    ],
    Role.ADMIN: [Permission.ADMIN],  # Admin has all permissions
}


class User:
    """User model"""

    def __init__(
        self,
        username: str,
        email: Optional[str] = None,
        roles: Optional[List[Role]] = None,
        tenant_id: str = "default",
    ):
        self.username = username
        self.email = email
        self.roles = roles or [Role.VIEWER]
        self.tenant_id = tenant_id

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission"""
        if Role.ADMIN in self.roles:
            return True

        for role in self.roles:
            if permission in ROLE_PERMISSIONS.get(role, []):
                return True

        return False

    def to_dict(self):
        """Convert user to dictionary"""
        return {
            "username": self.username,
            "email": self.email,
            "roles": [r.value for r in self.roles],
            "tenant_id": self.tenant_id,
        }


class AuthManager:
    """Manages authentication and authorization"""

    def __init__(self, secret_key: Optional[str] = None):
        # SECURITY: No hardcoded defaults - must be explicitly configured
        self.secret_key = secret_key or os.getenv("ADAPT_SECRET_KEY")

        if not self.secret_key:
            raise ValueError(
                "ADAPT_SECRET_KEY environment variable must be set. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        # Validate secret key strength
        if len(self.secret_key) < 32:
            raise ValueError(
                "ADAPT_SECRET_KEY must be at least 32 characters for security. "
                "Current length: {}".format(len(self.secret_key))
            )

        self.algorithm = "HS256"
        self.access_token_expire_minutes = 15  # Short-lived access tokens
        self.refresh_token_expire_days = 7

        # Refresh token storage (use Redis in production)
        self.refresh_tokens: dict = {}

        # Session storage
        self.sessions: dict = {}

        # API key store - load from environment only, no defaults
        self.api_keys = self._load_api_keys()

    def _load_api_keys(self) -> Dict[str, User]:
        """Load API keys from environment (v4.0 security enhancement)"""
        api_keys_json = os.getenv("ADAPT_API_KEYS_JSON", "{}")

        try:
            api_keys_data = json.loads(api_keys_json)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid ADAPT_API_KEYS_JSON format: {e}")
            api_keys_data = {}

        if not api_keys_data:
            logger.warning(
                "⚠️  No API keys configured. Set ADAPT_API_KEYS_JSON environment variable. "
                "API key authentication will be unavailable."
            )

        # Convert JSON to User objects
        api_keys = {}
        for key, user_data in api_keys_data.items():
            if len(key) < 32:
                logger.warning(f"API key too short (< 32 chars), skipping")
                continue

            api_keys[key] = User(
                username=user_data.get("username", "unknown"),
                email=user_data.get("email"),
                roles=[Role(r) for r in user_data.get("roles", ["viewer"])],
                tenant_id=user_data.get("tenant_id", "default"),
            )

        return api_keys

    def create_refresh_token(self, user: User) -> str:
        """Create long-lived refresh token (v4.0 enhancement)"""
        refresh_token = secrets.token_urlsafe(32)
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)

        self.refresh_tokens[refresh_token] = {
            "user": user,
            "expire": expire,
            "created_at": datetime.utcnow(),
        }

        return refresh_token

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Exchange refresh token for new access token (v4.0 enhancement)"""
        token_data = self.refresh_tokens.get(refresh_token)

        if not token_data:
            return None

        if token_data["expire"] < datetime.utcnow():
            # Token expired, remove it
            del self.refresh_tokens[refresh_token]
            return None

        # Create new access token
        return self.create_access_token(token_data["user"])

    def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a refresh token (v4.0 enhancement)"""
        if refresh_token in self.refresh_tokens:
            del self.refresh_tokens[refresh_token]
            return True
        return False

    def create_session(self, user: User, request: Request) -> str:
        """Create user session with timeout (v4.0 security enhancement)"""
        session_id = secrets.token_urlsafe(32)

        self.sessions[session_id] = {
            "user": user,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "ip_address": request.client.host if request.client else "unknown",
            "expires_at": datetime.utcnow() + timedelta(hours=8),
        }

        return session_id

    def validate_session(self, session_id: str, request: Request) -> Optional[User]:
        """Validate session and return user (v4.0 security enhancement)"""
        session = self.sessions.get(session_id)

        if not session:
            return None

        # Check expiration
        if session["expires_at"] < datetime.utcnow():
            del self.sessions[session_id]
            return None

        # Check IP hasn't changed (security measure)
        current_ip = request.client.host if request.client else "unknown"
        if session["ip_address"] != current_ip:
            logger.warning(
                f"Session IP mismatch: {session['ip_address']} != {current_ip}"
            )
            del self.sessions[session_id]
            return None

        # Update last activity
        session["last_activity"] = datetime.utcnow()

        return session["user"]

    def cleanup_expired_tokens(self):
        """Clean up expired refresh tokens and sessions (v4.0 enhancement)"""
        now = datetime.utcnow()

        # Clean refresh tokens
        expired_refresh = [
            token
            for token, data in self.refresh_tokens.items()
            if data["expire"] < now
        ]
        for token in expired_refresh:
            del self.refresh_tokens[token]

        # Clean sessions
        expired_sessions = [
            session_id
            for session_id, data in self.sessions.items()
            if data["expires_at"] < now
        ]
        for session_id in expired_sessions:
            del self.sessions[session_id]

        if expired_refresh or expired_sessions:
            logger.info(
                f"Cleaned up {len(expired_refresh)} refresh tokens and "
                f"{len(expired_sessions)} sessions"
            )

    async def start_periodic_cleanup(self, interval_seconds: int = 300):
        """Start periodic cleanup task (v4.0 enhancement)"""
        import asyncio

        while True:
            await asyncio.sleep(interval_seconds)
            self.cleanup_expired_tokens()

    def create_access_token(
        self, user: User, expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=self.access_token_expire_minutes
            )

        to_encode = {
            "sub": user.username,
            "email": user.email,
            "roles": [r.value for r in user.roles],
            "tenant_id": user.tenant_id,
            "exp": expire,
        }

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def decode_token(self, token: str) -> User:
        """Decode and verify JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            username = payload.get("sub")
            if username is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing subject",
                )

            roles = [Role(r) for r in payload.get("roles", [])]

            return User(
                username=username,
                email=payload.get("email"),
                roles=roles,
                tenant_id=payload.get("tenant_id", "default"),
            )

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )
        except jwt.JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
            )

    def verify_api_key(self, api_key: str) -> Optional[User]:
        """Verify API key and return associated user"""
        return self.api_keys.get(api_key)


# Global auth manager instance (lazy initialization for dev/test)
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get or create global auth manager instance"""
    global _auth_manager

    if _auth_manager is None:
        # For development/testing, allow initialization without secret key
        # by providing a generated one
        secret_key = os.getenv("ADAPT_SECRET_KEY")

        if not secret_key:
            environment = os.getenv("ENVIRONMENT", "development")

            if environment == "production":
                raise ValueError(
                    "ADAPT_SECRET_KEY must be set in production environment"
                )

            # Generate temporary secret for development
            logger.warning(
                "⚠️  No ADAPT_SECRET_KEY set. Generating temporary secret for development. "
                "This is INSECURE and should not be used in production!"
            )
            secret_key = secrets.token_urlsafe(32)

        _auth_manager = AuthManager(secret_key=secret_key)

    return _auth_manager


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    api_key: Optional[str] = Security(api_key_header),
) -> User:
    """
    Get current authenticated user from JWT token or API key.

    Priority: API key > JWT token
    """
    auth_mgr = get_auth_manager()

    # Try API key first
    if api_key:
        user = auth_mgr.verify_api_key(api_key)
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    # Try JWT token
    if credentials:
        token = credentials.credentials
        return auth_mgr.decode_token(token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: provide API key or bearer token",
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    api_key: Optional[str] = Security(api_key_header),
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None"""
    try:
        return await get_current_user(credentials, api_key)
    except HTTPException:
        return None


def require_permission(permission: Permission):
    """Dependency to require specific permission"""

    async def check_permission(user: User = Depends(get_current_user)) -> User:
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value} required",
            )
        return user

    return check_permission


def require_role(role: Role):
    """Dependency to require specific role"""

    async def check_role(user: User = Depends(get_current_user)) -> User:
        if role not in user.roles and Role.ADMIN not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role.value}",
            )
        return user

    return check_role


# Convenience dependencies
require_view_incidents = require_permission(Permission.VIEW_INCIDENTS)
require_run_rca = require_permission(Permission.RUN_RCA)
require_manage_playbooks = require_permission(Permission.MANAGE_PLAYBOOKS)
require_admin = require_role(Role.ADMIN)
