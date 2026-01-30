"""
Semantic extractor — enriches classified actions with vision context.

Takes classified actions + screenshots and uses a vision model to:
1. Describe what UI element was interacted with
2. Provide human-readable step descriptions
3. Assign confidence scores

This is the bridge between raw events and meaningful workflow steps.
"""

import logging
from pathlib import Path
from typing import Optional

from ..models import (
    ActionType,
    BoundingBox,
    Screenshot,
    SemanticStep,
)
from ..vision.base import VisionAdapter
from .action_classifier import ClassifiedAction

logger = logging.getLogger(__name__)


class SemanticExtractor:
    """Extracts semantic meaning from classified actions using vision."""

    def __init__(self, vision: VisionAdapter):
        self._vision = vision

    async def extract_step(
        self,
        action: ClassifiedAction,
        step_id: int,
        screenshots: dict[str, Screenshot],
        screenshot_dir: Path | None = None,
    ) -> SemanticStep:
        """
        Convert a single classified action into a semantic step.
        
        Args:
            action: The classified action to process.
            step_id: Sequence number for this step.
            screenshots: Map of screenshot_id → Screenshot.
            screenshot_dir: Directory containing screenshot files.
            
        Returns:
            A SemanticStep with vision-enriched descriptions.
        """
        screenshot_id = action.screenshot_id or ""
        target_description = ""
        confidence = 0.0
        target_region: Optional[BoundingBox] = None

        # Try to get vision context if we have a screenshot
        if screenshot_id and screenshot_id in screenshots and screenshot_dir:
            screenshot = screenshots[screenshot_id]
            image_path = screenshot_dir / screenshot.filepath

            if image_path.exists():
                image_data = image_path.read_bytes()
                target_description, confidence, target_region = (
                    await self._analyze_action(action, image_data)
                )

        # Fallback: generate description from action data alone
        if not target_description:
            target_description = self._describe_from_data(action)
            confidence = 0.3  # Low confidence for non-vision descriptions

        input_data = None
        if action.action_type == ActionType.TYPE:
            input_data = action.typed_text
        elif action.action_type == ActionType.HOTKEY:
            input_data = action.hotkey_combo

        return SemanticStep(
            step_id=step_id,
            action_type=action.action_type,
            target_description=target_description,
            target_screenshot_id=screenshot_id,
            target_region=target_region,
            input_data=input_data,
            confidence=confidence,
            raw_event_ids=list(range(len(action.source_events))),
        )

    async def extract_steps(
        self,
        actions: list[ClassifiedAction],
        screenshots: dict[str, Screenshot],
        screenshot_dir: Path | None = None,
    ) -> list[SemanticStep]:
        """
        Convert a list of classified actions into semantic steps.
        
        Args:
            actions: Classified actions in chronological order.
            screenshots: Map of screenshot_id → Screenshot.
            screenshot_dir: Directory containing screenshot files.
            
        Returns:
            List of SemanticSteps.
        """
        steps: list[SemanticStep] = []

        for i, action in enumerate(actions):
            logger.info(
                "Extracting step %d/%d: %s", i + 1, len(actions), action
            )
            step = await self.extract_step(
                action, step_id=i + 1,
                screenshots=screenshots,
                screenshot_dir=screenshot_dir,
            )
            steps.append(step)

        logger.info("Extracted %d semantic steps", len(steps))
        return steps

    async def _analyze_action(
        self,
        action: ClassifiedAction,
        image_data: bytes,
    ) -> tuple[str, float, Optional[BoundingBox]]:
        """
        Use vision to analyze an action in context of its screenshot.
        
        Returns:
            (description, confidence, bounding_box)
        """
        try:
            if action.action_type == ActionType.CLICK:
                return await self._analyze_click(action, image_data)
            elif action.action_type == ActionType.TYPE:
                return await self._analyze_typing(action, image_data)
            elif action.action_type == ActionType.SCROLL:
                return self._describe_scroll(action), 0.7, None
            elif action.action_type == ActionType.HOTKEY:
                return self._describe_hotkey(action), 0.9, None
            else:
                return "", 0.0, None
        except Exception as e:
            logger.warning("Vision analysis failed for step: %s", e)
            return "", 0.0, None

    async def _analyze_click(
        self,
        action: ClassifiedAction,
        image_data: bytes,
    ) -> tuple[str, float, Optional[BoundingBox]]:
        """Analyze a click action using vision."""
        # Use lightweight click context prompt
        if hasattr(self._vision, "get_click_context"):
            context = await self._vision.get_click_context(
                image_data, action.click_x, action.click_y
            )
        else:
            # Fallback to find_element with coordinate hint
            from ..vision.prompts import CLICK_CONTEXT, format_prompt
            prompt = format_prompt(
                CLICK_CONTEXT,
                click_x=action.click_x,
                click_y=action.click_y,
            )
            result = await self._vision.analyze_screenshot(image_data, prompt)
            context = {"element": result.description, "confidence": 0.5}

        element = context.get("element", f"element at ({action.click_x}, {action.click_y})")
        element_type = context.get("element_type", "unknown")
        confidence = float(context.get("confidence", 0.5))

        description = f"Click on {element}"
        if action.button != "left":
            description = f"Right-click on {element}"

        # Create approximate bounding box around click point
        bbox = BoundingBox(
            x=max(0, action.click_x - 20),
            y=max(0, action.click_y - 10),
            width=40,
            height=20,
        )

        return description, confidence, bbox

    async def _analyze_typing(
        self,
        action: ClassifiedAction,
        image_data: bytes,
    ) -> tuple[str, float, Optional[BoundingBox]]:
        """Analyze a typing action using vision."""
        # For typing, we want to know WHAT field the text was typed into
        # Use the screenshot to identify the active input field
        result = await self._vision.analyze_screenshot(
            image_data,
            "What text input field or area is currently focused/active in this screenshot? "
            "Respond in JSON: {\"field\": \"description of the field\", \"confidence\": 0.0-1.0}",
        )

        field_desc = "text field"
        confidence = 0.5

        if result.raw_response:
            try:
                import json
                parsed = json.loads(result.raw_response) if result.raw_response.strip().startswith("{") else {}
                field_desc = parsed.get("field", field_desc)
                confidence = float(parsed.get("confidence", confidence))
            except (json.JSONDecodeError, ValueError):
                pass

        preview = action.typed_text[:50]
        if len(action.typed_text) > 50:
            preview += "..."

        description = f"Type '{preview}' into {field_desc}"
        return description, confidence, None

    @staticmethod
    def _describe_scroll(action: ClassifiedAction) -> str:
        """Generate a description for a scroll action."""
        direction = "down" if action.scroll_dy < 0 else "up"
        if action.scroll_dx != 0:
            h_dir = "right" if action.scroll_dx > 0 else "left"
            return f"Scroll {direction} and {h_dir}"
        return f"Scroll {direction}"

    @staticmethod
    def _describe_hotkey(action: ClassifiedAction) -> str:
        """Generate a description for a hotkey action."""
        combo = action.hotkey_combo
        # Map common hotkeys to friendly names
        hotkey_names = {
            "ctrl+s": "Save (Ctrl+S)",
            "ctrl+c": "Copy (Ctrl+C)",
            "ctrl+v": "Paste (Ctrl+V)",
            "ctrl+x": "Cut (Ctrl+X)",
            "ctrl+z": "Undo (Ctrl+Z)",
            "ctrl+y": "Redo (Ctrl+Y)",
            "ctrl+a": "Select All (Ctrl+A)",
            "ctrl+f": "Find (Ctrl+F)",
            "ctrl+n": "New (Ctrl+N)",
            "ctrl+o": "Open (Ctrl+O)",
            "ctrl+p": "Print (Ctrl+P)",
            "ctrl+w": "Close Tab (Ctrl+W)",
            "ctrl+t": "New Tab (Ctrl+T)",
            "alt+tab": "Switch Window (Alt+Tab)",
            "alt+f4": "Close Window (Alt+F4)",
        }
        friendly = hotkey_names.get(combo.lower(), combo)
        return f"Press {friendly}"

    @staticmethod
    def _describe_from_data(action: ClassifiedAction) -> str:
        """Fallback: describe action from raw data without vision."""
        if action.action_type == ActionType.CLICK:
            btn = action.button
            return f"{'Right-click' if btn == 'right' else 'Click'} at ({action.click_x}, {action.click_y})"
        elif action.action_type == ActionType.TYPE:
            preview = action.typed_text[:50]
            return f"Type '{preview}'"
        elif action.action_type == ActionType.SCROLL:
            return SemanticExtractor._describe_scroll(action)
        elif action.action_type == ActionType.HOTKEY:
            return SemanticExtractor._describe_hotkey(action)
        return f"Unknown action: {action.action_type.value}"
