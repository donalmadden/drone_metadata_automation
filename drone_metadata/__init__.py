"""
Drone Metadata Automation System

Automated metadata extraction and annotation generation for drone inspection workflows.
This system leverages multiple data sources including flight telemetry, camera metadata,
and directory structure to produce comprehensive flight reports with minimal manual effort.

Core Components:
- Data ingestion (CSV, SRT, media files)  
- Automated analysis and classification
- Quality assessment and anomaly detection
- Report generation in multiple formats

Usage:
    from drone_metadata import DroneMetadataProcessor
    
    processor = DroneMetadataProcessor()
    report = processor.process_flight_directory("/path/to/flight/data")
"""

__version__ = "1.0.0"
__author__ = "Drone Metadata Automation Team"

# Core imports for external usage
from .processor import DroneMetadataProcessor, ProcessingError
from .models import (
    FlightReport, FlightData, FlightMetrics, QualityScore,
    MediaSummary, BayMapping, InspectionType
)

# Ingestion components
from .ingestion.directory_scanner import DirectoryScanner
from .ingestion.airdata_parser import AirdataParser  
from .ingestion.srt_parser import SRTParser

__all__ = [
    # Core processor
    "DroneMetadataProcessor",
    "ProcessingError",
    
    # Data models
    "FlightReport", 
    "FlightData",
    "FlightMetrics",
    "QualityScore", 
    "MediaSummary",
    "BayMapping",
    "InspectionType",
    
    # Ingestion components
    "DirectoryScanner",
    "AirdataParser",
    "SRTParser",
]
