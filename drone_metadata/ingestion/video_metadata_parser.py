"""
Video Metadata Parser for Drone Videos
======================================

This module provides the VideoMetadataParser class for extracting comprehensive
metadata from drone video files (primarily MP4). It uses multiple libraries to
extract as much metadata as possible:

- ffmpeg via ffmpeg-python for technical video metadata
- hachoir for parsing the MP4 container format  
- exifread as a fallback for EXIF metadata
- pymediainfo for detailed technical specifications

The parser follows the same architectural pattern as AirdataParser for consistency
within the drone_metadata_automation project.
"""

import os
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

# Optional imports with graceful fallback
try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False

try:
    from hachoir.parser import createParser
    from hachoir.metadata import extractMetadata
    HACHOIR_AVAILABLE = True
except ImportError:
    HACHOIR_AVAILABLE = False

try:
    import exifread
    EXIFREAD_AVAILABLE = True
except ImportError:
    EXIFREAD_AVAILABLE = False

try:
    from pymediainfo import MediaInfo
    PYMEDIAINFO_AVAILABLE = True
except ImportError:
    PYMEDIAINFO_AVAILABLE = False


logger = logging.getLogger(__name__)


class VideoMetadataParsingError(Exception):
    """Exception raised for errors during video metadata parsing."""
    pass


class MissingDependencyError(Exception):
    """Exception raised when required libraries are missing."""
    pass


