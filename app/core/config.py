import json
import logging
import os
from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# --- External Secrets Manager Loader ---

def fetch_aws_secrets(secret_name: str, region_name: str = "us-east-1") -> dict:
    """Fetches key-value secret pairs from AWS Secrets Manager if configured."""
    try:
        import boto3
        from botocore.exceptions import ClientError

        client = boto3.client("secretsmanager", region_name=region_name)
        response = client.get_secret_value(SecretId=secret_name)
        if "SecretString" in response:
            return json.loads(response["SecretString"])
    except Exception as e:
        logger.warning(f"Failed to fetch secrets from AWS Secrets Manager ({secret_name}): {e}")
    return {}


# --- Main Application Settings ---

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # --- 1. Environment & General ---
    ENVIRONMENT: str = Field("dev", description="Runtime environment: dev, staging, prod, test")
    DEBUG: bool = Field(True, description="Toggle debug mode")
    PROJECT_NAME: str = Field("Terminus Protocol Engine", description="Application Title")
    API_V1_STR: str = Field("/api/v1", description="API Route Prefix")

    # --- 2. Database & Connection Pooling ---
    DATABASE_URL: str = Field("sqlite:///./app.db", description="Database connection URI")
    DB_POOL_SIZE: int = Field(20, description="SQLAlchemy connection pool size")
    DB_MAX_OVERFLOW: int = Field(10, description="Max overflow connections allowed")
    DB_POOL_RECYCLE: int = Field(3600, description="Recycle connections after N seconds")
    DB_POOL_TIMEOUT: int = Field(30, description="Connection pool timeout in seconds")

    # --- 3. Security & Cryptography ---
    JWT_SECRET: str = Field("CHANGE_THIS_IN_PRODUCTION_SECRET_KEY_12345", description="JWT signing secret")
    JWT_ALGORITHM: str = Field("HS256", description="JWT encryption algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, description="JWT token TTL in minutes")
    WALLET_ENCRYPTION_KEY: Optional[str] = Field(None, description="Fernet key for custodial wallet encryption")

    # --- 4. Solana RPC & Blockchain Defaults ---
    SOLANA_RPC_URL: str = Field("https://api.devnet.solana.com", description="Primary Solana RPC endpoint")
    SOLANA_RPC_FALLBACKS: Union[List[str], str] = Field(
        default=["https://solana-api.projectserum.com", "https://rpc.ankr.com/solana"],
        description="Fallback RPC nodes"
    )
    CHALLENGE_TIMEOUT_SECONDS: int = Field(300, description="Dead-man switch challenge timeout window")

    # --- 5. Feature Flags ---
    FEATURE_ENABLE_SOLANA_WS: bool = Field(True, description="Enable WebSocket listener for Solana events")
    FEATURE_ENABLE_CRON_SCHEDULER: bool = Field(True, description="Enable background cron task scheduler")
    FEATURE_ENABLE_OCR: bool = Field(True, description="Enable OCR document verification module")
    FEATURE_ENABLE_DUAL_SIGN: bool = Field(True, description="Enable dual-signature approval workflows")

    # --- 6. Logging Settings ---
    LOG_LEVEL: str = Field("INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    LOG_FORMAT: str = Field("json", description="Log output format: json or text")

    # --- 7. Cloud Secrets Manager Integration ---
    USE_AWS_SECRETS: bool = Field(False, description="Fetch secrets from AWS Secrets Manager at launch")
    AWS_SECRET_NAME: Optional[str] = Field(None, description="AWS Secrets Manager Secret ID")
    AWS_REGION_NAME: str = Field("us-east-1", description="AWS Region for Secrets Manager")

    @field_validator("SOLANA_RPC_FALLBACKS", mode="before")
    @classmethod
    def parse_rpc_fallbacks(cls, v):
        if isinstance(v, str):
            return [endpoint.strip() for endpoint in v.split(",") if endpoint.strip()]
        return v

    def model_post_init(self, __context):
        """Overrides settings with AWS Secrets Manager if enabled."""
        if self.USE_AWS_SECRETS and self.AWS_SECRET_NAME:
            secrets = fetch_aws_secrets(self.AWS_SECRET_NAME, self.AWS_REGION_NAME)
            for key, val in secrets.items():
                if hasattr(self, key):
                    setattr(self, key, val)


settings = Settings()
