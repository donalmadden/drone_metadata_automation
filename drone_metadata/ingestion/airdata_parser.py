"""
Airdata CSV parser for drone flight telemetry data.

This module handles parsing and analysis of airdata CSV files containing
comprehensive flight telemetry at 10Hz sampling rate.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

from ..models import (
    FlightData, FlightMetrics, MediaEvent, FlightPhases, FlightPhase,
    MediaType, GPSPoint, CameraSettings
)

logger = logging.getLogger(__name__)


class AirdataParseError(Exception):
    """Raised when airdata CSV parsing fails."""
    pass


class AirdataParser:
    """Parser for DJI airdata CSV files with telemetry validation."""
    
    # Expected CSV column names (48 total fields)
    EXPECTED_COLUMNS = [
        'time(millisecond)', 'datetime(utc)', 'latitude', 'longitude',
        'height_above_takeoff(feet)', 'height_above_ground_at_drone_location(feet)',
        'ground_elevation_at_drone_location(feet)', 'altitude_above_seaLevel(feet)',
        'height_sonar(feet)', 'speed(mph)', 'distance(feet)', 'mileage(feet)',
        'satellites', 'gpslevel', 'voltage(v)', 'max_altitude(feet)',
        'max_ascent(feet)', 'max_speed(mph)', 'max_distance(feet)',
        'xSpeed(mph)', 'ySpeed(mph)', 'zSpeed(mph)', 'compass_heading(degrees)',
        'pitch(degrees)', 'roll(degrees)', 'isPhoto', 'isVideo',
        'rc_elevator', 'rc_aileron', 'rc_throttle', 'rc_rudder',
        'rc_elevator(percent)', 'rc_aileron(percent)', 'rc_throttle(percent)',
        'rc_rudder(percent)', 'gimbal_heading(degrees)', 'gimbal_pitch(degrees)',
        'gimbal_roll(degrees)', 'battery_percent', 'voltageCell1', 'voltageCell2',
        'voltageCell3', 'voltageCell4', 'voltageCell5', 'voltageCell6',
        'current(A)', 'battery_temperature(f)', 'altitude(feet)', 'ascent(feet)',
        'flycStateRaw', 'flycState', 'message'
    ]
    
    def __init__(self, validate_columns: bool = True):
        """Initialize parser with validation options."""
        self.validate_columns = validate_columns
        
    def parse_csv(self, file_path: str) -> FlightData:
        """
        Parse airdata CSV file and return structured flight data.
        
        Args:
            file_path: Path to airdata CSV file
            
        Returns:
            FlightData object with telemetry and derived metrics
            
        Raises:
            AirdataParseError: If parsing fails or data is invalid
        """
        try:
            path_obj = Path(file_path)
            if not path_obj.exists():
                raise AirdataParseError(f"File not found: {file_path}")
                
            logger.info(f"Parsing airdata CSV: {file_path}")
            
            # Handle mixed pipe-comma delimiter format
            df = self._read_mixed_delimiter_csv(file_path)
            
            # Validate structure
            self._validate_dataframe(df)
            
            # Clean and process data
            df_clean = self._clean_dataframe(df)
            
            # Extract basic flight information
            flight_id = self._generate_flight_id(path_obj.name, df_clean)
            timestamp_start, timestamp_end, duration = self._extract_timing(df_clean)
            
            # Parse media events
            media_events = self._extract_media_events(df_clean)
            
            # Parse flight phases
            flight_phases = self._extract_flight_phases(df_clean)
            
            # Create flight data object
            flight_data = FlightData(
                flight_id=flight_id,
                timestamp_start=timestamp_start,
                timestamp_end=timestamp_end,
                duration=duration,
                telemetry=df_clean,
                media_events=media_events,
                flight_phases=flight_phases,
                source_files={'airdata_csv': file_path}
            )
            
            logger.info(
                f"Successfully parsed flight {flight_id}: "
                f"{len(df_clean)} telemetry points, {len(media_events)} media events"
            )
            
            return flight_data
            
        except Exception as e:
            raise AirdataParseError(f"Failed to parse {file_path}: {str(e)}") from e
    
    def extract_flight_metrics(self, flight_data: FlightData) -> FlightMetrics:
        """
        Compute comprehensive flight performance metrics.
        
        Args:
            flight_data: Parsed flight data
            
        Returns:
            FlightMetrics with computed statistics
        """
        df = flight_data.telemetry
        
        # Altitude metrics (using height_above_takeoff as primary)
        altitude_col = 'height_above_takeoff(feet)'
        max_altitude = df[altitude_col].max()
        avg_altitude = df[altitude_col].mean()
        min_altitude = df[altitude_col].min()
        
        # Speed metrics
        max_speed = df['speed(mph)'].max()
        avg_speed = df['speed(mph)'].mean()
        
        # Distance (use max mileage as total distance)
        total_distance = df['mileage(feet)'].max() / 5280.0  # Convert to miles
        
        # Battery metrics
        battery_start = df['battery_percent'].iloc[0]
        battery_end = df['battery_percent'].iloc[-1]
        battery_consumed = battery_start - battery_end
        
        # GPS quality metrics
        gps_quality_avg = df['satellites'].mean()
        max_satellites = int(df['satellites'].max())
        min_satellites = int(df['satellites'].min())
        
        return FlightMetrics(
            max_altitude=max_altitude,
            avg_altitude=avg_altitude,
            min_altitude=min_altitude,
            max_speed=max_speed,
            avg_speed=avg_speed,
            total_distance=total_distance,
            battery_start=battery_start,
            battery_end=battery_end,
            battery_consumed=battery_consumed,
            gps_quality_avg=gps_quality_avg,
            max_satellites=max_satellites,
            min_satellites=min_satellites
        )
    
    def get_media_timestamps(self, flight_data: FlightData) -> List[MediaEvent]:
        """
        Extract media capture events from telemetry.
        
        Returns media events already parsed in parse_csv() for compatibility.
        """
        return flight_data.media_events
    
    def analyze_flight_phases(self, flight_data: FlightData) -> FlightPhases:
        """
        Extract flight phase transitions from flycState data.
        
        Returns flight phases already parsed in parse_csv() for compatibility.
        """
        return flight_data.flight_phases or FlightPhases()
    
    def _validate_dataframe(self, df: pd.DataFrame) -> None:
        """Validate dataframe structure and content."""
        if df.empty:
            raise AirdataParseError("CSV file is empty")
        
        # Check if we have enough columns
        if len(df.columns) == 1:
            raise AirdataParseError(
                "CSV appears to have single column - check separator format"
            )
        
        if self.validate_columns:
            missing_cols = set(self.EXPECTED_COLUMNS) - set(df.columns)
            if missing_cols:
                logger.warning(f"Missing expected columns: {missing_cols}")
        
        # Check for essential columns
        essential_cols = ['datetime(utc)', 'latitude', 'longitude', 'speed(mph)']
        missing_essential = set(essential_cols) - set(df.columns)
        if missing_essential:
            raise AirdataParseError(f"Missing essential columns: {missing_essential}")
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare dataframe for analysis."""
        df_clean = df.copy()
        
        # Convert datetime column
        if 'datetime(utc)' in df_clean.columns:
            df_clean['datetime(utc)'] = pd.to_datetime(
                df_clean['datetime(utc)'], errors='coerce'
            )
        
        # Convert numeric columns, handling string values
        numeric_columns = [
            'latitude', 'longitude', 'speed(mph)', 'altitude(feet)',
            'battery_percent', 'satellites', 'height_above_takeoff(feet)',
            'mileage(feet)'
        ]
        
        for col in numeric_columns:
            if col in df_clean.columns:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
        
        # Handle boolean columns (isPhoto, isVideo)
        bool_columns = ['isPhoto', 'isVideo']
        for col in bool_columns:
            if col in df_clean.columns:
                # Convert to boolean (1/0 or True/False)
                df_clean[col] = df_clean[col].astype(bool)
        
        # Sort by timestamp to ensure chronological order
        if 'datetime(utc)' in df_clean.columns:
            df_clean = df_clean.sort_values('datetime(utc)').reset_index(drop=True)
        
        # Remove rows with invalid GPS coordinates
        df_clean = df_clean.dropna(subset=['latitude', 'longitude'])
        
        return df_clean
    
    def _generate_flight_id(self, filename: str, df: pd.DataFrame) -> str:
        """Generate unique flight ID from filename and data."""
        # Extract base name without extension
        base_name = Path(filename).stem
        
        # Get start timestamp if available
        if not df.empty and 'datetime(utc)' in df.columns:
            start_time = df['datetime(utc)'].iloc[0]
            time_str = start_time.strftime("%Y%m%d_%H%M")
            return f"{base_name}_{time_str}"
        
        return base_name
    
    def _extract_timing(self, df: pd.DataFrame) -> Tuple[datetime, datetime, timedelta]:
        """Extract flight timing information."""
        if 'datetime(utc)' not in df.columns or df.empty:
            raise AirdataParseError("No valid datetime data found")
        
        timestamp_start = df['datetime(utc)'].iloc[0]
        timestamp_end = df['datetime(utc)'].iloc[-1]
        duration = timestamp_end - timestamp_start
        
        return timestamp_start, timestamp_end, duration
    
    def _extract_media_events(self, df: pd.DataFrame) -> List[MediaEvent]:
        """Extract media capture events from telemetry."""
        media_events = []
        
        if 'isPhoto' not in df.columns and 'isVideo' not in df.columns:
            logger.warning("No media event columns found in telemetry")
            return media_events
        
        for idx, row in df.iterrows():
            timestamp = row.get('datetime(utc)')
            if pd.isna(timestamp):
                continue
                
            # Create GPS point
            try:
                gps_point = GPSPoint(
                    latitude=row['latitude'],
                    longitude=row['longitude'],
                    altitude=row.get('altitude(feet)', 0.0),
                    timestamp=timestamp,
                    accuracy=row.get('satellites', None)
                )
            except (ValueError, TypeError):
                continue  # Skip invalid GPS data
            
            # Empty camera settings (SRT will provide detailed settings)
            camera_settings = CameraSettings()
            
            # Check for photo events
            if 'isPhoto' in df.columns and row.get('isPhoto', False):
                media_events.append(MediaEvent(
                    timestamp=timestamp,
                    event_type=MediaType.PHOTO,
                    location=gps_point,
                    camera_settings=camera_settings
                ))
            
            # Check for video events
            if 'isVideo' in df.columns and row.get('isVideo', False):
                # Determine if this is start or end of video
                # For now, treat each video flag as a start event
                # TODO: Implement proper video start/end detection
                media_events.append(MediaEvent(
                    timestamp=timestamp,
                    event_type=MediaType.VIDEO_START,
                    location=gps_point,
                    camera_settings=camera_settings
                ))
        
        logger.info(f"Extracted {len(media_events)} media events")
        return media_events
    
    def _extract_flight_phases(self, df: pd.DataFrame) -> Optional[FlightPhases]:
        """Extract flight phases from flycState column."""
        if 'flycState' not in df.columns:
            logger.warning("No flycState column found for phase analysis")
            return None
        
        phases = FlightPhases()
        current_phase = None
        phase_start = None
        
        for idx, row in df.iterrows():
            timestamp = row.get('datetime(utc)')
            flyc_state = row.get('flycState', '')
            
            if pd.isna(timestamp):
                continue
            
            # Map flycState to FlightPhase enum
            try:
                phase = FlightPhase(flyc_state)
            except ValueError:
                # Unknown phase, continue with current
                continue
            
            # Detect phase transition
            if current_phase != phase:
                # End previous phase
                if current_phase is not None and phase_start is not None:
                    phases.phases.append((current_phase, phase_start, timestamp))
                
                # Start new phase
                current_phase = phase
                phase_start = timestamp
        
        # End final phase
        if current_phase is not None and phase_start is not None:
            final_timestamp = df['datetime(utc)'].iloc[-1]
            phases.phases.append((current_phase, phase_start, final_timestamp))
        
        logger.info(f"Identified {len(phases.phases)} flight phases")
        return phases
    
    def validate_telemetry_consistency(self, flight_data: FlightData) -> Dict[str, bool]:
        """
        Validate telemetry data consistency and quality.
        
        Returns:
            Dictionary of validation results
        """
        df = flight_data.telemetry
        results = {}
        
        # Check timestamp continuity
        if 'datetime(utc)' in df.columns:
            time_diffs = df['datetime(utc)'].diff().dt.total_seconds()
            # Expect ~0.1 second intervals (10Hz)
            normal_intervals = (time_diffs > 0.05) & (time_diffs < 0.2)
            results['timestamp_continuity'] = normal_intervals.mean() > 0.9
        
        # Check GPS coordinate validity
        if all(col in df.columns for col in ['latitude', 'longitude']):
            valid_coords = (
                (df['latitude'] >= -90) & (df['latitude'] <= 90) &
                (df['longitude'] >= -180) & (df['longitude'] <= 180)
            )
            results['gps_validity'] = valid_coords.mean() > 0.95
        
        # Check battery level consistency (should be decreasing)
        if 'battery_percent' in df.columns:
            battery_changes = df['battery_percent'].diff()
            # Allow for small increases due to measurement noise, but overall decreasing
            results['battery_consistency'] = battery_changes.mean() <= 1.0
        
        # Check altitude reasonableness
        if 'height_above_takeoff(feet)' in df.columns:
            altitudes = df['height_above_takeoff(feet)']
            results['altitude_reasonable'] = (altitudes >= 0).all() and (altitudes <= 1000).all()
        
        return results
    
    def _read_mixed_delimiter_csv(self, file_path: str) -> pd.DataFrame:
        """
        Read CSV file with mixed pipe-comma delimiter format.
        
        The format is: line_number|csv_data_with_commas
        We need to strip the line number prefix and parse the comma-separated data.
        """
        import io
        
        # Read file and preprocess to remove line number prefixes
        processed_lines = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                # Split on first pipe to separate line number from data
                if '|' in line:
                    parts = line.split('|', 1)
                    if len(parts) == 2:
                        # Take the data part after the pipe
                        csv_data = parts[1]
                        processed_lines.append(csv_data)
                    else:
                        # Shouldn't happen, but just in case
                        processed_lines.append(line)
                else:
                    # No pipe found, use whole line
                    processed_lines.append(line)
        
        if not processed_lines:
            raise AirdataParseError("No valid data lines found in CSV file")
            
        # Create a StringIO object from processed lines and read with pandas
        csv_content = '\n'.join(processed_lines)
        return pd.read_csv(io.StringIO(csv_content), sep=',')
