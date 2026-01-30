"""
Prompt templates for vision model interactions.

Carefully engineered prompts for UI analysis, element finding,
and action description. These are model-agnostic — adapters
may wrap them with model-specific formatting.
"""

# --- Screenshot Analysis ---

ANALYZE_SCREENSHOT = """Analyze this screenshot of a desktop application.

Describe:
1. What application or window is active
2. What UI elements are visible (buttons, text fields, menus, etc.)
3. What the user appears to be doing

Respond in this exact JSON format:
{
    "active_window": "Application Name - Window Title",
    "description": "Brief description of what's on screen",
    "ui_elements": [
        {
            "type": "button|text_field|menu|link|icon|tab|checkbox|dropdown|other",
            "label": "visible text or description",
            "location": "top-left|top-center|top-right|center-left|center|center-right|bottom-left|bottom-center|bottom-right",
            "state": "normal|focused|selected|disabled|hover"
        }
    ]
}

Be precise about element labels — use the exact text visible on screen.
Only include clearly visible elements, not guesses."""


# --- Element Finding ---

FIND_ELEMENT = """Look at this screenshot and find the following UI element:

"{element_description}"

If you can see this element, respond with this exact JSON:
{{
    "found": true,
    "x": <left edge x pixel>,
    "y": <top edge y pixel>,
    "width": <element width in pixels>,
    "height": <element height in pixels>,
    "confidence": <0.0 to 1.0>,
    "description": "what you see at that location"
}}

If the element is NOT visible, respond with:
{{
    "found": false,
    "confidence": 0.0,
    "description": "why it wasn't found"
}}

Coordinates should be pixel positions from the top-left corner of the image.
Be precise — the coordinates will be used for automated clicking."""


# --- Action Description ---

DESCRIBE_ACTION = """I'm showing you two screenshots: BEFORE and AFTER a user action.

The user clicked at position ({click_x}, {click_y}) on the BEFORE screenshot.

Compare the two screenshots and describe:
1. What element the user clicked on
2. What changed as a result
3. A concise action description

Respond in this exact JSON format:
{{
    "clicked_element": "description of what was clicked",
    "element_type": "button|link|text_field|menu_item|icon|tab|checkbox|dropdown|other",
    "change_description": "what changed between before and after",
    "action_summary": "one-line summary like 'Clicked the Save button'"
}}"""


# --- Workflow Summary ---

SUMMARIZE_WORKFLOW = """Here is a sequence of actions that form a workflow:

{steps_text}

Provide a concise summary of this workflow:
1. What task is being accomplished?
2. What application(s) are used?
3. A short name for this workflow (2-5 words)

Respond in JSON:
{{
    "name": "Short Workflow Name",
    "description": "One paragraph describing what this workflow does",
    "application": "Primary application used"
}}"""


# --- Click Context (lightweight, for associating clicks with UI elements) ---

CLICK_CONTEXT = """Look at this screenshot. The user clicked at pixel position ({click_x}, {click_y}).

What UI element is at or near that position? Respond in JSON:
{{
    "element": "description of the clicked element",
    "element_type": "button|link|text_field|menu_item|icon|tab|checkbox|dropdown|scrollbar|titlebar|other",
    "confidence": <0.0 to 1.0>
}}

Be specific — use the exact label/text visible on the element."""


def format_prompt(template: str, **kwargs) -> str:
    """Format a prompt template with the given variables."""
    return template.format(**kwargs)
