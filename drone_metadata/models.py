"""
Core data models for drone metadata automation system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

import pandas as pd
import numpy as np


class InspectionType(Enum):
    """Types of drone inspections."""
    OVERVIEW = "overview"
    DETAILED = "detailed"
    ANGLES = "angles"
    SURVEY = "survey"
    PERIMETER = "perimeter"
    EMERGENCY = "emergency"


class FlightPhase(Enum):
    """Flight phases based on flycState from telemetry."""
    MOTORS_STARTED = "Motors_Started"
    ASSISTED_TAKEOFF = "Assisted_Takeoff"
    P_GPS = "P-GPS"
    HOVERING = "Hovering"
    LANDING = "Landing"
    MOTORS_STOPPED = "Motors_Stopped"


class MediaType(Enum):
    """Types of media files."""
    PHOTO = "photo"
    VIDEO_START = "video_start"
    VIDEO_END = "video_end"


@dataclass
class GPSPoint:
    """GPS coordinates with metadata."""
    latitude: float
    longitude: float
    altitude: float
    timestamp: datetime
    accuracy: Optional[float] = None  # Number of satellites
    
    def __post_init__(self) -> None:
        """Validate GPS coordinates."""
        if not (-90 <= self.latitude <= 90):
            raise ValueError(f"Invalid latitude: {self.latitude}")
        if not (-180 <= self.longitude <= 180):
            raise ValueError(f"Invalid longitude: {self.longitude}")


@dataclass
class GPSBounds:
    """GPS bounding box for areas."""
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    
    def contains_point(self, point: GPSPoint) -> bool:
        """Check if point is within bounds."""
        return (
            self.min_lat <= point.latitude <= self.max_lat and
            self.min_lon <= point.longitude <= self.max_lon
        )


@dataclass
class CameraSettings:
    """Camera settings extracted from SRT or EXIF data."""
    iso: Optional[int] = None
    shutter_speed: Optional[str] = None
    aperture: Optional[str] = None  # fnum
    exposure_compensation: Optional[float] = None  # ev
    color_temperature: Optional[int] = None  # ct
    color_mode: Optional[str] = None
    focal_length: Optional[int] = None


@dataclass
class MediaEvent:
    """Media capture event with location and camera data."""
    timestamp: datetime
    event_type: MediaType
    location: GPSPoint
    camera_settings: CameraSettings
    file_path: Optional[str] = None
    duration: Optional[timedelta] = None  # For videos


@dataclass
class FlightPhases:
    """Flight phase transitions and durations."""
    phases: List[Tuple[FlightPhase, datetime, datetime]] = field(default_factory=list)
    
    def get_phase_duration(self, phase: FlightPhase) -> timedelta:
        """Get total duration for a specific phase."""
        total = timedelta()
        for p, start, end in self.phases:
            if p == phase:
                total += (end - start)
        return total
    
    def get_total_flight_time(self) -> timedelta:
        """Get total flight time from first to last phase."""
        if not self.phases:
            return timedelta()
        
        start_time = min(start for _, start, _ in self.phases)
        end_time = max(end for _, _, end in self.phases)
        return end_time - start_time


@dataclass
class FlightMetrics:
    """Computed flight performance metrics."""
    max_altitude: float
    avg_altitude: float
    min_altitude: float
    max_speed: float
    avg_speed: float
    total_distance: float
    battery_start: float
    battery_end: float
    battery_consumed: float
    gps_quality_avg: float
    max_satellites: int
    min_satellites: int
    
    def get_altitude_range(self) -> float:
        """Get altitude variation range."""
        return self.max_altitude - self.min_altitude
    
    def get_battery_efficiency(self) -> float:
        """Battery consumption per distance (% per mile)."""
        if self.total_distance == 0:
            return 0.0
        return self.battery_consumed / self.total_distance


@dataclass
class FlightData:
    """Complete flight data container."""
    flight_id: str
    timestamp_start: datetime
    timestamp_end: datetime
    duration: timedelta
    telemetry: pd.DataFrame
    media_events: List[MediaEvent] = field(default_factory=list)
    flight_phases: Optional[FlightPhases] = None
    source_files: Dict[str, str] = field(default_factory=dict)  # file_type -> path


@dataclass
class SRTFrame:
    """Single frame from SRT subtitle file."""
    frame_number: int
    timestamp_start: str  # SRT format: "00:00:00,000"
    timestamp_end: str
    timestamp_absolute: datetime
    camera_settings: CameraSettings
    location: GPSPoint


@dataclass
class BayConfig:
    """Bay configuration from database."""
    bay_id: str
    name: str
    bay_type: str
    coordinates: GPSBounds
    inspection_types: List[InspectionType]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BayMapping:
    """Result of mapping flight to bay."""
    bay_id: str
    bay_name: str
    bay_config: BayConfig
    inspection_type: InspectionType
    confidence_score: float  # 0.0 to 1.0
    coverage_percentage: float  # Percentage of bay covered by flight
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Check if mapping confidence is above threshold."""
        return self.confidence_score >= threshold


