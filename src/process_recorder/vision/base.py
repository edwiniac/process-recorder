"""
Abstract base class for vision adapters.

All vision providers (Ollama, Claude, etc.) implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class AnalysisResult:
    """Result from analyzing a screenshot."""
    description: str  # Human-readable description of what's visible
    ui_elements: list[dict]  # Detected UI elements with descriptions
    active_window: Optional[str] = None  # Active application/window name
    raw_response: str = ""  # Full model response for debugging
    model: str = ""  # Model that produced this


@dataclass
class ElementLocation:
    """Result from finding a UI element."""
    found: bool
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0
    description: str = ""  # What the model thinks it found

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


class VisionAdapter(ABC):
    """
    Abstract interface for vision model backends.
    
    Implementations handle the specifics of communicating with
    different vision models (Ollama/LLaVA, Claude, GPT-4V, etc.)
    """

    @abstractmethod
    async def analyze_screenshot(
        self,
        image_data: bytes,
        prompt: str,
    ) -> AnalysisResult:
        """
        Analyze a screenshot and describe what's visible.
        
        Args:
            image_data: PNG image bytes.
            prompt: Analysis prompt/question.
            
        Returns:
            AnalysisResult with description and detected elements.
        """
        ...

    @abstractmethod
    async def find_element(
        self,
        image_data: bytes,
        element_description: str,
    ) -> ElementLocation:
        """
        Find a UI element in a screenshot by description.
        
        Args:
            image_data: PNG image bytes.
            element_description: Natural language description of the element.
            
        Returns:
            ElementLocation with coordinates and confidence.
        """
        ...

    @abstractmethod
    async def describe_action(
        self,
        before_image: bytes,
        after_image: bytes,
        click_x: int,
        click_y: int,
    ) -> str:
        """
        Describe what action was performed between two screenshots.
        
        Args:
            before_image: Screenshot before the action.
            after_image: Screenshot after the action.
            click_x: X coordinate of click.
            click_y: Y coordinate of click.
            
        Returns:
            Human-readable description of the action.
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the vision model is reachable and ready."""
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """Return identifier string like 'ollama:llava:13b' or 'claude:sonnet'."""
        ...
