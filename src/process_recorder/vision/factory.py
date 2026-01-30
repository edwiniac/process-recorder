"""
Vision adapter factory.

Creates the appropriate vision adapter based on configuration.
Handles fallback logic when preferred provider is unavailable.
"""

import logging

from ..models import AppConfig
from .base import VisionAdapter
from .claude_adapter import ClaudeAdapter
from .ollama_adapter import OllamaAdapter

logger = logging.getLogger(__name__)


def create_vision_adapter(config: AppConfig | None = None) -> VisionAdapter:
    """
    Create a vision adapter from configuration.
    
    Args:
        config: Application configuration. Uses defaults if None.
        
    Returns:
        Configured VisionAdapter instance.
        
    Raises:
        ValueError: If provider is unknown.
    """
    if config is None:
        config = AppConfig()

    vision_config = config.vision
    provider = vision_config.provider.lower()

    if provider == "ollama":
        return OllamaAdapter(
            model=vision_config.ollama_model,
            base_url=vision_config.ollama_base_url,
        )
    elif provider == "claude":
        return ClaudeAdapter(
            api_key=vision_config.claude_api_key,
            model=vision_config.claude_model,
        )
    else:
        raise ValueError(
            f"Unknown vision provider: '{provider}'. "
            "Supported: 'ollama', 'claude'"
        )


async def create_vision_adapter_with_fallback(
    config: AppConfig | None = None,
) -> VisionAdapter:
    """
    Create a vision adapter, falling back if the primary is unavailable.
    
    Tries the configured provider first. If unavailable, tries the other.
    
    Args:
        config: Application configuration.
        
    Returns:
        An available VisionAdapter, or the primary if neither responds.
    """
    if config is None:
        config = AppConfig()

    primary = create_vision_adapter(config)

    if await primary.is_available():
        logger.info("Using primary vision provider: %s", primary.get_model_name())
        return primary

    logger.warning(
        "Primary vision provider '%s' unavailable, trying fallback...",
        primary.get_model_name(),
    )

    # Try the other provider
    fallback_provider = "claude" if config.vision.provider == "ollama" else "ollama"
    fallback_config = config.model_copy(deep=True)
    fallback_config.vision.provider = fallback_provider

    try:
        fallback = create_vision_adapter(fallback_config)
        if await fallback.is_available():
            logger.info("Using fallback vision provider: %s", fallback.get_model_name())
            return fallback
    except Exception as e:
        logger.warning("Fallback provider also failed: %s", e)

    # Return primary anyway — caller can handle errors
    logger.warning("No vision provider available. Returning primary (will fail on use).")
    return primary
