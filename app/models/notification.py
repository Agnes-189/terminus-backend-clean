import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Enum, Text, Boolean, ForeignKey
from app.core.database import Base


class NotificationChannel(str, enum.Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"


class DeliveryStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    QUEUED_QUIET_HOURS = "QUEUED_QUIET_HOURS"


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_pubkey = Column(String, primary_key=True, index=True)
    email = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    push_token = Column(String, nullable=True)

    # Multi-Channel Opt-In/Opt-Out
    email_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=True)
    push_enabled = Column(Boolean, default=True)

    # Localization & Quiet Hours (Avoid nighttime disturbance)
    preferred_language = Column(String, default="en")  # 'en', 'sw', 'es', etc.
    quiet_hours_start_hour = Column(Integer, default=22)  # 10 PM
    quiet_hours_end_hour = Column(Integer, default=7)     # 7 AM
    user_timezone = Column(String, default="UTC")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(String, primary_key=True, index=True)
    user_pubkey = Column(String, nullable=False, index=True)
    channel = Column(Enum(NotificationChannel), nullable=False)
    template_name = Column(String, nullable=False)
    recipient = Column(String, nullable=False)
    
    status = Column(Enum(DeliveryStatus), default=DeliveryStatus.PENDING, nullable=False)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text, nullable=True)
    
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))