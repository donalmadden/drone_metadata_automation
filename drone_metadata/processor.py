"""
Main processing orchestrator for drone metadata automation.

This module coordinates all data ingestion, analysis, and report generation
components to produce automated metadata from flight directories.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd

from .models import (
    FlightDataset, FlightData, FlightReport, ProcessingContext,
    FlightMetrics, QualityScore, MediaSummary, Anomaly, 
    InspectionClassification, BayMapping, FlightPath, GPSPoint
)
from .ingestion.directory_scanner import DirectoryScanner, DirectoryScanError
from .ingestion.airdata_parser import AirdataParser, AirdataParseError  
from .ingestion.srt_parser import SRTParser, SRTParseError

logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    """Raised when processing fails."""
    pass


class DroneMetadataProcessor:
    """Main processor for automated drone metadata extraction."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize processor with configuration.
        
        Args:
            config: Processing configuration dictionary
        """
        self.config = config or self._get_default_config()
        
        # Initialize component parsers
        self.scanner = DirectoryScanner(
            case_sensitive=self.config.get('case_sensitive', False)
        )
        self.airdata_parser = AirdataParser(
            validate_columns=self.config.get('validate_csv_columns', True)
        )
        self.srt_parser = SRTParser()
        
        # Bay database (would be loaded from config in production)
        self.bay_database = self._load_bay_database()
        
        logger.info("DroneMetadataProcessor initialized")
    
    def process_flight_directory(self, directory_path: str) -> FlightReport:
        """
        Process a complete flight directory and generate metadata report.
        
        Args:
            directory_path: Path to flight directory
            
        Returns:
            FlightReport with automated metadata and analysis
            
        Raises:
            ProcessingError: If processing fails
        """
        processing_start = datetime.now()
        
        try:
            logger.info(f"Starting processing of flight directory: {directory_path}")
            
            # Step 1: Scan directory and discover data sources
            dataset = self._discover_data_sources(directory_path)
            
            # Step 2: Validate dataset completeness
            validation = self.scanner.validate_dataset_completeness(dataset)
            if not validation['is_complete']:
                logger.warning(f"Dataset validation issues: {validation}")
            
            # Step 3: Extract flight data from available sources
            flight_data = self._extract_flight_data(dataset)
            
            # Step 4: Compute flight metrics and analysis
            flight_metrics = self._compute_flight_metrics(flight_data)
            quality_score = self._assess_quality(flight_data, flight_metrics)
            media_summary = self._summarize_media(flight_data, dataset)
            
            # Step 5: Perform spatial and pattern analysis
            flight_path = self._analyze_flight_path(flight_data)
            bay_mapping = self._map_to_bay(flight_path, dataset.bay_identifier)
            inspection_classification = self._classify_inspection(
                flight_path, bay_mapping, dataset.inspection_type
            )
            
            # Step 6: Detect anomalies
            anomalies = self._detect_anomalies(flight_data, flight_metrics)
            
            # Step 7: Generate report
            processing_time = datetime.now() - processing_start
            
            report = FlightReport(
                flight_id=flight_data.flight_id,
                timestamp_generated=datetime.now(),
                bay_mapping=bay_mapping,
                flight_metrics=flight_metrics,
                flight_path=flight_path,
                inspection_classification=inspection_classification,
                media_summary=media_summary,
                quality_score=quality_score,
                anomalies=anomalies,
                processing_time=processing_time
            )
            
            # Add automated annotations
            report.automated_annotations = self._generate_annotations(report)
            
            # Identify fields needing human verification
            report.human_verification_needed = self._identify_verification_needed(report)
            
            logger.info(
                f"Processing completed in {processing_time.total_seconds():.2f}s. "
                f"Quality score: {quality_score.get_grade()}"
            )
            
            return report
            
        except Exception as e:
            raise ProcessingError(f"Failed to process directory {directory_path}: {str(e)}") from e
    
    def process_batch_directories(self, parent_directory: str) -> List[FlightReport]:
        """
        Process multiple flight directories in batch.
        
        Args:
            parent_directory: Parent directory containing flight subdirectories
            
        Returns:
            List of FlightReport objects
        """
        parent_path = Path(parent_directory)
        reports = []
        
        if not parent_path.exists() or not parent_path.is_dir():
            raise ProcessingError(f"Parent directory not found: {parent_directory}")
        
        # Find all subdirectories that look like flight data
        flight_dirs = []
        for item in parent_path.iterdir():
            if item.is_dir():
                # Quick check if directory contains flight data
                try:
                    dataset = self.scanner.scan_flight_directory(str(item))
                    validation = self.scanner.validate_dataset_completeness(dataset)
                    if validation.get('has_telemetry', False) or validation.get('has_media', False):
                        flight_dirs.append(str(item))
                except DirectoryScanError:
                    continue
        
        logger.info(f"Found {len(flight_dirs)} potential flight directories")
        
        # Process each directory
        for flight_dir in flight_dirs:
            try:
                report = self.process_flight_directory(flight_dir)
                reports.append(report)
                logger.info(f"Successfully processed: {flight_dir}")
            except ProcessingError as e:
                logger.error(f"Failed to process {flight_dir}: {e}")
                continue
        
        logger.info(f"Batch processing completed: {len(reports)}/{len(flight_dirs)} successful")
        return reports
    
    def _discover_data_sources(self, directory_path: str) -> FlightDataset:
        """Discover and categorize all data sources in directory."""
        return self.scanner.scan_flight_directory(directory_path)
    
    def _extract_flight_data(self, dataset: FlightDataset) -> FlightData:
        """Extract and merge flight data from available sources."""
        flight_data = None
        all_media_events = []
        
        # Process airdata CSV files (primary source)
        for csv_file in dataset.airdata_csv_files:
            try:
                csv_flight_data = self.airdata_parser.parse_csv(csv_file)
                if flight_data is None:
                    flight_data = csv_flight_data
                else:
                    # Merge multiple CSV files (combine telemetry)
                    flight_data.telemetry = pd.concat([
                        flight_data.telemetry, 
                        csv_flight_data.telemetry
                    ]).sort_values('datetime(utc)').reset_index(drop=True)
                    
                    flight_data.media_events.extend(csv_flight_data.media_events)
                    
                    # Update time range
                    flight_data.timestamp_start = min(
                        flight_data.timestamp_start, csv_flight_data.timestamp_start
                    )
                    flight_data.timestamp_end = max(
                        flight_data.timestamp_end, csv_flight_data.timestamp_end
                    )
                    flight_data.duration = flight_data.timestamp_end - flight_data.timestamp_start
                
            except AirdataParseError as e:
                logger.error(f"Failed to parse CSV {csv_file}: {e}")
        
        # Process SRT files for detailed camera metadata
        for srt_file in dataset.srt_files:
            try:
                srt_frames = self.srt_parser.parse_srt(srt_file)
                if srt_frames:
                    # Find corresponding video file
                    video_file = srt_file.replace('.SRT', '.MP4').replace('.srt', '.mp4')
                    
                    # Create media events from SRT
                    srt_media_events = self.srt_parser.correlate_with_video(
                        srt_frames, video_file
                    )
                    all_media_events.extend(srt_media_events)
                    
                    # If no flight data from CSV, create from SRT
                    if flight_data is None:
                        flight_data = self._create_flight_data_from_srt(srt_frames, dataset)
                    
            except SRTParseError as e:
                logger.error(f"Failed to parse SRT {srt_file}: {e}")
        
        # Fallback: create minimal flight data if none found
        if flight_data is None:
            flight_data = self._create_minimal_flight_data(dataset)
        
        # Add SRT-derived media events
        if all_media_events:
            flight_data.media_events.extend(all_media_events)
        
        # Update dataset with flight data
        dataset.flight_data = flight_data
        
        return flight_data
    
    def _compute_flight_metrics(self, flight_data: FlightData) -> FlightMetrics:
        """Compute comprehensive flight metrics."""
        if not flight_data.telemetry.empty:
            return self.airdata_parser.extract_flight_metrics(flight_data)
        else:
            # Fallback metrics from media events
            return self._compute_metrics_from_media(flight_data)
    
    def _assess_quality(self, flight_data: FlightData, metrics: FlightMetrics) -> QualityScore:
        """Assess overall flight quality."""
        # GPS quality (based on satellite count)
        gps_quality = min(metrics.gps_quality_avg / 15.0, 1.0)  # 15+ satellites = perfect
        
        # Battery health (penalize heavy consumption)
        battery_health = max(0.0, 1.0 - metrics.battery_consumed / 50.0)  # 50%+ consumption = poor
        
        # Flight stability (based on speed variance)
        if not flight_data.telemetry.empty and 'speed(mph)' in flight_data.telemetry.columns:
            speed_variance = flight_data.telemetry['speed(mph)'].var()
            flight_stability = max(0.0, 1.0 - speed_variance / 100.0)  # High variance = unstable
        else:
            flight_stability = 0.5  # Unknown
        
        # Coverage quality (based on media events)
        media_count = len(flight_data.media_events)
        expected_media = max(10, int(flight_data.duration.total_seconds() / 30))  # 1 event per 30s
        coverage_quality = min(media_count / expected_media, 1.0)
        
        # Equipment performance (based on no critical anomalies)
        equipment_performance = 0.9  # Default high, would be adjusted by anomaly detection
        
        # Overall score
        scores = [gps_quality, battery_health, flight_stability, coverage_quality, equipment_performance]
        overall_score = sum(scores) / len(scores)
        
        return QualityScore(
            overall_score=overall_score,
            gps_quality=gps_quality,
            battery_health=battery_health,
            flight_stability=flight_stability,
            coverage_quality=coverage_quality,
            equipment_performance=equipment_performance
        )
    
    def _summarize_media(self, flight_data: FlightData, dataset: FlightDataset) -> MediaSummary:
        """Create media summary from flight data and file discovery."""
        photo_events = [e for e in flight_data.media_events if 'photo' in e.event_type.value.lower()]
        video_events = [e for e in flight_data.media_events if 'video' in e.event_type.value.lower()]
        
        total_video_duration = timedelta()
        for event in video_events:
            if event.duration:
                total_video_duration += event.duration
        
        return MediaSummary(
            total_photos=len(photo_events),
            total_videos=len(video_events) // 2,  # Assuming start/end pairs
            total_video_duration=total_video_duration,
            media_files=dataset.media_files,
            coverage_events=flight_data.media_events
        )
    
    def _analyze_flight_path(self, flight_data: FlightData) -> FlightPath:
        """Analyze flight path geometry and characteristics."""
        if flight_data.telemetry.empty:
            # Fallback: use media event locations
            coordinates = [e.location for e in flight_data.media_events if e.location]
        else:
            # Extract coordinates from telemetry
            coordinates = []
            for _, row in flight_data.telemetry.iterrows():
                try:
                    gps_point = GPSPoint(
                        latitude=row['latitude'],
                        longitude=row['longitude'],
                        altitude=row.get('altitude(feet)', 0.0),
                        timestamp=row['datetime(utc)']
                    )
                    coordinates.append(gps_point)
                except (ValueError, TypeError):
                    continue
        
        if not coordinates:
            # Create minimal flight path
            return FlightPath(
                coordinates=[],
                total_distance=0.0,
                bounding_box=None,
                centroid=None,
                is_circular=False,
                is_linear=False,
                circuit_completion=0.0
            )
        
        # Compute bounding box
        lats = [p.latitude for p in coordinates]
        lons = [p.longitude for p in coordinates]
        
        from .models import GPSBounds
        bounding_box = GPSBounds(
            min_lat=min(lats),
            max_lat=max(lats),
            min_lon=min(lons),
            max_lon=max(lons)
        )
        
        # Compute centroid
        centroid = GPSPoint(
            latitude=sum(lats) / len(lats),
            longitude=sum(lons) / len(lons),
            altitude=sum(p.altitude for p in coordinates) / len(coordinates),
            timestamp=coordinates[0].timestamp
        )
        
        # Simple pattern detection
        is_circular = self._detect_circular_pattern(coordinates)
        is_linear = self._detect_linear_pattern(coordinates)
        circuit_completion = self._calculate_circuit_completion(coordinates)
        
        # Estimate total distance (simple haversine approximation)
        total_distance = self._calculate_path_distance(coordinates)
        
        return FlightPath(
            coordinates=coordinates,
            total_distance=total_distance,
            bounding_box=bounding_box,
            centroid=centroid,
            is_circular=is_circular,
            is_linear=is_linear,
            circuit_completion=circuit_completion
        )
    
    def _map_to_bay(self, flight_path: FlightPath, bay_hint: Optional[str]) -> Optional[BayMapping]:
        """Map flight path to bay configuration."""
        if bay_hint and bay_hint in self.bay_database:
            bay_config = self.bay_database[bay_hint]
            
            # Calculate coverage percentage (simplified)
            if flight_path.coordinates and flight_path.bounding_box:
                # Check if flight path overlaps with bay boundaries
                overlap_points = [
                    p for p in flight_path.coordinates 
                    if bay_config.coordinates.contains_point(p)
                ]
                coverage_percentage = len(overlap_points) / max(len(flight_path.coordinates), 1) * 100
                confidence_score = min(coverage_percentage / 100.0, 1.0)
            else:
                coverage_percentage = 0.0
                confidence_score = 0.5  # Medium confidence from directory name alone
            
            return BayMapping(
                bay_id=bay_hint,
                bay_name=bay_config.name,
                bay_config=bay_config,
                inspection_type=bay_config.inspection_types[0] if bay_config.inspection_types else None,
                confidence_score=confidence_score,
                coverage_percentage=coverage_percentage
            )
        
        return None
    
    def _classify_inspection(
        self, 
        flight_path: FlightPath, 
        bay_mapping: Optional[BayMapping],
        inspection_hint: Optional[Any]
    ) -> InspectionClassification:
        """Classify inspection type based on flight characteristics."""
        # Use hint if provided
        if inspection_hint:
            return InspectionClassification(
                inspection_type=inspection_hint,
                confidence=0.8,
                quality_indicators={'directory_hint': True}
            )
        
        # Use bay mapping if available
        if bay_mapping and bay_mapping.bay_config.inspection_types:
            return InspectionClassification(
                inspection_type=bay_mapping.bay_config.inspection_types[0],
                confidence=0.7,
                quality_indicators={'bay_mapping': True}
            )
        
        # Default classification
        from .models import InspectionType
        return InspectionClassification(
            inspection_type=InspectionType.SURVEY,
            confidence=0.5,
            quality_indicators={'default_classification': True}
        )
    
    def _detect_anomalies(self, flight_data: FlightData, metrics: FlightMetrics) -> List[Anomaly]:
        """Detect anomalies in flight data."""
        anomalies = []
        
        # Low battery anomaly
        if metrics.battery_consumed > 50:
            anomalies.append(Anomaly(
                timestamp=flight_data.timestamp_end,
                anomaly_type="high_battery_consumption",
                severity="medium",
                description=f"High battery consumption: {metrics.battery_consumed:.1f}%",
                affected_metrics=["battery_consumed"],
                suggested_action="Check flight duration and power management"
            ))
        
        # GPS quality anomaly
        if metrics.gps_quality_avg < 8:
            anomalies.append(Anomaly(
                timestamp=flight_data.timestamp_start,
                anomaly_type="poor_gps_quality",
                severity="medium",
                description=f"Low GPS satellite count: {metrics.gps_quality_avg:.1f}",
                affected_metrics=["gps_quality_avg"],
                suggested_action="Verify GPS positioning accuracy"
            ))
        
        return anomalies
    
    def _generate_annotations(self, report: FlightReport) -> Dict[str, Any]:
        """Generate automated annotations from report data."""
        annotations = {
            'flight_duration_minutes': report.flight_metrics.battery_consumed / 2.0,  # Rough estimate
            'max_altitude_ft': report.flight_metrics.max_altitude,
            'total_distance_miles': report.flight_metrics.total_distance,
            'media_captured': {
                'photos': report.media_summary.total_photos,
                'videos': report.media_summary.total_videos,
                'video_duration_minutes': report.media_summary.total_video_duration.total_seconds() / 60
            },
            'quality_grade': report.quality_score.get_grade(),
            'anomalies_detected': len(report.anomalies),
            'processing_timestamp': report.timestamp_generated.isoformat()
        }
        
        if report.bay_mapping:
            annotations['bay_identification'] = {
                'bay_id': report.bay_mapping.bay_id,
                'confidence': report.bay_mapping.confidence_score,
                'coverage_percent': report.bay_mapping.coverage_percentage
            }
        
        return annotations
    
    def _identify_verification_needed(self, report: FlightReport) -> List[str]:
        """Identify fields requiring human verification."""
        verification_needed = []
        
        # Low confidence bay mapping
        if not report.bay_mapping or not report.bay_mapping.is_high_confidence():
            verification_needed.append("bay_identification")
        
        # Low confidence inspection classification
        if report.inspection_classification.confidence < 0.8:
            verification_needed.append("inspection_type")
        
        # Quality issues
        if report.quality_score.overall_score < 0.7:
            verification_needed.append("flight_quality_assessment")
        
        # Anomalies present
        if report.anomalies:
            verification_needed.append("anomaly_review")
        
        return verification_needed
    
    # Helper methods for flight path analysis
    def _detect_circular_pattern(self, coordinates: List[GPSPoint]) -> bool:
        """Detect if flight follows circular pattern."""
        if len(coordinates) < 10:
            return False
        
        # Simple heuristic: check if start and end are close
        start = coordinates[0]
        end = coordinates[-1]
        distance = abs(start.latitude - end.latitude) + abs(start.longitude - end.longitude)
        return distance < 0.001  # Roughly 100m
    
    def _detect_linear_pattern(self, coordinates: List[GPSPoint]) -> bool:
        """Detect if flight follows linear pattern."""
        if len(coordinates) < 5:
            return False
        
        # Check if points roughly follow a straight line
        start = coordinates[0]
        end = coordinates[-1]
        
        # Calculate expected positions along straight line
        deviations = []
        for i, point in enumerate(coordinates[1:-1], 1):
            ratio = i / (len(coordinates) - 1)
            expected_lat = start.latitude + ratio * (end.latitude - start.latitude)
            expected_lon = start.longitude + ratio * (end.longitude - start.longitude)
            
            deviation = abs(point.latitude - expected_lat) + abs(point.longitude - expected_lon)
            deviations.append(deviation)
        
        avg_deviation = sum(deviations) / len(deviations) if deviations else 0
        return avg_deviation < 0.0005  # Roughly 50m deviation
    
    def _calculate_circuit_completion(self, coordinates: List[GPSPoint]) -> float:
        """Calculate how complete a circular circuit is."""
        if len(coordinates) < 3:
            return 0.0
        
        start = coordinates[0]
        end = coordinates[-1]
        distance = abs(start.latitude - end.latitude) + abs(start.longitude - end.longitude)
        
        # Convert to completion percentage (closer = more complete)
        max_distance = 0.002  # Roughly 200m
        completion = max(0.0, 1.0 - (distance / max_distance))
        return min(completion, 1.0)
    
    def _calculate_path_distance(self, coordinates: List[GPSPoint]) -> float:
        """Calculate total path distance in miles (simplified)."""
        if len(coordinates) < 2:
            return 0.0
        
        total_distance = 0.0
        for i in range(1, len(coordinates)):
            prev = coordinates[i-1]
            curr = coordinates[i]
            
            # Simple Euclidean approximation (not accurate but fast)
            lat_diff = curr.latitude - prev.latitude
            lon_diff = curr.longitude - prev.longitude
            distance = (lat_diff ** 2 + lon_diff ** 2) ** 0.5
            
            # Convert to miles (very rough approximation)
            total_distance += distance * 69  # Degrees to miles approximation
        
        return total_distance
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default processing configuration."""
        return {
            'case_sensitive': False,
            'validate_csv_columns': True,
            'quality_thresholds': {
                'min_gps_accuracy': 5,
                'max_altitude_variance': 50,
                'min_battery_level': 20,
                'max_speed_for_inspection': 15
            },
            'processing_timeouts': {
                'csv_parse_seconds': 30,
                'srt_parse_seconds': 60,
                'total_processing_seconds': 300
            }
        }
    
    def _load_bay_database(self) -> Dict[str, Any]:
        """Load bay database (placeholder - would load from config)."""
        from .models import BayConfig, GPSBounds, InspectionType
        
        return {
            '8B-7F': BayConfig(
                bay_id='8B-7F',
                name='Bay 8B-7F Primary Structure',
                bay_type='industrial_inspection',
                coordinates=GPSBounds(
                    min_lat=46.0130, max_lat=46.0135,
                    min_lon=13.2504, max_lon=13.2509
                ),
                inspection_types=[InspectionType.DETAILED, InspectionType.ANGLES]
            ),
            '8D': BayConfig(
                bay_id='8D',
                name='Bay 8D Secondary Structure',
                bay_type='infrastructure_survey', 
                coordinates=GPSBounds(
                    min_lat=46.0132, max_lat=46.0136,
                    min_lon=13.2506, max_lon=13.2510
                ),
                inspection_types=[InspectionType.SURVEY, InspectionType.ANGLES]
            )
        }
    
    def _create_flight_data_from_srt(self, srt_frames: List, dataset: FlightDataset) -> FlightData:
        """Create FlightData from SRT frames when no CSV available."""
        if not srt_frames:
            return self._create_minimal_flight_data(dataset)
        
        # Use SRT timing
        timestamp_start = srt_frames[0].timestamp_absolute
        timestamp_end = srt_frames[-1].timestamp_absolute
        duration = timestamp_end - timestamp_start
        
        # Create minimal telemetry from SRT
        telemetry_data = []
        for frame in srt_frames:
            telemetry_data.append({
                'datetime(utc)': frame.timestamp_absolute,
                'latitude': frame.location.latitude,
                'longitude': frame.location.longitude,
                'altitude(feet)': frame.location.altitude,
                'height_above_takeoff(feet)': frame.location.altitude,
                'speed(mph)': 0.0,  # Unknown from SRT
                'satellites': 10,  # Assume good GPS
                'battery_percent': 100.0  # Unknown
            })
        
        telemetry_df = pd.DataFrame(telemetry_data)
        
        return FlightData(
            flight_id=f"srt_{dataset.bay_identifier or 'unknown'}_{timestamp_start.strftime('%Y%m%d_%H%M')}",
            timestamp_start=timestamp_start,
            timestamp_end=timestamp_end,
            duration=duration,
            telemetry=telemetry_df,
            media_events=[],
            source_files={'srt_derived': ','.join(dataset.srt_files)}
        )
    
    def _create_minimal_flight_data(self, dataset: FlightDataset) -> FlightData:
        """Create minimal FlightData when no telemetry available."""
        timestamp = datetime.now()
        
        return FlightData(
            flight_id=f"minimal_{dataset.bay_identifier or 'unknown'}_{timestamp.strftime('%Y%m%d_%H%M')}",
            timestamp_start=timestamp,
            timestamp_end=timestamp,
            duration=timedelta(),
            telemetry=pd.DataFrame(),
            media_events=[],
            source_files={'directory': dataset.directory_path}
        )
    
    def _compute_metrics_from_media(self, flight_data: FlightData) -> FlightMetrics:
        """Compute basic metrics from media events when no telemetry."""
        return FlightMetrics(
            max_altitude=0.0,
            avg_altitude=0.0,
            min_altitude=0.0,
            max_speed=0.0,
            avg_speed=0.0,
            total_distance=0.0,
            battery_start=100.0,
            battery_end=100.0,
            battery_consumed=0.0,
            gps_quality_avg=10.0,  # Assume good
            max_satellites=15,
            min_satellites=10
        )
