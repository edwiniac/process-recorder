"""
Action classifier — groups raw events into logical actions.

Raw recordings contain individual mouse/keyboard events.
This module groups them into meaningful actions:
  - A click event → "click" action
  - A sequence of key presses → "type" action  
  - Scroll events → "scroll" action
  - Modifier + key → "hotkey" action
"""

import logging
from dataclasses import dataclass, field

from ..models import ActionType, EventType, RawEvent

logger = logging.getLogger(__name__)


# Time window for grouping consecutive keystrokes (seconds)
TYPING_GROUP_WINDOW = 2.0

# Minimum scroll events to count as intentional
MIN_SCROLL_EVENTS = 2

# Keys that indicate hotkey combinations
MODIFIER_KEYS = {"ctrl", "alt", "shift", "cmd", "meta", "ctrl_l", "ctrl_r",
                 "alt_l", "alt_r", "shift_l", "shift_r", "cmd_l", "cmd_r"}


@dataclass
class ClassifiedAction:
    """A classified user action derived from one or more raw events."""
    action_type: ActionType
    timestamp: float  # Start time
    end_timestamp: float  # End time
    source_events: list[RawEvent] = field(default_factory=list)

    # Click-specific
    click_x: int = 0
    click_y: int = 0
    button: str = "left"

    # Type-specific
    typed_text: str = ""

    # Scroll-specific
    scroll_dx: int = 0
    scroll_dy: int = 0

    # Hotkey-specific
    hotkey_combo: str = ""  # e.g., "ctrl+s"

    # Associated screenshot
    screenshot_id: str | None = None

    def __repr__(self) -> str:
        if self.action_type == ActionType.CLICK:
            return f"Click({self.click_x}, {self.click_y})"
        elif self.action_type == ActionType.TYPE:
            preview = self.typed_text[:30] + ("..." if len(self.typed_text) > 30 else "")
            return f"Type('{preview}')"
        elif self.action_type == ActionType.SCROLL:
            return f"Scroll(dx={self.scroll_dx}, dy={self.scroll_dy})"
        elif self.action_type == ActionType.HOTKEY:
            return f"Hotkey({self.hotkey_combo})"
        return f"Action({self.action_type.value})"


def classify_events(events: list[RawEvent]) -> list[ClassifiedAction]:
    """
    Group and classify a list of raw events into logical actions.
    
    Args:
        events: Chronologically sorted list of RawEvent.
        
    Returns:
        List of ClassifiedAction in chronological order.
    """
    if not events:
        return []

    actions: list[ClassifiedAction] = []
    i = 0

    while i < len(events):
        event = events[i]

        if event.event_type in (EventType.CLICK, EventType.DOUBLE_CLICK, EventType.RIGHT_CLICK):
            action = _classify_click(event)
            actions.append(action)
            i += 1

        elif event.event_type == EventType.KEY_TYPE:
            # Pre-grouped text from event listener
            action = _classify_typed_text(event)
            actions.append(action)
            i += 1

        elif event.event_type == EventType.KEY_PRESS:
            # Check for hotkey or start of typing sequence
            action, consumed = _classify_key_sequence(events, i)
            actions.append(action)
            i += consumed

        elif event.event_type == EventType.SCROLL:
            action, consumed = _classify_scroll_sequence(events, i)
            actions.append(action)
            i += consumed

        else:
            # Skip unrecognized events
            logger.debug("Skipping event type: %s", event.event_type)
            i += 1

    logger.info("Classified %d raw events into %d actions", len(events), len(actions))
    return actions


def _classify_click(event: RawEvent) -> ClassifiedAction:
    """Classify a click event."""
    data = event.data
    action_type = ActionType.CLICK

    return ClassifiedAction(
        action_type=action_type,
        timestamp=event.timestamp,
        end_timestamp=event.timestamp,
        source_events=[event],
        click_x=data.get("x", 0),
        click_y=data.get("y", 0),
        button=data.get("button", "left"),
        screenshot_id=event.screenshot_id,
    )


