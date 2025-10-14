"""
Output Formatters for Drone Metadata
=====================================

This package contains output formatters for generating various formats
from drone video metadata and analysis results.

Formatters follow a consistent interface pattern for generating:
- Markdown documentation files
- Video thumbnails  
- Semantic model CSV exports
- Dataset index files
- HTML reports

All formatters inherit from BaseFormatter for consistent behavior.
"""

from .base_formatter import BaseFormatter, FormatterError, FormatterConfig
from .markdown_formatter import MarkdownFormatter
from .thumbnail_generator import ThumbnailGenerator
from .semantic_model_exporter import SemanticModelExporter
from .dataset_index_generator import DatasetIndexGenerator

__all__ = [
    "BaseFormatter",
    "FormatterError", 
    "FormatterConfig",
    "MarkdownFormatter",
    "ThumbnailGenerator", 
    "SemanticModelExporter",
    "DatasetIndexGenerator",
]