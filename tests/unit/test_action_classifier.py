"""
Tests for the action classifier module.

Verifies that raw events are correctly grouped and classified
into logical user actions.
"""

import pytest

from process_recorder.learner.action_classifier import (
    ClassifiedAction,
    classify_events,
    _classify_click,
    _classify_scroll_sequence,
)
from process_recorder.models import ActionType, EventType, RawEvent


# ── Helpers ───────────────────────────────────────────────────────────

def make_event(
    event_type: EventType,
    timestamp: float = 1000.0,
    data: dict | None = None,
    screenshot_id: str | None = None,
) -> RawEvent:
    return RawEvent(
        timestamp=timestamp,
        event_type=event_type,
        data=data or {},
        screenshot_id=screenshot_id,
    )


def make_click(x: int, y: int, ts: float = 1000.0, button: str = "left") -> RawEvent:
    return make_event(
        EventType.CLICK, ts,
        data={"x": x, "y": y, "button": button},
        screenshot_id="sc_001",
    )


def make_key_press(key: str, ts: float = 1000.0, modifiers: list | None = None) -> RawEvent:
    data = {"key": key}
    if modifiers:
        data["modifiers"] = modifiers
    return make_event(EventType.KEY_PRESS, ts, data=data)


def make_key_type(text: str, ts: float = 1000.0) -> RawEvent:
    return make_event(EventType.KEY_TYPE, ts, data={"text": text})


def make_scroll(dx: int, dy: int, ts: float = 1000.0) -> RawEvent:
    return make_event(EventType.SCROLL, ts, data={"dx": dx, "dy": dy})


# ── Empty Input ───────────────────────────────────────────────────────

class TestEmptyInput:
    def test_empty_events_returns_empty(self):
        assert classify_events([]) == []

    def test_single_event(self):
        events = [make_click(100, 200)]
        actions = classify_events(events)
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.CLICK


# ── Click Classification ─────────────────────────────────────────────

class TestClickClassification:
    def test_left_click(self):
        events = [make_click(100, 200)]
        actions = classify_events(events)
        assert actions[0].action_type == ActionType.CLICK
        assert actions[0].click_x == 100
        assert actions[0].click_y == 200
        assert actions[0].button == "left"

    def test_right_click(self):
        events = [make_event(
            EventType.RIGHT_CLICK, 1000.0,
            data={"x": 300, "y": 400, "button": "right"},
        )]
        actions = classify_events(events)
        assert actions[0].action_type == ActionType.CLICK
        assert actions[0].button == "right"

    def test_double_click(self):
        events = [make_event(
            EventType.DOUBLE_CLICK, 1000.0,
            data={"x": 50, "y": 60, "button": "left"},
        )]
        actions = classify_events(events)
        assert actions[0].action_type == ActionType.CLICK

    def test_multiple_clicks(self):
        events = [
            make_click(100, 200, ts=1.0),
            make_click(300, 400, ts=2.0),
            make_click(500, 600, ts=3.0),
        ]
        actions = classify_events(events)
        assert len(actions) == 3
        assert all(a.action_type == ActionType.CLICK for a in actions)

    def test_click_with_screenshot(self):
        event = make_click(100, 200)
        actions = classify_events([event])
        assert actions[0].screenshot_id == "sc_001"

    def test_click_repr(self):
        actions = classify_events([make_click(100, 200)])
        assert "Click(100, 200)" in repr(actions[0])


# ── Typing Classification ────────────────────────────────────────────

class TestTypingClassification:
    def test_pre_grouped_text(self):
        """KEY_TYPE events are pre-grouped by the event listener."""
        events = [make_key_type("Hello World")]
        actions = classify_events(events)
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.TYPE
        assert actions[0].typed_text == "Hello World"

    def test_consecutive_keypresses(self):
        """Individual KEY_PRESS events should be grouped into typing."""
        events = [
            make_key_press("H", ts=1.0),
            make_key_press("i", ts=1.1),
            make_key_press("!", ts=1.2),
        ]
        actions = classify_events(events)
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.TYPE
        assert actions[0].typed_text == "Hi!"

    def test_typing_with_gap_splits(self):
        """Typing with >2s gap should split into separate actions."""
        events = [
            make_key_press("A", ts=1.0),
            make_key_press("B", ts=1.1),
            # 3 second gap
            make_key_press("C", ts=4.2),
        ]
        actions = classify_events(events)
        # Should be 2 typing groups
        assert len(actions) == 2
        assert actions[0].typed_text == "AB"

    def test_special_keys_in_typing(self):
        """Space, enter, tab should be included in typed text."""
        events = [
            make_key_press("H", ts=1.0),
            make_key_press("i", ts=1.1),
            make_key_press("space", ts=1.2),
            make_key_press("!", ts=1.3),
        ]
        actions = classify_events(events)
        assert actions[0].typed_text == "Hi !"

    def test_type_repr(self):
        actions = classify_events([make_key_type("Hello World")])
        assert "Type('Hello World')" in repr(actions[0])

    def test_long_type_repr_truncated(self):
        long_text = "A" * 50
        actions = classify_events([make_key_type(long_text)])
        assert "..." in repr(actions[0])


