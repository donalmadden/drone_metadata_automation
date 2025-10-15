"""
Mission-Based Directory Organizer
=================================

This module organizes video processing outputs into mission-specific directory structures,
creating clean, navigable folder hierarchies based on mission classifications.

Phase 2 Implementation: Automatic organization matching Pilot04 format with
box/, safety/, thumbnails/ structure.
"""

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from dataclasses import dataclass
from datetime import datetime

from ..models import MissionType, VideoAnalysisResult, VideoProcessingBatch
from .base_formatter import BaseFormatter, FormatterConfig, FormatterError

logger = logging.getLogger(__name__)


@dataclass
class DirectoryStructure:
    """Configuration for mission-based directory structure."""
    
    # Main mission directories
    box_dir: str = "box"
    safety_dir: str = "safety"
    
    # Subdirectories within each mission folder
    thumbnails_subdir: str = "thumbnails"
    metadata_subdir: str = "metadata"
    reports_subdir: str = "reports"
    semantic_subdir: str = "semantic"
    
    # Special directories
    batch_reports_dir: str = "batch_reports"
    logs_dir: str = "logs"
    
    def get_mission_dir(self, mission_type: MissionType) -> str:
        """Get directory name for a mission type."""
        mapping = {
            MissionType.BOX: self.box_dir,
            MissionType.SAFETY: self.safety_dir,
        }
        return mapping.get(mission_type, self.box_dir)  # Default to box


