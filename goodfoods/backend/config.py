"""
Configuration management for GoodFoods reservation system.
Handles environment variables, API keys, and system configuration.
"""

import os
from typing import Optional

# Load .env file FIRST before any class definitions
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use environment variables only


class Config:
    """Application configuration."""

    # Database configuration
    DB_PATH: str = os.getenv("DB_PATH", "goodfoods.db")

    # OpenAI API configuration - use classmethod to always read fresh
    @classmethod
    def get_openai_api_key(cls) -> Optional[str]:
        """Get OpenAI API key from environment."""
        return os.getenv("OPENAI_API_KEY")

    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # LLM configuration
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    TIMEOUT: int = int(os.getenv("TIMEOUT", "30"))

    # Agent configuration
    ENABLE_CONTEXT_MANAGEMENT: bool = (
        os.getenv("ENABLE_CONTEXT_MANAGEMENT", "true").lower() == "true"
    )

    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is present."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print(
                "[WARNING] OPENAI_API_KEY not set. Set it as an environment variable or in .env file"
            )
            return False
        return True

    @classmethod
    def get_openai_api_key_safe(cls) -> str:
        """Get OpenAI API key, raising error if not set."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Please set it as an environment variable:\n"
                "  export OPENAI_API_KEY=your_key_here\n"
                "Or create a .env file with: OPENAI_API_KEY=your_key_here"
            )
        return api_key
