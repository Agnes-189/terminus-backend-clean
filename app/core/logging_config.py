import logging
import sys
from app.core.config import settings


def setup_logging():
    """Initializes global application logging configuration based on settings."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    if settings.LOG_FORMAT == "json":
        log_format = (
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": "%(message)s"}'
        )
    else:
        log_format = "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Suppress verbose third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logger = logging.getLogger("terminus")
    logger.info(f"Logging initialized. Level: {settings.LOG_LEVEL} | Environment: {settings.ENVIRONMENT}")
