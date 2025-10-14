"""
Directory scanner for automatic discovery of flight data sources.

This module scans flight directories and automatically identifies:
- Bay identifiers from directory names
- Inspection types from subdirectories
- Available data files (CSV, SRT, media, etc.)
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

from ..models import (
    FlightDataset, InspectionType, ConfigDict
)

logger = logging.getLogger(__name__)


class DirectoryScanError(Exception):
    """Raised when directory scanning fails."""
    pass


class DirectoryScanner:
    """Scanner for flight data directories with automatic categorization."""
    
    # File patterns for different data types
    FILE_PATTERNS = {
        'airdata_csv': [
            r'.*Flight-Airdata\.csv$',
            r'.*-airdata\.csv$',
            r'MP4-\d+-.*-Flight-Airdata\.csv$',
            r'JPG-.*-Flight-Airdata\.csv$'
        ],
        'srt_files': [
            r'DJI_\d+\.SRT$',
            r'.*\.srt$',
            r'.*\.SRT$'
        ],
        'media_files': [
            r'DJI_\d+\.(MP4|MOV|AVI)$',
            r'DJI_\d+\.(JPG|JPEG|DNG)$',
            r'.*\.(mp4|mov|avi|jpg|jpeg|dng)$'
        ],
        'flight_records': [
            r'FlightRecord_.*\.txt$',
            r'flight_log.*\.txt$',
            r'.*flight.*record.*\.txt$'
        ]
    }
    
    # Bay identifier patterns
    BAY_PATTERNS = [
        r'^([0-9A-F]{1,2}[A-F]-[0-9A-F]{1,2}[A-F])$',  # Format: 8B-7F, 6E-7C
        r'^([0-9A-F]{1,2}[A-F])$',  # Format: 8D
        r'^bay[_-]?([a-zA-Z0-9\-]+)$',  # Format: bay_8B-7F
        r'^([A-Z]\d+)$'  # Format: A1, B2, etc.
    ]
    
    # Inspection type indicators in directory names
    INSPECTION_TYPE_INDICATORS = {
        InspectionType.ANGLES: ['angles', 'angle', 'angular'],
        InspectionType.DETAILED: ['detail', 'detailed', 'close', 'closeup'],
        InspectionType.OVERVIEW: ['overview', 'general', 'wide', 'survey'],
        InspectionType.PERIMETER: ['perimeter', 'boundary', 'edge'],
        InspectionType.EMERGENCY: ['emergency', 'urgent', 'incident']
    }
    
    def __init__(self, case_sensitive: bool = False):
        """
        Initialize directory scanner.
        
        Args:
            case_sensitive: Whether to use case-sensitive matching
        """
        self.case_sensitive = case_sensitive
        
    def scan_flight_directory(self, directory_path: str) -> FlightDataset:
        """
        Scan a flight directory and discover all data sources.
        
        Args:
            directory_path: Path to flight directory
            
        Returns:
            FlightDataset with discovered files and metadata
            
        Raises:
            DirectoryScanError: If scanning fails
        """
        try:
            path = Path(directory_path)
            if not path.exists() or not path.is_dir():
                raise DirectoryScanError(f"Directory not found: {directory_path}")
            
            logger.info(f"Scanning flight directory: {directory_path}")
            
            # Discover data sources
            data_sources = self.discover_data_sources(str(path))
            
            # Identify bay and inspection type
            bay_id = self.identify_bay_from_path(str(path))
            inspection_type = self.categorize_inspection_type(str(path))
            
            # Create dataset
            dataset = FlightDataset(
                directory_path=str(path),
                airdata_csv_files=data_sources.get('airdata_csv', []),
                srt_files=data_sources.get('srt_files', []),
                media_files=data_sources.get('media_files', []),
                flight_record_files=data_sources.get('flight_records', []),
                bay_identifier=bay_id,
                inspection_type=inspection_type
            )
            
            logger.info(
                f"Discovered: {len(dataset.airdata_csv_files)} CSV files, "
                f"{len(dataset.srt_files)} SRT files, "
                f"{len(dataset.media_files)} media files, "
                f"Bay: {bay_id}, Type: {inspection_type}"
            )
            
            return dataset
            
        except Exception as e:
            raise DirectoryScanError(f"Failed to scan directory {directory_path}: {str(e)}") from e
    
    def identify_bay_from_path(self, directory_path: str) -> Optional[str]:
        """
        Extract bay identifier from directory path.
        
        Args:
            directory_path: Path to analyze
            
        Returns:
            Bay identifier string or None if not found
        """
        path = Path(directory_path)
        
        # Check current directory name and parent directories
        for part in [path.name] + [p.name for p in path.parents]:
            bay_id = self._extract_bay_id(part)
            if bay_id:
                logger.info(f"Identified bay '{bay_id}' from path component '{part}'")
                return bay_id
        
        logger.warning(f"Could not identify bay from path: {directory_path}")
        return None
    
    def categorize_inspection_type(self, directory_path: str) -> Optional[InspectionType]:
        """
        Determine inspection type from directory structure.
        
        Args:
            directory_path: Path to analyze
            
        Returns:
            InspectionType or None if not determined
        """
        path = Path(directory_path)
        path_str = str(path).lower()
        
        # Check for inspection type indicators in path
        for inspection_type, indicators in self.INSPECTION_TYPE_INDICATORS.items():
            for indicator in indicators:
                if indicator in path_str:
                    logger.info(f"Identified inspection type '{inspection_type.value}' from indicator '{indicator}'")
                    return inspection_type
        
        # Default heuristics based on file patterns
        data_sources = self.discover_data_sources(str(path))
        
        # If many SRT/video files, likely detailed inspection
        if len(data_sources.get('srt_files', [])) > 5:
            return InspectionType.DETAILED
        
        # If only photos, likely overview
        media_files = data_sources.get('media_files', [])
        video_files = [f for f in media_files if f.lower().endswith(('.mp4', '.mov', '.avi'))]
        photo_files = [f for f in media_files if f.lower().endswith(('.jpg', '.jpeg', '.dng'))]
        
        if len(photo_files) > len(video_files):
            return InspectionType.OVERVIEW
        
        logger.info("Using default inspection type: SURVEY")
        return InspectionType.SURVEY
    
    def discover_data_sources(self, directory_path: str) -> Dict[str, List[str]]:
        """
        Discover all data source files in directory.
        
        Args:
            directory_path: Directory to scan
            
        Returns:
            Dictionary mapping file types to file paths
        """
        path = Path(directory_path)
        discovered = {key: [] for key in self.FILE_PATTERNS.keys()}
        
        # Recursively scan directory
        for root, dirs, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                file_type = self._classify_file(file)
                
                if file_type:
                    discovered[file_type].append(file_path)
        
        # Sort file lists for consistent ordering
        for file_type in discovered:
            discovered[file_type].sort()
        
        return discovered
    
    def get_directory_structure(self, directory_path: str) -> Dict[str, any]:
        """
        Get detailed directory structure analysis.
        
        Args:
            directory_path: Directory to analyze
            
        Returns:
            Dictionary with structure information
        """
        path = Path(directory_path)
        
        structure = {
            'path': str(path),
            'name': path.name,
            'parent': str(path.parent) if path.parent != path else None,
            'subdirectories': [],
            'total_files': 0,
            'file_types': {},
            'size_bytes': 0
        }
        
        try:
            for root, dirs, files in os.walk(path):
                # Track subdirectories
                if root != str(path):
                    rel_path = os.path.relpath(root, path)
                    structure['subdirectories'].append(rel_path)
                
                # Count files and sizes
                for file in files:
                    file_path = os.path.join(root, file)
                    structure['total_files'] += 1
                    
                    # Track file extensions
                    ext = Path(file).suffix.lower()
                    structure['file_types'][ext] = structure['file_types'].get(ext, 0) + 1
                    
                    # Get file size
                    try:
                        structure['size_bytes'] += os.path.getsize(file_path)
                    except OSError:
                        pass  # Skip files we can't access
        
        except Exception as e:
            logger.warning(f"Error analyzing directory structure: {e}")
        
        return structure
    
    def find_matching_files(
        self, 
        directory_path: str, 
        pattern: str, 
        case_sensitive: bool = None
    ) -> List[str]:
        """
        Find files matching a specific pattern.
        
        Args:
            directory_path: Directory to search
            pattern: Regex pattern to match
            case_sensitive: Override default case sensitivity
            
        Returns:
            List of matching file paths
        """
        if case_sensitive is None:
            case_sensitive = self.case_sensitive
        
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)
        
        matches = []
        path = Path(directory_path)
        
        try:
            for root, dirs, files in os.walk(path):
                for file in files:
                    if regex.search(file):
                        file_path = os.path.join(root, file)
                        matches.append(file_path)
        except Exception as e:
            logger.error(f"Error searching for pattern '{pattern}': {e}")
        
        return sorted(matches)
    
    def _extract_bay_id(self, directory_name: str) -> Optional[str]:
        """Extract bay ID from directory name using patterns."""
        for pattern in self.BAY_PATTERNS:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            match = re.match(pattern, directory_name, flags)
            if match:
                return match.group(1)
        
        return None
    
    def _classify_file(self, filename: str) -> Optional[str]:
        """Classify file based on filename patterns."""
        for file_type, patterns in self.FILE_PATTERNS.items():
            for pattern in patterns:
                flags = 0 if self.case_sensitive else re.IGNORECASE
                if re.search(pattern, filename, flags):
                    return file_type
        
        return None
    
    def validate_dataset_completeness(self, dataset: FlightDataset) -> Dict[str, bool]:
        """
        Validate that dataset has required components.
        
        Args:
            dataset: FlightDataset to validate
            
        Returns:
            Dictionary of validation results
        """
        validation = {}
        
        # Check for telemetry data (CSV or SRT)
        validation['has_telemetry'] = bool(
            dataset.airdata_csv_files or dataset.srt_files
        )
        
        # Check for media files
        validation['has_media'] = bool(dataset.media_files)
        
        # Check for GPS data source
        validation['has_gps_source'] = bool(
            dataset.airdata_csv_files  # CSV files contain GPS
        )
        
        # Check for bay identification
        validation['has_bay_id'] = dataset.bay_identifier is not None
        
        # Check for inspection type
        validation['has_inspection_type'] = dataset.inspection_type is not None
        
        # Check file accessibility
        all_files = (
            dataset.airdata_csv_files + 
            dataset.srt_files + 
            dataset.media_files + 
            dataset.flight_record_files
        )
        
        accessible_files = [f for f in all_files if os.path.exists(f)]
        validation['files_accessible'] = len(accessible_files) == len(all_files)
        validation['file_access_rate'] = len(accessible_files) / max(len(all_files), 1)
        
        # Overall completeness
        required_checks = ['has_telemetry', 'has_media', 'files_accessible']
        validation['is_complete'] = all(validation.get(check, False) for check in required_checks)
        
        return validation
    
    def get_processing_recommendations(self, dataset: FlightDataset) -> List[str]:
        """
        Get recommendations for processing the dataset.
        
        Args:
            dataset: FlightDataset to analyze
            
        Returns:
            List of processing recommendations
        """
        recommendations = []
        validation = self.validate_dataset_completeness(dataset)
        
        # Data source recommendations
        if not dataset.airdata_csv_files:
            if dataset.srt_files:
                recommendations.append(
                    "No airdata CSV files found. Will extract GPS and timing from SRT files."
                )
            else:
                recommendations.append(
                    "No telemetry data found. Consider manual GPS extraction from media EXIF."
                )
        
        if not dataset.srt_files:
            recommendations.append(
                "No SRT files found. Camera settings will be limited to EXIF data."
            )
        
        # Identification recommendations
        if not dataset.bay_identifier:
            recommendations.append(
                "Bay identifier not detected. Manual bay assignment may be required."
            )
        
        if not dataset.inspection_type:
            recommendations.append(
                "Inspection type not detected. Will attempt automatic classification."
            )
        
        # Processing priority recommendations
        if len(dataset.airdata_csv_files) > 1:
            recommendations.append(
                f"Multiple CSV files found ({len(dataset.airdata_csv_files)}). "
                "Will process all files and merge telemetry data."
            )
        
        if len(dataset.media_files) > 50:
            recommendations.append(
                f"Large number of media files ({len(dataset.media_files)}). "
                "Consider batch processing or sampling for initial analysis."
            )
        
        # Quality recommendations
        if validation['file_access_rate'] < 1.0:
            missing_files = int((1.0 - validation['file_access_rate']) * len(dataset.media_files))
            recommendations.append(
                f"Some files are inaccessible ({missing_files} files). "
                "Check file permissions and paths."
            )
        
        if not recommendations:
            recommendations.append("Dataset appears complete and ready for processing.")
        
        return recommendations