class DirectoryOrganizer(BaseFormatter):
    """
    Organizer for creating mission-based directory structures and moving files.
    
    This formatter creates organized directory structures based on mission classifications
    and moves/copies output files to appropriate locations.
    
    Directory Structure Created:
    output/
    ├── box/
    │   ├── thumbnails/
    │   ├── metadata/
    │   ├── reports/
    │   └── semantic/
    ├── safety/
    │   ├── thumbnails/
    │   ├── metadata/
    │   ├── reports/
    │   └── semantic/
    ├── batch_reports/
    └── logs/
    """
    
    def __init__(self, config: FormatterConfig):
        super().__init__(config)
        
        # Directory structure configuration
        self.structure = DirectoryStructure()
        
        # File organization settings
        self.move_files = getattr(config, 'move_files', True)  # Move vs copy files
        self.preserve_originals = getattr(config, 'preserve_originals', False)
        self.create_symlinks = getattr(config, 'create_symlinks', False)  # Create symlinks to original locations
        
        # Tracking
        self.created_directories: Set[Path] = set()
        self.organized_files: Dict[str, Path] = {}  # original_path -> new_path
        
        logger.info(f"DirectoryOrganizer initialized with move_files={self.move_files}")
    
    def get_supported_extensions(self) -> List[str]:
        """Return supported file extensions (all file types)."""
        return [".*"]  # All files
    
    def format_single_video(self, result: VideoAnalysisResult) -> List[Path]:
        """
        Organize files for a single video analysis result.
        
        Args:
            result: Video analysis result to organize
            
        Returns:
            List of organized file paths
        """
        video_name = result.video_metadata.filename
        self._log_processing_start("directory organization", video_name)
        
        try:
            # Determine mission type and target directory
            mission_type = result.mission_data.mission_type if result.mission_data else MissionType.BOX
            mission_dir = self.structure.get_mission_dir(mission_type)
            
            # Create mission directory structure
            mission_path = self._ensure_mission_structure(mission_dir)
            
            # Organize any existing output files for this video
            organized_paths = self._organize_video_files(result, mission_path)
            
            self._log_processing_complete("directory organization", video_name, mission_path)
            return organized_paths
            
        except Exception as e:
            error_msg = f"Failed to organize files for {video_name}: {str(e)}"
            self._log_processing_error("directory organization", video_name, error_msg)
            raise FormatterError(error_msg)
    
    def format_batch(self, batch: VideoProcessingBatch) -> List[Path]:
        """
        Organize files for a batch of video analysis results.
        
        Args:
            batch: Batch of video analysis results to organize
            
        Returns:
            List of organized file paths
        """
        all_organized_paths = []
        
        # Create batch reports directory
        batch_reports_path = self._ensure_directory(self.structure.batch_reports_dir)
        
        # Organize each video
        for result in batch.video_results:
            try:
                paths = self.format_single_video(result)
                all_organized_paths.extend(paths)
            except FormatterError:
                # Error already logged in format_single_video
                continue
        
        # Create batch organization summary
        summary_path = self._create_batch_summary(batch, batch_reports_path)
        if summary_path:
            all_organized_paths.append(summary_path)
        
        return all_organized_paths
    
    def _ensure_mission_structure(self, mission_dir: str) -> Path:
        """Create complete directory structure for a mission type."""
        mission_path = self._ensure_directory(mission_dir)
        
        # Create subdirectories
        self._ensure_directory(mission_path / self.structure.metadata_subdir)
        # Create thumbnails nested inside metadata
        self._ensure_directory(mission_path / self.structure.metadata_subdir / self.structure.thumbnails_subdir)
        self._ensure_directory(mission_path / self.structure.reports_subdir)
        self._ensure_directory(mission_path / self.structure.semantic_subdir)
        
        return mission_path
    
    def _ensure_directory(self, dir_path: Union[str, Path]) -> Path:
        """Ensure directory exists, create if needed."""
        if isinstance(dir_path, str):
            full_path = Path(self.config.output_directory) / dir_path
        else:
            full_path = Path(self.config.output_directory) / dir_path
        
        if full_path not in self.created_directories:
            full_path.mkdir(parents=True, exist_ok=True)
            self.created_directories.add(full_path)
            logger.debug(f"Created directory: {full_path}")
        
        return full_path
    
    def _organize_video_files(self, result: VideoAnalysisResult, mission_path: Path) -> List[Path]:
        """Organize all files related to a video into mission directory structure."""
        organized_paths = []
        video_name = result.video_metadata.filename
        
        # Define file type to subdirectory mapping - thumbnails nested in metadata
        file_mappings = {
            '.jpg': f"{self.structure.metadata_subdir}/{self.structure.thumbnails_subdir}",
            '.png': f"{self.structure.metadata_subdir}/{self.structure.thumbnails_subdir}",
            '.md': self.structure.metadata_subdir,
            '.json': self.structure.metadata_subdir,
            '.csv': self.structure.semantic_subdir,
            '.html': self.structure.reports_subdir,
            '.txt': self.structure.reports_subdir,
        }
        
        # Look for existing files that might need organization
        base_output_dir = Path(self.config.output_directory)
        
        # Search for files matching this video
        for file_pattern in [f"{video_name}*", f"{Path(video_name).stem}*"]:
            for existing_file in base_output_dir.rglob(file_pattern):
                if existing_file.is_file():
                    # Skip if file is already in the correct mission subdirectory
                    if self._is_already_organized(existing_file, mission_path):
                        organized_paths.append(existing_file)
                        continue
                    
                    # Determine target subdirectory
                    file_extension = existing_file.suffix.lower()
                    target_subdir = file_mappings.get(file_extension, self.structure.metadata_subdir)
                    target_dir = mission_path / target_subdir
                    
                    # Move the file to organized location
                    organized_file = self._organize_file(existing_file, target_dir)
                    if organized_file:
                        organized_paths.append(organized_file)
        
        return organized_paths
    
    def get_organized_output_path(self, result: VideoAnalysisResult, file_extension: str, filename: str = None) -> Path:
        """
        Get the organized output path for a file before it's created.
        
        Args:
            result: Video analysis result
            file_extension: File extension (e.g., '.md', '.jpg')
            filename: Optional specific filename to use (if not provided, generates from video name)
            
        Returns:
            Path where the file should be written
        """
        # Determine mission type and target directory
        mission_type = result.mission_data.mission_type if result.mission_data else MissionType.BOX
        mission_dir = self.structure.get_mission_dir(mission_type)
        
        # Create mission directory structure
        mission_path = self._ensure_mission_structure(mission_dir)
        
        # Define file type to subdirectory mapping - thumbnails nested in metadata
        file_mappings = {
            '.jpg': f"{self.structure.metadata_subdir}/{self.structure.thumbnails_subdir}",
            '.png': f"{self.structure.metadata_subdir}/{self.structure.thumbnails_subdir}",
            '.md': self.structure.metadata_subdir,
            '.json': self.structure.metadata_subdir,
            '.csv': self.structure.semantic_subdir,
            '.html': self.structure.reports_subdir,
            '.txt': self.structure.reports_subdir,
        }
        
        # Determine target subdirectory
        target_subdir = file_mappings.get(file_extension.lower(), self.structure.metadata_subdir)
        target_dir = mission_path / target_subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename - use provided filename if available, otherwise generate from video name
        if filename:
            final_filename = filename
        else:
            video_name = result.video_metadata.filename
            if file_extension == '.md':
                final_filename = f"{video_name}.md"
            elif file_extension in ['.jpg', '.png']:
                final_filename = f"{video_name}_thumbnail{file_extension}"
            else:
                final_filename = f"{Path(video_name).stem}{file_extension}"
            
        return target_dir / final_filename
    
    def _is_already_organized(self, file_path: Path, mission_path: Path) -> bool:
        """Check if a file is already in the correct mission directory structure."""
        try:
            # Check if the file is within the mission directory structure
            file_path.relative_to(mission_path)
            return True
        except ValueError:
            return False
    
    def _organize_file(self, source_path: Path, target_dir: Path) -> Optional[Path]:
        """Move or copy a file to the target directory."""
        try:
            target_path = target_dir / source_path.name
            
            # Check if source and target are the same file
            if source_path.resolve() == target_path.resolve():
                logger.debug(f"File already in correct location: {source_path}")
                return target_path
            
            # Handle existing files
            if target_path.exists():
                if not self.config.overwrite_existing:
                    logger.warning(f"Target file exists, skipping: {target_path}")
                    return target_path
                else:
                    logger.info(f"Overwriting existing file: {target_path}")
            
            # Ensure target directory exists
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Move or copy the file
            if self.move_files and not self.preserve_originals:
                shutil.move(str(source_path), str(target_path))
                logger.info(f"Moved: {source_path} -> {target_path}")
            else:
                shutil.copy2(str(source_path), str(target_path))
                logger.info(f"Copied: {source_path} -> {target_path}")
            
            # Create symlink to original location if requested
            if self.create_symlinks and self.move_files:
                try:
                    source_path.symlink_to(target_path)
                    logger.debug(f"Created symlink: {source_path} -> {target_path}")
                except (OSError, NotImplementedError) as e:
                    logger.warning(f"Could not create symlink: {e}")
            
            self.organized_files[str(source_path)] = target_path
            return target_path
            
        except Exception as e:
            logger.error(f"Failed to organize file {source_path}: {e}")
            return None
    
    def _create_batch_summary(self, batch: VideoProcessingBatch, batch_reports_path: Path) -> Optional[Path]:
        """Create a summary report of batch organization."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_path = batch_reports_path / f"organization_summary_{timestamp}.md"
            
            # Count files by mission type
            mission_counts = {}
            for result in batch.video_results:
                mission_type = result.mission_data.mission_type if result.mission_data else MissionType.BOX
                mission_dir = self.structure.get_mission_dir(mission_type)
                mission_counts[mission_dir] = mission_counts.get(mission_dir, 0) + 1
            
            # Generate summary content
            content = f"""# Batch Organization Summary
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Overview
- Total videos processed: {len(batch.video_results)}
- Files organized: {len(self.organized_files)}
- Directories created: {len(self.created_directories)}

