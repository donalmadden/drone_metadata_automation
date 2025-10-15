"""
Thumbnail Generator
===================

This module provides the ThumbnailGenerator class for extracting
video thumbnails using FFmpeg.

Phase 2 Implementation: Real FFmpeg frame extraction with configurable
dimensions, timestamps, and quality settings.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Union

try:
    import ffmpeg
except ImportError:
    ffmpeg = None

from .base_formatter import BaseFormatter, FormatterError
from ..models import VideoAnalysisResult, VideoProcessingBatch

logger = logging.getLogger(__name__)


class ThumbnailGenerator(BaseFormatter):
    """
    Formatter for generating video thumbnails using FFmpeg.
    
    This formatter extracts frame thumbnails from video files at
    specified timestamps (default 3 seconds) with configurable
    dimensions and quality settings.
    
    Phase 2 Implementation: Full FFmpeg integration with real frame extraction.
    
    Configuration options:
    - thumbnail_timestamp: Time in seconds to extract frame (default: 3.0)
    - thumbnail_width: Width in pixels (default: 640)
    - thumbnail_quality: JPEG quality 1-31, lower is better (default: 2)
    - fallback_enabled: Use placeholder if FFmpeg fails (default: True)
    """
    
    def __init__(self, config):
        super().__init__(config)
        
        # Thumbnail configuration with defaults
        self.thumbnail_timestamp = getattr(config, 'thumbnail_timestamp', 3.0)
        self.thumbnail_width = getattr(config, 'thumbnail_width', 640)
        self.thumbnail_quality = getattr(config, 'thumbnail_quality', 2)  # Lower is better for FFmpeg
        self.fallback_enabled = getattr(config, 'fallback_enabled', True)
        
        # Check FFmpeg availability
        self.ffmpeg_available = self._check_ffmpeg_availability()
    
    def get_supported_extensions(self) -> List[str]:
        """Return supported file extensions."""
        return [".jpg", ".png"]
    
    def format_single_video(self, result: VideoAnalysisResult) -> List[Path]:
        """
        Generate a thumbnail for a single video analysis result.
        
        Args:
            result: Video analysis result to format
            
        Returns:
            List containing the path to the generated thumbnail file
        """
        video_name = result.video_metadata.filename
        video_path = result.video_metadata.filepath
        self._log_processing_start("thumbnail generation", video_name)
        
        # Create output filename (e.g., DJI_0593.MP4_thumbnail.jpg)
        output_filename = f"{video_name}_thumbnail.jpg"
        
        # Use organized output path if organizer is configured
        output_path = self._get_output_path(output_filename, result, '.jpg')
        
        # Check if file exists and handle accordingly
        if self._check_file_exists(output_path):
            return [output_path]
        
        # Phase 2: Real FFmpeg thumbnail generation
        try:
            if self.ffmpeg_available and video_path and Path(video_path).exists():
                success = self._generate_ffmpeg_thumbnail(video_path, output_path, result)
                if success:
                    self._log_processing_complete("thumbnail generation (FFmpeg)", video_name, output_path)
                    return [output_path]
                elif self.fallback_enabled:
                    logger.warning(f"FFmpeg thumbnail failed for {video_name}, falling back to placeholder")
                else:
                    raise FormatterError(f"FFmpeg thumbnail generation failed for {video_name}")
            
            # Fallback to placeholder if FFmpeg not available or failed
            if self.fallback_enabled:
                placeholder_content = self._create_placeholder_thumbnail(result)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(placeholder_content)
                
                self._log_processing_complete("thumbnail generation (placeholder)", video_name, output_path)
                return [output_path]
            else:
                raise FormatterError(f"FFmpeg not available and fallback disabled for {video_name}")
            
        except Exception as e:
            error_msg = f"Failed to create thumbnail for {video_name}: {str(e)}"
            self._log_processing_error("thumbnail generation", video_name, error_msg)
            raise FormatterError(error_msg)
    
    def format_batch(self, batch: VideoProcessingBatch) -> List[Path]:
        """
        Generate thumbnails for a batch of video analysis results.
        
        Args:
            batch: Batch of video analysis results to format
            
        Returns:
            List of paths to generated thumbnail files
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
    
    def _check_ffmpeg_availability(self) -> bool:
        """
        Check if FFmpeg is available for thumbnail generation.
        
        Returns:
            bool: True if FFmpeg is available, False otherwise
        """
        try:
            # Try ffmpeg-python library first
            if ffmpeg is not None:
                # Test if we can probe a non-existent file (will fail but confirm ffmpeg works)
                try:
                    ffmpeg.probe('nonexistent.mp4')
                except ffmpeg.Error:
                    # Expected error, but confirms ffmpeg is working
                    return True
                except Exception:
                    # Unexpected error, ffmpeg may not be available
                    pass
            
            # Fallback: try calling ffmpeg directly
            try:
                result = subprocess.run(['ffmpeg', '-version'], 
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.PIPE,
                                        text=True, 
                                        timeout=5)
                return result.returncode == 0
            except subprocess.TimeoutExpired:
                return False
            
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            logger.warning("FFmpeg not found or not working, will use placeholder thumbnails")
            return False
        except Exception as e:
            logger.warning(f"Error checking FFmpeg availability: {e}")
            return False
    
    def _generate_ffmpeg_thumbnail(self, video_path: Union[str, Path], 
                                   output_path: Union[str, Path], 
                                   result: VideoAnalysisResult) -> bool:
        """
        Generate thumbnail using FFmpeg.
        
        Args:
            video_path: Path to input video file
            output_path: Path where thumbnail should be saved
            result: Video analysis result for context
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            video_path = Path(video_path)
            output_path = Path(output_path)
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Method 1: Try ffmpeg-python library
            if ffmpeg is not None:
                try:
                    (
                        ffmpeg
                        .input(str(video_path), ss=self.thumbnail_timestamp)
                        .filter('scale', self.thumbnail_width, -1)  # -1 maintains aspect ratio
                        .output(str(output_path), vframes=1, q=self.thumbnail_quality)
                        .overwrite_output()
                        .run(quiet=True)
                    )
                    
                    # Verify the thumbnail was created
                    if output_path.exists() and output_path.stat().st_size > 0:
                        logger.info(f"FFmpeg thumbnail generated: {output_path} ({output_path.stat().st_size} bytes)")
                        return True
                        
                except ffmpeg.Error as e:
                    logger.warning(f"FFmpeg-python failed: {e.stderr.decode() if e.stderr else str(e)}")
                except Exception as e:
                    logger.warning(f"FFmpeg-python error: {str(e)}")
            
            # Method 2: Fallback to direct subprocess call
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-ss', str(self.thumbnail_timestamp),
                '-vframes', '1',
                '-vf', f'scale={self.thumbnail_width}:-1',
                '-q:v', str(self.thumbnail_quality),
                '-y',  # Overwrite output file
                str(output_path)
            ]
            
            result = subprocess.run(cmd, 
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True, 
                                    timeout=30)
            
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                logger.info(f"FFmpeg subprocess thumbnail generated: {output_path} ({output_path.stat().st_size} bytes)")
                return True
            else:
                logger.warning(f"FFmpeg subprocess failed (code {result.returncode}): {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg timeout generating thumbnail for {video_path}")
            return False
        except Exception as e:
            logger.error(f"Error generating FFmpeg thumbnail: {str(e)}")
            return False
    
    def _create_placeholder_thumbnail(self, result: VideoAnalysisResult) -> str:
        """
        Create a placeholder file when FFmpeg is not available or fails.
        """
        ffmpeg_status = "Available" if self.ffmpeg_available else "Not Available"
        return f"""THUMBNAIL PLACEHOLDER
