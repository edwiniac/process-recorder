"""
Configuration loading and management for ProcessRecorder.
"""

import os
from pathlib import Path
from typing import Optional

import yaml

from .models import AppConfig


DEFAULT_CONFIG_FILENAME = "config.yaml"


def find_config_file() -> Optional[Path]:
    """Find the config file in standard locations."""
    search_paths = [
        Path.cwd() / DEFAULT_CONFIG_FILENAME,  # Current directory
        Path.home() / ".config" / "process-recorder" / DEFAULT_CONFIG_FILENAME,
        Path(__file__).parent.parent.parent.parent / DEFAULT_CONFIG_FILENAME,  # Project root
    ]
    
    for path in search_paths:
        if path.exists():
            return path
    
    return None


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """
    Load configuration from file.
    
    Args:
        config_path: Optional explicit path to config file.
        
    Returns:
        AppConfig instance with loaded values.
    """
    if config_path is None:
        config_path = find_config_file()
    
    if config_path is None or not config_path.exists():
        # Return defaults
        return AppConfig()
    
    with open(config_path, "r") as f:
        raw_config = yaml.safe_load(f) or {}
    
    # Handle environment variable substitution for API key
    if "vision" in raw_config:
        vision = raw_config["vision"]
        if vision.get("claude_api_key") is None:
            vision["claude_api_key"] = os.environ.get("ANTHROPIC_API_KEY")
    
    # Build config with proper nesting
    config_data = {}
    
    if "vision" in raw_config:
        config_data["vision"] = AppConfig.VisionConfig(**raw_config["vision"])
    if "recording" in raw_config:
        config_data["recording"] = AppConfig.RecordingConfig(**raw_config["recording"])
    if "replay" in raw_config:
        config_data["replay"] = AppConfig.ReplayConfig(**raw_config["replay"])
    if "storage" in raw_config:
        config_data["storage"] = AppConfig.StorageConfig(**raw_config["storage"])
    
    return AppConfig(**config_data)


def save_config(config: AppConfig, config_path: Path) -> None:
    """
    Save configuration to file.
    
    Args:
        config: AppConfig instance to save.
        config_path: Path to write config file.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    raw_config = {
        "vision": {
            "provider": config.vision.provider,
            "ollama_model": config.vision.ollama_model,
            "ollama_base_url": config.vision.ollama_base_url,
            "claude_api_key": config.vision.claude_api_key,
            "claude_model": config.vision.claude_model,
        },
        "recording": {
            "screenshot_interval_ms": config.recording.screenshot_interval_ms,
            "capture_on_click": config.recording.capture_on_click,
            "max_screenshots": config.recording.max_screenshots,
        },
        "replay": {
            "action_delay_ms": config.replay.action_delay_ms,
            "element_find_timeout_ms": config.replay.element_find_timeout_ms,
            "confidence_threshold": config.replay.confidence_threshold,
        },
        "storage": {
            "recordings_dir": config.storage.recordings_dir,
            "workflows_dir": config.storage.workflows_dir,
        },
    }
    
    with open(config_path, "w") as f:
        yaml.safe_dump(raw_config, f, default_flow_style=False, sort_keys=False)


# Global config instance (loaded lazily)
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get the global config instance (loads if needed)."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config(config_path: Optional[Path] = None) -> AppConfig:
    """Reload configuration from file."""
    global _config
    _config = load_config(config_path)
    return _config