@dataclass
class FlightPath:
    """Analyzed flight path with geometric properties."""
    coordinates: List[GPSPoint]
    total_distance: float
    bounding_box: GPSBounds
    centroid: GPSPoint
    is_circular: bool
    is_linear: bool
    circuit_completion: float  # 0.0 to 1.0 for circular patterns
    
    def get_path_density(self) -> float:
        """Points per square meter of bounding box."""
        # Simple approximation - would need proper geographic calculation
        lat_range = self.bounding_box.max_lat - self.bounding_box.min_lat
        lon_range = self.bounding_box.max_lon - self.bounding_box.min_lon
        area_approx = lat_range * lon_range * 111000 * 111000  # rough m²
        return len(self.coordinates) / max(area_approx, 1.0)


@dataclass
class FlightPattern:
    """Classified flight pattern."""
    pattern_type: str
    confidence: float
    characteristics: Dict[str, Any]
    
    # Common pattern types:
    # - "perimeter_inspection"
    # - "grid_survey" 
    # - "point_of_interest"
    # - "linear_infrastructure"
    # - "hover_detailed"


@dataclass
class Anomaly:
    """Detected anomaly in flight data."""
    timestamp: datetime
    anomaly_type: str
    severity: str  # "low", "medium", "high", "critical"
    description: str
    affected_metrics: List[str]
    suggested_action: Optional[str] = None


@dataclass
class QualityScore:
    """Flight quality assessment."""
    overall_score: float  # 0.0 to 1.0
    gps_quality: float
    battery_health: float
    flight_stability: float
    coverage_quality: float
    equipment_performance: float
    
    def get_grade(self) -> str:
        """Convert score to letter grade."""
        if self.overall_score >= 0.9:
            return "A"
        elif self.overall_score >= 0.8:
            return "B"
        elif self.overall_score >= 0.7:
            return "C"
        elif self.overall_score >= 0.6:
            return "D"
        else:
            return "F"


@dataclass
class InspectionClassification:
    """Classification of inspection type and quality."""
    inspection_type: InspectionType
    confidence: float
    sub_type: Optional[str] = None
    quality_indicators: Dict[str, float] = field(default_factory=dict)


@dataclass
class MediaSummary:
    """Summary of media captured during flight."""
    total_photos: int
    total_videos: int
    total_video_duration: timedelta
    media_files: List[str]
    coverage_events: List[MediaEvent]  # Media events correlated with locations


@dataclass
class FlightReport:
    """Complete automated flight report."""
    flight_id: str
    timestamp_generated: datetime
    
    # Core analysis results
    bay_mapping: Optional[BayMapping]
    flight_metrics: FlightMetrics
    flight_path: FlightPath
    inspection_classification: InspectionClassification
    media_summary: MediaSummary
    quality_score: QualityScore
    
    # Issues and anomalies
    anomalies: List[Anomaly] = field(default_factory=list)
    
    # Raw automated annotations
    automated_annotations: Dict[str, Any] = field(default_factory=dict)
    
    # Fields requiring human verification
    human_verification_needed: List[str] = field(default_factory=list)
    
    # Processing metadata
    processing_time: Optional[timedelta] = None
    confidence_flags: Dict[str, bool] = field(default_factory=dict)


