"""
Ollama/LLaVA vision adapter.

Communicates with a local Ollama instance running a multimodal
model (LLaVA, BakLLaVA, etc.) for screenshot analysis.
"""

import base64
import json
import logging
from typing import Any

import httpx

from .base import AnalysisResult, ElementLocation, VisionAdapter
from .prompts import (
    ANALYZE_SCREENSHOT,
    CLICK_CONTEXT,
    DESCRIBE_ACTION,
    FIND_ELEMENT,
    format_prompt,
)

logger = logging.getLogger(__name__)


class OllamaAdapter(VisionAdapter):
    """Vision adapter using Ollama with a multimodal model (e.g., LLaVA)."""

    def __init__(
        self,
        model: str = "llava:13b",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def _generate(
        self,
        prompt: str,
        images: list[bytes] | None = None,
    ) -> str:
        """Send a generate request to Ollama."""
        client = await self._get_client()

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temp for structured output
                "num_predict": 1024,
            },
        }

        if images:
            payload["images"] = [
                base64.b64encode(img).decode("utf-8") for img in images
            ]

        response = await client.post("/api/generate", json=payload)
        response.raise_for_status()

        result = response.json()
        return result.get("response", "")

    def _parse_json_response(self, text: str) -> dict:
        """Extract JSON from model response, handling markdown fences."""
        text = text.strip()

        # Try to find JSON block in markdown fences
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()

        # Find first { and last }
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            text = text[brace_start : brace_end + 1]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from response: %s", text[:200])
            return {}

    async def analyze_screenshot(
        self,
        image_data: bytes,
        prompt: str | None = None,
    ) -> AnalysisResult:
        """Analyze a screenshot using Ollama."""
        prompt = prompt or ANALYZE_SCREENSHOT
        raw_response = await self._generate(prompt, images=[image_data])
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
        """Find a UI element in a screenshot."""
        prompt = format_prompt(
            FIND_ELEMENT, element_description=element_description
        )
        raw_response = await self._generate(prompt, images=[image_data])
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
        """Describe an action between two screenshots."""
        prompt = format_prompt(
            DESCRIBE_ACTION, click_x=click_x, click_y=click_y
        )
        # Ollama supports multiple images
        raw_response = await self._generate(
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
        """Get context about what's at a click position (lightweight)."""
        prompt = format_prompt(
            CLICK_CONTEXT, click_x=click_x, click_y=click_y
        )
        raw_response = await self._generate(prompt, images=[image_data])
        return self._parse_json_response(raw_response)

    async def is_available(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            response.raise_for_status()

            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]

            # Check if our model (or a matching variant) is available
            for m in models:
                if self.model in m or m in self.model:
                    return True

            logger.warning(
                "Ollama running but model '%s' not found. Available: %s",
                self.model,
                models,
            )
            return False

        except (httpx.HTTPError, ConnectionError):
            return False

    def get_model_name(self) -> str:
        return f"ollama:{self.model}"

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