@dataclass
class VideoMetadataExtractionResult:
    """Result of video metadata extraction containing all extracted data."""
    success: bool
    file_path: str
    file_info: Dict[str, Any] = field(default_factory=dict)
    ffmpeg_metadata: Dict[str, Any] = field(default_factory=dict)
    hachoir_metadata: Dict[str, Any] = field(default_factory=dict)
    exif_metadata: Dict[str, Any] = field(default_factory=dict)
    mediainfo_metadata: Dict[str, Any] = field(default_factory=dict)
    gps_data: Dict[str, Any] = field(default_factory=dict)
    dji_specific: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class VideoMetadataParser:
    """
    Parser for extracting comprehensive metadata from drone video files.
    
    This class provides a unified interface for extracting metadata using
    multiple libraries and methods, with graceful fallback when libraries
    are missing.
    """
    
    def __init__(self, require_all_dependencies: bool = False):
        """
        Initialize the VideoMetadataParser.
        
        Args:
            require_all_dependencies: If True, raises MissingDependencyError
                                    if any metadata extraction libraries are missing.
                                    If False (default), gracefully handles missing libraries.
        """
        self.require_all_dependencies = require_all_dependencies
        self._check_dependencies()
        
    def _check_dependencies(self) -> None:
        """Check which metadata extraction libraries are available."""
        missing_libs = []
        
        if not FFMPEG_AVAILABLE:
            missing_libs.append("ffmpeg-python")
        if not HACHOIR_AVAILABLE:
            missing_libs.append("hachoir")
        if not EXIFREAD_AVAILABLE:
            missing_libs.append("exifread")
        if not PYMEDIAINFO_AVAILABLE:
            missing_libs.append("pymediainfo")
            
        if missing_libs:
            message = f"Missing video metadata libraries: {', '.join(missing_libs)}"
            if self.require_all_dependencies:
                raise MissingDependencyError(
                    f"{message}. Install with: pip install {' '.join(missing_libs)}"
                )
            else:
                logger.warning(f"{message}. Some metadata extraction will be unavailable.")
    
    def parse_video(self, file_path: str) -> VideoMetadataExtractionResult:
        """
        Extract comprehensive metadata from a video file.
        
        Args:
            file_path: Path to the video file to analyze
            
        Returns:
            VideoMetadataExtractionResult containing all extracted metadata
            
        Raises:
            VideoMetadataParsingError: If the file cannot be processed
        """
        file_path = str(Path(file_path).resolve())
        
        # Initialize result
        result = VideoMetadataExtractionResult(
            success=False,
            file_path=file_path
        )
        
        # Validate file
        try:
            self._validate_video_file(file_path)
        except Exception as e:
            result.errors.append(f"File validation failed: {str(e)}")
            return result
        
        # Extract basic file information
        try:
            result.file_info = self._extract_file_info(file_path)
        except Exception as e:
            result.errors.append(f"File info extraction failed: {str(e)}")
        
        # Extract metadata using different libraries
        if FFMPEG_AVAILABLE:
            try:
                result.ffmpeg_metadata = self._extract_ffmpeg_metadata(file_path)
            except Exception as e:
                result.errors.append(f"FFmpeg metadata extraction failed: {str(e)}")
                logger.exception("FFmpeg extraction error")
        
        if HACHOIR_AVAILABLE:
            try:
                result.hachoir_metadata = self._extract_hachoir_metadata(file_path)
            except Exception as e:
                result.errors.append(f"Hachoir metadata extraction failed: {str(e)}")
                logger.exception("Hachoir extraction error")
        
        if EXIFREAD_AVAILABLE:
            try:
                result.exif_metadata = self._extract_exif_metadata(file_path)
            except Exception as e:
                result.errors.append(f"EXIF metadata extraction failed: {str(e)}")
                logger.exception("EXIF extraction error")
        
        if PYMEDIAINFO_AVAILABLE:
            try:
                result.mediainfo_metadata = self._extract_mediainfo_metadata(file_path)
            except Exception as e:
                result.errors.append(f"MediaInfo metadata extraction failed: {str(e)}")
                logger.exception("MediaInfo extraction error")
        
        # Extract derived metadata
        try:
            all_metadata = {
                **result.ffmpeg_metadata,
                **result.hachoir_metadata,
                **result.exif_metadata,
                **result.mediainfo_metadata
            }
            
            result.gps_data = self._extract_gps_coordinates(all_metadata)
            result.dji_specific = self._extract_dji_specific_metadata(all_metadata)
        except Exception as e:
            result.errors.append(f"Derived metadata extraction failed: {str(e)}")
            logger.exception("Derived metadata extraction error")
        
        # Determine success
        result.success = (
            len(result.errors) == 0 or 
            any([result.ffmpeg_metadata, result.hachoir_metadata, 
                 result.exif_metadata, result.mediainfo_metadata])
        )
        
        return result
    
    def _validate_video_file(self, file_path: str) -> None:
        """Validate that the file exists and appears to be a video file."""
        if not os.path.isfile(file_path):
            raise VideoMetadataParsingError(f"File does not exist: {file_path}")
        
        # Check file extension (permissive check)
        valid_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp'}
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext not in valid_extensions:
            logger.warning(
                f"File '{file_path}' has extension '{file_ext}' which may not be a video file"
            )
    
    def _extract_file_info(self, file_path: str) -> Dict[str, Any]:
        """Extract basic file information."""
        path_obj = Path(file_path)
        stat = path_obj.stat()
        
        return {
            "filename": path_obj.name,
            "filepath": str(path_obj.absolute()),
            "filesize_bytes": stat.st_size,
            "filesize_mb": stat.st_size / (1024 * 1024),
            "last_modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "extraction_time": datetime.datetime.now().isoformat()
        }
    
    def _extract_ffmpeg_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata using FFmpeg."""
        if not FFMPEG_AVAILABLE:
            return {}
        
        try:
            probe = ffmpeg.probe(file_path)
            
            return {
                "ffmpeg_format": probe.get("format", {}),
                "video_streams": [
                    stream for stream in probe.get("streams", []) 
                    if stream.get("codec_type") == "video"
                ],
                "audio_streams": [
                    stream for stream in probe.get("streams", []) 
                    if stream.get("codec_type") == "audio"
                ],
                "subtitle_streams": [
                    stream for stream in probe.get("streams", []) 
                    if stream.get("codec_type") == "subtitle"
                ]
            }
        except Exception as e:
            logger.error(f"FFmpeg probe failed for {file_path}: {str(e)}")
            return {}
    
    def _extract_hachoir_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata using Hachoir."""
        if not HACHOIR_AVAILABLE:
            return {}
        
        try:
            parser = createParser(file_path)
            if not parser:
                return {}
            
            metadata = extractMetadata(parser)
            if not metadata:
                return {}
            
            # Convert hachoir metadata to dictionary
            metadata_dict = {}
            for line in metadata.exportPlaintext():
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    key = key.strip('- ')
                    metadata_dict[key] = value
            
            return {"hachoir_metadata": metadata_dict}
        except Exception as e:
            logger.error(f"Hachoir parsing failed for {file_path}: {str(e)}")
            return {}
    
    def _extract_exif_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract EXIF metadata using exifread."""
        if not EXIFREAD_AVAILABLE:
            return {}
        
        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f)
            
            # Convert tags to JSON-friendly format
            exif_data = {}
            for tag, value in tags.items():
                exif_data[tag] = str(value)
            
            return {"exif_metadata": exif_data}
        except Exception as e:
            logger.error(f"EXIF extraction failed for {file_path}: {str(e)}")
            return {}
    
    def _extract_mediainfo_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract detailed technical metadata using pymediainfo."""
        if not PYMEDIAINFO_AVAILABLE:
            return {}
        
        try:
            media_info = MediaInfo.parse(file_path)
            
            # Convert to dictionary
            info_dict = {"tracks": []}
            for track in media_info.tracks:
                track_dict = {}
                for key, value in track.__dict__.items():
                    if not key.startswith('_') and value is not None:
                        track_dict[key] = value
                info_dict["tracks"].append(track_dict)
            
            return {"mediainfo": info_dict}
        except Exception as e:
            logger.error(f"MediaInfo extraction failed for {file_path}: {str(e)}")
            return {}
    
    def _extract_dji_specific_metadata(self, all_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract DJI-specific metadata from the combined metadata.
        
        This method searches for known DJI metadata fields across all extracted metadata.
        """
        dji_metadata = {"dji_specific": {}}
        
        # Patterns to search for in all metadata
        dji_patterns = [
            "dji", "drone", "gps", "altitude", "gimbal", "camera",
            "iso", "shutter", "aperture", "ev", "white balance",
            "latitude", "longitude", "xmp"
        ]
        
        def search_dict(d: Dict[str, Any], prefix: str = "") -> None:
            """Recursively search dictionaries for DJI patterns."""
            for key, value in d.items():
                current_key = f"{prefix}.{key}" if prefix else key
                
                # Check if this key or value contains any DJI patterns
                key_str = str(key).lower()
                value_str = str(value).lower() if not isinstance(value, dict) else ""
                
                if (any(pattern in key_str for pattern in dji_patterns) or 
                    any(pattern in value_str for pattern in dji_patterns)):
                    dji_metadata["dji_specific"][current_key] = value
                
                # Recurse if value is a dictionary
                if isinstance(value, dict):
                    search_dict(value, current_key)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            search_dict(item, f"{current_key}[{i}]")
        
        # Search through all metadata
        search_dict(all_metadata)
        
        return dji_metadata
    
    def _extract_gps_coordinates(self, all_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempt to extract GPS coordinates from metadata.
        
        DJI drones typically store GPS information in the metadata.
        """
        gps_info = {"gps": {}}
        
        # Common GPS field patterns in various metadata formats
        lat_patterns = ["latitude", "lat", "gpslatitude"]
        long_patterns = ["longitude", "lon", "long", "gpslongitude"]
        alt_patterns = ["altitude", "alt", "gpsaltitude", "relative_altitude", "height"]
        lat_ref_patterns = ["latituderef", "gpslatituderef", "lat_ref"]
        long_ref_patterns = ["longituderef", "gpslongituderef", "long_ref"]
        
        def find_by_pattern(d: Dict[str, Any], patterns: List[str], path: str = "") -> List[tuple]:
            """Find values matching patterns in nested dictionaries."""
            results = []
            for key, value in d.items():
                current_path = f"{path}.{key}" if path else key
                key_lower = str(key).lower()
                
                # Check if key matches any pattern
                if any(pattern in key_lower for pattern in patterns):
                    results.append((current_path, value))
                
                # Recurse into nested structures
                if isinstance(value, dict):
                    results.extend(find_by_pattern(value, patterns, current_path))
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            results.extend(find_by_pattern(item, patterns, f"{current_path}[{i}]"))
            
            return results
        
        # Find GPS coordinate values
        lat_results = find_by_pattern(all_metadata, lat_patterns)
        long_results = find_by_pattern(all_metadata, long_patterns)
        alt_results = find_by_pattern(all_metadata, alt_patterns)
        lat_ref_results = find_by_pattern(all_metadata, lat_ref_patterns)
        long_ref_results = find_by_pattern(all_metadata, long_ref_patterns)
        
        # Store raw results
        if lat_results:
            gps_info["gps"]["latitude_raw"] = lat_results
        if long_results:
            gps_info["gps"]["longitude_raw"] = long_results
        if alt_results:
            gps_info["gps"]["altitude_raw"] = alt_results
        if lat_ref_results:
            gps_info["gps"]["latitude_ref_raw"] = lat_ref_results
        if long_ref_results:
            gps_info["gps"]["longitude_ref_raw"] = long_ref_results
        
        # Attempt to parse decimal coordinates from EXIF format
        for lat_path, lat_value in lat_results:
            if "exif" in lat_path.lower() and isinstance(lat_value, str):
                try:
                    decimal_lat = self._parse_exif_gps_coordinate(
                        lat_value, lat_ref_results, is_latitude=True
                    )
                    if decimal_lat is not None:
                        gps_info["gps"]["latitude_decimal"] = decimal_lat
                        break
                except Exception:
                    continue
        
        for long_path, long_value in long_results:
            if "exif" in long_path.lower() and isinstance(long_value, str):
                try:
                    decimal_long = self._parse_exif_gps_coordinate(
                        long_value, long_ref_results, is_latitude=False
                    )
                    if decimal_long is not None:
                        gps_info["gps"]["longitude_decimal"] = decimal_long
                        break
                except Exception:
                    continue
        
        return gps_info
    
    def _parse_exif_gps_coordinate(self, coord_value: str, ref_results: List[tuple], 
                                  is_latitude: bool) -> Optional[float]:
        """
        Parse EXIF GPS coordinate format (degrees, minutes, seconds) to decimal degrees.
        
        Args:
            coord_value: GPS coordinate string like "[51, 30, 32.5]"
            ref_results: Reference direction results (N/S for lat, E/W for long)
            is_latitude: True if parsing latitude, False for longitude
            
        Returns:
            Decimal degrees coordinate or None if parsing fails
        """
        try:
            # Default references
            default_ref = "N" if is_latitude else "E"
            ref_directions = ("N", "S") if is_latitude else ("E", "W")
            
            # Find reference direction
            ref = default_ref
            for ref_path, ref_value in ref_results:
                if isinstance(ref_value, str) and ref_value in ref_directions:
                    ref = ref_value
                    break
            
            # Parse coordinate value like "[51, 30, 32.5]"
            if "[" in coord_value and "]" in coord_value:
                parts = coord_value.strip("[]").split(", ")
                if len(parts) >= 3:
                    degrees = float(parts[0])
                    minutes = float(parts[1])
                    seconds = float(parts[2])
                    
                    decimal_degrees = degrees + minutes / 60 + seconds / 3600
                    
                    # Apply reference direction
                    if ref in ("S", "W"):
                        decimal_degrees = -decimal_degrees
                    
                    return decimal_degrees
        except Exception:
            pass
        
        return None
    
    def get_available_libraries(self) -> Dict[str, bool]:
        """Return a dictionary showing which metadata extraction libraries are available."""
        return {
            "ffmpeg-python": FFMPEG_AVAILABLE,
            "hachoir": HACHOIR_AVAILABLE, 
            "exifread": EXIFREAD_AVAILABLE,
            "pymediainfo": PYMEDIAINFO_AVAILABLE
        }