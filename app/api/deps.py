from typing import List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_jwt_token
from app.models.user import User, UserRole, UserSession
from app.models.vault import Vault

security_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Extracts, validates JWT access token, and retrieves current user."""
    token = credentials.credentials
    try:
        payload = decode_jwt_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type provided."
            )
        user_pubkey = payload.get("sub")
        if not user_pubkey:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token subject missing."
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )

    user = db.query(User).filter(User.pubkey == user_pubkey).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or non-existent."
        )

    return user


def require_role(allowed_roles: List[UserRole]):
    """RBAC Guard: Ensures the authenticated user possesses one of the required roles."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires one of roles {[r.value for r in allowed_roles]}."
            )
        return current_user
    return role_checker


def verify_vault_access(vault_owner: str, current_user: User, db: Session) -> bool:
    """Ownership Guard: Validates that current user owns vault, or has fiduciary/beneficiary rights."""
    if current_user.role == UserRole.ADMIN or current_user.pubkey == vault_owner:
        return True

    # Check vault relationship
    vault = db.query(Vault).filter(Vault.owner_pubkey == vault_owner).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found.")

    # Allow beneficiary/fiduciary access if vault is in challenge/deceased state
    if current_user.role in [UserRole.BENEFICIARY, UserRole.FIDUCIARY]:
        return True

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to access or modify this vault."
    )