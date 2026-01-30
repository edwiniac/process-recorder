"""
Tests for vision adapter module.

Tests the base interface, factory, adapters (mocked), and prompts.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from process_recorder.models import AppConfig
from process_recorder.vision.base import AnalysisResult, ElementLocation, VisionAdapter
from process_recorder.vision.claude_adapter import ClaudeAdapter
from process_recorder.vision.factory import create_vision_adapter, create_vision_adapter_with_fallback
from process_recorder.vision.ollama_adapter import OllamaAdapter
from process_recorder.vision.prompts import (
    ANALYZE_SCREENSHOT,
    CLICK_CONTEXT,
    DESCRIBE_ACTION,
    FIND_ELEMENT,
    format_prompt,
)


# ── Fixtures ──────────────────────────────────────────────────────────

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # Minimal PNG-ish bytes


@pytest.fixture
def ollama_config():
    return AppConfig(
        vision=AppConfig.VisionConfig(
            provider="ollama",
            ollama_model="llava:7b",
            ollama_base_url="http://localhost:11434",
        )
    )


@pytest.fixture
def claude_config():
    return AppConfig(
        vision=AppConfig.VisionConfig(
            provider="claude",
            claude_api_key="test-key-123",
            claude_model="claude-3-5-sonnet-20241022",
        )
    )


# ── AnalysisResult Tests ─────────────────────────────────────────────

class TestAnalysisResult:
    def test_create_basic(self):
        result = AnalysisResult(
            description="A text editor window",
            ui_elements=[{"type": "button", "label": "Save"}],
            active_window="Notepad",
        )
        assert result.description == "A text editor window"
        assert len(result.ui_elements) == 1
        assert result.active_window == "Notepad"

    def test_defaults(self):
        result = AnalysisResult(description="test", ui_elements=[])
        assert result.active_window is None
        assert result.raw_response == ""
        assert result.model == ""


class TestElementLocation:
    def test_found_element(self):
        loc = ElementLocation(
            found=True, x=100, y=200, width=80, height=30,
            confidence=0.95, description="Save button",
        )
        assert loc.found is True
        assert loc.center == (140, 215)
        assert loc.confidence == 0.95

    def test_not_found(self):
        loc = ElementLocation(found=False)
        assert loc.found is False
        assert loc.center == (0, 0)
        assert loc.confidence == 0.0


# ── Prompt Tests ──────────────────────────────────────────────────────

class TestPrompts:
    def test_analyze_prompt_exists(self):
        assert "JSON" in ANALYZE_SCREENSHOT
        assert "ui_elements" in ANALYZE_SCREENSHOT

    def test_find_element_format(self):
        prompt = format_prompt(FIND_ELEMENT, element_description="Save button")
        assert "Save button" in prompt
        assert "found" in prompt

    def test_click_context_format(self):
        prompt = format_prompt(CLICK_CONTEXT, click_x=100, click_y=200)
        assert "100" in prompt
        assert "200" in prompt

    def test_describe_action_format(self):
        prompt = format_prompt(DESCRIBE_ACTION, click_x=50, click_y=75)
        assert "50" in prompt
        assert "75" in prompt


# ── Factory Tests ─────────────────────────────────────────────────────

class TestFactory:
    def test_create_ollama_adapter(self, ollama_config):
        adapter = create_vision_adapter(ollama_config)
        assert isinstance(adapter, OllamaAdapter)
        assert adapter.model == "llava:7b"

    def test_create_claude_adapter(self, claude_config):
        adapter = create_vision_adapter(claude_config)
        assert isinstance(adapter, ClaudeAdapter)

    def test_create_default_adapter(self):
        adapter = create_vision_adapter()
        assert isinstance(adapter, OllamaAdapter)  # Default is ollama

    def test_unknown_provider_raises(self):
        config = AppConfig(
            vision=AppConfig.VisionConfig(provider="gpt4v")
        )
        with pytest.raises(ValueError, match="Unknown vision provider"):
            create_vision_adapter(config)

    @pytest.mark.asyncio
    async def test_fallback_when_primary_unavailable(self, ollama_config):
        with patch.object(OllamaAdapter, "is_available", new_callable=AsyncMock, return_value=False), \
             patch.object(ClaudeAdapter, "is_available", new_callable=AsyncMock, return_value=True):
            adapter = await create_vision_adapter_with_fallback(ollama_config)
            assert isinstance(adapter, ClaudeAdapter)

    @pytest.mark.asyncio
    async def test_primary_used_when_available(self, ollama_config):
        with patch.object(OllamaAdapter, "is_available", new_callable=AsyncMock, return_value=True):
            adapter = await create_vision_adapter_with_fallback(ollama_config)
            assert isinstance(adapter, OllamaAdapter)

    @pytest.mark.asyncio
    async def test_fallback_returns_primary_when_both_unavailable(self, ollama_config):
        with patch.object(OllamaAdapter, "is_available", new_callable=AsyncMock, return_value=False), \
             patch.object(ClaudeAdapter, "is_available", new_callable=AsyncMock, return_value=False):
            adapter = await create_vision_adapter_with_fallback(ollama_config)
            # Returns primary as last resort
            assert isinstance(adapter, OllamaAdapter)


# ── OllamaAdapter Tests (mocked HTTP) ────────────────────────────────

class TestOllamaAdapter:
    @pytest.fixture
    def adapter(self):
        return OllamaAdapter(model="llava:7b", base_url="http://localhost:11434")

    def test_model_name(self, adapter):
        assert adapter.get_model_name() == "ollama:llava:7b"

    def test_parse_json_clean(self, adapter):
        text = '{"description": "A window", "ui_elements": []}'
        result = adapter._parse_json_response(text)
        assert result["description"] == "A window"

    def test_parse_json_with_markdown(self, adapter):
        text = 'Here is the analysis:\n```json\n{"found": true, "x": 10}\n```'
        result = adapter._parse_json_response(text)
        assert result["found"] is True
        assert result["x"] == 10

    def test_parse_json_with_surrounding_text(self, adapter):
        text = 'I can see a button. {"element": "Save", "confidence": 0.9} That is my analysis.'
        result = adapter._parse_json_response(text)
        assert result["element"] == "Save"

    def test_parse_json_invalid(self, adapter):
        result = adapter._parse_json_response("This is not JSON at all")
        assert result == {}

    @pytest.mark.asyncio
    async def test_analyze_screenshot(self, adapter):
        mock_response = json.dumps({
            "description": "A text editor with Hello World",
            "active_window": "Notepad",
            "ui_elements": [{"type": "text_field", "label": "Editor area"}],
        })

        with patch.object(adapter, "_generate", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.analyze_screenshot(FAKE_PNG)
            assert result.description == "A text editor with Hello World"
            assert result.active_window == "Notepad"
            assert len(result.ui_elements) == 1
            assert result.model == "ollama:llava:7b"

    @pytest.mark.asyncio
    async def test_find_element_found(self, adapter):
        mock_response = json.dumps({
            "found": True, "x": 100, "y": 50,
            "width": 80, "height": 30,
            "confidence": 0.92,
            "description": "Save button in toolbar",
        })

        with patch.object(adapter, "_generate", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.find_element(FAKE_PNG, "Save button")
            assert result.found is True
            assert result.x == 100
            assert result.y == 50
            assert result.confidence == 0.92

    @pytest.mark.asyncio
    async def test_find_element_not_found(self, adapter):
        mock_response = json.dumps({
            "found": False, "confidence": 0.0,
            "description": "No Save button visible",
        })

        with patch.object(adapter, "_generate", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.find_element(FAKE_PNG, "Save button")
            assert result.found is False

    @pytest.mark.asyncio
    async def test_describe_action(self, adapter):
        mock_response = json.dumps({
            "clicked_element": "File menu",
            "action_summary": "Clicked the File menu",
        })

        with patch.object(adapter, "_generate", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.describe_action(FAKE_PNG, FAKE_PNG, 50, 10)
            assert "File menu" in result

    @pytest.mark.asyncio
    async def test_is_available_true(self, adapter):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [{"name": "llava:7b"}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        adapter._client = mock_client

        assert await adapter.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_wrong_model(self, adapter):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [{"name": "mistral:7b"}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        adapter._client = mock_client

        assert await adapter.is_available() is False

    @pytest.mark.asyncio
    async def test_get_click_context(self, adapter):
        mock_response = json.dumps({
            "element": "File menu item",
            "element_type": "menu_item",
            "confidence": 0.85,
        })

        with patch.object(adapter, "_generate", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.get_click_context(FAKE_PNG, 100, 25)
            assert result["element"] == "File menu item"
            assert result["confidence"] == 0.85


# ── ClaudeAdapter Tests (mocked API) ─────────────────────────────────

class TestClaudeAdapter:
    @pytest.fixture
    def adapter(self):
        with patch("process_recorder.vision.claude_adapter.anthropic"):
            return ClaudeAdapter(api_key="test-key", model="claude-3-5-sonnet-20241022")

    def test_model_name(self, adapter):
        assert adapter.get_model_name() == "claude:claude-3-5-sonnet-20241022"

    def test_make_image_block(self, adapter):
        block = adapter._make_image_block(b"fake-image-data")
        assert block["type"] == "image"
        assert block["source"]["type"] == "base64"
        assert block["source"]["media_type"] == "image/png"

    def test_parse_json(self, adapter):
        result = adapter._parse_json_response('{"found": true, "x": 42}')
        assert result["found"] is True
        assert result["x"] == 42

    @pytest.mark.asyncio
    async def test_analyze_screenshot(self, adapter):
        mock_response = json.dumps({
            "description": "Browser showing Google",
            "active_window": "Chrome",
            "ui_elements": [{"type": "text_field", "label": "Search bar"}],
        })

        with patch.object(adapter, "_send_message", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.analyze_screenshot(FAKE_PNG)
            assert result.description == "Browser showing Google"
            assert result.active_window == "Chrome"

    @pytest.mark.asyncio
    async def test_find_element(self, adapter):
        mock_response = json.dumps({
            "found": True, "x": 200, "y": 100,
            "width": 120, "height": 40,
            "confidence": 0.98,
            "description": "Google Search button",
        })

        with patch.object(adapter, "_send_message", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.find_element(FAKE_PNG, "Search button")
            assert result.found is True
            assert result.confidence == 0.98
