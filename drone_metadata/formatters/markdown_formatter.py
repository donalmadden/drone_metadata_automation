"""
Markdown Formatter
==================

This module provides the MarkdownFormatter class for generating
individual .md documentation files for drone videos, similar to
the format used in the Pilot04_Field_Test_April_25 example.
"""

from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .base_formatter import BaseFormatter, FormatterError
from ..models import VideoAnalysisResult, VideoProcessingBatch


class MarkdownFormatter(BaseFormatter):
    """
    Formatter for generating Markdown documentation files for drone videos.
    
    This formatter creates individual .md files for each video with:
    - Basic video information (duration, resolution, file size)
    - GPS coordinates if available
    - DJI-specific metadata
    - Mission classification
    - Technical specifications
    - Links to thumbnails
    """
    
    def get_supported_extensions(self) -> List[str]:
        """Return supported file extensions."""
        return [".md"]
    
    def format_single_video(self, result: VideoAnalysisResult) -> List[Path]:
        """
        Generate a Markdown file for a single video analysis result.
        
        Args:
            result: Video analysis result to format
            
        Returns:
            List containing the path to the generated .md file
        """
        video_name = result.video_metadata.filename
        self._log_processing_start("markdown generation", video_name)
        
        try:
            # Create output filename (e.g., DJI_0593.MP4.md)
            output_filename = f"{video_name}.md"
            output_path = self._get_output_path(output_filename)
            
            # Check if file exists and handle accordingly
            if self._check_file_exists(output_path):
                return [output_path]
            
            # Generate markdown content
            markdown_content = self._generate_video_markdown(result)
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            self._log_processing_complete("markdown generation", video_name, output_path)
            return [output_path]
            
        except Exception as e:
            error_msg = f"Failed to generate markdown for {video_name}: {str(e)}"
            self._log_processing_error("markdown generation", video_name, error_msg)
            raise FormatterError(error_msg)
    
    def format_batch(self, batch: VideoProcessingBatch) -> List[Path]:
        """
        Generate Markdown files for a batch of video analysis results.
        
        Args:
            batch: Batch of video analysis results to format
            
        Returns:
            List of paths to generated .md files
        """
        output_paths = []
        
        for result in batch.video_results:
            try:
                paths = self.format_single_video(result)
                output_paths.extend(paths)
            except FormatterError:
                # Error already logged in format_single_video
                continue
        
        return output_paths
    
    def _generate_video_markdown(self, result: VideoAnalysisResult) -> str:
        """
        Generate the markdown content for a video analysis result.
        
        Args:
            result: Video analysis result to format
            
        Returns:
            Markdown content string
        """
        video = result.video_metadata
        specs = result.technical_specs
        gps = result.gps_data
        mission = result.mission_data
        
        # Start building markdown content
        lines = []
        
        # Title
        lines.append(f"# {video.filename}")
        lines.append("")
        
        # Basic video information
        lines.append("## Video Information")
        lines.append("")
        lines.append(f"- **Filename**: {video.filename}")
        lines.append(f"- **File Size**: {video.filesize_mb:.2f} MB ({video.filesize_bytes:,} bytes)")
        
        if video.duration_seconds:
            lines.append(f"- **Duration**: {video.get_duration_formatted()}")
        
        if video.last_modified:
            lines.append(f"- **Last Modified**: {video.last_modified.strftime('%Y-%m-%d %H:%M:%S')}")
        
        lines.append(f"- **Analysis Date**: {video.extraction_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Technical specifications
        if specs.width or specs.height or specs.video_codec:
            lines.append("## Technical Specifications")
            lines.append("")
            
            if specs.width and specs.height:
                lines.append(f"- **Resolution**: {specs.width}x{specs.height}")
                if specs.is_4k():
                    lines.append("  - 4K Ultra HD quality")
                elif specs.is_hd():
                    lines.append("  - HD quality")
            
            if specs.video_codec:
                lines.append(f"- **Video Codec**: {specs.video_codec}")
            
            if specs.audio_codec:
                lines.append(f"- **Audio Codec**: {specs.audio_codec}")
            
            if specs.container_format:
                lines.append(f"- **Container Format**: {specs.container_format}")
            
            if specs.framerate:
                # Handle framerate which might be a string like "30/1" or a float
                try:
                    if isinstance(specs.framerate, str) and '/' in specs.framerate:
                        # Parse fractional framerate like "30/1"
                        num, den = specs.framerate.split('/')
                        framerate_float = float(num) / float(den)
                        lines.append(f"- **Frame Rate**: {framerate_float:.1f} fps")
                    else:
                        framerate_float = float(specs.framerate)
                        lines.append(f"- **Frame Rate**: {framerate_float:.1f} fps")
                except (ValueError, ZeroDivisionError):
                    lines.append(f"- **Frame Rate**: {specs.framerate}")
            
            if specs.bitrate_video:
                lines.append(f"- **Video Bitrate**: {specs.bitrate_video:,} bps")
            
            aspect_ratio = specs.get_aspect_ratio()
            if aspect_ratio:
                lines.append(f"- **Aspect Ratio**: {aspect_ratio:.2f}:1")
            
            lines.append("")
        
        # GPS information
        if gps and gps.is_valid():
            lines.append("## GPS Information")
            lines.append("")
            lines.append(f"- **Coordinates**: {gps.latitude_decimal:.6f}, {gps.longitude_decimal:.6f}")
            
            if gps.altitude_meters:
                lines.append(f"- **Altitude**: {gps.altitude_meters:.1f} meters")
                if gps.altitude_reference:
                    lines.append(f"  - Reference: {gps.altitude_reference}")
            
            lines.append(f"- **Coordinate System**: {gps.coordinate_system}")
            
            if gps.gps_accuracy:
                lines.append(f"- **GPS Accuracy**: {gps.gps_accuracy:.1f}")
            
            if gps.gps_timestamp:
                lines.append(f"- **GPS Timestamp**: {gps.gps_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            
            lines.append("")
        
        # Mission information
        if mission and mission.is_classified():
            lines.append("## Mission Information")
            lines.append("")
            lines.append(f"- **Mission Type**: {mission.mission_type.value.title()}")
            lines.append(f"- **Mission Code**: {mission.get_mission_code()}")
            
            if mission.bay_designation:
                lines.append(f"- **Bay**: {mission.bay_designation}")
            
            if mission.flight_purpose:
                lines.append(f"- **Purpose**: {mission.flight_purpose}")
            
            if mission.pilot_name:
                lines.append(f"- **Pilot**: {mission.pilot_name}")
            
            if mission.weather_conditions:
                lines.append(f"- **Weather**: {mission.weather_conditions}")
            
            if mission.classification_confidence > 0:
                lines.append(f"- **Classification Confidence**: {mission.classification_confidence:.1%}")
                if mission.classification_method:
                    lines.append(f"- **Classification Method**: {mission.classification_method}")
            
            if mission.mission_notes:
                lines.append(f"- **Notes**: {mission.mission_notes}")
            
            lines.append("")
        
        # DJI-specific metadata (if any interesting fields found)
        if result.dji_metadata and len(result.dji_metadata) > 0:
            lines.append("## DJI Metadata")
            lines.append("")
            
            # Add first few DJI metadata fields (avoid overwhelming output)
            dji_count = 0
            for key, value in result.dji_metadata.items():
                if dji_count >= 10:  # Limit to first 10 entries
                    lines.append(f"- *(and {len(result.dji_metadata) - 10} more fields...)*")
                    break
                lines.append(f"- **{key}**: {value}")
                dji_count += 1
            
            lines.append("")
        
        # Processing information
        lines.append("## Processing Information")
        lines.append("")
        lines.append(f"- **Extraction Success**: {'✅ Yes' if result.extraction_success else '❌ No'}")
        
        if result.processing_duration:
            lines.append(f"- **Processing Time**: {result.processing_duration.total_seconds():.2f} seconds")
        
        if result.extraction_errors:
            lines.append(f"- **Errors**: {len(result.extraction_errors)}")
            for error in result.extraction_errors[:3]:  # Show first 3 errors
                lines.append(f"  - {error}")
            if len(result.extraction_errors) > 3:
                lines.append(f"  - *(and {len(result.extraction_errors) - 3} more...)*")
        
        if result.extraction_warnings:
            lines.append(f"- **Warnings**: {len(result.extraction_warnings)}")
            for warning in result.extraction_warnings[:3]:  # Show first 3 warnings
                lines.append(f"  - {warning}")
            if len(result.extraction_warnings) > 3:
                lines.append(f"  - *(and {len(result.extraction_warnings) - 3} more...)*")
        
        lines.append("")
        
        # Thumbnail link (placeholder for Phase 2)
        lines.append("## Media")
        lines.append("")
        lines.append("### Thumbnail")
        lines.append("")
        lines.append(f"![{video.filename} thumbnail](thumbnails/{video.filename}_thumbnail.jpg)")
        lines.append("")
        lines.append("*Thumbnail will be generated in Phase 2 implementation*")
        lines.append("")
        
        # Footer
        lines.append("---")
        lines.append("")
        lines.append(f"*Generated by drone_metadata_automation on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        
        return "\n".join(lines)
