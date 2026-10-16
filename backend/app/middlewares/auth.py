from typing import Optional, List, Callable
from fastapi import Request, Depends
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.configs.security import decode_access_token
from app.models.user import User
from app.models.business_membership import BusinessMembership
from app.helpers.exceptions import AuthenticationException, AuthorizationException


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Dependency to extract and verify JWT token from Authorization header and return active User."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise AuthenticationException(
            message="Authentication failed",
            errors={"authentication": "Missing authorization token"},
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationException(
            message="Authentication failed",
            errors={"authentication": "Invalid authorization header format. Expected 'Bearer <token>'"},
        )

    token = parts[1]
    payload = decode_access_token(token)

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationException(
            message="Authentication failed",
            errors={"authentication": "Invalid token subject"},
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise AuthenticationException(
            message="Authentication failed",
            errors={"authentication": "Invalid user ID in token"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationException(
            message="Authentication failed",
            errors={"authentication": "User not found"},
        )

    if not user.is_active:
        raise AuthenticationException(
            message="Authentication failed",
            errors={"authentication": "User account is inactive"},
        )

    return user


def require_business_membership(allowed_roles: Optional[List[str]] = None) -> Callable:
    """Dependency factory to verify that the current user belongs to the requested business with appropriate role."""
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> BusinessMembership:
        business_id_param = request.path_params.get("business_id")
        if not business_id_param:
            raise AuthorizationException(
                message="Access denied",
                errors={"authorization": "Missing business identifier in request path"},
            )

        try:
            business_id = int(business_id_param)
        except ValueError:
            raise AuthorizationException(
                message="Access denied",
                errors={"authorization": "Invalid business ID format"},
            )

        membership = db.query(BusinessMembership).filter(
            BusinessMembership.business_id == business_id,
            BusinessMembership.user_id == current_user.id,
        ).first()

        if not membership:
            raise AuthorizationException(
                message="Access denied",
                errors={"authorization": "You are not a member of this business"},
            )

        if allowed_roles and membership.role not in allowed_roles:
            raise AuthorizationException(
                message="Access denied",
                errors={"authorization": f"Role '{membership.role}' does not have sufficient permissions"},
            )

        return membership

    return dependency
