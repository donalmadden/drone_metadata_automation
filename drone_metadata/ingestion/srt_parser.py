"""
SRT parser for DJI video subtitle files.

This module handles parsing SRT files that contain frame-by-frame
camera settings and GPS coordinates at 25Hz sampling rate.
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import logging

from ..models import (
    SRTFrame, CameraSettings, GPSPoint, MediaEvent, MediaType,
    FlightData
)

logger = logging.getLogger(__name__)


class SRTParseError(Exception):
    """Raised when SRT parsing fails."""
    pass


class SRTParser:
    """Parser for DJI SRT subtitle files with camera and GPS metadata."""
    
    # Regex patterns for extracting metadata from SRT content
    METADATA_PATTERN = re.compile(
        r'\[iso : (\d+)\] \[shutter : ([^\]]+)\] \[fnum : (\d+)\] '
        r'\[ev : ([^\]]+)\] \[ct : (\d+)\] \[color_md : ([^\]]+)\] '
        r'\[focal_len : (\d+)\] \[latitude: ([^\]]+)\] '
        r'\[longitude: ([^\]]+)\] \[altitude: ([^\]]+)\]'
    )
    
    TIMESTAMP_PATTERN = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})')
    
    def __init__(self):
        """Initialize SRT parser."""
        pass
    
    def parse_srt(self, file_path: str) -> List[SRTFrame]:
        """
        Parse SRT file and extract frame-by-frame metadata.
        
        Args:
            file_path: Path to SRT subtitle file
            
        Returns:
            List of SRTFrame objects with metadata
            
        Raises:
            SRTParseError: If parsing fails
        """
        try:
            path_obj = Path(file_path)
            if not path_obj.exists():
                raise SRTParseError(f"SRT file not found: {file_path}")
            
            logger.info(f"Parsing SRT file: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            frames = self._parse_srt_content(content)
            
            logger.info(f"Parsed {len(frames)} SRT frames from {file_path}")
            return frames
            
        except Exception as e:
            raise SRTParseError(f"Failed to parse SRT {file_path}: {str(e)}") from e
    
    def extract_camera_profile(self, srt_frames: List[SRTFrame]) -> Dict[str, any]:
        """
        Extract camera profile statistics from SRT frames.
        
        Args:
            srt_frames: List of parsed SRT frames
            
        Returns:
            Dictionary with camera statistics
        """
        if not srt_frames:
            return {}
        
        # Collect all camera settings
        iso_values = []
        shutter_speeds = []
        apertures = []
        focal_lengths = []
        color_temps = []
        
        for frame in srt_frames:
            settings = frame.camera_settings
            if settings.iso is not None:
                iso_values.append(settings.iso)
            if settings.shutter_speed:
                shutter_speeds.append(settings.shutter_speed)
            if settings.aperture:
                apertures.append(settings.aperture)
            if settings.focal_length is not None:
                focal_lengths.append(settings.focal_length)
            if settings.color_temperature is not None:
                color_temps.append(settings.color_temperature)
        
        profile = {
            'total_frames': len(srt_frames),
            'duration_seconds': len(srt_frames) * 0.04,  # 25fps = 0.04s per frame
        }
        
        if iso_values:
            profile['iso'] = {
                'min': min(iso_values),
                'max': max(iso_values),
                'avg': sum(iso_values) / len(iso_values),
                'most_common': max(set(iso_values), key=iso_values.count)
            }
        
        if focal_lengths:
            profile['focal_length'] = {
                'min': min(focal_lengths),
                'max': max(focal_lengths),
                'avg': sum(focal_lengths) / len(focal_lengths)
            }
        
        if color_temps:
            profile['color_temperature'] = {
                'min': min(color_temps),
                'max': max(color_temps),
                'avg': sum(color_temps) / len(color_temps)
            }
        
        profile['unique_shutter_speeds'] = list(set(shutter_speeds))
        profile['unique_apertures'] = list(set(apertures))
        
        return profile
    
    def correlate_with_video(
        self, 
        srt_frames: List[SRTFrame], 
        video_path: str,
        base_timestamp: Optional[datetime] = None
    ) -> List[MediaEvent]:
        """
        Correlate SRT frames with video file to create media events.
        
        Args:
            srt_frames: Parsed SRT frames
            video_path: Path to corresponding video file
            base_timestamp: Base timestamp for absolute time calculation
            
        Returns:
            List of MediaEvent objects
        """
        if not srt_frames:
            return []
        
        # Use first frame timestamp as base if not provided
        if base_timestamp is None:
            base_timestamp = srt_frames[0].timestamp_absolute
        
        media_events = []
        
        # Create video start event from first frame
        first_frame = srt_frames[0]
        start_event = MediaEvent(
            timestamp=first_frame.timestamp_absolute,
            event_type=MediaType.VIDEO_START,
            location=first_frame.location,
            camera_settings=first_frame.camera_settings,
            file_path=video_path
        )
        media_events.append(start_event)
        
        # Create video end event from last frame
        if len(srt_frames) > 1:
            last_frame = srt_frames[-1]
            duration = last_frame.timestamp_absolute - first_frame.timestamp_absolute
            
            end_event = MediaEvent(
                timestamp=last_frame.timestamp_absolute,
                event_type=MediaType.VIDEO_END,
                location=last_frame.location,
                camera_settings=last_frame.camera_settings,
                file_path=video_path,
                duration=duration
            )
            media_events.append(end_event)
        
        logger.info(f"Created {len(media_events)} media events for {video_path}")
        return media_events
    
    def _parse_srt_content(self, content: str) -> List[SRTFrame]:
        """Parse SRT content into frames."""
        frames = []
        
        # Split content into individual subtitle blocks
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            if not block.strip():
                continue
                
            try:
                frame = self._parse_srt_block(block)
                if frame:
                    frames.append(frame)
            except Exception as e:
                logger.warning(f"Failed to parse SRT block: {e}")
                continue
        
        return frames
    
    def _parse_srt_block(self, block: str) -> Optional[SRTFrame]:
        """Parse individual SRT subtitle block."""
        lines = block.strip().split('\n')
        
        if len(lines) < 3:
            return None
        
        try:
            # Parse frame number
            frame_number = int(lines[0])
            
            # Parse timestamp range
            timestamp_line = lines[1]
            timestamps = timestamp_line.split(' --> ')
            if len(timestamps) != 2:
                return None
                
            timestamp_start = timestamps[0].strip()
            timestamp_end = timestamps[1].strip()
            
            # Parse content with metadata
            content_lines = lines[2:]
            metadata_content = ' '.join(content_lines)
            
            # Extract absolute timestamp (first timestamp in content)
            absolute_timestamp = self._extract_absolute_timestamp(metadata_content)
            
            # Extract camera settings and GPS
            camera_settings, gps_point = self._parse_metadata(
                metadata_content, absolute_timestamp
            )
            
            if not gps_point:
                return None
            
            return SRTFrame(
                frame_number=frame_number,
                timestamp_start=timestamp_start,
                timestamp_end=timestamp_end,
                timestamp_absolute=absolute_timestamp,
                camera_settings=camera_settings,
                location=gps_point
            )
            
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse SRT block: {e}")
            return None
    
    def _extract_absolute_timestamp(self, content: str) -> datetime:
        """Extract absolute timestamp from SRT content."""
        # Look for timestamp pattern like "2025-08-27 15:27:47,428,379"
        timestamp_match = re.search(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}),(\d{3})',
            content
        )
        
        if timestamp_match:
            timestamp_str = timestamp_match.group(1)
            milliseconds = int(timestamp_match.group(2))
            
            # Parse base timestamp
            base_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            
            # Add milliseconds
            return base_time + timedelta(milliseconds=milliseconds)
        
        # Fallback to current time if no timestamp found
        logger.warning("No absolute timestamp found in SRT content")
        return datetime.now()
    
    def _parse_metadata(
        self, 
        content: str, 
        timestamp: datetime
    ) -> tuple[CameraSettings, Optional[GPSPoint]]:
        """Parse camera settings and GPS from SRT content."""
        camera_settings = CameraSettings()
        gps_point = None
        
        # Extract metadata using regex
        match = self.METADATA_PATTERN.search(content)
        
        if match:
            try:
                # Camera settings
                camera_settings.iso = int(match.group(1))
                camera_settings.shutter_speed = match.group(2)
                camera_settings.aperture = match.group(3)  # fnum as string
                camera_settings.exposure_compensation = float(match.group(4))
                camera_settings.color_temperature = int(match.group(5))
                camera_settings.color_mode = match.group(6)
                camera_settings.focal_length = int(match.group(7))
                
                # GPS coordinates
                latitude = float(match.group(8))
                longitude = float(match.group(9))
                altitude = float(match.group(10))
                
                gps_point = GPSPoint(
                    latitude=latitude,
                    longitude=longitude,
                    altitude=altitude,
                    timestamp=timestamp
                )
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse metadata values: {e}")
        else:
            logger.warning("No metadata pattern match found in SRT content")
        
        return camera_settings, gps_point
    
    def get_video_coverage_events(
        self, 
        srt_frames: List[SRTFrame],
        sample_rate: int = 5
    ) -> List[MediaEvent]:
        """
        Generate coverage events by sampling SRT frames.
        
        Args:
            srt_frames: All SRT frames
            sample_rate: Take every Nth frame (5 = every 5th frame = 5Hz from 25Hz)
            
        Returns:
            List of sampled MediaEvent objects for coverage analysis
        """
        if not srt_frames:
            return []
        
        coverage_events = []
        
        # Sample frames at specified rate
        for i in range(0, len(srt_frames), sample_rate):
            frame = srt_frames[i]
            
            event = MediaEvent(
                timestamp=frame.timestamp_absolute,
                event_type=MediaType.VIDEO_START,  # Use as coverage point
                location=frame.location,
                camera_settings=frame.camera_settings
            )
            coverage_events.append(event)
        
        logger.info(
            f"Generated {len(coverage_events)} coverage events "
            f"from {len(srt_frames)} SRT frames (sample rate: {sample_rate})"
        )
        
        return coverage_events