def _classify_typed_text(event: RawEvent) -> ClassifiedAction:
    """Classify a pre-grouped KEY_TYPE event."""
    return ClassifiedAction(
        action_type=ActionType.TYPE,
        timestamp=event.timestamp,
        end_timestamp=event.timestamp,
        source_events=[event],
        typed_text=event.data.get("text", ""),
        screenshot_id=event.screenshot_id,
    )


def _classify_key_sequence(
    events: list[RawEvent], start: int
) -> tuple[ClassifiedAction, int]:
    """
    Classify a sequence starting with KEY_PRESS.
    
    Could be:
    - A hotkey (modifier + key)
    - Start of a typing sequence (consecutive characters)
    """
    event = events[start]
    data = event.data
    key = data.get("key", "").lower()

    # Check if this is a modifier key (potential hotkey)
    if key in MODIFIER_KEYS or data.get("modifiers"):
        modifiers = data.get("modifiers", [])
        if key in MODIFIER_KEYS:
            # Look ahead for the actual key
            if start + 1 < len(events):
                next_event = events[start + 1]
                if next_event.event_type == EventType.KEY_PRESS:
                    actual_key = next_event.data.get("key", "")
                    if actual_key.lower() not in MODIFIER_KEYS:
                        combo = "+".join(modifiers + [actual_key]) if modifiers else f"{key}+{actual_key}"
                        return ClassifiedAction(
                            action_type=ActionType.HOTKEY,
                            timestamp=event.timestamp,
                            end_timestamp=next_event.timestamp,
                            source_events=[event, next_event],
                            hotkey_combo=combo,
                            screenshot_id=event.screenshot_id,
                        ), 2

    # Otherwise, group consecutive character keypresses as typing
    typed_chars = []
    consumed = 0
    last_ts = event.timestamp

    for j in range(start, len(events)):
        ev = events[j]
        if ev.event_type not in (EventType.KEY_PRESS, EventType.KEY_RELEASE):
            break
        if ev.event_type == EventType.KEY_RELEASE:
            consumed += 1
            continue
        if ev.timestamp - last_ts > TYPING_GROUP_WINDOW and j > start:
            break

        k = ev.data.get("key", "")
        if k.lower() in MODIFIER_KEYS:
            consumed += 1
            continue

        # Convert special keys
        if len(k) == 1:
            typed_chars.append(k)
        elif k.lower() == "space":
            typed_chars.append(" ")
        elif k.lower() in ("enter", "return"):
            typed_chars.append("\n")
        elif k.lower() == "tab":
            typed_chars.append("\t")
        # Skip other special keys (backspace, etc.)

        last_ts = ev.timestamp
        consumed += 1

    if not consumed:
        consumed = 1

    if typed_chars:
        return ClassifiedAction(
            action_type=ActionType.TYPE,
            timestamp=event.timestamp,
            end_timestamp=last_ts,
            source_events=events[start : start + consumed],
            typed_text="".join(typed_chars),
            screenshot_id=event.screenshot_id,
        ), consumed
    else:
        # Single keypress that isn't a character — treat as hotkey
        return ClassifiedAction(
            action_type=ActionType.HOTKEY,
            timestamp=event.timestamp,
            end_timestamp=event.timestamp,
            source_events=[event],
            hotkey_combo=key,
            screenshot_id=event.screenshot_id,
        ), consumed


def _classify_scroll_sequence(
    events: list[RawEvent], start: int
) -> tuple[ClassifiedAction, int]:
    """Group consecutive scroll events into one action."""
    total_dx = 0
    total_dy = 0
    consumed = 0
    last_ts = events[start].timestamp

    for j in range(start, len(events)):
        ev = events[j]
        if ev.event_type != EventType.SCROLL:
            break
        if ev.timestamp - last_ts > 1.0 and j > start:
            break

        total_dx += ev.data.get("dx", 0)
        total_dy += ev.data.get("dy", 0)
        last_ts = ev.timestamp
        consumed += 1

    return ClassifiedAction(
        action_type=ActionType.SCROLL,
        timestamp=events[start].timestamp,
        end_timestamp=last_ts,
        source_events=events[start : start + consumed],
        scroll_dx=total_dx,
        scroll_dy=total_dy,
        screenshot_id=events[start].screenshot_id,
    ), consumed