@dataclass
class FlightDataset:
    """Complete dataset for a flight directory."""
    directory_path: str
    flight_data: Optional[FlightData] = None
    srt_files: List[str] = field(default_factory=list)
    media_files: List[str] = field(default_factory=list)
    flight_record_files: List[str] = field(default_factory=list)
    airdata_csv_files: List[str] = field(default_factory=list)
    
    # Derived information
    bay_identifier: Optional[str] = None
    inspection_type: Optional[InspectionType] = None
    
    def is_complete(self) -> bool:
        """Check if dataset has minimum required files."""
        return bool(
            self.flight_data and 
            (self.airdata_csv_files or self.srt_files) and
            self.media_files
        )


@dataclass
class ProcessingContext:
    """Context information for processing pipeline."""
    dataset: FlightDataset
    config: Dict[str, Any]
    bay_database: Dict[str, BayConfig]
    processing_start_time: datetime
    
    def get_processing_duration(self) -> timedelta:
        """Get elapsed processing time."""
        return datetime.now() - self.processing_start_time


@dataclass
class VideoMetadata:
    """Basic video file metadata and properties."""
    filename: str
    filepath: str
    filesize_bytes: int
    filesize_mb: float
    duration_seconds: Optional[float] = None
    creation_time: Optional[datetime] = None
    last_modified: datetime = field(default_factory=datetime.now)
    extraction_time: datetime = field(default_factory=datetime.now)
    file_hash: Optional[str] = None  # MD5 or similar for integrity checking
    
    def get_duration_formatted(self) -> str:
        """Get duration in MM:SS format."""
        if not self.duration_seconds:
            return "00:00"
        mins = int(self.duration_seconds // 60)
        secs = int(self.duration_seconds % 60)
        return f"{mins:02d}:{secs:02d}"


@dataclass
class TechnicalSpecs:
    """Technical video specifications and encoding details."""
    width: Optional[int] = None
    height: Optional[int] = None
    resolution_string: Optional[str] = None  # e.g., "3840x2160"
    video_codec: Optional[str] = None  # e.g., "h264"
    audio_codec: Optional[str] = None
    container_format: Optional[str] = None  # e.g., "mp4"
    bitrate_video: Optional[int] = None  # bits per second
    bitrate_audio: Optional[int] = None
    framerate: Optional[float] = None  # frames per second
    color_space: Optional[str] = None
    bit_depth: Optional[int] = None
    profile: Optional[str] = None  # codec profile
    level: Optional[str] = None  # codec level
    
    def get_aspect_ratio(self) -> Optional[float]:
        """Calculate aspect ratio from width/height."""
        if self.width and self.height:
            return self.width / self.height
        return None
    
    def is_4k(self) -> bool:
        """Check if video is 4K resolution."""
        return bool(self.width and self.width >= 3840)
    
    def is_hd(self) -> bool:
        """Check if video is HD resolution."""
        return bool(self.width and self.width >= 1280)


@dataclass
class GPSData:
    """GPS coordinate data extracted from video metadata."""
    latitude_decimal: Optional[float] = None
    longitude_decimal: Optional[float] = None
    altitude_meters: Optional[float] = None
    altitude_reference: Optional[str] = None  # "above_sea_level", "above_ground"
    coordinate_system: str = "WGS84"
    gps_accuracy: Optional[float] = None
    gps_timestamp: Optional[datetime] = None
    
    # Raw GPS data for debugging/verification
    raw_gps_data: Dict[str, Any] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        """Check if GPS coordinates are valid."""
        return (
            self.latitude_decimal is not None and 
            self.longitude_decimal is not None and
            -90 <= self.latitude_decimal <= 90 and
            -180 <= self.longitude_decimal <= 180
        )
    
    def to_gps_point(self) -> Optional[GPSPoint]:
        """Convert to existing GPSPoint model if data is valid."""
        if not self.is_valid():
            return None
        
        timestamp = self.gps_timestamp or datetime.now()
        altitude = self.altitude_meters or 0.0
        
        return GPSPoint(
            latitude=self.latitude_decimal,
            longitude=self.longitude_decimal,
            altitude=altitude,
            timestamp=timestamp,
            accuracy=self.gps_accuracy
        )


class MissionType(Enum):
    """Types of drone missions for video classification."""
    BOX = "box"
    SAFETY = "safety"


@dataclass
class MissionData:
    """Mission classification and parameters for drone videos."""
    mission_type: MissionType = MissionType.BOX
    bay_designation: Optional[str] = None
    mission_id: Optional[str] = None
    pilot_name: Optional[str] = None
    weather_conditions: Optional[str] = None
    flight_purpose: Optional[str] = None
    
    # Flight parameters
    max_altitude: Optional[float] = None
    flight_distance: Optional[float] = None
    battery_used_percent: Optional[float] = None
    
    # Classification confidence and metadata
    classification_confidence: float = 0.0  # 0.0 to 1.0
    classification_method: Optional[str] = None  # "filename", "metadata", "manual"
    mission_notes: Optional[str] = None
    
    def is_classified(self) -> bool:
        """Check if mission has been classified."""
        return self.mission_type in [MissionType.BOX, MissionType.SAFETY]
    
    def get_mission_code(self) -> str:
        """Get standardized mission code for filing/organization."""
        base_code = self.mission_type.value.upper()
        if self.bay_designation:
            return f"{base_code}_{self.bay_designation}"
        return base_code


@dataclass
class VideoAnalysisResult:
    """Complete result of video metadata analysis."""
    video_metadata: VideoMetadata
    technical_specs: TechnicalSpecs
    gps_data: Optional[GPSData] = None
    mission_data: Optional[MissionData] = None
    
    # DJI-specific extracted data
    dji_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Processing information
    extraction_success: bool = True
    extraction_errors: List[str] = field(default_factory=list)
    extraction_warnings: List[str] = field(default_factory=list)
    processing_duration: Optional[timedelta] = None
    
    # Raw metadata for debugging/advanced use
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_gps(self) -> bool:
        """Check if valid GPS data is available."""
        return self.gps_data is not None and self.gps_data.is_valid()
    
    def get_summary_string(self) -> str:
        """Get a brief summary string for logging/display."""
        duration = self.video_metadata.get_duration_formatted()
        resolution = self.technical_specs.resolution_string or "Unknown"
        gps_status = "GPS" if self.has_gps() else "No GPS"
        mission = self.mission_data.mission_type.value if self.mission_data else "unclassified"
        
        return f"{self.video_metadata.filename} ({duration}, {resolution}, {gps_status}, {mission})"


@dataclass
class VideoProcessingBatch:
    """Batch processing results for multiple videos."""
    batch_id: str
    processing_start: datetime
    processing_end: Optional[datetime] = None
    source_directory: Optional[str] = None
    
    # Results
    video_results: List[VideoAnalysisResult] = field(default_factory=list)
    successful_count: int = 0
    failed_count: int = 0
    
    # Processing summary
    batch_errors: List[str] = field(default_factory=list)
    batch_warnings: List[str] = field(default_factory=list)
    
    def add_result(self, result: VideoAnalysisResult) -> None:
        """Add a video analysis result to the batch."""
        self.video_results.append(result)
        if result.extraction_success:
            self.successful_count += 1
        else:
            self.failed_count += 1
    
    def get_processing_duration(self) -> Optional[timedelta]:
        """Get total batch processing time."""
        if self.processing_end:
            return self.processing_end - self.processing_start
        return None
    
    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        total = self.successful_count + self.failed_count
        if total == 0:
            return 0.0
        return (self.successful_count / total) * 100.0


# Type aliases for complex types
TelemetryData = pd.DataFrame
CoordinateList = List[Tuple[float, float]]  # (lat, lon) pairs
TimestampRange = Tuple[datetime, datetime]
ConfigDict = Dict[str, Any]
VideoMetadataDict = Dict[str, Any]  # Raw video metadata dictionary
