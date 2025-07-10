"""Configuration settings using Pydantic with environment variables."""
import os
from pathlib import Path
from typing import Tuple

from pydantic import BaseSettings, Field, validator

# Load environment variables from .env file
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    """Application settings with environment variable loading and validation."""
    
    # Required settings
    TICKETMASTER_URL: str = Field(
        ...,
        env="TICKETMASTER_URL",
        description="URL of the Ticketmaster event page to monitor"
    )
    NTFY_TOPIC: str = Field(
        ...,
        env="NTFY_TOPIC",
        description="ntfy.sh topic for notifications"
    )
    
    # Optional settings with defaults
    HEADLESS: bool = Field(
        False,
        env="HEADLESS",
        description="Run browser in headless mode"
    )
    CHECK_INTERVAL_MIN: Tuple[float, float] = Field(
        (8.0, 12.0),
        env="CHECK_INTERVAL_MIN",
        description="Random interval range in minutes between checks"
    )
    BROWSER_TIMEOUT: int = Field(
        360,
        env="BROWSER_TIMEOUT",
        description="Time in seconds to keep browser open when tickets are found"
    )
    MAX_RETRIES: int = Field(
        3,
        env="MAX_RETRIES",
        description="Maximum number of retries for failed operations"
    )
    RETRY_DELAY: int = Field(
        5,
        env="RETRY_DELAY",
        description="Initial delay between retries in seconds"
    )
    LOG_LEVEL: str = Field(
        "INFO",
        env="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    @validator('TICKETMASTER_URL')
    def validate_ticketmaster_url(cls, v):
        """Validate Ticketmaster URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('TICKETMASTER_URL must start with http:// or https://')
        if 'ticketmaster.' not in v:
            raise ValueError('TICKETMASTER_URL must be a valid Ticketmaster URL')
        return v

    @validator('CHECK_INTERVAL_MIN', pre=True)
    def parse_check_interval(cls, v):
        """Parse CHECK_INTERVAL_MIN from string to tuple."""
        if isinstance(v, str):
            try:
                min_val, max_val = map(float, v.split(','))
                return (min_val, max_val)
            except (ValueError, AttributeError) as e:
                raise ValueError('CHECK_INTERVAL_MIN must be in format "min,max" (e.g., "8.0,12.0")') from e
        return v

    @validator('LOG_LEVEL')
    def validate_log_level(cls, v):
        """Validate LOG_LEVEL is a valid logging level."""
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if v.upper() not in valid_levels:
            raise ValueError(f'LOG_LEVEL must be one of {valid_levels}')
        return v.upper()

    class Config:
        """Pydantic config."""
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = True

# Create settings instance
settings = Settings()

# For backward compatibility
TICKETMASTER_URL = settings.TICKETMASTER_URL
NTFY_TOPIC = settings.NTFY_TOPIC
HEADLESS = settings.HEADLESS
CHECK_INTERVAL_MIN = settings.CHECK_INTERVAL_MIN
BROWSER_TIMEOUT = settings.BROWSER_TIMEOUT
MAX_RETRIES = settings.MAX_RETRIES
RETRY_DELAY = settings.RETRY_DELAY
LOG_LEVEL = settings.LOG_LEVEL
