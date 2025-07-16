"""Configuration management for the AI Sales Evaluation Arena."""

import os
from typing import Optional
from dotenv import load_dotenv

from .models import ArenaConfig


def load_config_from_env() -> ArenaConfig:
    """Load configuration from environment variables."""
    # Try to load .env file if it exists
    load_dotenv()
    
    return ArenaConfig(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
        max_concurrent_matches=int(os.getenv("MAX_CONCURRENT_MATCHES", "3")),
        grading_timeout_seconds=int(os.getenv("GRADING_TIMEOUT_SECONDS", "60"))
    )


def get_config() -> ArenaConfig:
    """Get configuration, with environment variables as the preferred source."""
    config = load_config_from_env()
    
    if not config.anthropic_api_key:
        raise ValueError(
            "Anthropic API key not found. Please set ANTHROPIC_API_KEY environment variable "
            "or add it to your .env file."
        )
    
    return config 