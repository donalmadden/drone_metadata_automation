"""
Semantic Model Exporter
========================

This module provides the SemanticModelExporter class for generating
normalized CSV data tables in the semantic model format used by
the Pilot04_Field_Test_April_25 example.
"""

from pathlib import Path
from typing import List, Dict, Any
import csv

from .base_formatter import BaseFormatter, FormatterError
from ..models import VideoAnalysisResult, VideoProcessingBatch


class SemanticModelExporter(BaseFormatter):
    """
    Formatter for generating normalized CSV tables from video metadata.
    
    This formatter creates semantic model tables similar to those in
    Pilot04_Field_Test_April_25:
    - flight_facts.csv (main fact table)
    - altitude_dimension.csv
    - bay_dimension.csv
    - angle_dimension.csv
    - speed_dimension.csv
    - distance_dimension.csv
    
    Phase 2 Implementation: Complete semantic model with all dimension tables
    matching the Pilot04_Field_Test_April_25 format.
    """
    
    def get_supported_extensions(self) -> List[str]:
        """Return supported file extensions."""
        return [".csv"]
    
    def format_single_video(self, result: VideoAnalysisResult) -> List[Path]:
        """
        Generate semantic model CSV files for a single video.
        
        Args:
            result: Video analysis result to format
            
        Returns:
            List of paths to generated CSV files
        """
        video_name = result.video_metadata.filename
        self._log_processing_start("semantic model export", video_name)
        
        output_paths = []
        
        try:
            # Generate flight facts entry
            facts_path = self._generate_flight_facts([result])
            if facts_path:
                output_paths.append(facts_path)
            
            # Generate dimension tables (placeholder for Phase 1)
            dimension_paths = self._generate_dimension_tables([result])
            output_paths.extend(dimension_paths)
            
            self._log_processing_complete("semantic model export", video_name, Path(self.config.output_directory))
            return output_paths
            
        except Exception as e:
            error_msg = f"Failed to export semantic model for {video_name}: {str(e)}"
            self._log_processing_error("semantic model export", video_name, error_msg)
            raise FormatterError(error_msg)
    
    def format_batch(self, batch: VideoProcessingBatch) -> List[Path]:
        """
        Generate semantic model CSV files for a batch of videos.
        
        Args:
            batch: Batch of video analysis results to format
            
        Returns:
            List of paths to generated CSV files
        """
        if not batch.video_results:
            return []
        
        try:
            output_paths = []
            
            # Generate consolidated flight facts table
            facts_path = self._generate_flight_facts(batch.video_results)
            if facts_path:
                output_paths.append(facts_path)
            
            # Generate dimension tables
            dimension_paths = self._generate_dimension_tables(batch.video_results)
            output_paths.extend(dimension_paths)
            
            return output_paths
            
        except Exception as e:
            error_msg = f"Failed to export semantic model for batch: {str(e)}"
            self._log_processing_error("semantic model export", "batch", error_msg)
            raise FormatterError(error_msg)
    
    def _generate_flight_facts(self, results: List[VideoAnalysisResult]) -> Path:
        """
        Generate the main flight_facts.csv table.
        
        Args:
            results: List of video analysis results
            
        Returns:
            Path to generated flight_facts.csv file
        """
        # Use first result to determine organized path for batch files
        first_result = results[0] if results else None
        facts_path = self._get_output_path("flight_facts.csv", first_result, '.csv')
        
        # Check if file exists and handle accordingly
        if self._check_file_exists(facts_path):
            return facts_path
        
        # Define CSV headers based on Pilot04 format
        headers = [
            "flight_id",
            "video_filename", 
            "duration_seconds",
            "file_size_mb",
            "resolution_width",
            "resolution_height",
            "video_codec",
            "gps_latitude",
            "gps_longitude", 
            "gps_altitude",
            "mission_type",
            "bay_designation",
            "extraction_timestamp",
            "processing_success"
        ]
        
        # Write CSV data
        with open(facts_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            
            for i, result in enumerate(results, 1):
                video = result.video_metadata
                specs = result.technical_specs
                gps = result.gps_data
                mission = result.mission_data
                
                row = [
                    f"flight_{i:03d}",  # flight_id
                    video.filename,
                    video.duration_seconds or 0,
                    round(video.filesize_mb, 2),
                    specs.width or 0,
                    specs.height or 0,
                    specs.video_codec or "unknown",
                    gps.latitude_decimal if gps and gps.is_valid() else None,
                    gps.longitude_decimal if gps and gps.is_valid() else None,
                    gps.altitude_meters if gps else None,
                    mission.mission_type.value if mission else "unknown",
                    mission.bay_designation if mission else None,
                    video.extraction_time.isoformat(),
                    result.extraction_success
                ]
                
                writer.writerow(row)
        
        return facts_path
    
    def _generate_dimension_tables(self, results: List[VideoAnalysisResult]) -> List[Path]:
        """
        Generate dimension tables for the semantic model.
        
        Args:
            results: List of video analysis results
            
        Returns:
            List of paths to generated dimension CSV files
        """
        dimension_paths = []
        
        # Altitude dimension
        altitude_path = self._generate_altitude_dimension(results)
        if altitude_path:
            dimension_paths.append(altitude_path)
        
        # Bay dimension  
        bay_path = self._generate_bay_dimension(results)
        if bay_path:
            dimension_paths.append(bay_path)
        
        # Resolution dimension
        resolution_path = self._generate_resolution_dimension(results)
        if resolution_path:
            dimension_paths.append(resolution_path)
        
        # Phase 2 additions: speed, distance, and angle dimensions
        speed_path = self._generate_speed_dimension(results)
        if speed_path:
            dimension_paths.append(speed_path)
            
        distance_path = self._generate_distance_dimension(results)
        if distance_path:
            dimension_paths.append(distance_path)
            
        angle_path = self._generate_angle_dimension(results)
        if angle_path:
            dimension_paths.append(angle_path)
        
        return dimension_paths
    
    def _generate_altitude_dimension(self, results: List[VideoAnalysisResult]) -> Path:
        """Generate altitude_dimension.csv table."""
        first_result = results[0] if results else None
        altitude_path = self._get_output_path("altitude_dimension.csv", first_result, '.csv')
        
        if self._check_file_exists(altitude_path):
            return altitude_path
        
        # Extract unique altitude values
        altitudes = set()
        for result in results:
            if result.gps_data and result.gps_data.altitude_meters is not None:
                altitudes.add(result.gps_data.altitude_meters)
        
        # Write altitude dimension table
        with open(altitude_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["altitude_id", "altitude_meters", "altitude_category"])
            
            for i, alt in enumerate(sorted(altitudes), 1):
                category = "low" if alt < 50 else "medium" if alt < 150 else "high"
                writer.writerow([f"alt_{i:03d}", alt, category])
        
        return altitude_path
    
    def _generate_bay_dimension(self, results: List[VideoAnalysisResult]) -> Path:
        """Generate bay_dimension.csv table."""
        first_result = results[0] if results else None
        bay_path = self._get_output_path("bay_dimension.csv", first_result, '.csv')
        
        if self._check_file_exists(bay_path):
            return bay_path
        
        # Extract unique bay designations
        bays = set()
        for result in results:
            if result.mission_data and result.mission_data.bay_designation:
                bays.add(result.mission_data.bay_designation)
        
        # Write bay dimension table
        with open(bay_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["bay_id", "bay_name", "bay_type"])
            
            for i, bay in enumerate(sorted(bays), 1):
                writer.writerow([f"bay_{i:03d}", bay, "inspection_bay"])
        
        return bay_path
    
    def _generate_resolution_dimension(self, results: List[VideoAnalysisResult]) -> Path:
        """Generate resolution_dimension.csv table (Phase 1 addition)."""
        first_result = results[0] if results else None
        resolution_path = self._get_output_path("resolution_dimension.csv", first_result, '.csv')
        
        if self._check_file_exists(resolution_path):
            return resolution_path
        
        # Extract unique resolutions
        resolutions = set()
        for result in results:
            specs = result.technical_specs
            if specs.width and specs.height:
                resolutions.add((specs.width, specs.height))
        
        # Write resolution dimension table
        with open(resolution_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["resolution_id", "width", "height", "resolution_name", "quality_category"])
            
            for i, (width, height) in enumerate(sorted(resolutions), 1):
                resolution_name = f"{width}x{height}"
                if width >= 3840:
                    quality_category = "4K"
                elif width >= 1920:
                    quality_category = "Full HD"
                elif width >= 1280:
                    quality_category = "HD"
                else:
                    quality_category = "Standard"
                
                writer.writerow([f"res_{i:03d}", width, height, resolution_name, quality_category])
        
        return resolution_path
    
    def _generate_speed_dimension(self, results: List[VideoAnalysisResult]) -> Path:
        """Generate speed_dimension.csv table (Phase 2 addition)."""
        first_result = results[0] if results else None
        speed_path = self._get_output_path("speed_dimension.csv", first_result, '.csv')
        
        if self._check_file_exists(speed_path):
            return speed_path
        
        # Calculate estimated speeds from video duration and estimated distance
        speeds = set()
        for result in results:
            duration = result.video_metadata.duration_seconds
            if duration and duration > 0:
                # Estimate based on mission type and duration
                if result.mission_data:
                    mission_type = result.mission_data.mission_type.value
                    if mission_type in ["box", "safety", "angles"]:
                        # Slow inspection speeds (1-5 mph)
                        estimated_speed = min(5.0, 120.0 / duration)  # Conservative estimate
                    elif mission_type in ["overview", "survey"]:
                        # Moderate survey speeds (5-15 mph)
                        estimated_speed = min(15.0, 300.0 / duration)
                    else:
                        # Default estimation
                        estimated_speed = min(10.0, 180.0 / duration)
                    
                    speeds.add(round(estimated_speed, 1))
        
        # Add some standard speed ranges if no specific data
        if not speeds:
            speeds = {2.0, 5.0, 8.0, 12.0, 15.0}
        
        # Write speed dimension table
        with open(speed_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["speed_id", "speed_mph", "speed_category", "typical_use"])
            
            for i, speed in enumerate(sorted(speeds), 1):
                if speed <= 3:
                    category = "very_slow"
                    use = "detailed_inspection"
                elif speed <= 6:
                    category = "slow"
                    use = "close_inspection"
                elif speed <= 10:
                    category = "moderate"
                    use = "general_inspection"
                elif speed <= 15:
                    category = "fast"
                    use = "survey_mapping"
                else:
                    category = "very_fast"
                    use = "transit"
                
                writer.writerow([f"spd_{i:03d}", speed, category, use])
        
        return speed_path
    
    def _generate_distance_dimension(self, results: List[VideoAnalysisResult]) -> Path:
        """Generate distance_dimension.csv table (Phase 2 addition)."""
        first_result = results[0] if results else None
        distance_path = self._get_output_path("distance_dimension.csv", first_result, '.csv')
        
        if self._check_file_exists(distance_path):
            return distance_path
        
        # Calculate estimated distances from video duration and estimated speed
        distances = set()
        for result in results:
            duration = result.video_metadata.duration_seconds
            if duration and duration > 0:
                duration_hours = duration / 3600.0
                
                # Estimate based on mission type
                if result.mission_data:
                    mission_type = result.mission_data.mission_type.value
                    if mission_type in ["box", "safety", "angles"]:
                        # Short distance inspections
                        estimated_distance = duration_hours * 3.0  # ~3 mph average
                    elif mission_type in ["overview", "survey"]:
                        # Longer distance surveys
                        estimated_distance = duration_hours * 8.0  # ~8 mph average
                    else:
                        # Default estimation
                        estimated_distance = duration_hours * 5.0  # ~5 mph average
                    
                    distances.add(round(estimated_distance, 2))
        
        # Add some standard distance ranges if no specific data
        if not distances:
            distances = {0.05, 0.1, 0.25, 0.5, 1.0, 2.0}
        
        # Write distance dimension table
        with open(distance_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["distance_id", "distance_miles", "distance_category", "typical_mission"])
            
            for i, distance in enumerate(sorted(distances), 1):
                if distance <= 0.1:
                    category = "very_short"
                    mission = "hover_inspection"
                elif distance <= 0.3:
                    category = "short"
                    mission = "focused_inspection"
                elif distance <= 1.0:
                    category = "medium"
                    mission = "area_inspection"
                elif distance <= 3.0:
                    category = "long"
                    mission = "perimeter_survey"
                else:
                    category = "very_long"
                    mission = "comprehensive_survey"
                
                writer.writerow([f"dst_{i:03d}", distance, category, mission])
        
        return distance_path
    
    def _generate_angle_dimension(self, results: List[VideoAnalysisResult]) -> Path:
        """Generate angle_dimension.csv table (Phase 2 addition)."""
        first_result = results[0] if results else None
        angle_path = self._get_output_path("angle_dimension.csv", first_result, '.csv')
        
        if self._check_file_exists(angle_path):
            return angle_path
        
        # Extract camera angles from DJI metadata or estimate from mission type
        angles = set()
        for result in results:
            # Try to extract gimbal angles from DJI metadata
            if result.dji_metadata:
                for key, value in result.dji_metadata.items():
                    if "pitch" in key.lower() or "tilt" in key.lower():
                        try:
                            angle_value = float(value)
                            angles.add(round(angle_value, 1))
                        except (ValueError, TypeError):
                            continue
            
            # Estimate based on mission type if no DJI data
            if result.mission_data and not angles:
                mission_type = result.mission_data.mission_type.value
                if mission_type in ["box", "safety"]:
                    angles.update([-30.0, -45.0, -60.0])  # Downward angles for inspection
                elif mission_type == "angles":
                    angles.update([-15.0, -30.0, -45.0, -60.0, -75.0])  # Multiple angles
                elif mission_type in ["overview", "survey"]:
                    angles.update([-20.0, -30.0])  # Moderate downward angles
        
        # Add standard angles if no data found
        if not angles:
            angles = {0.0, -15.0, -30.0, -45.0, -60.0, -90.0}
        
        # Write angle dimension table
        with open(angle_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["angle_id", "angle_degrees", "angle_category", "camera_orientation"])
            
            for i, angle in enumerate(sorted(angles, reverse=True), 1):  # Sort high to low
                if angle >= 0:
                    category = "horizontal"
                    orientation = "forward_facing"
                elif angle >= -30:
                    category = "slight_down"
                    orientation = "slight_downward"
                elif angle >= -60:
                    category = "moderate_down"
                    orientation = "moderate_downward"
                else:
                    category = "steep_down"
                    orientation = "steep_downward"
                
                writer.writerow([f"ang_{i:03d}", angle, category, orientation])
        
        return angle_path
    
    def get_formatter_info(self) -> dict:
        """Get information about this formatter."""
        info = super().get_formatter_info()
        info.update({
            "phase": "Phase 2 (Complete Implementation)",
            "generated_tables": [
                "flight_facts.csv",
                "altitude_dimension.csv", 
                "bay_dimension.csv",
                "resolution_dimension.csv",
                "speed_dimension.csv",
                "distance_dimension.csv", 
                "angle_dimension.csv"
            ],
            "implemented_features": [
                "Complete semantic model with all dimension tables",
                "Intelligent estimation from video metadata",
                "Mission-type-based parameter estimation",
                "DJI metadata extraction for camera angles",
                "Categorized dimension values",
                "Pilot04-compatible table structure"
            ],
            "future_features": [
                "Foreign key relationships",
                "Data validation and constraints",
                "Metadata schema documentation",
                "Advanced telemetry-based calculations",
                "Custom dimension table configuration"
            ]
        })
        return info
