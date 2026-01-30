"""
Claude (Anthropic) vision adapter.

Uses the Anthropic API with Claude's vision capabilities
for high-accuracy screenshot analysis.
"""

import base64
import json
import logging
from typing import Any

import anthropic

from .base import AnalysisResult, ElementLocation, VisionAdapter
from .prompts import (
    ANALYZE_SCREENSHOT,
    CLICK_CONTEXT,
    DESCRIBE_ACTION,
    FIND_ELEMENT,
    format_prompt,
)

logger = logging.getLogger(__name__)


class ClaudeAdapter(VisionAdapter):
    """Vision adapter using Anthropic's Claude API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 1024,
    ):
        self.model = model
        self.max_tokens = max_tokens
        # anthropic.Anthropic reads ANTHROPIC_API_KEY env var automatically
        self._client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else anthropic.AsyncAnthropic()

    def _make_image_block(self, image_data: bytes) -> dict[str, Any]:
        """Create a Claude image content block from raw bytes."""
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(image_data).decode("utf-8"),
            },
        }

    async def _send_message(
        self,
        text_prompt: str,
        images: list[bytes] | None = None,
    ) -> str:
        """Send a message to Claude and return the text response."""
        content: list[dict[str, Any]] = []

        # Add images first, then text
        if images:
            for img in images:
                content.append(self._make_image_block(img))

        content.append({"type": "text", "text": text_prompt})

        response = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": content}],
            temperature=0.1,  # Low for structured output
        )

        # Extract text from response
        text_parts = [
            block.text for block in response.content if block.type == "text"
        ]
        return "\n".join(text_parts)

    def _parse_json_response(self, text: str) -> dict:
        """Extract JSON from model response."""
        text = text.strip()

        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()

        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            text = text[brace_start : brace_end + 1]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from Claude response: %s", text[:200])
            return {}

    async def analyze_screenshot(
        self,
        image_data: bytes,
        prompt: str | None = None,
    ) -> AnalysisResult:
        """Analyze a screenshot using Claude."""
        prompt = prompt or ANALYZE_SCREENSHOT
        raw_response = await self._send_message(prompt, images=[image_data])
        parsed = self._parse_json_response(raw_response)

        return AnalysisResult(
            description=parsed.get("description", raw_response),
            ui_elements=parsed.get("ui_elements", []),
            active_window=parsed.get("active_window"),
            raw_response=raw_response,
            model=self.get_model_name(),
        )

    async def find_element(
        self,
        image_data: bytes,
        element_description: str,
    ) -> ElementLocation:
        """Find a UI element in a screenshot using Claude."""
        prompt = format_prompt(
            FIND_ELEMENT, element_description=element_description
        )
        raw_response = await self._send_message(prompt, images=[image_data])
        parsed = self._parse_json_response(raw_response)

        if not parsed or not parsed.get("found", False):
            return ElementLocation(
                found=False,
                confidence=0.0,
                description=parsed.get("description", "Element not found"),
            )

        return ElementLocation(
            found=True,
            x=int(parsed.get("x", 0)),
            y=int(parsed.get("y", 0)),
            width=int(parsed.get("width", 0)),
            height=int(parsed.get("height", 0)),
            confidence=float(parsed.get("confidence", 0.0)),
            description=parsed.get("description", ""),
        )

    async def describe_action(
        self,
        before_image: bytes,
        after_image: bytes,
        click_x: int,
        click_y: int,
    ) -> str:
        """Describe an action between two screenshots using Claude."""
        prompt = format_prompt(
            DESCRIBE_ACTION, click_x=click_x, click_y=click_y
        )
        # Claude handles multiple images naturally
        raw_response = await self._send_message(
            prompt, images=[before_image, after_image]
        )
        parsed = self._parse_json_response(raw_response)
        return parsed.get("action_summary", raw_response)

    async def get_click_context(
        self,
        image_data: bytes,
        click_x: int,
        click_y: int,
    ) -> dict:
        """Get context about what's at a click position."""
        prompt = format_prompt(
            CLICK_CONTEXT, click_x=click_x, click_y=click_y
        )
        raw_response = await self._send_message(prompt, images=[image_data])
        return self._parse_json_response(raw_response)

    async def is_available(self) -> bool:
        """Check if Claude API is reachable."""
        try:
            # Light check: list models (doesn't consume tokens)
            await self._client.models.list(limit=1)
            return True
        except Exception as e:
            logger.warning("Claude API not available: %s", e)
            return False

    def get_model_name(self) -> str:
        return f"claude:{self.model}"

    async def close(self) -> None:
        """Close the async client."""
        if self._client:
            await self._client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
