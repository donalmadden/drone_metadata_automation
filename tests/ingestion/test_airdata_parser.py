#!/usr/bin/env python3
"""
Unit tests for AirdataParser.

This module contains comprehensive tests for the AirdataParser class,
including tests for the mixed delimiter format fix.
"""

import unittest
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from drone_metadata.ingestion.airdata_parser import AirdataParser, AirdataParseError


class TestAirdataParser(unittest.TestCase):
    """Test cases for AirdataParser class."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class with logging and test data paths."""
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
        
        # Path to the test CSV file (mixed delimiter format)
        cls.test_csv_file = r"C:\Users\donal\Downloads\aug_2025\8D\JPG-Aug-27th-2025-12-00PM-Flight-Airdata.csv"
        
        # Initialize parser
        cls.parser = AirdataParser()
    
    def test_mixed_delimiter_csv_parsing(self):
        """Test parsing CSV file with mixed pipe-comma delimiter format."""
        print(f"\n🧪 Testing mixed delimiter CSV parsing...")
        print(f"File: {self.test_csv_file}")
        
        # Parse the CSV file
        flight_data = self.parser.parse_csv(self.test_csv_file)
        
        # Assertions
        self.assertIsNotNone(flight_data)
        self.assertIsNotNone(flight_data.flight_id)
        self.assertIsInstance(flight_data.timestamp_start, datetime)
        self.assertIsInstance(flight_data.timestamp_end, datetime)
        self.assertIsInstance(flight_data.duration, timedelta)
        
        # Check telemetry data
        self.assertGreater(len(flight_data.telemetry), 0)
        self.assertIn('datetime(utc)', flight_data.telemetry.columns)
        self.assertIn('latitude', flight_data.telemetry.columns)
        self.assertIn('longitude', flight_data.telemetry.columns)
        self.assertIn('mileage(feet)', flight_data.telemetry.columns)
        self.assertIn('speed(mph)', flight_data.telemetry.columns)
        
        print(f"✅ Successfully parsed {len(flight_data.telemetry)} telemetry points")
        print(f"✅ Flight duration: {flight_data.duration}")
        print(f"✅ Media events: {len(flight_data.media_events)}")
    
    def test_flight_metrics_extraction(self):
        """Test extraction of flight performance metrics."""
        print(f"\n🧪 Testing flight metrics extraction...")
        
        # Parse the CSV file first
        flight_data = self.parser.parse_csv(self.test_csv_file)
        
        # Extract metrics
        metrics = self.parser.extract_flight_metrics(flight_data)
        
        # Assertions
        self.assertIsNotNone(metrics)
        self.assertIsInstance(metrics.max_altitude, (int, float, type(None)))
        self.assertIsInstance(metrics.avg_altitude, (int, float, type(None)))
        self.assertIsInstance(metrics.max_speed, (int, float, type(None)))
        self.assertIsInstance(metrics.total_distance, (int, float, type(None)))
        # Battery consumed can be numpy types, so check if it's numeric
        self.assertTrue(isinstance(metrics.battery_consumed, (int, float)) or hasattr(metrics.battery_consumed, '__float__'))
        
        # Reasonable value checks
        self.assertGreaterEqual(metrics.max_altitude, 0)
        self.assertGreaterEqual(metrics.max_speed, 0)
        self.assertGreaterEqual(metrics.total_distance, 0)
        
        print(f"✅ Max altitude: {metrics.max_altitude:.1f} feet")
        print(f"✅ Max speed: {metrics.max_speed:.1f} mph")
        print(f"✅ Total distance: {metrics.total_distance:.2f} miles")
        print(f"✅ Battery consumed: {metrics.battery_consumed:.1f}%")
    
    def test_media_events_extraction(self):
        """Test extraction of media capture events."""
        print(f"\n🧪 Testing media events extraction...")
        
        # Parse the CSV file first
        flight_data = self.parser.parse_csv(self.test_csv_file)
        
        # Get media events
        media_events = self.parser.get_media_timestamps(flight_data)
        
        # Assertions
        self.assertIsInstance(media_events, list)
        
        if media_events:
            for event in media_events:
                self.assertIsInstance(event.timestamp, datetime)
                self.assertIsNotNone(event.event_type)
                self.assertIsNotNone(event.location)
        
        print(f"✅ Found {len(media_events)} media events")
    
    def test_flight_phases_analysis(self):
        """Test flight phase transition analysis."""
        print(f"\n🧪 Testing flight phases analysis...")
        
        # Parse the CSV file first
        flight_data = self.parser.parse_csv(self.test_csv_file)
        
        # Analyze flight phases
        flight_phases = self.parser.analyze_flight_phases(flight_data)
        
        # Assertions
        self.assertIsNotNone(flight_phases)
        
        if flight_phases and flight_phases.phases:
            self.assertGreater(len(flight_phases.phases), 0)
            
            # Check first phase structure
            first_phase = flight_phases.phases[0]
            self.assertEqual(len(first_phase), 3)  # (phase, start_time, end_time)
            
        print(f"✅ Identified {len(flight_phases.phases) if flight_phases else 0} flight phases")
    
    def test_telemetry_validation(self):
        """Test telemetry data consistency validation."""
        print(f"\n🧪 Testing telemetry validation...")
        
        # Parse the CSV file first
        flight_data = self.parser.parse_csv(self.test_csv_file)
        
        # Validate telemetry
        validation_results = self.parser.validate_telemetry_consistency(flight_data)
        
        # Assertions
        self.assertIsInstance(validation_results, dict)
        self.assertGreater(len(validation_results), 0)
        
        for check_name, result in validation_results.items():
            # Result should be boolean or boolean-like
            self.assertTrue(isinstance(result, (bool, type(True), type(False))) or str(result).lower() in ['true', 'false'])
            status = "✅ PASS" if bool(result) else "❌ FAIL"
            print(f"✅ {check_name}: {status}")
    
    def test_nonexistent_file_error(self):
        """Test error handling for nonexistent files."""
        print(f"\n🧪 Testing error handling for nonexistent file...")
        
        with self.assertRaises(AirdataParseError) as context:
            self.parser.parse_csv("nonexistent_file.csv")
        
        self.assertIn("File not found", str(context.exception))
        print(f"✅ Correctly raised AirdataParseError for nonexistent file")
    
    def test_csv_structure_validation(self):
        """Test CSV structure and column validation."""
        print(f"\n🧪 Testing CSV structure validation...")
        
        # Parse the CSV file
        flight_data = self.parser.parse_csv(self.test_csv_file)
        
        # Check that essential columns are present after parsing
        essential_cols = ['datetime(utc)', 'latitude', 'longitude', 'speed(mph)']
        for col in essential_cols:
            self.assertIn(col, flight_data.telemetry.columns, 
                         f"Essential column '{col}' missing from parsed data")
        
        print(f"✅ All essential columns present in parsed data")


def run_integration_test():
    """
    Run a comprehensive integration test of the AirdataParser.
    This function can be called independently for manual testing.
    """
    print("🚀 Running AirdataParser Integration Test")
    print("=" * 60)
    
    try:
        # Run all tests
        suite = unittest.TestLoader().loadTestsFromTestCase(TestAirdataParser)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        if result.wasSuccessful():
            print("\n🎉 All tests passed successfully!")
            return True
        else:
            print(f"\n❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
            return False
            
    except Exception as e:
        print(f"❌ Integration test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run integration test when script is executed directly
    success = run_integration_test()
    sys.exit(0 if success else 1)