import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.user import User, UserRole, UserSession, AuthAuditLog
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    generate_totp_secret,
    get_totp_uri,
    verify_totp_code,
)

logger = logging.getLogger("AuthService")


class AuthService:
    @staticmethod
    def _log_auth_event(db: Session, user_pubkey: str, event: str, status: str, details: str = None, ip: str = None):
        """Writes an immutable log for security audit trails."""
        audit = AuthAuditLog(
            user_pubkey=user_pubkey,
            event=event,
            status=status,
            details=details,
            ip_address=ip
        )
        db.add(audit)
        db.commit()

    @classmethod
    def register_user(
        cls,
        db: Session,
        pubkey: str,
        email: str,
        password: str,
        role: UserRole = UserRole.OWNER
    ) -> User:
        """Registers a new account with hashed password credentials."""
        existing = db.query(User).filter((User.pubkey == pubkey) | (User.email == email)).first()
        if existing:
            raise ValueError("User with this wallet pubkey or email already exists.")

        user = User(
            pubkey=pubkey,
            email=email,
            password_hash=hash_password(password),
            role=role,
            mfa_secret=generate_totp_secret()
        )
        db.add(user)
        db.commit()

        cls._log_auth_event(db, pubkey, "REGISTER", "SUCCESS", f"Registered role: {role.value}")
        return user

    @classmethod
    def login(
        cls,
        db: Session,
        email_or_pubkey: str,
        password: str,
        ip_address: Optional[str] = None,
        device_info: Optional[str] = None
    ) -> Dict[str, Any]:
        """Authenticates user credentials and checks if MFA verification is pending."""
        user = db.query(User).filter(
            (User.email == email_or_pubkey) | (User.pubkey == email_or_pubkey)
        ).first()

        if not user or not verify_password(password, user.password_hash):
            if user:
                cls._log_auth_event(db, user.pubkey, "LOGIN", "FAILED", "Invalid password", ip_address)
            raise ValueError("Invalid login credentials.")

        # Require MFA verification if enabled
        if user.mfa_enabled:
            cls._log_auth_event(db, user.pubkey, "LOGIN_MFA_REQUIRED", "PENDING", ip=ip_address)
            return {
                "mfa_required": True,
                "user_pubkey": user.pubkey,
                "message": "TOTP MFA code required to complete login."
            }

        # Issue Full Session Tokens
        return cls._create_user_session(db, user, ip_address, device_info)

    @classmethod
    def verify_mfa_and_login(
        cls,
        db: Session,
        user_pubkey: str,
        totp_code: str,
        ip_address: Optional[str] = None,
        device_info: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validates 6-digit TOTP MFA code and issues session tokens."""
        user = db.query(User).filter(User.pubkey == user_pubkey).first()
        if not user or not user.mfa_secret:
            raise ValueError("User not found or MFA not configured.")

        if not verify_totp_code(user.mfa_secret, totp_code):
            cls._log_auth_event(db, user_pubkey, "MFA_VERIFY", "FAILED", "Incorrect TOTP code", ip_address)
            raise ValueError("Invalid TOTP verification code.")

        cls._log_auth_event(db, user_pubkey, "MFA_VERIFY", "SUCCESS", ip=ip_address)
        return cls._create_user_session(db, user, ip_address, device_info)

    @classmethod
    def _create_user_session(
        cls,
        db: Session,
        user: User,
        ip_address: Optional[str] = None,
        device_info: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates access & refresh tokens, persisting active session metadata."""
        token_data = {"sub": user.pubkey, "role": user.role.value, "email": user.email}
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"sub": user.pubkey})

        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        user_session = UserSession(
            id=session_id,
            user_pubkey=user.pubkey,
            refresh_token=refresh_token,
            device_info=device_info or "Unknown Device",
            ip_address=ip_address,
            expires_at=expires_at
        )
        db.add(user_session)
        db.commit()

        cls._log_auth_event(db, user.pubkey, "SESSION_CREATED", "SUCCESS", f"Session: {session_id}", ip_address)

        return {
            "mfa_required": False,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 3600,
            "user": {
                "pubkey": user.pubkey,
                "email": user.email,
                "role": user.role.value,
                "mfa_enabled": user.mfa_enabled
            }
        }

    @classmethod
    def refresh_access_token(cls, db: Session, refresh_token: str) -> Dict[str, str]:
        """Validates refresh token and issues a new access token."""
        try:
            payload = decode_jwt_token(refresh_token)
            if payload.get("type") != "refresh":
                raise ValueError("Invalid token type.")
            user_pubkey = payload.get("sub")
        except Exception as e:
            raise ValueError(f"Invalid refresh token: {str(e)}")

        session = db.query(UserSession).filter(
            UserSession.refresh_token == refresh_token,
            UserSession.is_revoked == False
        ).first()

        if not session:
            raise ValueError("Session expired or revoked.")

        user = db.query(User).filter(User.pubkey == user_pubkey).first()
        if not user or not user.is_active:
            raise ValueError("User account inactive.")

        token_data = {"sub": user.pubkey, "role": user.role.value, "email": user.email}
        new_access_token = create_access_token(token_data)

        cls._log_auth_event(db, user.pubkey, "TOKEN_REFRESH", "SUCCESS")
        return {"access_token": new_access_token, "token_type": "bearer", "expires_in": 3600}

    @classmethod
    def enable_mfa(cls, db: Session, user_pubkey: str, totp_code: str) -> bool:
        """Enables TOTP MFA after verifying code match."""
        user = db.query(User).filter(User.pubkey == user_pubkey).first()
        if not user or not user.mfa_secret:
            raise ValueError("User not found or secret uninitialized.")

        if not verify_totp_code(user.mfa_secret, totp_code):
            raise ValueError("Invalid verification code. Could not enable MFA.")

        user.mfa_enabled = True
        db.commit()
        cls._log_auth_event(db, user_pubkey, "MFA_ENABLED", "SUCCESS")
        return True