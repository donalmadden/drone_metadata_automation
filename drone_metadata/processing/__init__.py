"""
Processing Module
=================

This module provides advanced processing capabilities for drone metadata,
including batch processing with parallel execution, progress tracking,
and error recovery.

Phase 2 Components:
- BatchProcessor: Parallel batch processing with resume capabilities
- Future: Advanced pipeline components
"""

from .batch_processor import BatchProcessor, BatchConfig, VideoProcessingJob, BatchProgress

__all__ = [
    "BatchProcessor",
    "BatchConfig", 
    "VideoProcessingJob",
    "BatchProgress"
]