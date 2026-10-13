import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Enum, Text, Boolean, ForeignKey
from app.core.database import Base


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    BENEFICIARY = "BENEFICIARY"
    FIDUCIARY = "FIDUCIARY"
    ADMIN = "ADMIN"


class OwnerStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    WARNING = "WARNING"
    INACTIVE = "INACTIVE"
    CHALLENGED = "CHALLENGED"
    SETTLED = "SETTLED"


class User(Base):
    __tablename__ = "users"

    pubkey = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.OWNER, nullable=False)
    status = Column(Enum(OwnerStatus), default=OwnerStatus.ACTIVE, nullable=False)

    # Multi-Factor Authentication (MFA)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String, nullable=True)
    recovery_code_hash = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True, index=True)  # Session UUID
    user_pubkey = Column(String, ForeignKey("users.pubkey"), nullable=False, index=True)
    refresh_token = Column(String, unique=True, nullable=False)
    
    device_info = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    is_revoked = Column(Boolean, default=False)
    
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuthAuditLog(Base):
    __tablename__ = "auth_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_pubkey = Column(String, nullable=False, index=True)
    event = Column(String, nullable=False)  # LOGIN, LOGOUT, MFA_VERIFY, REFRESH, ACCESS_DENIED
    status = Column(String, nullable=False)  # SUCCESS / FAILED
    ip_address = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))