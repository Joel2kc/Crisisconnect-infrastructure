import os
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from core.session_dependency import sessionDep
from db.models.user_model import User
from enums.user import UserRole

security_scheme = HTTPBearer()
optional_security_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


def get_secret_key() -> str:
    secret_key = os.getenv("AUTH_SECRET")
    if not secret_key:
        raise HTTPException(status_code=500, detail="AUTH_SECRET is not configured")
    return secret_key

def _decode_user(session, token: str) -> User:
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
 
    if payload.get("type") == "refresh":
        raise HTTPException(status_code=401, detail="Refresh tokens cannot be used for authentication")
 
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
 
    try:
        user = session.get(User, int(user_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
 
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
 
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
 
    return user



def get_current_user(
    session: sessionDep,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> User:
    """
    Decodes the bearer token from the Authorization header and resolves
    the corresponding User.
    """
    token = credentials.credentials
    return _decode_user(session, token)


def get_current_user_optional(
    session: sessionDep,
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security_scheme),
) -> User | None:
    """
    For endpoints that allow both anonymous and logged-in access (e.g.
    incident reporting) - returns None instead of raising when no token
    is supplied, but still enforces the token as valid if one is given.
    """
    if credentials is None:
        return None
    
    token = credentials.credentials
    return _decode_user(session, token)


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]


def require_role(*allowed_roles: UserRole):
    """
    Restricts a route to one or more roles.

    Usage:
        admin: Annotated[User, Depends(require_role(UserRole.crisis_connect_admin))]
    """

    def role_checker(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return current_user

    return role_checker
