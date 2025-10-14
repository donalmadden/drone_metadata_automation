"""
Data ingestion components for drone metadata automation.

This module contains parsers and scanners for different data sources:
- Airdata CSV files (flight telemetry)
- SRT subtitle files (camera metadata)
- Directory scanning and file discovery
"""

from .airdata_parser import AirdataParser, AirdataParseError
from .srt_parser import SRTParser, SRTParseError  
from .directory_scanner import DirectoryScanner, DirectoryScanError

__all__ = [
    "AirdataParser",
    "AirdataParseError", 
    "SRTParser",
    "SRTParseError",
    "DirectoryScanner", 
    "DirectoryScanError"
]