# ── Hotkey Classification ────────────────────────────────────────────

class TestHotkeyClassification:
    def test_modifier_plus_key(self):
        """Ctrl + S should be classified as a hotkey."""
        events = [
            make_key_press("ctrl", ts=1.0),
            make_key_press("s", ts=1.05),
        ]
        actions = classify_events(events)
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.HOTKEY
        assert "s" in actions[0].hotkey_combo.lower()

    def test_hotkey_with_modifiers_list(self):
        events = [
            make_key_press("s", ts=1.0, modifiers=["ctrl"]),
        ]
        # Single key with modifiers — gets treated as typing/hotkey
        actions = classify_events(events)
        assert len(actions) >= 1

    def test_hotkey_repr(self):
        events = [
            make_key_press("ctrl", ts=1.0),
            make_key_press("s", ts=1.05),
        ]
        actions = classify_events(events)
        assert "Hotkey(" in repr(actions[0])


# ── Scroll Classification ────────────────────────────────────────────

class TestScrollClassification:
    def test_single_scroll(self):
        events = [make_scroll(0, -3, ts=1.0)]
        actions = classify_events(events)
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.SCROLL
        assert actions[0].scroll_dy == -3

    def test_consecutive_scrolls_grouped(self):
        """Rapid scroll events should be grouped."""
        events = [
            make_scroll(0, -3, ts=1.0),
            make_scroll(0, -3, ts=1.1),
            make_scroll(0, -3, ts=1.2),
        ]
        actions = classify_events(events)
        assert len(actions) == 1
        assert actions[0].scroll_dy == -9

    def test_scroll_with_gap_splits(self):
        """Scroll events >1s apart should split."""
        events = [
            make_scroll(0, -3, ts=1.0),
            make_scroll(0, -3, ts=1.1),
            # 2 second gap
            make_scroll(0, -5, ts=3.2),
        ]
        actions = classify_events(events)
        assert len(actions) == 2

    def test_horizontal_scroll(self):
        events = [make_scroll(5, 0, ts=1.0)]
        actions = classify_events(events)
        assert actions[0].scroll_dx == 5
        assert actions[0].scroll_dy == 0

    def test_scroll_repr(self):
        actions = classify_events([make_scroll(0, -3)])
        assert "Scroll(" in repr(actions[0])


# ── Mixed Event Sequences ────────────────────────────────────────────

class TestMixedSequences:
    def test_click_then_type(self):
        """Click on a field then type into it."""
        events = [
            make_click(200, 100, ts=1.0),
            make_key_type("Hello", ts=2.0),
        ]
        actions = classify_events(events)
        assert len(actions) == 2
        assert actions[0].action_type == ActionType.CLICK
        assert actions[1].action_type == ActionType.TYPE

    def test_full_workflow(self):
        """Simulate: click file menu → click save → type filename → click OK."""
        events = [
            make_click(50, 10, ts=1.0),      # Click File
            make_click(50, 80, ts=2.0),       # Click Save As
            make_key_type("report.txt", ts=3.0),  # Type filename
            make_click(400, 300, ts=5.0),     # Click OK
        ]
        actions = classify_events(events)
        assert len(actions) == 4
        assert actions[0].action_type == ActionType.CLICK
        assert actions[1].action_type == ActionType.CLICK
        assert actions[2].action_type == ActionType.TYPE
        assert actions[2].typed_text == "report.txt"
        assert actions[3].action_type == ActionType.CLICK

    def test_click_scroll_click(self):
        events = [
            make_click(100, 200, ts=1.0),
            make_scroll(0, -5, ts=2.0),
            make_scroll(0, -5, ts=2.1),
            make_click(100, 400, ts=3.0),
        ]
        actions = classify_events(events)
        assert len(actions) == 3
        assert actions[0].action_type == ActionType.CLICK
        assert actions[1].action_type == ActionType.SCROLL
        assert actions[2].action_type == ActionType.CLICK

    def test_preserves_timestamps(self):
        events = [
            make_click(10, 20, ts=100.0),
            make_click(30, 40, ts=200.0),
        ]
        actions = classify_events(events)
        assert actions[0].timestamp == 100.0
        assert actions[1].timestamp == 200.0

    def test_preserves_source_events(self):
        events = [make_click(10, 20)]
        actions = classify_events(events)
        assert len(actions[0].source_events) == 1
        assert actions[0].source_events[0] is events[0]
