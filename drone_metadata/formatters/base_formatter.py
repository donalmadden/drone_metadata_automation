"""
Base Formatter Architecture
===========================

This module provides the abstract base class for all output formatters
in the drone metadata automation system. All formatters should inherit
from BaseFormatter to ensure consistent interface and behavior.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from ..models import VideoAnalysisResult, VideoProcessingBatch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .directory_organizer import DirectoryOrganizer


logger = logging.getLogger(__name__)


class FormatterError(Exception):
    """Exception raised for formatter-related errors."""
    pass


@dataclass
class FormatterConfig:
    """Configuration settings for formatters."""
    output_directory: str
    template_directory: Optional[str] = None
    overwrite_existing: bool = False
    create_directories: bool = True
    timestamp_format: str = "%Y-%m-%d %H:%M:%S"
    
    # Common formatting options
    include_raw_metadata: bool = False
    include_processing_logs: bool = True
    generate_checksums: bool = False
    
    # Organization support
    organizer: Optional['DirectoryOrganizer'] = None
    
    # Custom formatter-specific settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)


class BaseFormatter(ABC):
    """
    Abstract base class for all output formatters.
    
    This class defines the common interface and shared functionality
    for all formatters in the system. Concrete formatters should
    inherit from this class and implement the required abstract methods.
    """
    
    def __init__(self, config: FormatterConfig):
        """
        Initialize the formatter.
        
        Args:
            config: Formatter configuration settings
        """
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        # Ensure output directory exists
        if self.config.create_directories:
            self._ensure_output_directory()
    
    def _ensure_output_directory(self) -> None:
        """Ensure the output directory exists."""
        output_path = Path(self.config.output_directory)
        if not output_path.exists():
            try:
                output_path.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created output directory: {output_path}")
            except Exception as e:
                raise FormatterError(f"Failed to create output directory {output_path}: {str(e)}")
    
    def _check_file_exists(self, file_path: Path) -> bool:
        """Check if output file already exists and handle based on configuration."""
        if file_path.exists():
            if not self.config.overwrite_existing:
                self.logger.warning(f"File exists and overwrite disabled: {file_path}")
                return True
            else:
                self.logger.info(f"Overwriting existing file: {file_path}")
        return False
    
    def _get_output_path(self, filename: str, result: Optional[VideoAnalysisResult] = None, file_extension: str = None) -> Path:
        """Get the full output path for a filename."""
        # If organizer is configured and we have result info, use organized path
        if self.config.organizer and result and file_extension:
            return self.config.organizer.get_organized_output_path(result, file_extension, filename)
        else:
            return Path(self.config.output_directory) / filename
    
    def _log_processing_start(self, operation: str, target: str) -> None:
        """Log the start of a processing operation."""
        self.logger.info(f"Starting {operation} for: {target}")
    
    def _log_processing_complete(self, operation: str, target: str, output_path: Path) -> None:
        """Log the completion of a processing operation."""
        self.logger.info(f"Completed {operation} for {target} -> {output_path}")
    
    def _log_processing_error(self, operation: str, target: str, error: str) -> None:
        """Log a processing error."""
        self.logger.error(f"Failed {operation} for {target}: {error}")
    
    @abstractmethod
    def format_single_video(self, result: VideoAnalysisResult) -> List[Path]:
        """
        Format output for a single video analysis result.
        
        Args:
            result: Video analysis result to format
            
        Returns:
            List of output file paths created
            
        Raises:
            FormatterError: If formatting fails
        """
        pass
    
    @abstractmethod
    def format_batch(self, batch: VideoProcessingBatch) -> List[Path]:
        """
        Format output for a batch of video analysis results.
        
        Args:
            batch: Batch of video analysis results to format
            
        Returns:
            List of output file paths created
            
        Raises:
            FormatterError: If formatting fails
        """
        pass
    
    def get_supported_extensions(self) -> List[str]:
        """
        Get list of file extensions this formatter generates.
        
        Returns:
            List of file extensions (including the dot)
        """
        return []  # Override in subclasses
    
    def validate_config(self) -> None:
        """
        Validate formatter configuration.
        
        Raises:
            FormatterError: If configuration is invalid
        """
        if not self.config.output_directory:
            raise FormatterError("Output directory is required")
        
        # Additional validation can be added by subclasses
    
    def get_formatter_info(self) -> Dict[str, Any]:
        """
        Get information about this formatter.
        
        Returns:
            Dictionary with formatter information
        """
        return {
            "name": self.__class__.__name__,
            "description": self.__class__.__doc__ or "No description available",
            "supported_extensions": self.get_supported_extensions(),
            "config": {
                "output_directory": self.config.output_directory,
                "overwrite_existing": self.config.overwrite_existing,
                "create_directories": self.config.create_directories,
            }
        }


class FormatterRegistry:
    """Registry for managing available formatters."""
    
    def __init__(self):
        self._formatters: Dict[str, type] = {}
    
    def register(self, name: str, formatter_class: type) -> None:
        """Register a formatter class."""
        if not issubclass(formatter_class, BaseFormatter):
            raise FormatterError(f"Formatter {name} must inherit from BaseFormatter")
        
        self._formatters[name] = formatter_class
        logger.info(f"Registered formatter: {name}")
    
    def get_formatter(self, name: str, config: FormatterConfig) -> BaseFormatter:
        """Get an instance of a registered formatter."""
        if name not in self._formatters:
            raise FormatterError(f"Formatter '{name}' not found. Available: {list(self._formatters.keys())}")
        
        formatter_class = self._formatters[name]
        return formatter_class(config)
    
    def list_formatters(self) -> List[str]:
        """Get list of registered formatter names."""
        return list(self._formatters.keys())


# Global formatter registry
formatter_registry = FormatterRegistry()