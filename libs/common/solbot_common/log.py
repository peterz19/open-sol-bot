import sys
from pathlib import Path

from loguru import logger

from solbot_common.config import settings

__all__ = ["logger"]

LOG_LEVEL = settings.log.level.upper()
logger.configure(handlers=[{"sink": sys.stderr, "level": LOG_LEVEL}])

# Remove default handler
logger.remove()

# Add console handler with custom format
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=LOG_LEVEL,
    enqueue=True,
)
# Determine service name from the running module
service_name = "common"
for path in sys.path:
    if "tg_bot" in path:
        service_name = "tg-bot"
        break
    elif "trading" in path:
        service_name = "trading"
        break
    elif "wallet_tracker" in path:
        service_name = "wallet-tracker"
        break
    elif "cache_preloader" in path:
        service_name = "cache-preloader"
        break

# Create service-specific log directory
log_path = Path(__file__).parent.parent.parent / "logs" / service_name
log_path.mkdir(parents=True, exist_ok=True)

# Add file handler for errors
# log_path = Path(__file__).parent.parent.parent / "logs"
log_path.mkdir(exist_ok=True)
logger.add(
    log_path / "info.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="1 day",
    retention="7 days",
    enqueue=True,
)
logger.add(
    log_path / "error.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR",
    rotation="1 day",
    retention="7 days",
    enqueue=True,
)
