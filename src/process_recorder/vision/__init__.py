"""
Vision module — abstract vision model integration.

Provides adapters for Ollama (LLaVA) and Claude (Anthropic)
with a common interface for screenshot analysis and element finding.
"""

from .base import AnalysisResult, ElementLocation, VisionAdapter
from .claude_adapter import ClaudeAdapter
from .factory import create_vision_adapter, create_vision_adapter_with_fallback
from .ollama_adapter import OllamaAdapter
from .prompts import format_prompt

__all__ = [
    "VisionAdapter",
    "AnalysisResult",
    "ElementLocation",
    "OllamaAdapter",
    "ClaudeAdapter",
    "create_vision_adapter",
    "create_vision_adapter_with_fallback",
    "format_prompt",
]
