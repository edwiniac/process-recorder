"""
Workflow processor — the full pipeline from recording to workflow.

Orchestrates:
1. Action classification (raw events → classified actions)
2. Semantic extraction (classified actions → semantic steps)
3. Workflow assembly (semantic steps → complete workflow)
4. Optional: Workflow summarization via vision model
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import (
    Recording,
    Screenshot,
    SemanticStep,
    Workflow,
)
from ..vision.base import VisionAdapter
from ..vision.prompts import SUMMARIZE_WORKFLOW, format_prompt
from .action_classifier import ClassifiedAction, classify_events
from .semantic_extractor import SemanticExtractor

logger = logging.getLogger(__name__)


class WorkflowProcessor:
    """
    Full pipeline: Recording → Workflow.
    
    Usage:
        processor = WorkflowProcessor(vision_adapter)
        workflow = await processor.process(recording, screenshot_dir)
    """

    def __init__(self, vision: VisionAdapter):
        self._vision = vision
        self._extractor = SemanticExtractor(vision)

    async def process(
        self,
        recording: Recording,
        screenshot_dir: Optional[Path] = None,
        name: Optional[str] = None,
    ) -> Workflow:
        """
        Process a complete recording into a workflow.
        
        Args:
            recording: The raw recording data.
            screenshot_dir: Path to the directory containing screenshots.
            name: Optional workflow name (auto-generated if not provided).
            
        Returns:
            A complete Workflow ready for replay.
        """
        logger.info(
            "Processing recording '%s' (%d events, %d screenshots)",
            recording.name,
            len(recording.events),
            len(recording.screenshots),
        )

        # Step 1: Classify raw events into actions
        logger.info("Step 1/4: Classifying events...")
        actions = classify_events(recording.events)
        logger.info("Classified into %d actions", len(actions))

        if not actions:
            logger.warning("No actions found in recording")
            return self._empty_workflow(recording, name)

        # Step 2: Build screenshot lookup
        screenshots = {s.screenshot_id: s for s in recording.screenshots}

        # Step 3: Extract semantic steps
        logger.info("Step 2/4: Extracting semantic steps...")
        steps = await self._extractor.extract_steps(
            actions, screenshots, screenshot_dir
        )
        logger.info("Extracted %d semantic steps", len(steps))

        # Step 4: Generate workflow summary
        logger.info("Step 3/4: Generating workflow summary...")
        description = await self._generate_summary(steps)

        # Step 5: Assemble workflow
        logger.info("Step 4/4: Assembling workflow...")
        workflow_name = name or await self._generate_name(steps, description)

        workflow = Workflow(
            workflow_id=str(uuid.uuid4())[:8],
            name=workflow_name,
            description=description,
            created_at=datetime.now(),
            steps=steps,
            source_recording_id=recording.recording_id,
            model_used=self._vision.get_model_name(),
        )

        logger.info(
            "Workflow '%s' created with %d steps",
            workflow.name,
            len(workflow.steps),
        )
        return workflow

    async def process_and_save(
        self,
        recording: Recording,
        screenshot_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        name: Optional[str] = None,
    ) -> Workflow:
        """
        Process a recording and save the workflow to disk.
        
        Args:
            recording: The raw recording.
            screenshot_dir: Where screenshots are stored.
            output_dir: Where to save the workflow JSON.
            name: Optional workflow name.
            
        Returns:
            The saved Workflow.
        """
        workflow = await self.process(recording, screenshot_dir, name)

        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            filepath = output_dir / f"{workflow.workflow_id}.json"
            filepath.write_text(
                json.dumps(workflow.to_dict(), indent=2, default=str)
            )
            logger.info("Workflow saved to %s", filepath)

        return workflow

    async def _generate_summary(self, steps: list[SemanticStep]) -> str:
        """Generate a human-readable summary of the workflow."""
        if not steps:
            return "Empty workflow"

        steps_text = "\n".join(
            f"{s.step_id}. {s.target_description}"
            + (f" → '{s.input_data}'" if s.input_data else "")
            for s in steps
        )

        try:
            prompt = format_prompt(SUMMARIZE_WORKFLOW, steps_text=steps_text)
            result = await self._vision.analyze_screenshot(
                # Send a minimal image — we only need text processing here
                # Some models require an image even for text prompts
                b"",  # Empty bytes — adapter should handle gracefully
                prompt,
            )

            if result.raw_response:
                parsed = self._parse_json(result.raw_response)
                if "description" in parsed:
                    return parsed["description"]
                return result.raw_response[:500]
        except Exception as e:
            logger.warning("Summary generation failed: %s", e)

        # Fallback: simple summary
        action_types = set(s.action_type.value for s in steps)
        return (
            f"Workflow with {len(steps)} steps involving "
            f"{', '.join(sorted(action_types))} actions."
        )

    async def _generate_name(
        self, steps: list[SemanticStep], description: str
    ) -> str:
        """Generate a short name for the workflow."""
        # Try to extract name from the summary generation
        try:
            parsed = self._parse_json(description)
            if "name" in parsed:
                return parsed["name"]
        except Exception:
            pass

        # Fallback: derive from first action
        if steps:
            first = steps[0].target_description
            return first[:40] if first else "Unnamed Workflow"
        return "Unnamed Workflow"

    def _empty_workflow(
        self, recording: Recording, name: Optional[str]
    ) -> Workflow:
        """Create an empty workflow (no actions found)."""
        return Workflow(
            workflow_id=str(uuid.uuid4())[:8],
            name=name or "Empty Workflow",
            description="No actions were detected in the recording.",
            created_at=datetime.now(),
            steps=[],
            source_recording_id=recording.recording_id,
            model_used=self._vision.get_model_name(),
        )

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Try to parse JSON from text."""
        text = text.strip()
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            try:
                return json.loads(text[brace_start : brace_end + 1])
            except json.JSONDecodeError:
                pass
        return {}
