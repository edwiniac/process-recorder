"""
Tests for the element finder module.

Verifies element location with retries, timeouts, confidence
thresholds, and fallback behavior.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from process_recorder.replayer.element_finder import ElementFinder, FinderConfig, FindResult
from process_recorder.vision.base import ElementLocation, VisionAdapter


# ── Mock Vision ──────────────────────────────────────────────────────

class MockVision:
    """Mock vision adapter for finder tests."""

    def __init__(self):
        self.find_element = AsyncMock()
        self.analyze_screenshot = AsyncMock()
        self.describe_action = AsyncMock()
        self.is_available = AsyncMock(return_value=True)
        self.get_model_name = MagicMock(return_value="mock:test")

    def set_found(self, x=100, y=50, w=80, h=30, conf=0.95, desc="Found it"):
        self.find_element.return_value = ElementLocation(
            found=True, x=x, y=y, width=w, height=h,
            confidence=conf, description=desc,
        )

    def set_not_found(self):
        self.find_element.return_value = ElementLocation(
            found=False, confidence=0.0, description="Not found",
        )

    def set_low_confidence(self, conf=0.3):
        self.find_element.return_value = ElementLocation(
            found=True, x=100, y=50, width=80, height=30,
            confidence=conf, description="Maybe found",
        )


# ── Fixtures ──────────────────────────────────────────────────────────

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


@pytest.fixture
def mock_vision():
    return MockVision()


@pytest.fixture
def capture_fn():
    return MagicMock(return_value=FAKE_PNG)


@pytest.fixture
def fast_config():
    """Quick config for tests (short timeouts)."""
    return FinderConfig(
        timeout_ms=1000,
        retry_interval_ms=50,
        confidence_threshold=0.7,
        max_retries=5,
    )


@pytest.fixture
def finder(mock_vision, capture_fn, fast_config):
    return ElementFinder(mock_vision, capture_fn=capture_fn, config=fast_config)


# ── Element Found ────────────────────────────────────────────────────

class TestElementFound:
    @pytest.mark.asyncio
    async def test_find_element_success(self, finder, mock_vision):
        mock_vision.set_found(x=100, y=50, w=80, h=30, conf=0.95)
        result = await finder.find("Save button")

        assert result.found is True
        assert result.x == 100
        assert result.y == 50
        assert result.confidence == 0.95
        assert result.attempts >= 1

    @pytest.mark.asyncio
    async def test_center_calculation(self, finder, mock_vision):
        mock_vision.set_found(x=100, y=50, w=80, h=30)
        result = await finder.find("Save button")
        assert result.center == (140, 65)

    @pytest.mark.asyncio
    async def test_captures_screenshot(self, finder, mock_vision, capture_fn):
        mock_vision.set_found()
        await finder.find("Save button")
        capture_fn.assert_called()

    @pytest.mark.asyncio
    async def test_elapsed_time_tracked(self, finder, mock_vision):
        mock_vision.set_found()
        result = await finder.find("Save button")
        assert result.elapsed_ms > 0

    @pytest.mark.asyncio
    async def test_found_first_attempt(self, finder, mock_vision):
        mock_vision.set_found()
        result = await finder.find("Save button")
        assert result.attempts == 1


# ── Element Not Found ────────────────────────────────────────────────

class TestElementNotFound:
    @pytest.mark.asyncio
    async def test_not_found_returns_false(self, finder, mock_vision):
        mock_vision.set_not_found()
        result = await finder.find("Invisible button")
        assert result.found is False

    @pytest.mark.asyncio
    async def test_retries_before_giving_up(self, finder, mock_vision):
        mock_vision.set_not_found()
        result = await finder.find("Missing element")
        assert result.attempts > 1

    @pytest.mark.asyncio
    async def test_respects_timeout(self, mock_vision, capture_fn):
        config = FinderConfig(timeout_ms=200, retry_interval_ms=50, max_retries=100)
        finder = ElementFinder(mock_vision, capture_fn=capture_fn, config=config)
        mock_vision.set_not_found()

        start = time.monotonic()
        result = await finder.find("Missing")
        elapsed = (time.monotonic() - start) * 1000

        assert not result.found
        assert elapsed < 1000  # Should finish well before 1s


# ── Confidence Threshold ─────────────────────────────────────────────

class TestConfidenceThreshold:
    @pytest.mark.asyncio
    async def test_rejects_low_confidence(self, mock_vision, capture_fn):
        config = FinderConfig(
            timeout_ms=300, retry_interval_ms=50,
            confidence_threshold=0.7, max_retries=3,
        )
        finder = ElementFinder(mock_vision, capture_fn=capture_fn, config=config)
        mock_vision.set_low_confidence(conf=0.3)

        result = await finder.find("Blurry button")
        assert result.found is False

    @pytest.mark.asyncio
    async def test_accepts_above_threshold(self, finder, mock_vision):
        mock_vision.set_found(conf=0.75)
        result = await finder.find("Clear button")
        assert result.found is True
        assert result.confidence == 0.75

    @pytest.mark.asyncio
    async def test_exactly_at_threshold(self, finder, mock_vision):
        mock_vision.set_found(conf=0.7)
        result = await finder.find("Exact match")
        assert result.found is True


# ── Retry Behavior ───────────────────────────────────────────────────

class TestRetryBehavior:
    @pytest.mark.asyncio
    async def test_finds_on_second_attempt(self, mock_vision, capture_fn):
        config = FinderConfig(timeout_ms=2000, retry_interval_ms=50, max_retries=5)
        finder = ElementFinder(mock_vision, capture_fn=capture_fn, config=config)

        # First call: not found. Second call: found.
        mock_vision.find_element.side_effect = [
            ElementLocation(found=False),
            ElementLocation(found=True, x=100, y=50, width=80, height=30, confidence=0.9),
        ]

        result = await finder.find("Appearing button")
        assert result.found is True
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_handles_vision_error_gracefully(self, mock_vision, capture_fn):
        config = FinderConfig(timeout_ms=500, retry_interval_ms=50, max_retries=3)
        finder = ElementFinder(mock_vision, capture_fn=capture_fn, config=config)

        # First attempt throws, second succeeds
        mock_vision.find_element.side_effect = [
            RuntimeError("Model crashed"),
            ElementLocation(found=True, x=50, y=25, width=40, height=20, confidence=0.8),
        ]

        result = await finder.find("Flaky element")
        assert result.found is True


# ── Verify Element ───────────────────────────────────────────────────

class TestVerifyElement:
    @pytest.mark.asyncio
    async def test_verify_within_tolerance(self, finder, mock_vision):
        mock_vision.set_found(x=95, y=48, w=80, h=30)
        # Center = (135, 63), expected = (140, 65), diff = (5, 2) < 50
        result = await finder.verify_element("Button", expected_x=140, expected_y=65)
        assert result.found is True

    @pytest.mark.asyncio
    async def test_verify_outside_tolerance(self, finder, mock_vision):
        mock_vision.set_found(x=500, y=400, w=80, h=30)
        # Center = (540, 415), expected = (100, 100), way too far
        result = await finder.verify_element(
            "Button", expected_x=100, expected_y=100, tolerance=50
        )
        assert result.found is False

    @pytest.mark.asyncio
    async def test_verify_not_found(self, finder, mock_vision):
        mock_vision.set_not_found()
        result = await finder.verify_element("Ghost", expected_x=100, expected_y=100)
        assert result.found is False


# ── FindResult Properties ────────────────────────────────────────────

class TestFindResult:
    def test_center_calculation(self):
        r = FindResult(found=True, x=100, y=200, width=50, height=30)
        assert r.center == (125, 215)

    def test_default_center(self):
        r = FindResult(found=False)
        assert r.center == (0, 0)