## Mission Type Distribution
"""
            
            for mission_dir, count in sorted(mission_counts.items()):
                content += f"- {mission_dir}: {count} videos\n"
            
            content += f"""
## Directory Structure Created
```
{self.config.output_directory}/
"""
            
            # Add directory structure
            for mission_dir, count in sorted(mission_counts.items()):
                if count > 0:
                    content += f"├── {mission_dir}/\n"
                    content += f"│   ├── {self.structure.thumbnails_subdir}/\n"
                    content += f"│   ├── {self.structure.metadata_subdir}/\n"
                    content += f"│   ├── {self.structure.reports_subdir}/\n"
                    content += f"│   └── {self.structure.semantic_subdir}/\n"
            
            content += f"├── {self.structure.batch_reports_dir}/\n"
            content += f"└── {self.structure.logs_dir}/\n```\n"
            
            # File organization details
            if self.organized_files:
                content += "\n## File Organization Details\n"
                for original, new_path in self.organized_files.items():
                    content += f"- `{Path(original).name}` -> `{new_path.relative_to(Path(self.config.output_directory))}`\n"
            
            # Write summary
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Created batch organization summary: {summary_path}")
            return summary_path
            
        except Exception as e:
            logger.error(f"Failed to create batch summary: {e}")
            return None
    
    def get_directory_structure(self) -> Dict[str, Any]:
        """Get information about the created directory structure."""
        structure_info = {}
        
        for directory in sorted(self.created_directories):
            rel_path = directory.relative_to(Path(self.config.output_directory))
            structure_info[str(rel_path)] = {
                "absolute_path": str(directory),
                "exists": directory.exists(),
                "file_count": len(list(directory.iterdir())) if directory.exists() else 0
            }
        
        return structure_info
    
    def validate_config(self) -> None:
        """Validate directory organizer configuration."""
        super().validate_config()
        
        # Additional validation for directory organizer
        if hasattr(self.config, 'move_files') and hasattr(self.config, 'preserve_originals'):
            if self.config.move_files and self.config.preserve_originals:
                logger.warning("Both move_files and preserve_originals are True - files will be copied")
    
    def get_formatter_info(self) -> Dict[str, Any]:
        """Get information about this formatter."""
        info = super().get_formatter_info()
        info.update({
            "phase": "Phase 2 (Mission-Based Organization)",
            "directory_structure": {
                "mission_dirs": {
                    "box": self.structure.box_dir,
                    "safety": self.structure.safety_dir,
                },
                "subdirs": {
                    "thumbnails": self.structure.thumbnails_subdir,
                    "metadata": self.structure.metadata_subdir,
                    "reports": self.structure.reports_subdir,
                    "semantic": self.structure.semantic_subdir,
                }
            },
            "organization_settings": {
                "move_files": self.move_files,
                "preserve_originals": self.preserve_originals,
                "create_symlinks": self.create_symlinks,
            },
            "statistics": {
                "directories_created": len(self.created_directories),
                "files_organized": len(self.organized_files),
            }
        })
        return info