=====================

Video: {result.video_metadata.filename}
Duration: {result.video_metadata.get_duration_formatted()}
Resolution: {result.technical_specs.width or 'N/A'}x{result.technical_specs.height or 'N/A'}
FFmpeg Status: {ffmpeg_status}

This placeholder is used when FFmpeg thumbnail extraction is not available.

Configuration:
- Thumbnail timestamp: {self.thumbnail_timestamp}s
- Thumbnail width: {self.thumbnail_width}px
- Quality: {self.thumbnail_quality}
- Fallback enabled: {self.fallback_enabled}

To enable real thumbnails:
1. Install FFmpeg: https://ffmpeg.org/download.html
2. Or install ffmpeg-python: pip install ffmpeg-python
3. Ensure ffmpeg is in your PATH
"""
    
    def validate_config(self) -> None:
        """Validate thumbnail generator configuration."""
        super().validate_config()
        
        # Validate thumbnail-specific configuration
        if self.thumbnail_timestamp < 0:
            raise FormatterError("thumbnail_timestamp must be >= 0")
        
        if self.thumbnail_width <= 0:
            raise FormatterError("thumbnail_width must be > 0")
            
        if not (1 <= self.thumbnail_quality <= 31):
            raise FormatterError("thumbnail_quality must be between 1-31 (lower is better)")
        
        # Log FFmpeg availability status
        if self.ffmpeg_available:
            logger.info("FFmpeg is available for thumbnail generation")
        else:
            if self.fallback_enabled:
                logger.warning("FFmpeg not available, will use placeholder thumbnails")
            else:
                raise FormatterError("FFmpeg not available and fallback disabled")
    
    def get_formatter_info(self) -> dict:
        """Get information about this formatter."""
        info = super().get_formatter_info()
        info.update({
            "phase": "Phase 2 (FFmpeg Implementation)",
            "ffmpeg_available": self.ffmpeg_available,
            "configuration": {
                "thumbnail_timestamp": self.thumbnail_timestamp,
                "thumbnail_width": self.thumbnail_width,
                "thumbnail_quality": self.thumbnail_quality,
                "fallback_enabled": self.fallback_enabled
            },
            "implemented_features": [
                "Real FFmpeg frame extraction",
                "Configurable thumbnail dimensions and timestamp",
                "Quality control (JPEG quality settings)",
                "Graceful fallback to placeholder when FFmpeg unavailable",
                "Subprocess and ffmpeg-python library support"
            ],
            "future_features": [
                "Multiple output formats (PNG, WebP)",
                "Mission-based thumbnail organization",
                "Batch processing optimization with parallel execution",
                "Smart timestamp selection (avoid black frames)"
            ]
        })
        return info
