"""
Authentication and Authorization for ADAPT API.
"""

from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from typing import Optional, List
from datetime import datetime, timedelta
from enum import Enum
import jwt
import os


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
        self.secret_key = secret_key or os.getenv(
            "ADAPT_SECRET_KEY", "your-secret-key-change-in-production"
        )
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60

        # Simple in-memory API key store (replace with database in production)
        self.api_keys = {
            os.getenv("ADAPT_API_KEY", "demo-api-key"): User(
                username="api_user",
                roles=[Role.ANALYST],
                tenant_id="default",
            )
        }

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


# Global auth manager instance
auth_manager = AuthManager()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    api_key: Optional[str] = Security(api_key_header),
) -> User:
    """
    Get current authenticated user from JWT token or API key.

    Priority: API key > JWT token
    """
    # Try API key first
    if api_key:
        user = auth_manager.verify_api_key(api_key)
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    # Try JWT token
    if credentials:
        token = credentials.credentials
        return auth_manager.decode_token(token)

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
