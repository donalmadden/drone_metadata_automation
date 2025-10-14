"""
Test configuration and fixtures for the drone metadata automation tests.

This module contains shared test configuration, fixtures, and constants
used across all test modules.
"""

import os
from pathlib import Path

# Test data paths
TEST_DATA_DIR = Path(__file__).parent / "test_data"
SAMPLE_CSV_PATH = r"C:\Users\donal\Downloads\aug_2025\8D\JPG-Aug-27th-2025-12-00PM-Flight-Airdata.csv"

# Test configuration
TEST_CONFIG = {
    "log_level": "INFO",
    "test_timeout": 60,  # seconds
    "enable_integration_tests": True,
}

# Expected test data characteristics
EXPECTED_TEST_DATA = {
    "min_telemetry_points": 1000,
    "expected_duration_minutes": 3,  # Approximate flight duration
    "expected_columns": [
        'datetime(utc)', 'latitude', 'longitude', 'mileage(feet)', 
        'speed(mph)', 'battery_percent', 'height_above_takeoff(feet)'
    ]
}