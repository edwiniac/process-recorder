"""
Learner module — converts raw recordings into semantic workflows.

Pipeline:
  Raw Events → Action Classifier → Semantic Extractor → Workflow Processor
"""

from .action_classifier import ClassifiedAction, classify_events
from .semantic_extractor import SemanticExtractor
from .workflow_processor import WorkflowProcessor

__all__ = [
    "ClassifiedAction",
    "classify_events",
    "SemanticExtractor",
    "WorkflowProcessor",
]
