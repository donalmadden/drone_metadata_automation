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
    
    Note: This is a basic implementation for Phase 1.
    Full semantic model implementation will be in Phase 2.
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
        facts_path = self._get_output_path("flight_facts.csv")
        
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
        
        # Resolution dimension (Phase 1 addition)
        resolution_path = self._generate_resolution_dimension(results)
        if resolution_path:
            dimension_paths.append(resolution_path)
        
        return dimension_paths
    
    def _generate_altitude_dimension(self, results: List[VideoAnalysisResult]) -> Path:
        """Generate altitude_dimension.csv table."""
        altitude_path = self._get_output_path("altitude_dimension.csv")
        
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
        bay_path = self._get_output_path("bay_dimension.csv")
        
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
        resolution_path = self._get_output_path("resolution_dimension.csv")
        
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
    
    def get_formatter_info(self) -> dict:
        """Get information about this formatter."""
        info = super().get_formatter_info()
        info.update({
            "phase": "Phase 1 (Basic Implementation)",
            "generated_tables": [
                "flight_facts.csv",
                "altitude_dimension.csv", 
                "bay_dimension.csv",
                "resolution_dimension.csv"
            ],
            "future_features": [
                "angle_dimension.csv",
                "speed_dimension.csv", 
                "distance_dimension.csv",
                "Foreign key relationships",
                "Data validation and constraints",
                "Metadata schema documentation"
            ]
        })
        return info
