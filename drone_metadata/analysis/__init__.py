"""
Analysis Module
===============

This module provides advanced analysis capabilities for drone metadata,
including mission classification, pattern recognition, and batch processing.

Phase 2 Components:
- MissionClassifier: Intelligent mission type classification
- Future: FlightPatternAnalyzer, QualityAnalyzer, etc.
"""

from .mission_classifier import MissionClassifier, ClassificationRule

__all__ = [
    "MissionClassifier",
    "ClassificationRule"
]